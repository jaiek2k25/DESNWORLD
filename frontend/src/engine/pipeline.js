/**
 * The DESNWORLD scenario pipeline — browser port of engine/desnworld/engine.py.
 *
 * Same stages, same bounded repair loop, same deterministic provenance
 * downgrade and normalization. Produces schema-v1 reports interchangeable
 * with the Python engine (CLI / GitHub Actions / API server).
 */
import * as prompts from './prompts.js'
import { MalformedResponseError, SchemaValidationError } from './errors.js'
import { validateRequest } from './input.js'
import {
  ENGINE_NAME,
  ENGINE_VERSION,
  MAX_TREE_DEPTH,
  SCHEMA_VERSION,
  findScenarioWithDepth,
  normalizeComparison,
  normalizeNode,
  sanitizeProvenance,
  validateComparisonPublic,
  validateReport,
  validateScenarioNodePublic
} from './schema.js'

export const STAGES = [
  ['baseline', 'Establishing the baseline scenario and its assumptions'],
  ['alternatives', 'Generating three alternative branches and their triggers'],
  ['uncertainties', 'Identifying uncertainties, missing evidence, and consequences'],
  ['comparison', 'Writing the comparison report']
]

function extractKey(key) {
  return (payload) => {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return { value: null, problems: ['response: expected a JSON object'] }
    }
    if (!(key in payload)) {
      return { value: null, problems: [`response: missing required top-level key '${key}'`] }
    }
    return { value: payload[key], problems: [] }
  }
}

function extractChildren(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { value: null, problems: ['response: expected a JSON object'] }
  }
  if (!('children' in payload)) {
    return { value: null, problems: ["response: missing required top-level key 'children'"] }
  }
  return {
    value: { children: payload.children, child_comparison: payload.child_comparison ?? null },
    problems: []
  }
}

function validateNode(node, evidenceIds) {
  // id/parent drift is normalized deterministically, so only shape problems
  // are hard failures at stage level.
  return validateScenarioNodePublic(node, evidenceIds, 0)
}

function validateAlternatives(value, evidenceIds) {
  if (!Array.isArray(value)) return ['alternatives: must be a list']
  if (value.length !== 3) {
    return [
      `alternatives: exactly 3 alternative scenarios are required (found ${value.length})`
    ]
  }
  const problems = []
  const titles = {}
  const triggerSets = {}
  value.forEach((node, i) => {
    problems.push(
      ...validateNode(node, evidenceIds).map((p) => p.replace(/^scenario/, `alternatives[${i}]`))
    )
    if (node && typeof node === 'object') {
      const titleKey = String(node.title ?? '').trim().toLowerCase()
      if (titleKey in titles) {
        problems.push(
          `alternatives[${i}].title: duplicates alternatives[${titles[titleKey]}] ` +
            '(alternatives must be meaningfully different)'
        )
      } else {
        titles[titleKey] = i
      }
      const triggerKey = (node.triggers ?? [])
        .filter((t) => t && typeof t === 'object')
        .map((t) => String(t.event ?? '').trim().toLowerCase())
        .sort()
        .join('||')
      if (triggerKey && triggerKey in triggerSets) {
        problems.push(
          `alternatives[${i}].triggers: identical trigger set to ` +
            `alternatives[${triggerSets[triggerKey]}] ` +
            '(branches must be distinguished by different triggers)'
        )
      } else if (triggerKey) {
        triggerSets[triggerKey] = i
      }
    }
  })
  return problems
}

function validateExtras(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return ['response: expected a JSON object']
  }
  const problems = []
  const uncertainties = value.uncertainties
  if (!Array.isArray(uncertainties) || !uncertainties.length) {
    problems.push('uncertainties: at least one uncertainty is required')
  } else {
    uncertainties.forEach((u, i) => {
      if (!u || typeof u !== 'object') {
        problems.push(`uncertainties[${i}]: must be an object`)
        return
      }
      for (const [field, minimum] of [['id', 1], ['statement', 5], ['missing_evidence', 1]]) {
        const text = u[field]
        if (typeof text !== 'string' || text.trim().length < minimum) {
          problems.push(`uncertainties[${i}].${field}: missing or too short`)
        }
      }
      if (!['low', 'medium', 'high'].includes(u.impact)) {
        problems.push(`uncertainties[${i}].impact: must be low, medium, or high`)
      }
    })
  }
  for (const field of ['missing_information', 'limitations']) {
    const items = value[field]
    if (
      !Array.isArray(items) ||
      !items.length ||
      !items.every((x) => typeof x === 'string' && x.trim())
    ) {
      problems.push(`${field}: must be a non-empty list of strings`)
    }
  }
  return problems
}

function validateChildren(value, evidenceIds, parentId) {
  if (!value || typeof value !== 'object') return ["response: expected an object with 'children'"]
  const children = value.children
  if (!Array.isArray(children) || children.length !== 3) {
    return [
      `children: exactly 3 sub-branches are required ` +
        `(found ${Array.isArray(children) ? children.length : 'none'})`
    ]
  }
  const problems = []
  const titles = {}
  children.forEach((node, i) => {
    if (!node || typeof node !== 'object') {
      problems.push(`children[${i}]: must be an object`)
      return
    }
    problems.push(
      ...validateNode(node, evidenceIds).map((p) =>
        p.replace(/^scenario/, `children[${i}]`)
      )
    )
    const titleKey = String(node.title ?? '').trim().toLowerCase()
    if (titleKey in titles) {
      problems.push(
        `children[${i}].title: duplicates children[${titles[titleKey]}] ` +
          '(sub-branches must be meaningfully different)'
      )
    } else {
      titles[titleKey] = i
    }
  })
  if (value.child_comparison != null) {
    problems.push(...validateComparisonPublic(value.child_comparison))
  }
  return problems
}

/* ------------------------------------------------------------------ */
/* pipeline                                                            */
/* ------------------------------------------------------------------ */

function newReportId() {
  const hex =
    typeof crypto !== 'undefined' && crypto.getRandomValues
      ? Array.from(crypto.getRandomValues(new Uint8Array(6)), (b) => b.toString(16).padStart(2, '0')).join('')
      : Math.random().toString(16).slice(2, 14)
  return `rpt-${hex}`
}

function generatorBlock(provider) {
  return {
    name: ENGINE_NAME,
    engine_version: ENGINE_VERSION,
    schema_version: SCHEMA_VERSION,
    provider: provider.providerName ?? 'unknown',
    model: provider.modelName ?? '',
    mock: Boolean(provider.isMock),
    runtime: 'browser'
  }
}

function buildEvidenceLedger(request) {
  return (request.evidence ?? []).map((item) => ({
    id: item.id,
    kind: item.kind,
    text: item.text,
    source_uri: item.source_uri ?? null,
    evidence_ref: null,
    note: item.note ?? null
  }))
}

function disclaimerFor(domain) {
  const base =
    'DESNWORLD explores possible futures; it does not predict the future with certainty. ' +
    'All scenarios are structured possibilities with documented assumptions, triggers, and uncertainties.'
  if (domain === 'stock_market_education') {
    return (
      base +
      ' This stock-market module is educational: scenarios are not price predictions, ' +
      'not personalized investment advice, and no outcome or return is guaranteed.'
    )
  }
  return base
}

function dataStatusFor(request, provider) {
  const sources = [
    ...new Set((request.evidence ?? []).map((item) => item.source_uri).filter(Boolean))
  ].sort()
  let message
  if (provider.isMock) {
    message =
      'This run used the offline demo engine: no live market data or economic indicators were ' +
      'queried, and no AI model was called. Content is illustrative only.'
  } else if (request.domain === 'stock_market_education') {
    message =
      'No live market data or economic indicators were queried in this run. Scenarios are ' +
      'qualitative and rest only on the question and user-supplied evidence. Do not treat ' +
      'anything here as a price prediction.'
  } else {
    message =
      'No live external data sources were queried in this run. Scenarios rest only on the ' +
      'question and user-supplied evidence.'
  }
  return { live_market_data_checked: false, sources, message }
}

function mergeLimitations(limitations, provider) {
  const merged = [...limitations]
  if (provider.isMock) {
    merged.push(
      'This report was produced by the deterministic demo engine without calling an AI model; ' +
        'content is illustrative and must not be treated as analysis.'
    )
  } else {
    merged.push(
      'This report was generated in your browser by a language model via your own API ' +
        'credentials; model output can be wrong or incomplete.'
    )
  }
  return merged
}

async function runStage({ provider, stage, messages, extract, validate, onStage }) {
  onStage?.({ stage, state: 'active' })
  let raw = await provider.chatJSON(messages)
  let { value, problems } = extract(raw)
  if (!problems.length) {
    value = sanitizeProvenance(value)
    problems = validate(value)
  }
  if (problems.length) {
    onStage?.({ stage, state: 'repairing', problems })
    const repairMessages = prompts.repairPrompt(stage, JSON.stringify(raw), problems)
    raw = await provider.chatJSON(repairMessages)
    ;({ value, problems } = extract(raw))
    if (!problems.length) {
      value = sanitizeProvenance(value)
      problems = validate(value)
    }
    if (problems.length) {
      onStage?.({ stage, state: 'error', problems })
      throw new SchemaValidationError(
        `Stage '${stage}' produced invalid output even after repair.`,
        {
          problems,
          hint: 'Re-run generation, or switch to a stronger model.'
        }
      )
    }
  }
  onStage?.({ stage, state: 'done' })
  return value
}

export async function generate(requestInput, provider, { onStage } = {}) {
  const request = validateRequest(requestInput)
  const evidenceIds = Object.fromEntries((request.evidence ?? []).map((e) => [e.id, e.kind]))
  const ledger = buildEvidenceLedger(request)

  const baselineRaw = await runStage({
    provider,
    stage: 'baseline',
    messages: prompts.baselinePrompt(request),
    extract: extractKey('scenario'),
    validate: (node) => validateNode(node, evidenceIds),
    onStage
  })
  const baseline = normalizeNode(baselineRaw, 'baseline', null)

  const alternativesRaw = await runStage({
    provider,
    stage: 'alternatives',
    messages: prompts.alternativesPrompt(request, baseline),
    extract: extractKey('alternatives'),
    validate: (value) => validateAlternatives(value, evidenceIds),
    onStage
  })
  const alternatives = alternativesRaw.map((node, i) => normalizeNode(node, `alt-${i + 1}`, null))

  const extras = await runStage({
    provider,
    stage: 'uncertainties',
    messages: prompts.uncertaintiesPrompt(request, baseline, alternatives),
    extract: (payload) => ({ value: payload, problems: [] }),
    validate: validateExtras,
    onStage
  })

  const comparisonRaw = await runStage({
    provider,
    stage: 'comparison',
    messages: prompts.comparisonPrompt(request, baseline, alternatives),
    extract: extractKey('comparison'),
    validate: validateComparisonPublic,
    onStage
  })
  const comparison = normalizeComparison(comparisonRaw, ['baseline', 'alt-1', 'alt-2', 'alt-3'])

  const report = {
    schema_version: SCHEMA_VERSION,
    report_id: newReportId(),
    generated_at: new Date().toISOString(),
    generator: generatorBlock(provider),
    request: {
      question: request.question,
      domain: request.domain,
      horizon: { months: request.horizon.months, label: request.horizon.label },
      evidence: ledger
    },
    disclaimer: disclaimerFor(request.domain),
    data_status: dataStatusFor(request, provider),
    baseline,
    alternatives,
    comparison,
    uncertainties: extras.uncertainties,
    missing_information: extras.missing_information,
    limitations: mergeLimitations(extras.limitations, provider),
    evidence_ledger: ledger
  }

  sanitizeProvenance(report)
  const problems = validateReport(report)
  if (problems.length) {
    throw new SchemaValidationError(
      `Invalid scenario report: ${problems.length} schema problem(s) found.`,
      { problems, hint: 'Re-run generation; see problems for details.' }
    )
  }
  return report
}

export async function expandBranch(report, scenarioId, provider, { onStage } = {}) {
  const working = structuredClone(report)
  const pre = validateReport(working)
  if (pre.length) {
    throw new SchemaValidationError(`Invalid input report: ${pre.length} schema problem(s) found.`, {
      problems: pre
    })
  }
  const { node, depth } = findScenarioWithDepth(working, scenarioId)
  if (!node) {
    throw new SchemaValidationError(`Scenario '${scenarioId}' was not found in the report.`, {
      problems: [`scenario_id: '${scenarioId}' does not exist`]
    })
  }
  if (depth >= MAX_TREE_DEPTH || (node.children ?? []).length) {
    throw new SchemaValidationError(`Scenario '${scenarioId}' cannot be expanded further.`, {
      problems: [
        `scenario_id: '${scenarioId}' is already at the maximum supported tree depth (${MAX_TREE_DEPTH})`
      ],
      hint: 'Expand a different branch instead.'
    })
  }

  const request = {
    question: working.request.question,
    domain: working.request.domain,
    horizon: working.request.horizon,
    evidence: working.request.evidence ?? []
  }
  const evidenceIds = Object.fromEntries(request.evidence.map((e) => [e.id, e.kind]))
  const siblingNodes = siblingsOf(working, node)

  const extracted = await runStage({
    provider,
    stage: `sub_branch:${scenarioId}`,
    messages: prompts.subBranchPrompt(request, node, siblingNodes),
    extract: extractChildren,
    validate: (value) => validateChildren(value, evidenceIds, scenarioId),
    onStage
  })
  const children = extracted.children.map((child, i) =>
    normalizeNode(child, `${scenarioId}.c${i + 1}`, scenarioId)
  )
  let childComparison = null
  if (extracted.child_comparison) {
    const childIds = children.map((c) => c.id)
    childComparison = normalizeComparison(extracted.child_comparison, ['baseline', ...childIds])
  }

  node.children = children
  node.child_comparison = childComparison

  sanitizeProvenance(working)
  const problems = validateReport(working)
  if (problems.length) {
    throw new SchemaValidationError(`Invalid expanded report: ${problems.length} schema problem(s).`, {
      problems
    })
  }
  return working
}

function siblingsOf(report, node) {
  const parentId = node.parent_id
  let siblings
  if (parentId == null) {
    siblings = [report.baseline, ...(report.alternatives ?? [])]
  } else {
    const { node: parent } = findScenarioWithDepth(report, parentId)
    siblings = (parent?.children ?? [])
  }
  return siblings.filter((s) => s && s.id !== node.id)
}
