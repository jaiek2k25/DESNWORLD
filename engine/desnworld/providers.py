"""
LLM providers for the DESNWORLD engine.

- `OpenAIProvider`: any OpenAI-compatible Chat Completions endpoint, built on
  the MiroFish-derived `llm_client.LLMClient` layer.
- `MockScenarioProvider`: deterministic, offline, schema-valid canned output
  used by tests, CI, and the `--mock` demo mode. Its output is clearly marked
  as mock data in the report's `generator` block — it is never presented as
  live analysis.
- `ScriptedProvider`: queue-driven test double for error-handling tests.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .errors import ProviderError
from .schema import (
    make_assumption,
    make_comparison,
    make_evidence_item,
    make_scenario,
    make_trigger,
    make_uncertainty,
)


class ChatJSONProvider(Protocol):
    """Minimal provider interface used by the scenario engine."""

    #: Human-readable provider name recorded in reports.
    provider_name: str
    #: Model identifier recorded in reports ("" for non-model providers).
    model_name: str

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4096,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        ...


class OpenAIProvider:
    """Adapter around `desnworld.llm_client.LLMClient`."""

    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        from .config import Config
        from .llm_client import LLMClient

        self.model_name = model or Config.LLM_MODEL_NAME
        self._client = LLMClient(
            api_key=api_key or Config.LLM_API_KEY,
            base_url=base_url or Config.LLM_BASE_URL,
            model=self.model_name,
        )

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4096,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        return self._client.chat_json(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            max_attempts=max_attempts,
        )


class ScriptedProvider:
    """Test double: returns queued results or raises queued exceptions."""

    provider_name = "scripted"
    model_name = "scripted-test-double"

    def __init__(self, queue: List[Any]):
        self.queue = list(queue)
        self.calls: List[List[Dict[str, str]]] = []

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4096,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        self.calls.append(messages)
        if not self.queue:
            raise ProviderError("ScriptedProvider queue is empty")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


_QUESTION_RE = re.compile(r"^Question:\s*(.+)$", re.MULTILINE)
_STAGE_RE = re.compile(r"^# stage:\s*(\S+)", re.MULTILINE)


def _extract_question(user_content: str) -> str:
    match = _QUESTION_RE.search(user_content)
    return match.group(1).strip() if match else "the question under exploration"


def _extract_stage(user_content: str) -> str:
    match = _STAGE_RE.search(user_content)
    return match.group(1) if match else "unknown"


class MockScenarioProvider:
    """
    Deterministic offline provider.

    Produces schema-valid canned output so the full pipeline (validation,
    branching, comparison, expansion) can run without network access or API
    keys. Reports generated through this provider record `generator.mock=true`.
    """

    provider_name = "mock"
    model_name = "desnworld-mock"

    def __init__(self, *, scenario_theme: str = "generic"):
        self.scenario_theme = scenario_theme

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4096,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        user_content = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        stage = _extract_stage(user_content)
        question = _extract_question(user_content)

        if stage in ("baseline", "repair:baseline"):
            return self._baseline(question)
        if stage in ("alternatives", "repair:alternatives"):
            return self._alternatives(question)
        if stage in ("uncertainties", "repair:uncertainties"):
            return self._uncertainties()
        if stage in ("comparison", "repair:comparison"):
            return self._comparison()
        if stage.startswith("sub_branch") or stage.startswith("repair:sub_branch"):
            parent_id = self._extract_parent_id(user_content)
            return {
                "children": self._children(parent_id, question),
                "child_comparison": self._child_comparison(parent_id),
            }
        raise ProviderError(
            f"MockScenarioProvider does not recognise pipeline stage '{stage}'",
            hint="This indicates a bug in the engine's prompt wiring.",
        )

    # -- canned content ----------------------------------------------------

    @staticmethod
    def _extract_parent_id(user_content: str) -> str:
        match = re.search(r'"id":\s*"([^"]+)"', user_content)
        return match.group(1) if match else "node"

    @staticmethod
    def _stance_note() -> str:
        return (
            "Qualitative assessment only; DESNWORLD does not compute "
            "probabilities and this is not a prediction."
        )

    def _baseline(self, question: str) -> Dict[str, Any]:
        return {
            "scenario": make_scenario(
                "baseline",
                "Baseline",
                "Continuation of visible conditions",
                (
                    f"For the question '{question}', the baseline scenario "
                    "extends currently visible conditions over the chosen "
                    "horizon without assuming major surprises. Slow-moving "
                    "trends continue at roughly their recent pace, and no "
                    "single shock dominates the picture. This is one possible "
                    "future among several — not a forecast."
                ),
                stance="more_likely",
                stance_note=self._stance_note(),
                assumptions=[
                    make_assumption(
                        "b-a1",
                        "No unprecedented structural break occurs within the horizon.",
                        kind="ai_assumption",
                        confidence="medium",
                    ),
                    make_assumption(
                        "b-a2",
                        "Conditions visible in the user's question and evidence persist roughly unchanged.",
                        kind="user_supplied_fact",
                        confidence="medium",
                    ),
                ],
                triggers=[
                    make_trigger(
                        "b-t1",
                        "A major unexpected shock",
                        "A large shock would break the baseline and push the future toward one of the alternative branches."),
                    make_trigger(
                        "b-t2",
                        "Sustained trend reversal in key indicators",
                        "If leading indicators reverse for several periods, the continuation assumption weakens."),
                ],
                possible_consequences=[
                    "Outcomes stay within the range of recent experience.",
                    "Planning assumptions from the past period remain usable with modest adjustments.",
                ],
                indicators_to_watch=[
                    "Momentum in the indicators named in the question",
                    "Surprise indices and policy announcements",
                ],
            )
        }

    def _alternatives(self, question: str) -> Dict[str, Any]:
        shared_note = self._stance_note()
        alt1 = make_scenario(
            "alt-1",
            "Alternative 1",
            "Upside drift beyond trend",
            (
                f"A plausible alternative for '{question}' is an upside "
                "surprise: conditions improve beyond the baseline trend. "
                "Confidence builds gradually, and early signals appear in "
                "indicators before the broader picture shifts. This branch is "
                "conditional on specific triggers occurring — it is a "
                "possibility to explore, not a prediction."
            ),
            stance="plausible",
            stance_note=shared_note,
            assumptions=[
                make_assumption(
                    "a1-a1",
                    "Positive catalysts identified in the triggers materialise.",
                    kind="ai_assumption",
                    confidence="low",
                ),
                make_assumption(
                    "a1-a2",
                    "No offsetting negative shock occurs in the same window.",
                    kind="ai_assumption",
                    confidence="low",
                ),
            ],
            triggers=[
                make_trigger(
                    "a1-t1",
                    "Broad-based improvement in leading indicators",
                    "Sustained improvement pulls expectations above the baseline path."),
            ],
            possible_consequences=[
                "Expectations re-rate gradually toward the improved path.",
                "Planning under the baseline becomes conservative relative to outcomes.",
            ],
            indicators_to_watch=[
                "Revision direction in leading indicators",
                "Breadth of improvement across sectors",
            ],
        )
        alt2 = make_scenario(
            "alt-2",
            "Alternative 2",
            "Downside stress episode",
            (
                f"Another possibility for '{question}' is a downside stress "
                "episode: a deterioration that exceeds ordinary variation. "
                "Typically this unfolds as a trigger event followed by "
                "second-round effects that reinforce the initial move. This "
                "branch is conditional, not forecasted."
            ),
            stance="plausible",
            stance_note=shared_note,
            assumptions=[
                make_assumption(
                    "a2-a1",
                    "A stress trigger occurs and is not quickly contained.",
                    kind="ai_assumption",
                    confidence="low",
                ),
            ],
            triggers=[
                make_trigger(
                    "a2-t1",
                    "A disorderly repricing event",
                    "A sharp repricing event raises risk aversion and pushes outcomes below the baseline."),
            ],
            possible_consequences=[
                "Uncertainty rises and decision-making windows shorten.",
                "Weak assumptions embedded in plans are exposed.",
            ],
            indicators_to_watch=[
                "Volatility and funding-stress measures",
                "Policy response speed and credibility",
            ],
        )
        alt3 = make_scenario(
            "alt-3",
            "Alternative 3",
            "Structural regime shift",
            (
                f"A third possibility for '{question}' is a regime shift: the "
                "rules, institutions, or technology landscape change enough "
                "that extrapolation from the past stops working. Historical "
                "patterns become less informative; new baselines must be "
                "formed. This is the branch of deep uncertainty."
            ),
            stance="less_likely",
            stance_note=shared_note,
            assumptions=[
                make_assumption(
                    "a3-a1",
                    "A structural change (regulatory, technological, or institutional) takes hold within the horizon.",
                    kind="ai_assumption",
                    confidence="low",
                ),
            ],
            triggers=[
                make_trigger(
                    "a3-t1",
                    "Durable policy or technology regime change",
                    "A lasting change in the operating environment invalidates extrapolation from the recent past."),
            ],
            possible_consequences=[
                "Historical analogies lose predictive value for a time.",
                "Scenario ranges widen; diversification of options gains value.",
            ],
            indicators_to_watch=[
                "Regulatory and standards decisions",
                "Adoption curves of the new technology or regime",
            ],
        )
        return {"alternatives": [alt1, alt2, alt3]}

    @staticmethod
    def _uncertainties() -> Dict[str, Any]:
        return {
            "uncertainties": [
                make_uncertainty(
                    "u1",
                    "The pace and sequencing of the triggers above are unknown.",
                    impact="high",
                    missing_evidence="Time-stamped leading-indicator data covering the horizon.",
                ),
                make_uncertainty(
                    "u2",
                    "Interactions between triggers could amplify or dampen each branch.",
                    impact="medium",
                    missing_evidence="Cross-domain evidence on how these factors have co-moved historically.",
                ),
            ],
            "missing_information": [
                "No live market data or economic indicators were queried for this run; any market-quantitative claim would need such data to be supplied as evidence.",
                "Domain-expert judgement on the plausibility of each trigger has not been collected.",
            ],
            "limitations": [
                "All scenarios are AI-generated possibilities, not predictions, and may omit important factors.",
                "The evidence base consists only of the question and user-supplied evidence; without external data the analysis is qualitative.",
                "This is educational scenario exploration, not financial advice; no buy/sell instruction or guaranteed return is implied.",
            ],
        }

    @staticmethod
    def _comparison() -> Dict[str, Any]:
        return {
            "comparison": make_comparison(
                (
                    "The baseline extends visible conditions; the alternatives "
                    "explore an upside drift, a downside stress episode, and a "
                    "structural regime shift. They differ in direction, in the "
                    "triggers that would select each branch, and in how much "
                    "historical experience remains informative. None of these "
                    "branches is a prediction."
                ),
                [
                    {
                        "dimension": "Direction vs. baseline",
                        "baseline": "Path continuation",
                        "alternatives": {
                            "alt-1": "Above trend",
                            "alt-2": "Below trend",
                            "alt-3": "New trend definition",
                        },
                    },
                    {
                        "dimension": "Dominant trigger type",
                        "baseline": "Absence of major shocks",
                        "alternatives": {
                            "alt-1": "Broad indicator improvement",
                            "alt-2": "Disorderly repricing event",
                            "alt-3": "Regime change",
                        },
                    },
                    {
                        "dimension": "Value of historical analogies",
                        "baseline": "High",
                        "alternatives": {
                            "alt-1": "Moderate",
                            "alt-2": "Moderate",
                            "alt-3": "Low",
                        },
                    },
                    {
                        "dimension": "Uncertainty level",
                        "baseline": "Moderate",
                        "alternatives": {
                            "alt-1": "Moderate-high",
                            "alt-2": "High",
                            "alt-3": "Very high",
                        },
                    },
                ],
                [
                    "The branches differ most in which trigger fires and how much history remains informative.",
                    "The baseline is the only branch that assumes continuity; all alternatives require a specific trigger.",
                ],
                [
                    "Sustained movement in leading indicators toward either alternative.",
                    "A policy or technology decision that would constitute a regime change.",
                ],
            )
        }

    @staticmethod
    def _children(parent_id: str, question: str) -> List[Dict[str, Any]]:
        definitions = [
            (
                f"{parent_id}.c1",
                "Gradual development",
                "This sub-branch develops gradually: early signals strengthen slowly and the parent scenario deepens without abrupt moves.",
                "plausible",
                [
                    (f"{parent_id}.c1.a1", "Current momentum continues without interruption.", "ai_assumption"),
                ],
                [
                    (f"{parent_id}.c1.t1", "Steady continuation of leading indicators", "Indicators keep moving in the parent branch's direction."),
                ],
            ),
            (
                f"{parent_id}.c2",
                "Accelerated development",
                "This sub-branch develops faster than expected: feedback effects amplify the parent scenario, compressing the timeline of consequences.",
                "plausible",
                [
                    (f"{parent_id}.c2.a1", "Feedback loops strengthen rather than dampen the initial move.", "ai_assumption"),
                ],
                [
                    (f"{parent_id}.c2.t1", "Self-reinforcing feedback in the parent branch", "Amplification shortens the path to the parent scenario's consequences."),
                ],
            ),
            (
                f"{parent_id}.c3",
                "Stalled or reversed development",
                "This sub-branch stalls or partially reverses: the parent scenario's drivers fade, and outcomes drift back toward the baseline.",
                "less_likely",
                [
                    (f"{parent_id}.c3.a1", "The parent branch's drivers prove temporary.", "ai_assumption"),
                ],
                [
                    (f"{parent_id}.c3.t1", "Fade-out of the parent branch's triggers", "Loss of momentum pulls outcomes back toward baseline conditions."),
                ],
            ),
        ]
        children = []
        for index, (cid, title, narrative, stance, assumptions, triggers) in enumerate(definitions, start=1):
            children.append(
                make_scenario(
                    cid,
                    f"Sub {index}",
                    title,
                    narrative,
                    stance=stance,
                    stance_note=(
                        "Qualitative assessment only; not a probability estimate. "
                        f"Derived sub-branch under {parent_id} for '{question}'."
                    ),
                    assumptions=[
                        make_assumption(aid, text, kind=kind, confidence="low")
                        for aid, text, kind in assumptions
                    ],
                    triggers=[make_trigger(tid, event, desc) for tid, event, desc in triggers],
                    possible_consequences=[
                        f"Consequences of '{title}' unfold within the parent branch's framing.",
                    ],
                    indicators_to_watch=[
                        "Persistence of the parent branch's triggers",
                    ],
                    parent_id=parent_id,
                )
            )
        return children

    @staticmethod
    def _child_comparison(parent_id: str) -> Dict[str, Any]:
        c1, c2, c3 = f"{parent_id}.c1", f"{parent_id}.c2", f"{parent_id}.c3"
        return make_comparison(
            (
                "The three sub-branches differ in tempo and persistence: "
                "gradual deepening, accelerated development, or a stall back "
                "toward baseline. Which one unfolds depends on whether the "
                "parent branch's drivers persist, amplify, or fade."
            ),
            [
                {
                    "dimension": "Tempo",
                    "baseline": "Parent branch tempo",
                    "alternatives": {
                        c1: "Gradual",
                        c2: "Accelerated",
                        c3: "Stalling",
                    },
                },
                {
                    "dimension": "Persistence of parent drivers",
                    "baseline": "n/a",
                    "alternatives": {
                        c1: "Steady",
                        c2: "Self-reinforcing",
                        c3: "Fading",
                    },
                },
            ],
            [
                "Sub-branches differ mainly in tempo and in whether parent drivers persist or fade.",
            ],
            [
                "Evidence that the parent branch's triggers are strengthening, weakening, or reversing.",
            ],
        )

    # -- helpers for the demo dataset --------------------------------------

    @staticmethod
    def demo_evidence() -> List[Dict[str, Any]]:
        """Sample evidence items used by the bundled demo report."""
        return [
            make_evidence_item(
                "e1",
                "User observation: recent commentary has focused on how sensitive "
                "equity valuations are to interest-rate expectations.",
                kind="user_supplied_fact",
            ),
            make_evidence_item(
                "e2",
                "Historical example (educational): the 2022 rate-hiking cycle "
                "coincided with broad equity drawdowns before partial recovery.",
                kind="sourced_fact",
                source_uri="https://en.wikipedia.org/wiki/2021%E2%80%932023_inflation_surge",
                note="Background context only; not a prediction base.",
            ),
        ]
