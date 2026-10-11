/**
 * Prompt library for the in-browser DESNWORLD pipeline.
 *
 * Mirrors engine/desnworld/prompts.py: one configurable model, separate
 * prompts per pipeline stage, with the same honesty rules and the same
 * `# stage:` markers so both runtimes produce interchangeable reports.
 */

export const SYSTEM_PREAMBLE = [
  'You are the scenario engine of DESNWORLD, a general-purpose AI scenario',
  'exploration engine. DESNWORLD helps users explore possible futures for a',
  'question; it does NOT predict the future with certainty.',
  '',
  'Hard rules you must follow in every response:',
  '1. Explore possibilities. Use conditional language ("could", "might", "would',
  'require"); never claim an outcome is certain or guaranteed.',
  '2. Provenance is mandatory. Every assumption must carry a "kind":',
  '   - "sourced_fact": verifiable external information. You MUST attach the',
  '"source_uri" or the "evidence_ref" of the user evidence that backs it. If you',
  'cannot point to a real source or user evidence, it is NOT a sourced_fact.',
  '   - "user_supplied_fact": taken from the user\'s evidence (use its',
  '"evidence_ref").',
  '   - "ai_assumption": your own reasoning. This is the default kind.',
  '3. Never invent sources, citations, URLs, statistics, dates, or price levels.',
  'If reliable data is missing, say so in "missing_evidence" instead of guessing.',
  '4. Never state or imply that live data (market prices, indicators) was checked',
  'unless the user evidence actually contains it.',
  '5. In the stock_market_education domain: these are educational scenarios, not',
  'price predictions. Do not give personalized buy/sell instructions, target',
  'prices, or promised returns.',
  '6. Return ONLY a single JSON object matching the requested shape. No markdown',
  'fences, no commentary before or after the JSON.'
].join('\n')

function userMessage(stage, body) {
  return { role: 'user', content: `# stage: ${stage}\n\n${body.trim()}\n` }
}

function systemMessage() {
  return { role: 'system', content: SYSTEM_PREAMBLE }
}

function evidenceBlock(request) {
  const evidence = request.evidence || []
  if (!evidence.length) return 'User evidence: none provided.'
  const lines = ['User evidence items (id, kind, source_uri, text):']
  for (const item of evidence) {
    lines.push(`- [${item.id}] (${item.kind}, source: ${item.source_uri || '-'}) ${item.text}`)
  }
  return lines.join('\n')
}

function requestBlock(request) {
  return [
    `Question: ${request.question}`,
    `Domain: ${request.domain}`,
    `Time horizon: ${request.horizon.label} (${request.horizon.months} months)`,
    evidenceBlock(request)
  ].join('\n')
}

function scenarioShape(idField) {
  return `{
  "id": "${idField}",
  "label": "short label",
  "title": "short scenario title",
  "narrative": "2-4 paragraph description of how this future could unfold over the horizon",
  "stance": {"qualitative": "more_likely|plausible|less_likely|unlikely", "note": "why this stance; state explicitly that this is not a probability estimate"},
  "assumptions": [
    {"id": "a1", "text": "...", "kind": "ai_assumption|user_supplied_fact|sourced_fact", "confidence": "low|medium|high", "evidence_ref": "e1 or null", "source_uri": "https://... or null"}
  ],
  "triggers": [
    {"id": "t1", "event": "a concrete event or condition", "description": "how this event pushes the future toward this scenario"}
  ],
  "possible_consequences": ["consequence 1", "consequence 2"],
  "indicators_to_watch": ["indicator 1", "indicator 2"],
  "parent_id": null,
  "children": [],
  "child_comparison": null
}`
}

export function baselinePrompt(request) {
  const body = `${requestBlock(request)}

Task: establish the BASELINE scenario — the continuation of currently visible \
conditions, without assuming major surprises. Document the assumptions this \
baseline rests on, with provenance tags for each assumption. Include the \
events that would weaken the baseline (its triggers/fragilities) and \
indicators to watch.

Return a single JSON object exactly of this shape:
{
  "scenario": ${scenarioShape('baseline')}
}`
  return [systemMessage(), userMessage('baseline', body)]
}

export function alternativesPrompt(request, baseline) {
  const digest = JSON.stringify(
    {
      id: baseline.id,
      title: baseline.title,
      narrative: baseline.narrative,
      assumptions: baseline.assumptions
    },
    null,
    0
  )
  const body = `${requestBlock(request)}

Baseline scenario (already established):
${digest}

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
{
  "alternatives": [
    ${scenarioShape('alt-1')},
    ${scenarioShape('alt-2')},
    ${scenarioShape('alt-3')}
  ]
}`
  return [systemMessage(), userMessage('alternatives', body)]
}

export function uncertaintiesPrompt(request, baseline, alternatives) {
  const titles = [baseline.title, ...alternatives.map((a) => a.title)].join(', ')
  const body = `${requestBlock(request)}

Scenarios under consideration: ${titles}

Task: identify the uncertainties, missing evidence, and possible consequences \
that matter across these scenarios. Be explicit about what is NOT known and \
what evidence would reduce each uncertainty. Do not invent data to fill gaps.

Return a single JSON object exactly of this shape:
{
  "uncertainties": [
    {"id": "u1", "statement": "what is uncertain", "impact": "low|medium|high", "missing_evidence": "what evidence is missing to resolve it"}
  ],
  "missing_information": ["specific missing information item"],
  "limitations": ["limitation of this analysis, including data limitations"]
}`
  return [systemMessage(), userMessage('uncertainties', body)]
}

export function comparisonPrompt(request, baseline, alternatives) {
  const body = `${requestBlock(request)}

Baseline: ${baseline.title} — ${baseline.narrative}
Alternative 1 (alt-1): ${alternatives[0].title} — ${alternatives[0].narrative}
Alternative 2 (alt-2): ${alternatives[1].title} — ${alternatives[1].narrative}
Alternative 3 (alt-3): ${alternatives[2].title} — ${alternatives[2].narrative}

Task: write the COMPARISON report explaining how the scenarios differ. Compare \
them along 3-6 meaningful dimensions (for the stock_market_education domain \
prefer qualitative dimensions such as direction of pressure, volatility \
regime, uncertainty level — never specific price targets). State what would \
change the overall outlook.

Return a single JSON object exactly of this shape:
{
  "comparison": {
    "summary": "1-2 paragraph comparison summary",
    "dimensions": [
      {"dimension": "dimension name", "baseline": "baseline position", "alternatives": {"alt-1": "...", "alt-2": "...", "alt-3": "..."}}
    ],
    "key_differences": ["key difference 1", "key difference 2"],
    "what_would_change_the_outlook": ["event or evidence 1", "event or evidence 2"]
  }
}`
  return [systemMessage(), userMessage('comparison', body)]
}

export function subBranchPrompt(request, parent, siblings = []) {
  const digest = JSON.stringify(
    {
      id: parent.id,
      title: parent.title,
      narrative: parent.narrative,
      assumptions: parent.assumptions,
      triggers: parent.triggers
    },
    null,
    0
  )
  const siblingTitles = siblings.map((s) => s.title).join(', ') || 'none'
  const body = `${requestBlock(request)}

Parent scenario to explore deeper:
${digest}

Sibling branches (do NOT duplicate these): ${siblingTitles}

Task: expand the parent scenario into EXACTLY THREE meaningfully different \
sub-branches — distinct ways this branch could develop further from here. Each \
sub-branch needs its own triggers and assumptions with provenance tags. Set \
each child's "parent_id" to "${parent.id}" and use ids \
"${parent.id}.c1", "${parent.id}.c2", "${parent.id}.c3". \
Also write a small comparison of the three children.

Return a single JSON object exactly of this shape:
{
  "children": [
    ${scenarioShape(`${parent.id}.c1`)},
    ${scenarioShape(`${parent.id}.c2`)},
    ${scenarioShape(`${parent.id}.c3`)}
  ],
  "child_comparison": {
    "summary": "how these three sub-branches differ",
    "dimensions": [
      {"dimension": "dimension name", "baseline": "the parent's position", "alternatives": {"${parent.id}.c1": "...", "${parent.id}.c2": "...", "${parent.id}.c3": "..."}}
    ],
    "key_differences": ["difference"],
    "what_would_change_the_outlook": ["event or evidence"]
  }
}`
  return [systemMessage(), userMessage('sub_branch', body)]
}

export function repairPrompt(stage, rawOutput, problems) {
  const problemList = problems.slice(0, 30).map((p) => `- ${p}`).join('\n')
  const truncated = rawOutput.length > 6000 ? `${rawOutput.slice(0, 6000)}…` : rawOutput
  const body = `The previous response for pipeline stage '${stage}' was rejected by the \
DESNWORLD schema validator for the following reasons:
${problemList}

Previous response:
${truncated}

Task: return a corrected single JSON object for stage '${stage}' that fixes ALL \
of the problems above while keeping the same substance. Follow the system \
rules, especially the provenance rules: never invent sources; if a claim has \
no real source or user evidence, set its kind to "ai_assumption".`
  return [systemMessage(), userMessage(`repair:${stage}`, body)]
}
