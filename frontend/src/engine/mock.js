/**
 * Deterministic offline scenario provider — the "Demo engine".
 *
 * JS port of engine/desnworld/providers.py::MockScenarioProvider. Produces
 * schema-valid canned output so anyone can run the full pipeline in the web
 * UI with no credentials and no network. Reports generated through it record
 * `generator.mock = true` and an explicit limitations entry.
 */

function makeAssumption(id, text, kind = 'ai_assumption', confidence = 'medium', extra = {}) {
  return {
    id,
    text,
    kind,
    confidence,
    evidence_ref: extra.evidence_ref ?? null,
    source_uri: extra.source_uri ?? null
  }
}

function makeTrigger(id, event, description) {
  return { id, event, description }
}

function makeScenario(id, label, title, narrative, options = {}) {
  return {
    id,
    label,
    title,
    narrative,
    stance: {
      qualitative: options.stance ?? 'plausible',
      note:
        options.stance_note ??
        'Qualitative assessment only; DESNWORLD does not compute probabilities and this is not a prediction.'
    },
    assumptions: options.assumptions ?? [],
    triggers: options.triggers ?? [],
    possible_consequences: options.possible_consequences ?? [],
    indicators_to_watch: options.indicators_to_watch ?? [],
    parent_id: options.parent_id ?? null,
    children: [],
    child_comparison: null
  }
}

function makeComparison(summary, dimensions, keyDifferences, whatWouldChange) {
  return {
    summary,
    dimensions,
    key_differences: keyDifferences,
    what_would_change_the_outlook: whatWouldChange
  }
}

function makeUncertainty(id, statement, impact = 'medium', missingEvidence = '') {
  return { id, statement, impact, missing_evidence: missingEvidence }
}

const STAGE_RE = /^# stage:\s*(\S+)/m
const QUESTION_RE = /^Question:\s*(.+)$/m
const PARENT_ID_RE = /"id":\s*"([^"]+)"/

export function baselineScenario(question) {
  return makeScenario(
    'baseline',
    'Baseline',
    'Continuation of visible conditions',
    `For the question '${question}', the baseline scenario extends currently visible ` +
      'conditions over the chosen horizon without assuming major surprises. Slow-moving ' +
      'trends continue at roughly their recent pace, and no single shock dominates the ' +
      'picture. This is one possible future among several — not a forecast.',
    {
      stance: 'more_likely',
      assumptions: [
        makeAssumption(
          'b-a1',
          'No unprecedented structural break occurs within the horizon.',
          'ai_assumption',
          'medium'
        ),
        makeAssumption(
          'b-a2',
          "Conditions visible in the user's question and evidence persist roughly unchanged.",
          'user_supplied_fact',
          'medium'
        )
      ],
      triggers: [
        makeTrigger(
          'b-t1',
          'A major unexpected shock',
          'A large shock would break the baseline and push the future toward one of the alternative branches.'
        ),
        makeTrigger(
          'b-t2',
          'Sustained trend reversal in key indicators',
          'If leading indicators reverse for several periods, the continuation assumption weakens.'
        )
      ],
      possible_consequences: [
        'Outcomes stay within the range of recent experience.',
        'Planning assumptions from the past period remain usable with modest adjustments.'
      ],
      indicators_to_watch: [
        'Momentum in the indicators named in the question',
        'Surprise indices and policy announcements'
      ]
    }
  )
}

export function alternativeScenarios(question) {
  const alt1 = makeScenario(
    'alt-1',
    'Alternative 1',
    'Upside drift beyond trend',
    `A plausible alternative for '${question}' is an upside surprise: conditions improve ` +
      'beyond the baseline trend. Confidence builds gradually, and early signals appear in ' +
      'indicators before the broader picture shifts. This branch is conditional on specific ' +
      'triggers occurring — it is a possibility to explore, not a prediction.',
    {
      assumptions: [
        makeAssumption(
          'a1-a1',
          'Positive catalysts identified in the triggers materialise.',
          'ai_assumption',
          'low'
        ),
        makeAssumption(
          'a1-a2',
          'No offsetting negative shock occurs in the same window.',
          'ai_assumption',
          'low'
        )
      ],
      triggers: [
        makeTrigger(
          'a1-t1',
          'Broad-based improvement in leading indicators',
          'Sustained improvement pulls expectations above the baseline path.'
        )
      ],
      possible_consequences: [
        'Expectations re-rate gradually toward the improved path.',
        'Planning under the baseline becomes conservative relative to outcomes.'
      ],
      indicators_to_watch: [
        'Revision direction in leading indicators',
        'Breadth of improvement across sectors'
      ]
    }
  )
  const alt2 = makeScenario(
    'alt-2',
    'Alternative 2',
    'Downside stress episode',
    `Another possibility for '${question}' is a downside stress episode: a deterioration ` +
      'that exceeds ordinary variation. Typically this unfolds as a trigger event followed ' +
      'by second-round effects that reinforce the initial move. This branch is conditional, ' +
      'not forecasted.',
    {
      assumptions: [
        makeAssumption(
          'a2-a1',
          'A stress trigger occurs and is not quickly contained.',
          'ai_assumption',
          'low'
        )
      ],
      triggers: [
        makeTrigger(
          'a2-t1',
          'A disorderly repricing event',
          'A sharp repricing event raises risk aversion and pushes outcomes below the baseline.'
        )
      ],
      possible_consequences: [
        'Uncertainty rises and decision-making windows shorten.',
        'Weak assumptions embedded in plans are exposed.'
      ],
      indicators_to_watch: ['Volatility and funding-stress measures', 'Policy response speed and credibility']
    }
  )
  const alt3 = makeScenario(
    'alt-3',
    'Alternative 3',
    'Structural regime shift',
    `A third possibility for '${question}' is a regime shift: the rules, institutions, or ` +
      'technology landscape change enough that extrapolation from the past stops working. ' +
      'Historical patterns become less informative; new baselines must be formed. This is ' +
      'the branch of deep uncertainty.',
    {
      stance: 'less_likely',
      assumptions: [
        makeAssumption(
          'a3-a1',
          'A structural change (regulatory, technological, or institutional) takes hold within the horizon.',
          'ai_assumption',
          'low'
        )
      ],
      triggers: [
        makeTrigger(
          'a3-t1',
          'Durable policy or technology regime change',
          'A lasting change in the operating environment invalidates extrapolation from the recent past.'
        )
      ],
      possible_consequences: [
        'Historical analogies lose predictive value for a time.',
        'Scenario ranges widen; diversification of options gains value.'
      ],
      indicators_to_watch: ['Regulatory and standards decisions', 'Adoption curves of the new technology or regime']
    }
  )
  return [alt1, alt2, alt3]
}

export function uncertaintyBundle() {
  return {
    uncertainties: [
      makeUncertainty(
        'u1',
        'The pace and sequencing of the triggers above are unknown.',
        'high',
        'Time-stamped leading-indicator data covering the horizon.'
      ),
      makeUncertainty(
        'u2',
        'Interactions between triggers could amplify or dampen each branch.',
        'medium',
        'Cross-domain evidence on how these factors have co-moved historically.'
      )
    ],
    missing_information: [
      'No live market data or economic indicators were queried for this run; any market-quantitative claim would need such data to be supplied as evidence.',
      'Domain-expert judgement on the plausibility of each trigger has not been collected.'
    ],
    limitations: [
      'All scenarios are AI-generated possibilities, not predictions, and may omit important factors.',
      'The evidence base consists only of the question and user-supplied evidence; without external data the analysis is qualitative.',
      'This is educational scenario exploration, not financial advice; no buy/sell instruction or guaranteed return is implied.'
    ]
  }
}

export function comparisonBundle() {
  return makeComparison(
    'The baseline extends visible conditions; the alternatives explore an upside drift, a ' +
      'downside stress episode, and a structural regime shift. They differ in direction, in ' +
      "the triggers that would select each branch, and in how much historical experience " +
      'remains informative. None of these branches is a prediction.',
    [
      {
        dimension: 'Direction vs. baseline',
        baseline: 'Path continuation',
        alternatives: { 'alt-1': 'Above trend', 'alt-2': 'Below trend', 'alt-3': 'New trend definition' }
      },
      {
        dimension: 'Dominant trigger type',
        baseline: 'Absence of major shocks',
        alternatives: {
          'alt-1': 'Broad indicator improvement',
          'alt-2': 'Disorderly repricing event',
          'alt-3': 'Regime change'
        }
      },
      {
        dimension: 'Value of historical analogies',
        baseline: 'High',
        alternatives: { 'alt-1': 'Moderate', 'alt-2': 'Moderate', 'alt-3': 'Low' }
      },
      {
        dimension: 'Uncertainty level',
        baseline: 'Moderate',
        alternatives: { 'alt-1': 'Moderate-high', 'alt-2': 'High', 'alt-3': 'Very high' }
      }
    ],
    [
      'The branches differ most in which trigger fires and how much history remains informative.',
      'The baseline is the only branch that assumes continuity; all alternatives require a specific trigger.'
    ],
    [
      'Sustained movement in leading indicators toward either alternative.',
      'A policy or technology decision that would constitute a regime change.'
    ]
  )
}

export function childScenarios(parentId, question) {
  const definitions = [
    [
      'Gradual development',
      'This sub-branch develops gradually: early signals strengthen slowly and the parent scenario deepens without abrupt moves.',
      'plausible',
      'Steady continuation of leading indicators',
      'Indicators keep moving in the parent branch’s direction.'
    ],
    [
      'Accelerated development',
      'This sub-branch develops faster than expected: feedback effects amplify the parent scenario, compressing the timeline of consequences.',
      'plausible',
      'Self-reinforcing feedback in the parent branch',
      'Amplification shortens the path to the parent scenario’s consequences.'
    ],
    [
      'Stalled or reversed development',
      'This sub-branch stalls or partially reverses: the parent scenario’s drivers fade, and outcomes drift back toward the baseline.',
      'less_likely',
      'Fade-out of the parent branch’s triggers',
      'Loss of momentum pulls outcomes back toward baseline conditions.'
    ]
  ]
  return definitions.map(([title, narrative, stance, triggerEvent, triggerDesc], index) => {
    const cid = `${parentId}.c${index + 1}`
    return makeScenario(cid, `Sub ${index + 1}`, title, narrative, {
      stance,
      stance_note: `Qualitative assessment only; not a probability estimate. Derived sub-branch under ${parentId} for '${question}'.`,
      assumptions: [
        makeAssumption(
          `${cid}.a1`,
          index === 0
            ? 'Current momentum continues without interruption.'
            : index === 1
              ? 'Feedback loops strengthen rather than dampen the initial move.'
              : 'The parent branch’s drivers prove temporary.',
          'ai_assumption',
          'low'
        )
      ],
      triggers: [makeTrigger(`${cid}.t1`, triggerEvent, triggerDesc)],
      possible_consequences: [`Consequences of '${title}' unfold within the parent branch’s framing.`],
      indicators_to_watch: ['Persistence of the parent branch’s triggers'],
      parent_id: parentId
    })
  })
}

export function childComparisonBundle(parentId) {
  const c1 = `${parentId}.c1`
  const c2 = `${parentId}.c2`
  const c3 = `${parentId}.c3`
  return makeComparison(
    'The three sub-branches differ in tempo and persistence: gradual deepening, accelerated ' +
      'development, or a stall back toward baseline. Which one unfolds depends on whether the ' +
      "parent branch's drivers persist, amplify, or fade.",
    [
      {
        dimension: 'Tempo',
        baseline: 'Parent branch tempo',
        alternatives: { [c1]: 'Gradual', [c2]: 'Accelerated', [c3]: 'Stalling' }
      },
      {
        dimension: 'Persistence of parent drivers',
        baseline: 'n/a',
        alternatives: { [c1]: 'Steady', [c2]: 'Self-reinforcing', [c3]: 'Fading' }
      }
    ],
    ['Sub-branches differ mainly in tempo and in whether parent drivers persist or fade.'],
    ["Evidence that the parent branch's triggers are strengthening, weakening, or reversing."]
  )
}

export class MockScenarioProvider {
  providerName = 'browser-mock'
  modelName = 'desnworld-mock'
  isMock = true

  async chatJSON(messages) {
    const userContent = [...messages].reverse().find((m) => m.role === 'user')?.content ?? ''
    const stage = (STAGE_RE.exec(userContent) ?? [])[1] ?? 'unknown'
    const question = (QUESTION_RE.exec(userContent) ?? [])[1] ?? 'the question under exploration'

    if (stage === 'baseline' || stage === 'repair:baseline') {
      return { scenario: baselineScenario(question) }
    }
    if (stage === 'alternatives' || stage === 'repair:alternatives') {
      return { alternatives: alternativeScenarios(question) }
    }
    if (stage === 'uncertainties' || stage === 'repair:uncertainties') {
      return uncertaintyBundle()
    }
    if (stage === 'comparison' || stage === 'repair:comparison') {
      return { comparison: comparisonBundle() }
    }
    if (stage.startsWith('sub_branch') || stage.startsWith('repair:sub_branch')) {
      const parentId = (PARENT_ID_RE.exec(userContent) ?? [])[1] ?? 'node'
      return {
        children: childScenarios(parentId, question),
        child_comparison: childComparisonBundle(parentId)
      }
    }
    throw new Error(`MockScenarioProvider does not recognise pipeline stage '${stage}'`)
  }
}
