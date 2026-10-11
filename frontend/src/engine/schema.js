/**
 * Versioned DESNWORLD scenario-report schema (v1) — client-side port of
 * engine/desnworld/schema.py plus the deterministic normalizers from
 * engine/desnworld/engine.py. Reports produced by the browser engine and the
 * Python engine are interchangeable.
 */

export const SCHEMA_VERSION = '1.0.0'
export const ENGINE_NAME = 'DESNWORLD'
export const ENGINE_VERSION = '0.1.0'

export const DOMAINS = ['general', 'stock_market_education', 'business', 'technology']
export const PROVENANCE_KINDS = ['sourced_fact', 'user_supplied_fact', 'ai_assumption']
export const CONFIDENCE_LEVELS = ['low', 'medium', 'high']
export const LIKELIHOOD_STANCES = ['more_likely', 'plausible', 'less_likely', 'unlikely']
export const IMPACT_LEVELS = ['low', 'medium', 'high']
export const MAX_TREE_DEPTH = 2

const ID_RE = /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/

function isStr(value, minLen = 1) {
  return typeof value === 'string' && value.trim().length >= minLen
}

function isStrList(value, { minLen = 1, itemMin = 1 } = {}) {
  if (!Array.isArray(value) || value.length < minLen) return false
  return value.every((item) => isStr(item, itemMin))
}

export function parseSchemaVersion(version) {
  if (typeof version !== 'string') return null
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version.trim())
  if (!match) return null
  return [Number(match[1]), Number(match[2]), Number(match[3])]
}

export function isCompatibleVersion(version) {
  const parsed = parseSchemaVersion(version)
  if (!parsed) return false
  const [major, minor] = parsed
  const current = parseSchemaVersion(SCHEMA_VERSION)
  return major === current[0] && minor <= current[1]
}

/* ------------------------------------------------------------------ */
/* validation                                                          */
/* ------------------------------------------------------------------ */

function validateEvidenceItem(item, index, problems) {
  const prefix = `request.evidence[${index}]`
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    problems.push(`${prefix}: must be an object`)
    return
  }
  if (!isStr(item.id) || !ID_RE.test(String(item.id))) {
    problems.push(`${prefix}.id: missing or invalid id`)
  }
  if (!isStr(item.text, 3)) {
    problems.push(`${prefix}.text: must be a string of at least 3 characters`)
  }
  const kind = item.kind
  if (!PROVENANCE_KINDS.includes(kind)) {
    problems.push(`${prefix}.kind: must be one of ${PROVENANCE_KINDS.join(', ')}`)
  }
  if (kind === 'sourced_fact' && !isStr(item.source_uri)) {
    problems.push(
      `${prefix}: kind is 'sourced_fact' but source_uri is missing ` +
        '(fabricated provenance is not allowed)'
    )
  }
  if (item.source_uri != null && !(isStr(item.source_uri) && /^https?:\/\//.test(item.source_uri))) {
    problems.push(`${prefix}.source_uri: must be an http(s) URL when present`)
  }
}

function validateAssumption(item, path, problems) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    problems.push(`${path}: must be an object`)
    return
  }
  if (!isStr(item.id)) problems.push(`${path}.id: missing`)
  if (!isStr(item.text, 3)) problems.push(`${path}.text: must be a string of at least 3 characters`)
  const kind = item.kind
  if (!PROVENANCE_KINDS.includes(kind)) {
    problems.push(`${path}.kind: must be one of ${PROVENANCE_KINDS.join(', ')}`)
  }
  if (!CONFIDENCE_LEVELS.includes(item.confidence)) {
    problems.push(`${path}.confidence: must be one of ${CONFIDENCE_LEVELS.join(', ')}`)
  }
  if (kind === 'sourced_fact' && !(isStr(item.source_uri) || isStr(item.evidence_ref))) {
    problems.push(
      `${path}: kind is 'sourced_fact' but neither source_uri nor ` +
        'evidence_ref is set (fabricated provenance is not allowed)'
    )
  }
  if (item.evidence_ref != null && !isStr(item.evidence_ref)) {
    problems.push(`${path}.evidence_ref: must be a non-empty string when present`)
  }
}

function validateTrigger(item, path, problems) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    problems.push(`${path}: must be an object`)
    return
  }
  if (!isStr(item.id)) problems.push(`${path}.id: missing`)
  if (!isStr(item.event, 3)) problems.push(`${path}.event: must be a string of at least 3 characters`)
  if (!isStr(item.description, 3)) {
    problems.push(`${path}.description: must be a string of at least 3 characters`)
  }
}

function validateScenarioNodeInternal(node, path, problems, depth, evidenceIds) {
  if (!node || typeof node !== 'object' || Array.isArray(node)) {
    problems.push(`${path}: must be an object`)
    return
  }
  if (!isStr(node.id)) problems.push(`${path}.id: missing`)
  for (const field of ['label', 'title', 'narrative']) {
    if (!isStr(node[field], 3)) {
      problems.push(`${path}.${field}: must be a string of at least 3 characters`)
    }
  }
  const stance = node.stance
  if (!stance || typeof stance !== 'object' || !LIKELIHOOD_STANCES.includes(stance.qualitative)) {
    problems.push(`${path}.stance.qualitative: must be one of ${LIKELIHOOD_STANCES.join(', ')}`)
  } else if (!isStr(stance.note, 3)) {
    problems.push(`${path}.stance.note: must explain the qualitative stance`)
  }

  const assumptions = node.assumptions
  if (!Array.isArray(assumptions) || !assumptions.length) {
    problems.push(`${path}.assumptions: at least one assumption is required`)
  } else {
    assumptions.forEach((item, i) => {
      validateAssumption(item, `${path}.assumptions[${i}]`, problems)
      if (item && typeof item === 'object') {
        const ref = item.evidence_ref
        if (ref != null && !(ref in evidenceIds)) {
          problems.push(
            `${path}.assumptions[${i}].evidence_ref: '${ref}' does not ` +
              'match any request evidence id'
          )
        }
      }
    })
  }

  const triggers = node.triggers
  if (!Array.isArray(triggers) || !triggers.length) {
    problems.push(`${path}.triggers: at least one trigger is required`)
  } else {
    triggers.forEach((item, i) => validateTrigger(item, `${path}.triggers[${i}]`, problems))
  }

  for (const field of ['possible_consequences', 'indicators_to_watch']) {
    if (!isStrList(node[field])) {
      problems.push(`${path}.${field}: must be a non-empty list of strings`)
    }
  }

  if (node.parent_id != null && !isStr(node.parent_id)) {
    problems.push(`${path}.parent_id: must be a non-empty string or null`)
  }

  const children = node.children ?? []
  if (!Array.isArray(children)) {
    problems.push(`${path}.children: must be a list`)
    return
  }
  if (children.length) {
    if (depth >= MAX_TREE_DEPTH) {
      problems.push(
        `${path}.children: tree depth exceeds the supported maximum ` +
          `of ${MAX_TREE_DEPTH} levels below the report root`
      )
      return
    }
    if (children.length !== 3) {
      problems.push(
        `${path}.children: expansion branches must contain exactly 3 ` +
          `sub-branches (found ${children.length})`
      )
    }
    const seenTitles = {}
    children.forEach((child, i) => {
      const childPath = `${path}.children[${i}]`
      validateScenarioNodeInternal(child, childPath, problems, depth + 1, evidenceIds)
      if (child && typeof child === 'object') {
        if (child.parent_id !== node.id) {
          problems.push(
            `${childPath}.parent_id: must equal the parent node id ` +
              `'${node.id}' (found ${JSON.stringify(child.parent_id)})`
          )
        }
        const titleKey = String(child.title ?? '').trim().toLowerCase()
        if (titleKey in seenTitles) {
          problems.push(
            `${childPath}.title: duplicates ${seenTitles[titleKey]} ` +
              '(sub-branches must be meaningfully different)'
          )
        } else {
          seenTitles[titleKey] = `${childPath}.title`
        }
      }
    })
  }

  if (node.child_comparison != null && typeof node.child_comparison !== 'object') {
    problems.push(`${path}.child_comparison: must be an object when present`)
  }
}

function validateComparisonInternal(comparison, problems) {
  const path = 'comparison'
  if (!comparison || typeof comparison !== 'object' || Array.isArray(comparison)) {
    problems.push(`${path}: must be an object`)
    return
  }
  if (!isStr(comparison.summary, 10)) {
    problems.push(`${path}.summary: must be a string of at least 10 characters`)
  }
  const dimensions = comparison.dimensions
  if (!Array.isArray(dimensions) || !dimensions.length) {
    problems.push(`${path}.dimensions: at least one dimension is required`)
  } else {
    dimensions.forEach((dim, i) => {
      const dimPath = `${path}.dimensions[${i}]`
      if (!dim || typeof dim !== 'object' || Array.isArray(dim)) {
        problems.push(`${dimPath}: must be an object`)
        return
      }
      if (!isStr(dim.dimension, 3)) problems.push(`${dimPath}.dimension: missing label`)
      if (!isStr(dim.baseline, 1)) problems.push(`${dimPath}.baseline: missing value`)
      const alts = dim.alternatives
      if (!alts || typeof alts !== 'object' || Object.keys(alts).length !== 3) {
        problems.push(`${dimPath}.alternatives: must map exactly 3 scenario ids`)
      }
    })
  }
  if (!isStrList(comparison.key_differences)) {
    problems.push(`${path}.key_differences: must be a non-empty list of strings`)
  }
  if (!isStrList(comparison.what_would_change_the_outlook)) {
    problems.push(`${path}.what_would_change_the_outlook: must be a non-empty list of strings`)
  }
}

export function validateScenarioNodePublic(node, evidenceIds = {}, depth = 0) {
  const problems = []
  validateScenarioNodeInternal(node, 'scenario', problems, depth, evidenceIds)
  return problems
}

export function validateComparisonPublic(comparison) {
  const problems = []
  validateComparisonInternal(comparison, problems)
  return problems
}

export function validateReport(doc) {
  const problems = []
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) {
    return ['report: must be a JSON object']
  }

  if (!isCompatibleVersion(doc.schema_version)) {
    problems.push(
      `schema_version: ${JSON.stringify(doc.schema_version)} is not compatible ` +
        `with this engine (expected MAJOR ${SCHEMA_VERSION.split('.')[0]}, ` +
        `MINOR <= ${SCHEMA_VERSION.split('.')[1]})`
    )
  }

  for (const field of ['report_id', 'generated_at']) {
    if (!isStr(doc[field])) problems.push(`${field}: missing or empty`)
  }

  const generator = doc.generator
  if (!generator || typeof generator !== 'object' || !isStr(generator.name)) {
    problems.push('generator: must be an object with a name')
  } else if (!isStr(generator.engine_version)) {
    problems.push('generator.engine_version: missing')
  }

  const evidenceIds = {}
  const request = doc.request
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    problems.push('request: must be an object')
  } else {
    if (!isStr(request.question, 10)) {
      problems.push('request.question: must be at least 10 characters')
    }
    if (!DOMAINS.includes(request.domain)) {
      problems.push(`request.domain: must be one of ${DOMAINS.join(', ')}`)
    }
    const horizon = request.horizon
    if (
      !horizon ||
      typeof horizon !== 'object' ||
      !Number.isInteger(horizon.months) ||
      horizon.months < 1 ||
      horizon.months > 120
    ) {
      problems.push('request.horizon.months: must be an integer between 1 and 120')
    } else if (!isStr(horizon.label)) {
      problems.push('request.horizon.label: missing')
    }
    const evidence = request.evidence ?? []
    if (!Array.isArray(evidence)) {
      problems.push('request.evidence: must be a list')
    } else {
      evidence.forEach((item, i) => {
        validateEvidenceItem(item, i, problems)
        if (item && typeof item === 'object' && isStr(item.id)) {
          const eid = String(item.id)
          if (eid in evidenceIds) {
            problems.push(`request.evidence[${i}].id: duplicate id '${eid}'`)
          }
          evidenceIds[eid] = String(item.kind ?? '')
        }
      })
    }
  }

  if (!isStr(doc.disclaimer, 10)) problems.push('disclaimer: missing or too short')

  const dataStatus = doc.data_status
  if (!dataStatus || typeof dataStatus !== 'object' || Array.isArray(dataStatus)) {
    problems.push('data_status: must be an object')
  } else {
    if (typeof dataStatus.live_market_data_checked !== 'boolean') {
      problems.push('data_status.live_market_data_checked: must be a boolean')
    }
    if (!isStr(dataStatus.message, 5)) {
      problems.push('data_status.message: must describe what was and was not checked')
    }
    if (!Array.isArray(dataStatus.sources ?? [])) {
      problems.push('data_status.sources: must be a list')
    }
  }

  const baseline = doc.baseline
  if (!baseline || typeof baseline !== 'object' || Array.isArray(baseline)) {
    problems.push('baseline: missing scenario object')
  } else {
    validateScenarioNodeInternal(baseline, 'baseline', problems, 0, evidenceIds)
    if (baseline.parent_id != null) {
      problems.push('baseline.parent_id: must be null for the baseline scenario')
    }
  }

  const alternatives = doc.alternatives
  if (!Array.isArray(alternatives) || alternatives.length !== 3) {
    problems.push(
      `alternatives: exactly 3 alternative scenarios are required ` +
        `(found ${Array.isArray(alternatives) ? alternatives.length : 'none'})`
    )
  } else {
    const seenTitles = {}
    const seenTriggerSets = {}
    alternatives.forEach((alt, i) => {
      const path = `alternatives[${i}]`
      validateScenarioNodeInternal(alt, path, problems, 0, evidenceIds)
      if (alt && typeof alt === 'object') {
        if (alt.parent_id != null) {
          problems.push(`${path}.parent_id: must be null for top-level alternatives`)
        }
        const titleKey = String(alt.title ?? '').trim().toLowerCase()
        if (titleKey in seenTitles) {
          problems.push(
            `${path}.title: duplicates ${seenTitles[titleKey]} ` +
              '(alternatives must be meaningfully different)'
          )
        } else {
          seenTitles[titleKey] = `${path}.title`
        }
        const triggerKey = (alt.triggers ?? [])
          .filter((t) => t && typeof t === 'object')
          .map((t) => String(t.event ?? '').trim().toLowerCase())
          .sort()
          .join('||')
        if (triggerKey && triggerKey in seenTriggerSets) {
          problems.push(
            `${path}.triggers: identical trigger set to ` +
              `${seenTriggerSets[triggerKey]} (branches must be ` +
              'distinguished by different triggers)'
          )
        } else if (triggerKey) {
          seenTriggerSets[triggerKey] = `${path}.triggers`
        }
      }
    })
  }

  validateComparisonInternal(doc.comparison, problems)

  const uncertainties = doc.uncertainties
  if (!Array.isArray(uncertainties) || !uncertainties.length) {
    problems.push('uncertainties: at least one uncertainty is required')
  } else {
    uncertainties.forEach((item, i) => {
      const path = `uncertainties[${i}]`
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        problems.push(`${path}: must be an object`)
        return
      }
      if (!isStr(item.id)) problems.push(`${path}.id: missing`)
      if (!isStr(item.statement, 5)) problems.push(`${path}.statement: must be at least 5 characters`)
      if (!IMPACT_LEVELS.includes(item.impact)) {
        problems.push(`${path}.impact: must be one of ${IMPACT_LEVELS.join(', ')}`)
      }
      if (!isStr(item.missing_evidence, 1)) {
        problems.push(`${path}.missing_evidence: describe what evidence is missing`)
      }
    })
  }

  if (!isStrList(doc.missing_information)) {
    problems.push('missing_information: must be a non-empty list of strings')
  }
  if (!isStrList(doc.limitations)) {
    problems.push('limitations: must be a non-empty list of strings')
  }

  const ledger = doc.evidence_ledger
  if (!Array.isArray(ledger)) {
    problems.push('evidence_ledger: must be a list')
  } else {
    ledger.forEach((item, i) => {
      const path = `evidence_ledger[${i}]`
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        problems.push(`${path}: must be an object`)
        return
      }
      if (!PROVENANCE_KINDS.includes(item.kind)) {
        problems.push(`${path}.kind: must be one of ${PROVENANCE_KINDS.join(', ')}`)
      }
      if (!isStr(item.text, 3)) problems.push(`${path}.text: missing`)
      if (item.kind === 'sourced_fact' && !(isStr(item.source_uri) || isStr(item.evidence_ref))) {
        problems.push(
          `${path}: 'sourced_fact' entries require source_uri or ` +
            'evidence_ref (fabricated provenance is not allowed)'
        )
      }
    })
  }

  return problems
}

/* ------------------------------------------------------------------ */
/* deterministic normalization (mirrors engine.py)                      */
/* ------------------------------------------------------------------ */

export function sanitizeProvenance(value) {
  const fixClaim = (claim) => {
    if (!claim || typeof claim !== 'object') return
    if (claim.kind !== 'sourced_fact') return
    const hasUri = String(claim.source_uri ?? '').trim()
    const hasRef = String(claim.evidence_ref ?? '').trim()
    if (!hasUri && !hasRef) claim.kind = 'ai_assumption'
  }
  const walk = (node) => {
    if (Array.isArray(node)) {
      node.forEach(walk)
    } else if (node && typeof node === 'object') {
      for (const item of node.assumptions ?? []) fixClaim(item)
      if (node.kind === 'sourced_fact' && 'text' in node) fixClaim(node)
      for (const child of node.children ?? []) walk(child)
    }
  }
  walk(value)
  return value
}

export function normalizeNode(node, expectedId, parentId) {
  const out = { ...node }
  out.id = expectedId
  out.parent_id = parentId
  out.label ??= expectedId
  out.title ??= expectedId
  out.narrative ??= ''
  const stance =
    out.stance && typeof out.stance === 'object'
      ? { ...out.stance }
      : {
          qualitative: 'plausible',
          note: 'Qualitative assessment only; not a probability estimate.'
        }
  stance.qualitative ??= 'plausible'
  stance.note ??= 'Qualitative assessment only; not a probability estimate.'
  out.stance = stance
  out.assumptions = (out.assumptions ?? []).map((item, i) => {
    if (!item || typeof item !== 'object') return item
    return {
      ...item,
      id: item.id ?? `${expectedId}-a${i + 1}`,
      kind: item.kind ?? 'ai_assumption',
      confidence: item.confidence ?? 'medium',
      evidence_ref: item.evidence_ref ?? null,
      source_uri: item.source_uri ?? null
    }
  })
  out.triggers = (out.triggers ?? []).map((item, i) => {
    if (!item || typeof item !== 'object') return item
    return { ...item, id: item.id ?? `${expectedId}-t${i + 1}` }
  })
  out.children = []
  out.child_comparison = null
  return out
}

export function normalizeComparison(comparison, scenarioIds) {
  const out = { ...comparison }
  out.summary ??= ''
  out.key_differences ??= []
  out.what_would_change_the_outlook ??= []
  const altIds = scenarioIds.filter((sid) => sid !== 'baseline')
  const dimensions = []
  for (const dim of out.dimensions ?? []) {
    if (!dim || typeof dim !== 'object') continue
    const alternatives = dim.alternatives && typeof dim.alternatives === 'object' ? dim.alternatives : {}
    const fixed = {}
    for (const sid of altIds) {
      if (sid in alternatives) fixed[sid] = String(alternatives[sid] ?? '')
    }
    if (Object.keys(fixed).length === altIds.length) {
      dimensions.push({ ...dim, alternatives: fixed })
    } else {
      dimensions.push(dim)
    }
  }
  out.dimensions = dimensions
  return out
}

export function findScenarioNode(report, scenarioId) {
  if (!report) return null
  const stack = [report.baseline, ...(report.alternatives ?? [])]
  while (stack.length) {
    const node = stack.pop()
    if (!node || typeof node !== 'object') continue
    if (node.id === scenarioId) return node
    stack.push(...(node.children ?? []))
  }
  return null
}

export function findScenarioWithDepth(report, scenarioId) {
  const stack = [[report.baseline, 0], ...(report.alternatives ?? []).map((a) => [a, 0])]
  while (stack.length) {
    const [node, depth] = stack.pop()
    if (!node || typeof node !== 'object') continue
    if (node.id === scenarioId) return { node, depth }
    for (const child of node.children ?? []) stack.push([child, depth + 1])
  }
  return { node: null, depth: -1 }
}
