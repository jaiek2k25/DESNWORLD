"""
The DESNWORLD scenario engine — pipeline orchestration.

Pipeline (see README "AI scenario engine"):
  1. Validate the user's question and request  (input_validation)
  2. Collect/accept evidence and build the evidence ledger
  3. Establish the baseline scenario and its assumptions      [prompt: baseline]
  4. Generate exactly three alternative branches              [prompt: alternatives]
  5. Explain the triggers that distinguish each branch        [prompt: alternatives]
  6. Identify uncertainties, missing evidence, consequences   [prompt: uncertainties]
  7. Validate the structured response (schema + provenance)
  8. Generate the comparison report                           [prompt: comparison]
  9. Explore a branch and generate further sub-branches       [prompt: sub_branch]

Every stage runs through the same provider with its own prompt, validates the
structured response, and makes one bounded repair attempt before failing with
a structured error. Provenance is enforced deterministically: claims tagged
`sourced_fact` without any backing source are downgraded to `ai_assumption`
before final validation — the engine never fabricates sources.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import prompts
from .errors import MalformedResponseError, SchemaValidationError
from .input_validation import request_from_mapping
from .providers import ChatJSONProvider
from .schema import (
    ENGINE_NAME,
    ENGINE_VERSION,
    MAX_TREE_DEPTH,
    SCHEMA_VERSION,
    assert_valid_report,
    find_scenario,
    utc_now_iso,
    validate_comparison_public,
    validate_scenario_node_public,
)

logger = logging.getLogger("desnworld.engine")

StageValidator = Callable[[Any], List[str]]


def _extract_key(key: str) -> Callable[[Any], Tuple[Any, List[str]]]:
    def extractor(payload: Any) -> Tuple[Any, List[str]]:
        if not isinstance(payload, dict):
            return None, ["response: expected a JSON object"]
        if key not in payload:
            return None, [f"response: missing required top-level key '{key}'"]
        return payload[key], []

    return extractor


def _extract_children(payload: Any) -> Tuple[Any, List[str]]:
    if not isinstance(payload, dict):
        return None, ["response: expected a JSON object"]
    if "children" not in payload:
        return None, ["response: missing required top-level key 'children'"]
    return {"children": payload.get("children"), "child_comparison": payload.get("child_comparison")}, []


class ScenarioEngine:
    """Runs the DESNWORLD scenario pipeline against any chat-JSON provider."""

    def __init__(
        self,
        provider: ChatJSONProvider,
        *,
        market_data_checked: Optional[bool] = None,
    ):
        self.provider = provider
        if market_data_checked is None:
            from .config import Config

            market_data_checked = Config.MARKET_DATA_CHECKED
        self.market_data_checked = bool(market_data_checked)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def generate(self, request: Any) -> Dict[str, Any]:
        """Run the full pipeline for a scenario request; returns a valid report."""
        req = request_from_mapping(request) if not (
            isinstance(request, dict)
            and "horizon" in request
            and isinstance(request.get("horizon"), dict)
        ) else request

        evidence_ids = {item["id"]: item["kind"] for item in req.get("evidence", [])}
        ledger = self._build_evidence_ledger(req)

        baseline = self._run_stage(
            "baseline",
            prompts.baseline_prompt(req),
            _extract_key("scenario"),
            lambda node: self._validate_node(node, evidence_ids, expected_id="baseline", parent_id=None),
        )
        baseline = self._normalize_node(baseline, expected_id="baseline", parent_id=None)

        alternatives_raw = self._run_stage(
            "alternatives",
            prompts.alternatives_prompt(req, baseline),
            _extract_key("alternatives"),
            lambda value: self._validate_alternatives(value, evidence_ids),
        )
        alternatives = [
            self._normalize_node(node, expected_id=f"alt-{i + 1}", parent_id=None)
            for i, node in enumerate(alternatives_raw)
        ]

        extras = self._run_stage(
            "uncertainties",
            prompts.uncertainties_prompt(req, baseline, alternatives),
            lambda payload: (
                (payload, [])
                if isinstance(payload, dict)
                else (None, ["response: expected a JSON object"])
            ),
            self._validate_extras,
        )

        comparison_raw = self._run_stage(
            "comparison",
            prompts.comparison_prompt(req, baseline, alternatives),
            _extract_key("comparison"),
            validate_comparison_public,
        )
        comparison = self._normalize_comparison(comparison_raw, ["baseline", "alt-1", "alt-2", "alt-3"])

        report: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "report_id": self._new_report_id(),
            "generated_at": utc_now_iso(),
            "generator": self._generator_block(),
            "request": {
                "question": req["question"],
                "domain": req["domain"],
                "horizon": {"months": req["horizon"]["months"], "label": req["horizon"]["label"]},
                "evidence": ledger,
            },
            "disclaimer": self._disclaimer(req["domain"]),
            "data_status": self._data_status(req),
            "baseline": baseline,
            "alternatives": alternatives,
            "comparison": comparison,
            "uncertainties": extras["uncertainties"],
            "missing_information": extras["missing_information"],
            "limitations": self._merge_limitations(extras["limitations"]),
            "evidence_ledger": ledger,
        }

        self._downgrade_unbacked_provenance(report)
        assert_valid_report(report)
        return report

    def expand_branch(self, report: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
        """
        Explore a branch: generate exactly three sub-branches under a scenario.

        Returns a new, validated report (the input report is not mutated).
        """
        working = copy.deepcopy(report)
        assert_valid_report(working, context="input report")

        node, depth = self._find_node_with_depth(working, scenario_id)
        if node is None:
            raise SchemaValidationError(
                f"Scenario '{scenario_id}' was not found in the report.",
                problems=[f"scenario_id: '{scenario_id}' does not exist"],
            )
        if depth >= MAX_TREE_DEPTH or node.get("children"):
            raise SchemaValidationError(
                f"Scenario '{scenario_id}' cannot be expanded further.",
                problems=[
                    f"scenario_id: '{scenario_id}' is already at the maximum "
                    f"supported tree depth ({MAX_TREE_DEPTH})"
                ],
                hint="Expand a different branch instead.",
            )

        req = {
            "question": working["request"]["question"],
            "domain": working["request"]["domain"],
            "horizon": working["request"]["horizon"],
            "evidence": working["request"].get("evidence", []),
        }
        evidence_ids = {item["id"]: item["kind"] for item in req.get("evidence", [])}
        siblings = self._sibling_nodes(working, node)

        extracted = self._run_stage(
            f"sub_branch:{scenario_id}",
            prompts.sub_branch_prompt(req, node, siblings),
            _extract_children,
            lambda value: self._validate_children(value, evidence_ids, parent_id=scenario_id),
        )
        children = [
            self._normalize_node(
                child,
                expected_id=f"{scenario_id}.c{i + 1}",
                parent_id=scenario_id,
            )
            for i, child in enumerate(extracted["children"])
        ]
        child_comparison = None
        if extracted.get("child_comparison"):
            child_ids = [c["id"] for c in children]
            child_comparison = self._normalize_comparison(
                extracted["child_comparison"], ["baseline"] + child_ids
            )

        node["children"] = children
        node["child_comparison"] = child_comparison

        self._downgrade_unbacked_provenance(working)
        assert_valid_report(working, context="expanded report")
        return working

    # ------------------------------------------------------------------
    # stage execution with bounded repair
    # ------------------------------------------------------------------

    def _run_stage(
        self,
        stage: str,
        messages: List[Dict[str, str]],
        extract: Callable[[Any], Tuple[Any, List[str]]],
        validate: StageValidator,
    ) -> Any:
        raw = self.provider.chat_json(messages)
        value, problems = extract(raw)
        if not problems:
            value = self._sanitize_provenance(value)
            problems = validate(value)
        if problems:
            logger.warning("Stage '%s' failed validation (%d problems); repairing", stage, len(problems))
            repair_messages = prompts.repair_prompt(stage, json.dumps(raw, ensure_ascii=False), problems)
            try:
                raw = self.provider.chat_json(repair_messages)
            except MalformedResponseError:
                raise
            value, problems = extract(raw)
            if not problems:
                value = self._sanitize_provenance(value)
                problems = validate(value)
            if problems:
                raise SchemaValidationError(
                    f"Stage '{stage}' produced invalid output even after repair.",
                    problems=problems,
                    hint="Re-run generation, or switch to a stronger model via LLM_MODEL_NAME.",
                )
        return value

    # ------------------------------------------------------------------
    # stage validators
    # ------------------------------------------------------------------

    def _validate_node(
        self,
        node: Any,
        evidence_ids: Dict[str, str],
        *,
        expected_id: str,
        parent_id: Optional[str],
    ) -> List[str]:
        problems = validate_scenario_node_public(node, evidence_ids=evidence_ids, depth=0)
        if isinstance(node, dict):
            if node.get("id") not in (None, expected_id):
                problems.append(
                    f"scenario.id: expected '{expected_id}' (found {node.get('id')!r}); "
                    "it will be normalized"
                )
            if node.get("parent_id") not in (None, parent_id):
                problems.append(
                    f"scenario.parent_id: expected {parent_id!r} "
                    f"(found {node.get('parent_id')!r}); it will be normalized"
                )
        # id/parent drift is normalized deterministically, not a hard failure
        return [p for p in problems if "will be normalized" not in p]

    def _validate_alternatives(self, value: Any, evidence_ids: Dict[str, str]) -> List[str]:
        if not isinstance(value, list):
            return ["alternatives: must be a list"]
        if len(value) != 3:
            return [
                f"alternatives: exactly 3 alternative scenarios are required (found {len(value)})"
            ]
        problems: List[str] = []
        titles: Dict[str, int] = {}
        trigger_sets: Dict[Tuple[str, ...], int] = {}
        for i, node in enumerate(value):
            problems.extend(
                self._validate_node(node, evidence_ids, expected_id=f"alt-{i + 1}", parent_id=None)
                if isinstance(node, dict)
                else [f"alternatives[{i}]: must be an object"]
            )
            if isinstance(node, dict):
                title_key = str(node.get("title", "")).strip().lower()
                if title_key in titles:
                    problems.append(
                        f"alternatives[{i}].title: duplicates alternatives[{titles[title_key]}] "
                        "(alternatives must be meaningfully different)"
                    )
                else:
                    titles[title_key] = i
                trigger_key = tuple(
                    sorted(
                        str(t.get("event", "")).strip().lower()
                        for t in node.get("triggers", [])
                        if isinstance(t, dict)
                    )
                )
                if trigger_key and trigger_key in trigger_sets:
                    problems.append(
                        f"alternatives[{i}].triggers: identical trigger set to "
                        f"alternatives[{trigger_sets[trigger_key]}] "
                        "(branches must be distinguished by different triggers)"
                    )
                elif trigger_key:
                    trigger_sets[trigger_key] = i
        return problems

    def _validate_extras(self, value: Any) -> List[str]:
        problems: List[str] = []
        if not isinstance(value, dict):
            return ["response: expected a JSON object"]
        uncertainties = value.get("uncertainties")
        if not isinstance(uncertainties, list) or not uncertainties:
            problems.append("uncertainties: at least one uncertainty is required")
        else:
            for i, u in enumerate(uncertainties):
                if not isinstance(u, dict):
                    problems.append(f"uncertainties[{i}]: must be an object")
                    continue
                for field, minimum in (("id", 1), ("statement", 5), ("missing_evidence", 1)):
                    text = u.get(field)
                    if not isinstance(text, str) or len(text.strip()) < minimum:
                        problems.append(f"uncertainties[{i}].{field}: missing or too short")
                if u.get("impact") not in ("low", "medium", "high"):
                    problems.append(f"uncertainties[{i}].impact: must be low, medium, or high")
        for field in ("missing_information", "limitations"):
            items = value.get(field)
            if not isinstance(items, list) or not items or not all(
                isinstance(x, str) and x.strip() for x in items
            ):
                problems.append(f"{field}: must be a non-empty list of strings")
        return problems

    def _validate_children(
        self, value: Any, evidence_ids: Dict[str, str], *, parent_id: str
    ) -> List[str]:
        if not isinstance(value, dict):
            return ["response: expected an object with 'children'"]
        children = value.get("children")
        problems: List[str] = []
        if not isinstance(children, list) or len(children) != 3:
            return [
                f"children: exactly 3 sub-branches are required "
                f"(found {len(children) if isinstance(children, list) else 'none'})"
            ]
        titles: Dict[str, int] = {}
        for i, node in enumerate(children):
            if not isinstance(node, dict):
                problems.append(f"children[{i}]: must be an object")
                continue
            problems.extend(
                self._validate_node(node, evidence_ids, expected_id=f"{parent_id}.c{i + 1}", parent_id=parent_id)
            )
            title_key = str(node.get("title", "")).strip().lower()
            if title_key in titles:
                problems.append(
                    f"children[{i}].title: duplicates children[{titles[title_key]}] "
                    "(sub-branches must be meaningfully different)"
                )
            else:
                titles[title_key] = i
        if value.get("child_comparison") is not None:
            problems.extend(validate_comparison_public(value["child_comparison"]))
        return [p for p in problems if "will be normalized" not in p]

    # ------------------------------------------------------------------
    # deterministic normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_node(
        node: Dict[str, Any], *, expected_id: str, parent_id: Optional[str]
    ) -> Dict[str, Any]:
        node = dict(node)
        node["id"] = expected_id
        node["parent_id"] = parent_id
        node.setdefault("label", expected_id)
        node.setdefault("title", expected_id)
        node.setdefault("narrative", "")
        stance = node.get("stance")
        if not isinstance(stance, dict):
            stance = {"qualitative": "plausible", "note": "Qualitative assessment only; not a probability estimate."}
        stance.setdefault("qualitative", "plausible")
        stance.setdefault("note", "Qualitative assessment only; not a probability estimate.")
        node["stance"] = stance
        for i, item in enumerate(node.get("assumptions") or []):
            if isinstance(item, dict):
                item.setdefault("id", f"{expected_id}-a{i + 1}")
                item.setdefault("kind", "ai_assumption")
                item.setdefault("confidence", "medium")
                item.setdefault("evidence_ref", None)
                item.setdefault("source_uri", None)
        for i, item in enumerate(node.get("triggers") or []):
            if isinstance(item, dict):
                item.setdefault("id", f"{expected_id}-t{i + 1}")
        node.setdefault("children", [])
        node.setdefault("child_comparison", None)
        node["children"] = []
        node["child_comparison"] = None
        return node

    @staticmethod
    def _normalize_comparison(comparison: Dict[str, Any], scenario_ids: List[str]) -> Dict[str, Any]:
        comparison = dict(comparison)
        comparison.setdefault("summary", "")
        comparison.setdefault("key_differences", [])
        comparison.setdefault("what_would_change_the_outlook", [])
        dimensions = []
        alt_ids = [sid for sid in scenario_ids if sid != "baseline"]
        for dim in comparison.get("dimensions") or []:
            if not isinstance(dim, dict):
                continue
            alternatives = dim.get("alternatives")
            if not isinstance(alternatives, dict):
                alternatives = {}
            # Keep exactly the expected alternative keys when recognizable.
            fixed = {sid: str(alternatives.get(sid, "")) for sid in alt_ids if sid in alternatives}
            if len(fixed) == len(alt_ids):
                dim = dict(dim)
                dim["alternatives"] = fixed
            dimensions.append(dim)
        comparison["dimensions"] = dimensions
        return comparison

    @staticmethod
    def _sanitize_provenance(value: Any) -> Any:
        """
        Deterministic provenance repair on stage output: any `sourced_fact`
        claim without a backing source_uri/evidence_ref is downgraded to
        `ai_assumption`. The engine never keeps (or invents) unsupported
        source claims; this runs before stage validation so a model that tags
        claims sloppily is corrected instead of needlessly re-prompted.
        """

        def fix_claim(claim: Dict[str, Any]) -> None:
            if claim.get("kind") != "sourced_fact":
                return
            has_uri = bool(str(claim.get("source_uri") or "").strip())
            has_ref = bool(str(claim.get("evidence_ref") or "").strip())
            if not (has_uri or has_ref):
                claim["kind"] = "ai_assumption"

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for item in node.get("assumptions") or []:
                    if isinstance(item, dict):
                        fix_claim(item)
                if node.get("kind") == "sourced_fact" and "text" in node:
                    fix_claim(node)
                for child in node.get("children") or []:
                    walk(child)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(value)
        return value

    @staticmethod
    def _downgrade_unbacked_provenance(report: Dict[str, Any]) -> None:
        """
        Deterministic provenance repair: any `sourced_fact` without a backing
        source_uri/evidence_ref becomes `ai_assumption`. The engine never keeps
        (or invents) unsupported source claims.
        """

        def fix_claim(claim: Dict[str, Any]) -> None:
            if claim.get("kind") != "sourced_fact":
                return
            has_uri = bool(str(claim.get("source_uri") or "").strip())
            has_ref = bool(str(claim.get("evidence_ref") or "").strip())
            if not (has_uri or has_ref):
                claim["kind"] = "ai_assumption"

        def walk(node: Any) -> None:
            if not isinstance(node, dict):
                return
            for item in node.get("assumptions") or []:
                if isinstance(item, dict):
                    fix_claim(item)
            for child in node.get("children") or []:
                walk(child)

        walk(report.get("baseline"))
        for alt in report.get("alternatives") or []:
            walk(alt)
        for item in report.get("evidence_ledger") or []:
            if isinstance(item, dict):
                fix_claim(item)

    # ------------------------------------------------------------------
    # report assembly helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _new_report_id() -> str:
        import uuid

        return f"rpt-{uuid.uuid4().hex[:12]}"

    def _generator_block(self) -> Dict[str, Any]:
        return {
            "name": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "provider": getattr(self.provider, "provider_name", "unknown"),
            "model": getattr(self.provider, "model_name", ""),
            "mock": getattr(self.provider, "provider_name", "") == "mock",
        }

    @staticmethod
    def _build_evidence_ledger(request: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "kind": item["kind"],
                "text": item["text"],
                "source_uri": item.get("source_uri"),
                "evidence_ref": None,
                "note": item.get("note"),
            }
            for item in request.get("evidence", [])
        ]

    @staticmethod
    def _disclaimer(domain: str) -> str:
        base = (
            "DESNWORLD explores possible futures; it does not predict the "
            "future with certainty. All scenarios are structured possibilities "
            "with documented assumptions, triggers, and uncertainties."
        )
        if domain == "stock_market_education":
            return (
                base
                + " This stock-market module is educational: scenarios are not "
                "price predictions, not personalized investment advice, and no "
                "outcome or return is guaranteed."
            )
        return base

    def _data_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        sources = sorted(
            {
                item["source_uri"]
                for item in request.get("evidence", [])
                if item.get("source_uri")
            }
        )
        if self.market_data_checked:
            message = (
                "A configured data adapter reported that live data sources were "
                "queried during this run. See 'sources' for what was referenced."
            )
        elif request["domain"] == "stock_market_education":
            message = (
                "No live market data or economic indicators were queried in this "
                "run. Scenarios are qualitative and rest only on the question and "
                "user-supplied evidence. Do not treat anything here as a price "
                "prediction."
            )
        else:
            message = (
                "No live external data sources were queried in this run. Scenarios "
                "rest only on the question and user-supplied evidence."
            )
        return {
            "live_market_data_checked": self.market_data_checked,
            "sources": sources,
            "message": message,
        }

    def _merge_limitations(self, limitations: List[str]) -> List[str]:
        merged = list(limitations)
        if getattr(self.provider, "provider_name", "") == "mock":
            merged.append(
                "This report was produced by the deterministic mock provider "
                "(demo/test mode) without calling an AI model; content is "
                "illustrative and must not be treated as analysis."
            )
        return merged

    # ------------------------------------------------------------------
    # tree helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_node_with_depth(
        report: Dict[str, Any], scenario_id: str
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        stacks: List[Tuple[Any, int]] = [(report.get("baseline"), 0)]
        stacks.extend((alt, 0) for alt in report.get("alternatives") or [])
        while stacks:
            node, depth = stacks.pop()
            if not isinstance(node, dict):
                continue
            if node.get("id") == scenario_id:
                return node, depth
            stacks.extend((child, depth + 1) for child in node.get("children") or [])
        return None, -1

    @staticmethod
    def _sibling_nodes(report: Dict[str, Any], node: Dict[str, Any]) -> List[Dict[str, Any]]:
        parent_id = node.get("parent_id")
        if parent_id is None:
            siblings = [report.get("baseline")] + list(report.get("alternatives") or [])
        else:
            parent, _ = ScenarioEngine._find_node_with_depth(report, parent_id)
            siblings = list((parent or {}).get("children") or [])
        return [s for s in siblings if isinstance(s, dict) and s.get("id") != node.get("id")]
