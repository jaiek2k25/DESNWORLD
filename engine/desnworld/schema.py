"""
Versioned DESNWORLD scenario-report schema and validators.

A scenario report is a plain JSON document (no framework bindings) so it can be
produced by the engine, uploaded as a GitHub Actions artifact, and rendered by
the static web interface.

Schema versioning policy:
- `schema_version` uses MAJOR.MINOR.PATCH.
- Consumers accept documents whose MAJOR version matches their own and whose
  MINOR version is less than or equal to their own.
- New optional fields are added in MINOR revisions; breaking changes bump MAJOR.

Provenance is first class: every claim carries a `kind` of
`sourced_fact` (verifiable external source with a URI), `user_supplied_fact`
(evidence the user provided), or `ai_assumption` (model-generated reasoning).
`sourced_fact` claims MUST carry a `source_uri` or an `evidence_ref` pointing to
user-supplied evidence — the validator rejects fabricated provenance.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .errors import SchemaValidationError

SCHEMA_VERSION = "1.0.0"
ENGINE_NAME = "DESNWORLD"
ENGINE_VERSION = "0.1.0"

DOMAINS: Tuple[str, ...] = (
    "general",
    "stock_market_education",
    "business",
    "technology",
)

PROVENANCE_KINDS: Tuple[str, ...] = (
    "sourced_fact",
    "user_supplied_fact",
    "ai_assumption",
)

CONFIDENCE_LEVELS: Tuple[str, ...] = ("low", "medium", "high")
LIKELIHOOD_STANCES: Tuple[str, ...] = (
    "more_likely",
    "plausible",
    "less_likely",
    "unlikely",
)
IMPACT_LEVELS: Tuple[str, ...] = ("low", "medium", "high")

MAX_TREE_DEPTH = 2  # root -> alternatives -> sub-branches
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _is_str(value: Any, *, min_len: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= min_len


def _is_str_list(value: Any, *, min_len: int = 1, item_min: int = 1) -> bool:
    if not isinstance(value, list) or len(value) < min_len:
        return False
    return all(_is_str(item, min_len=item_min) for item in value)


def parse_schema_version(version: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(version, str):
        return None
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_compatible_version(version: Any) -> bool:
    """True when `version` is readable by this engine build."""
    parsed = parse_schema_version(version)
    if parsed is None:
        return False
    major, minor, _patch = parsed
    current = parse_schema_version(SCHEMA_VERSION)
    assert current is not None
    return major == current[0] and minor <= current[1]


# ---------------------------------------------------------------------------
# document constructors (used by the engine and the mock provider)
# ---------------------------------------------------------------------------

def make_evidence_item(
    evidence_id: str,
    text: str,
    *,
    kind: str = "user_supplied_fact",
    source_uri: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": evidence_id,
        "text": text.strip(),
        "kind": kind,
        "source_uri": source_uri,
        "note": note,
    }


def make_assumption(
    assumption_id: str,
    text: str,
    *,
    kind: str = "ai_assumption",
    confidence: str = "medium",
    evidence_ref: Optional[str] = None,
    source_uri: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": assumption_id,
        "text": text.strip(),
        "kind": kind,
        "confidence": confidence,
        "evidence_ref": evidence_ref,
        "source_uri": source_uri,
    }


def make_trigger(trigger_id: str, event: str, description: str) -> Dict[str, Any]:
    return {
        "id": trigger_id,
        "event": event.strip(),
        "description": description.strip(),
    }


def make_scenario(
    scenario_id: str,
    label: str,
    title: str,
    narrative: str,
    *,
    stance: str = "plausible",
    stance_note: str = "Qualitative assessment only; not a probability estimate.",
    assumptions: Optional[List[Dict[str, Any]]] = None,
    triggers: Optional[List[Dict[str, Any]]] = None,
    possible_consequences: Optional[List[str]] = None,
    indicators_to_watch: Optional[List[str]] = None,
    parent_id: Optional[str] = None,
    children: Optional[List[Dict[str, Any]]] = None,
    child_comparison: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": scenario_id,
        "label": label.strip(),
        "title": title.strip(),
        "narrative": narrative.strip(),
        "stance": {"qualitative": stance, "note": stance_note},
        "assumptions": assumptions or [],
        "triggers": triggers or [],
        "possible_consequences": possible_consequences or [],
        "indicators_to_watch": indicators_to_watch or [],
        "parent_id": parent_id,
        "children": children or [],
        "child_comparison": child_comparison,
    }


def make_comparison(
    summary: str,
    dimensions: List[Dict[str, Any]],
    key_differences: List[str],
    what_would_change_the_outlook: List[str],
) -> Dict[str, Any]:
    return {
        "summary": summary.strip(),
        "dimensions": dimensions,
        "key_differences": key_differences,
        "what_would_change_the_outlook": what_would_change_the_outlook,
    }


def make_uncertainty(
    uncertainty_id: str,
    statement: str,
    *,
    impact: str = "medium",
    missing_evidence: str = "",
) -> Dict[str, Any]:
    return {
        "id": uncertainty_id,
        "statement": statement.strip(),
        "impact": impact,
        "missing_evidence": missing_evidence.strip(),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def _validate_evidence_item(item: Any, index: int, problems: List[str]) -> None:
    prefix = f"request.evidence[{index}]"
    if not isinstance(item, dict):
        problems.append(f"{prefix}: must be an object")
        return
    if not _is_str(item.get("id")) or not _ID_RE.match(str(item.get("id", ""))):
        problems.append(f"{prefix}.id: missing or invalid id")
    if not _is_str(item.get("text"), min_len=3):
        problems.append(f"{prefix}.text: must be a string of at least 3 characters")
    kind = item.get("kind")
    if kind not in PROVENANCE_KINDS:
        problems.append(f"{prefix}.kind: must be one of {list(PROVENANCE_KINDS)}")
    if kind == "sourced_fact":
        uri = item.get("source_uri")
        if not _is_str(uri):
            problems.append(
                f"{prefix}: kind is 'sourced_fact' but source_uri is missing "
                "(fabricated provenance is not allowed)"
            )
    uri = item.get("source_uri")
    if uri is not None and not (isinstance(uri, str) and uri.startswith(("http://", "https://"))):
        problems.append(f"{prefix}.source_uri: must be an http(s) URL when present")


def _validate_assumption(item: Any, path: str, problems: List[str]) -> None:
    if not isinstance(item, dict):
        problems.append(f"{path}: must be an object")
        return
    if not _is_str(item.get("id")):
        problems.append(f"{path}.id: missing")
    if not _is_str(item.get("text"), min_len=3):
        problems.append(f"{path}.text: must be a string of at least 3 characters")
    kind = item.get("kind")
    if kind not in PROVENANCE_KINDS:
        problems.append(f"{path}.kind: must be one of {list(PROVENANCE_KINDS)}")
    if item.get("confidence") not in CONFIDENCE_LEVELS:
        problems.append(f"{path}.confidence: must be one of {list(CONFIDENCE_LEVELS)}")
    if kind == "sourced_fact":
        has_uri = _is_str(item.get("source_uri"))
        has_ref = _is_str(item.get("evidence_ref"))
        if not (has_uri or has_ref):
            problems.append(
                f"{path}: kind is 'sourced_fact' but neither source_uri nor "
                "evidence_ref is set (fabricated provenance is not allowed)"
            )
    ref = item.get("evidence_ref")
    if ref is not None and not _is_str(ref):
        problems.append(f"{path}.evidence_ref: must be a non-empty string when present")


def _validate_trigger(item: Any, path: str, problems: List[str]) -> None:
    if not isinstance(item, dict):
        problems.append(f"{path}: must be an object")
        return
    if not _is_str(item.get("id")):
        problems.append(f"{path}.id: missing")
    if not _is_str(item.get("event"), min_len=3):
        problems.append(f"{path}.event: must be a string of at least 3 characters")
    if not _is_str(item.get("description"), min_len=3):
        problems.append(f"{path}.description: must be a string of at least 3 characters")


def _validate_scenario_node(
    node: Any,
    path: str,
    problems: List[str],
    *,
    depth: int,
    evidence_ids: Dict[str, str],
) -> None:
    if not isinstance(node, dict):
        problems.append(f"{path}: must be an object")
        return

    if not _is_str(node.get("id")):
        problems.append(f"{path}.id: missing")
    for field in ("label", "title", "narrative"):
        if not _is_str(node.get(field), min_len=3):
            problems.append(f"{path}.{field}: must be a string of at least 3 characters")

    stance = node.get("stance")
    if not isinstance(stance, dict) or stance.get("qualitative") not in LIKELIHOOD_STANCES:
        problems.append(
            f"{path}.stance.qualitative: must be one of {list(LIKELIHOOD_STANCES)}"
        )
    elif not _is_str(stance.get("note"), min_len=3):
        problems.append(f"{path}.stance.note: must explain the qualitative stance")

    assumptions = node.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        problems.append(f"{path}.assumptions: at least one assumption is required")
    else:
        for i, item in enumerate(assumptions):
            _validate_assumption(item, f"{path}.assumptions[{i}]", problems)
            if isinstance(item, dict):
                ref = item.get("evidence_ref")
                if ref is not None and ref not in evidence_ids:
                    problems.append(
                        f"{path}.assumptions[{i}].evidence_ref: '{ref}' does not "
                        "match any request evidence id"
                    )

    triggers = node.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        problems.append(f"{path}.triggers: at least one trigger is required")
    else:
        for i, item in enumerate(triggers):
            _validate_trigger(item, f"{path}.triggers[{i}]", problems)

    for field in ("possible_consequences", "indicators_to_watch"):
        if not _is_str_list(node.get(field)):
            problems.append(f"{path}.{field}: must be a non-empty list of strings")

    if node.get("parent_id") is not None and not _is_str(node.get("parent_id")):
        problems.append(f"{path}.parent_id: must be a non-empty string or null")

    children = node.get("children", [])
    if not isinstance(children, list):
        problems.append(f"{path}.children: must be a list")
        return
    if children:
        if depth >= MAX_TREE_DEPTH:
            problems.append(
                f"{path}.children: tree depth exceeds the supported maximum "
                f"of {MAX_TREE_DEPTH} levels below the report root"
            )
            return
        if len(children) != 3:
            problems.append(
                f"{path}.children: expansion branches must contain exactly 3 "
                f"sub-branches (found {len(children)})"
            )
        seen_labels: Dict[str, str] = {}
        for i, child in enumerate(children):
            child_path = f"{path}.children[{i}]"
            _validate_scenario_node(
                child, child_path, problems, depth=depth + 1, evidence_ids=evidence_ids
            )
            if isinstance(child, dict):
                parent_id = child.get("parent_id")
                node_id = node.get("id")
                if parent_id != node_id:
                    problems.append(
                        f"{child_path}.parent_id: must equal the parent node id "
                        f"'{node_id}' (found {parent_id!r})"
                    )
                label_key = str(child.get("title", "")).strip().lower()
                if label_key in seen_labels:
                    problems.append(
                        f"{child_path}.title: duplicates {seen_labels[label_key]} "
                        "(sub-branches must be meaningfully different)"
                    )
                else:
                    seen_labels[label_key] = f"{child_path}.title"

    if node.get("child_comparison") is not None and not isinstance(
        node.get("child_comparison"), dict
    ):
        problems.append(f"{path}.child_comparison: must be an object when present")


def _validate_comparison(comparison: Any, problems: List[str]) -> None:
    path = "comparison"
    if not isinstance(comparison, dict):
        problems.append(f"{path}: must be an object")
        return
    if not _is_str(comparison.get("summary"), min_len=10):
        problems.append(f"{path}.summary: must be a string of at least 10 characters")
    dimensions = comparison.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        problems.append(f"{path}.dimensions: at least one dimension is required")
    else:
        for i, dim in enumerate(dimensions):
            dim_path = f"{path}.dimensions[{i}]"
            if not isinstance(dim, dict):
                problems.append(f"{dim_path}: must be an object")
                continue
            if not _is_str(dim.get("dimension"), min_len=3):
                problems.append(f"{dim_path}.dimension: missing label")
            if not _is_str(dim.get("baseline"), min_len=1):
                problems.append(f"{dim_path}.baseline: missing value")
            alts = dim.get("alternatives")
            if not isinstance(alts, dict) or len(alts) != 3:
                problems.append(
                    f"{dim_path}.alternatives: must map exactly 3 scenario ids"
                )
    if not _is_str_list(comparison.get("key_differences")):
        problems.append(f"{path}.key_differences: must be a non-empty list of strings")
    if not _is_str_list(comparison.get("what_would_change_the_outlook")):
        problems.append(
            f"{path}.what_would_change_the_outlook: must be a non-empty list of strings"
        )


def validate_report(doc: Any) -> List[str]:
    """Validate a scenario report document. Returns a list of problems."""
    problems: List[str] = []

    if not isinstance(doc, dict):
        return ["report: must be a JSON object"]

    if not is_compatible_version(doc.get("schema_version")):
        problems.append(
            f"schema_version: {doc.get('schema_version')!r} is not compatible "
            f"with this engine (expected MAJOR {SCHEMA_VERSION.split('.')[0]}, "
            f"MINOR <= {SCHEMA_VERSION.split('.')[1]})"
        )

    for field in ("report_id", "generated_at"):
        if not _is_str(doc.get(field)):
            problems.append(f"{field}: missing or empty")

    generator = doc.get("generator")
    if not isinstance(generator, dict) or not _is_str(generator.get("name")):
        problems.append("generator: must be an object with a name")
    elif not _is_str(generator.get("engine_version")):
        problems.append("generator.engine_version: missing")

    request = doc.get("request")
    evidence_ids: Dict[str, str] = {}
    if not isinstance(request, dict):
        problems.append("request: must be an object")
    else:
        if not _is_str(request.get("question"), min_len=10):
            problems.append("request.question: must be at least 10 characters")
        if request.get("domain") not in DOMAINS:
            problems.append(f"request.domain: must be one of {list(DOMAINS)}")
        horizon = request.get("horizon")
        if (
            not isinstance(horizon, dict)
            or not isinstance(horizon.get("months"), int)
            or not (1 <= horizon.get("months", 0) <= 120)
        ):
            problems.append("request.horizon.months: must be an integer between 1 and 120")
        elif not _is_str(horizon.get("label")):
            problems.append("request.horizon.label: missing")
        evidence = request.get("evidence", [])
        if not isinstance(evidence, list):
            problems.append("request.evidence: must be a list")
        else:
            for i, item in enumerate(evidence):
                _validate_evidence_item(item, i, problems)
                if isinstance(item, dict) and _is_str(item.get("id")):
                    eid = str(item["id"])
                    if eid in evidence_ids:
                        problems.append(f"request.evidence[{i}].id: duplicate id '{eid}'")
                    evidence_ids[eid] = str(item.get("kind", ""))

    if not _is_str(doc.get("disclaimer"), min_len=10):
        problems.append("disclaimer: missing or too short")

    data_status = doc.get("data_status")
    if not isinstance(data_status, dict):
        problems.append("data_status: must be an object")
    else:
        if not isinstance(data_status.get("live_market_data_checked"), bool):
            problems.append("data_status.live_market_data_checked: must be a boolean")
        if not _is_str(data_status.get("message"), min_len=5):
            problems.append("data_status.message: must describe what was and was not checked")
        sources = data_status.get("sources", [])
        if not isinstance(sources, list):
            problems.append("data_status.sources: must be a list")

    baseline = doc.get("baseline")
    if not isinstance(baseline, dict):
        problems.append("baseline: missing scenario object")
    else:
        _validate_scenario_node(
            baseline, "baseline", problems, depth=0, evidence_ids=evidence_ids
        )
        if baseline.get("parent_id") is not None:
            problems.append("baseline.parent_id: must be null for the baseline scenario")

    alternatives = doc.get("alternatives")
    if not isinstance(alternatives, list) or len(alternatives) != 3:
        problems.append(
            f"alternatives: exactly 3 alternative scenarios are required "
            f"(found {len(alternatives) if isinstance(alternatives, list) else 'none'})"
        )
    else:
        seen_titles: Dict[str, str] = {}
        seen_trigger_sets: Dict[Tuple[str, ...], str] = {}
        for i, alt in enumerate(alternatives):
            path = f"alternatives[{i}]"
            _validate_scenario_node(alt, path, problems, depth=0, evidence_ids=evidence_ids)
            if isinstance(alt, dict):
                if alt.get("parent_id") is not None:
                    problems.append(f"{path}.parent_id: must be null for top-level alternatives")
                title_key = str(alt.get("title", "")).strip().lower()
                if title_key in seen_titles:
                    problems.append(
                        f"{path}.title: duplicates {seen_titles[title_key]} "
                        "(alternatives must be meaningfully different)"
                    )
                else:
                    seen_titles[title_key] = f"{path}.title"
                trigger_key = tuple(
                    sorted(str(t.get("event", "")).strip().lower() for t in alt.get("triggers", []) if isinstance(t, dict))
                )
                if trigger_key and trigger_key in seen_trigger_sets:
                    problems.append(
                        f"{path}.triggers: identical trigger set to "
                        f"{seen_trigger_sets[trigger_key]} (branches must be "
                        "distinguished by different triggers)"
                    )
                elif trigger_key:
                    seen_trigger_sets[trigger_key] = f"{path}.triggers"

    _validate_comparison(doc.get("comparison"), problems)

    uncertainties = doc.get("uncertainties")
    if not isinstance(uncertainties, list) or not uncertainties:
        problems.append("uncertainties: at least one uncertainty is required")
    else:
        for i, item in enumerate(uncertainties):
            path = f"uncertainties[{i}]"
            if not isinstance(item, dict):
                problems.append(f"{path}: must be an object")
                continue
            if not _is_str(item.get("id")):
                problems.append(f"{path}.id: missing")
            if not _is_str(item.get("statement"), min_len=5):
                problems.append(f"{path}.statement: must be at least 5 characters")
            if item.get("impact") not in IMPACT_LEVELS:
                problems.append(f"{path}.impact: must be one of {list(IMPACT_LEVELS)}")
            if not _is_str(item.get("missing_evidence"), min_len=1):
                problems.append(f"{path}.missing_evidence: describe what evidence is missing")

    if not _is_str_list(doc.get("missing_information")):
        problems.append("missing_information: must be a non-empty list of strings")
    if not _is_str_list(doc.get("limitations")):
        problems.append("limitations: must be a non-empty list of strings")

    ledger = doc.get("evidence_ledger")
    if not isinstance(ledger, list):
        problems.append("evidence_ledger: must be a list")
    else:
        for i, item in enumerate(ledger):
            path = f"evidence_ledger[{i}]"
            if not isinstance(item, dict):
                problems.append(f"{path}: must be an object")
                continue
            if item.get("kind") not in PROVENANCE_KINDS:
                problems.append(f"{path}.kind: must be one of {list(PROVENANCE_KINDS)}")
            if not _is_str(item.get("text"), min_len=3):
                problems.append(f"{path}.text: missing")
            if item.get("kind") == "sourced_fact":
                has_uri = _is_str(item.get("source_uri"))
                has_ref = _is_str(item.get("evidence_ref"))
                if not (has_uri or has_ref):
                    problems.append(
                        f"{path}: 'sourced_fact' entries require source_uri or "
                        "evidence_ref (fabricated provenance is not allowed)"
                    )

    return problems


def validate_scenario_node_public(
    node: Any, *, evidence_ids: Optional[Dict[str, str]] = None, depth: int = 0
) -> List[str]:
    """Validate a single scenario node (used by the engine's stage checks)."""
    problems: List[str] = []
    _validate_scenario_node(
        node, "scenario", problems, depth=depth, evidence_ids=evidence_ids or {}
    )
    return problems


def validate_comparison_public(comparison: Any) -> List[str]:
    """Validate a comparison object (used by the engine's stage checks)."""
    problems: List[str] = []
    _validate_comparison(comparison, problems)
    return problems


def assert_valid_report(doc: Any, *, context: str = "scenario report") -> Dict[str, Any]:
    """Raise SchemaValidationError when `doc` is not a valid report."""
    problems = validate_report(doc)
    if problems:
        raise SchemaValidationError(
            f"Invalid {context}: {len(problems)} schema problem(s) found.",
            problems=problems,
            hint="Fix the model output or re-run generation; see 'problems' for details.",
        )
    if not isinstance(doc, dict):  # pragma: no cover - validate_report covers this
        raise SchemaValidationError(f"Invalid {context}: not an object.")
    return doc


def find_scenario(report: Dict[str, Any], scenario_id: str) -> Optional[Dict[str, Any]]:
    """Locate a scenario node by id anywhere in the report's scenario tree."""
    stacks: List[Any] = [report.get("baseline")]
    stacks.extend(report.get("alternatives") or [])
    while stacks:
        node = stacks.pop()
        if not isinstance(node, dict):
            continue
        if node.get("id") == scenario_id:
            return node
        stacks.extend(node.get("children") or [])
    return None
