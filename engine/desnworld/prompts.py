"""
Prompt library for the DESNWORLD scenario pipeline.

One configurable external model performs several tasks through *separate*
prompts (baseline, alternatives, uncertainties, comparison, repair,
sub-branch expansion). Every prompt shares a system preamble that encodes
DESNWORLD's honesty rules:

- Explore possibilities; never present scenarios as predictions.
- Never fabricate sources; tag every claim as sourced_fact,
  user_supplied_fact, or ai_assumption.
- Never imply live market data was checked when it was not.
- No personalized financial advice or guaranteed returns.

Each user prompt begins with a `# stage: <name>` marker so the deterministic
mock provider (tests / demo runs) can dispatch on the same call graph.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

Message = Dict[str, str]

SYSTEM_PREAMBLE = """\
You are the scenario engine of DESNWORLD, a general-purpose AI scenario \
exploration engine. DESNWORLD helps users explore possible futures for a \
question; it does NOT predict the future with certainty.

Hard rules you must follow in every response:
1. Explore possibilities. Use conditional language ("could", "might", "would \
require"); never claim an outcome is certain or guaranteed.
2. Provenance is mandatory. Every assumption must carry a "kind":
   - "sourced_fact": verifiable external information. You MUST attach the \
"source_uri" or the "evidence_ref" of the user evidence that backs it. If you \
cannot point to a real source or user evidence, it is NOT a sourced_fact.
   - "user_supplied_fact": taken from the user's evidence (use its \
"evidence_ref").
   - "ai_assumption": your own reasoning. This is the default kind.
3. Never invent sources, citations, URLs, statistics, dates, or price levels. \
If reliable data is missing, say so in "missing_evidence" instead of guessing.
4. Never state or imply that live data (market prices, indicators) was checked \
unless the user evidence actually contains it.
5. In the stock_market_education domain: these are educational scenarios, not \
price predictions. Do not give personalized buy/sell instructions, target \
prices, or promised returns.
6. Return ONLY a single JSON object matching the requested shape. No markdown \
fences, no commentary before or after the JSON.
"""


def _user(stage: str, body: str) -> str:
    return f"# stage: {stage}\n\n{body.strip()}\n"


def _evidence_block(request: Dict[str, Any]) -> str:
    evidence = request.get("evidence") or []
    if not evidence:
        return "User evidence: none provided."
    lines = ["User evidence items (id, kind, source_uri, text):"]
    for item in evidence:
        uri = item.get("source_uri") or "-"
        lines.append(f"- [{item['id']}] ({item['kind']}, source: {uri}) {item['text']}")
    return "\n".join(lines)


def _request_block(request: Dict[str, Any]) -> str:
    return (
        f"Question: {request['question']}\n"
        f"Domain: {request['domain']}\n"
        f"Time horizon: {request['horizon']['label']} "
        f"({request['horizon']['months']} months)\n"
        + _evidence_block(request)
    )


def _scenario_shape(id_field: str) -> str:
    return f"""\
{{
  "id": "{id_field}",
  "label": "short label",
  "title": "short scenario title",
  "narrative": "2-4 paragraph description of how this future could unfold over the horizon",
  "stance": {{"qualitative": "more_likely|plausible|less_likely|unlikely", "note": "why this stance; state explicitly that this is not a probability estimate"}},
  "assumptions": [
    {{"id": "a1", "text": "...", "kind": "ai_assumption|user_supplied_fact|sourced_fact", "confidence": "low|medium|high", "evidence_ref": "e1 or null", "source_uri": "https://... or null"}}
  ],
  "triggers": [
    {{"id": "t1", "event": "a concrete event or condition", "description": "how this event pushes the future toward this scenario"}}
  ],
  "possible_consequences": ["consequence 1", "consequence 2"],
  "indicators_to_watch": ["indicator 1", "indicator 2"],
  "parent_id": null,
  "children": [],
  "child_comparison": null
}}"""


def baseline_prompt(request: Dict[str, Any]) -> List[Message]:
    body = f"""\
{_request_block(request)}

Task: establish the BASELINE scenario — the continuation of currently visible \
conditions, without assuming major surprises. Document the assumptions this \
baseline rests on, with provenance tags for each assumption. Include the \
events that would weaken the baseline (its triggers/fragilities) and \
indicators to watch.

Return a single JSON object exactly of this shape:
{{
  "scenario": {_scenario_shape("baseline")}
}}
"""
    return [
        {"role": "system", "content": SYSTEM_PREAMBLE},
        {"role": "user", "content": _user("baseline", body)},
    ]


def alternatives_prompt(
    request: Dict[str, Any], baseline: Dict[str, Any]
) -> List[Message]:
    baseline_digest = json.dumps(
        {
            "id": baseline.get("id"),
            "title": baseline.get("title"),
            "narrative": baseline.get("narrative"),
            "assumptions": baseline.get("assumptions"),
        },
        ensure_ascii=False,
    )
    body = f"""\
{_request_block(request)}

Baseline scenario (already established):
{baseline_digest}

Task: generate EXACTLY THREE meaningfully different alternative scenarios that \
diverge from the baseline. Requirements:
- Each alternative must differ in direction and underlying assumptions, not in \
wording. Do not produce three variants of the same story.
- Each alternative needs at least one trigger: the concrete event or condition \
whose occurrence would push the future toward that branch instead of the \
baseline. Triggers must differ between alternatives.
- Keep the "id" values exactly "alt-1", "alt-2", "alt-3" and set "parent_id" \
to null.
- Tag every assumption with its provenance kind as per the system rules.

Return a single JSON object exactly of this shape:
{{
  "alternatives": [
    {_scenario_shape("alt-1")},
    {_scenario_shape("alt-2")},
    {_scenario_shape("alt-3")}
  ]
}}
"""
    return [
        {"role": "system", "content": SYSTEM_PREAMBLE},
        {"role": "user", "content": _user("alternatives", body)},
    ]


def uncertainties_prompt(
    request: Dict[str, Any],
    baseline: Dict[str, Any],
    alternatives: List[Dict[str, Any]],
) -> List[Message]:
    titles = ", ".join(
        [str(baseline.get("title"))] + [str(a.get("title")) for a in alternatives]
    )
    body = f"""\
{_request_block(request)}

Scenarios under consideration: {titles}

Task: identify the uncertainties, missing evidence, and possible consequences \
that matter across these scenarios. Be explicit about what is NOT known and \
what evidence would reduce each uncertainty. Do not invent data to fill gaps.

Return a single JSON object exactly of this shape:
{{
  "uncertainties": [
    {{"id": "u1", "statement": "what is uncertain", "impact": "low|medium|high", "missing_evidence": "what evidence is missing to resolve it"}}
  ],
  "missing_information": ["specific missing information item"],
  "limitations": ["limitation of this analysis, including data limitations"]
}}
"""
    return [
        {"role": "system", "content": SYSTEM_PREAMBLE},
        {"role": "user", "content": _user("uncertainties", body)},
    ]


def comparison_prompt(
    request: Dict[str, Any],
    baseline: Dict[str, Any],
    alternatives: List[Dict[str, Any]],
) -> List[Message]:
    body = f"""\
{_request_block(request)}

Baseline: {baseline.get("title")} — {baseline.get("narrative")}
Alternative 1 (alt-1): {alternatives[0].get("title")} — {alternatives[0].get("narrative")}
Alternative 2 (alt-2): {alternatives[1].get("title")} — {alternatives[1].get("narrative")}
Alternative 3 (alt-3): {alternatives[2].get("title")} — {alternatives[2].get("narrative")}

Task: write the COMPARISON report explaining how the scenarios differ. Compare \
them along 3-6 meaningful dimensions (for the stock_market_education domain \
prefer qualitative dimensions such as direction of pressure, volatility \
regime, uncertainty level — never specific price targets). State what would \
change the overall outlook.

Return a single JSON object exactly of this shape:
{{
  "comparison": {{
    "summary": "1-2 paragraph comparison summary",
    "dimensions": [
      {{"dimension": "dimension name", "baseline": "baseline position", "alternatives": {{"alt-1": "...", "alt-2": "...", "alt-3": "..."}}}}
    ],
    "key_differences": ["key difference 1", "key difference 2"],
    "what_would_change_the_outlook": ["event or evidence 1", "event or evidence 2"]
  }}
}}
"""
    return [
        {"role": "system", "content": SYSTEM_PREAMBLE},
        {"role": "user", "content": _user("comparison", body)},
    ]


def sub_branch_prompt(
    request: Dict[str, Any],
    parent: Dict[str, Any],
    siblings: Optional[List[Dict[str, Any]]] = None,
) -> List[Message]:
    parent_digest = json.dumps(
        {
            "id": parent.get("id"),
            "title": parent.get("title"),
            "narrative": parent.get("narrative"),
            "assumptions": parent.get("assumptions"),
            "triggers": parent.get("triggers"),
        },
        ensure_ascii=False,
    )
    sibling_titles = ", ".join(str(s.get("title")) for s in (siblings or [])) or "none"
    child_depth = 1 if parent.get("id") == "baseline" or str(parent.get("id", "")).startswith("alt-") else 2
    body = f"""\
{_request_block(request)}

Parent scenario to explore deeper:
{parent_digest}

Sibling branches (do NOT duplicate these): {sibling_titles}

Task: expand the parent scenario into EXACTLY THREE meaningfully different \
sub-branches — distinct ways this branch could develop further from here. Each \
sub-branch needs its own triggers and assumptions with provenance tags. Set \
each child's "parent_id" to "{parent.get('id')}" and use ids \
"{parent.get('id')}.c1", "{parent.get('id')}.c2", "{parent.get('id')}.c3". \
Also write a small comparison of the three children.

Return a single JSON object exactly of this shape:
{{
  "children": [
    {_scenario_shape(f"{parent.get('id')}.c1")},
    {_scenario_shape(f"{parent.get('id')}.c2")},
    {_scenario_shape(f"{parent.get('id')}.c3")}
  ],
  "child_comparison": {{
    "summary": "how these three sub-branches differ",
    "dimensions": [
      {{"dimension": "dimension name", "baseline": "the parent's position", "alternatives": {{"{parent.get('id')}.c1": "...", "{parent.get('id')}.c2": "...", "{parent.get('id')}.c3": "..."}}}}
    ],
    "key_differences": ["difference"],
    "what_would_change_the_outlook": ["event or evidence"]
  }}
}}
"""
    return [
        {"role": "system", "content": SYSTEM_PREAMBLE},
        {"role": "user", "content": _user("sub_branch", body)},
    ]


def repair_prompt(
    stage: str,
    raw_output: str,
    problems: List[str],
) -> List[Message]:
    problem_list = "\n".join(f"- {p}" for p in problems[:30])
    truncated = raw_output if len(raw_output) <= 6000 else raw_output[:6000] + "…"
    body = f"""\
The previous response for pipeline stage '{stage}' was rejected by the \
DESNWORLD schema validator for the following reasons:
{problem_list}

Previous response:
{truncated}

Task: return a corrected single JSON object for stage '{stage}' that fixes ALL \
of the problems above while keeping the same substance. Follow the system \
rules, especially the provenance rules: never invent sources; if a claim has \
no real source or user evidence, set its kind to "ai_assumption".
"""
    return [
        {"role": "system", "content": SYSTEM_PREAMBLE},
        {"role": "user", "content": _user(f"repair:{stage}", body)},
    ]
