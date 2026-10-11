/**
 * Scenario-request validation for the browser engine.
 * Port of engine/desnworld/input_validation.py (pure, no I/O).
 */
import { InputValidationError } from './errors.js'
import { DOMAINS, PROVENANCE_KINDS } from './schema.js'

export const MIN_QUESTION_LENGTH = 10
export const MIN_HORIZON_MONTHS = 1
export const MAX_HORIZON_MONTHS = 120
export const MAX_EVIDENCE_ITEMS = 20
export const MAX_EVIDENCE_TEXT_LENGTH = 4000
export const MAX_QUESTION_LENGTH = 2000

const DOMAIN_ALIASES = {
  general: 'general',
  stock_market_education: 'stock_market_education',
  'stock market education': 'stock_market_education',
  'stock-market-education': 'stock_market_education',
  stockmarket: 'stock_market_education',
  stock_market: 'stock_market_education',
  business: 'business',
  technology: 'technology',
  tech: 'technology'
}

export function normalizeDomain(raw) {
  if (typeof raw !== 'string') {
    throw new InputValidationError('Domain must be a string.', { problems: ['domain: not a string'] })
  }
  const key = raw.trim().toLowerCase()
  const slug = DOMAIN_ALIASES[key] ?? DOMAIN_ALIASES[key.replace(/ /g, '_')]
  if (!slug) {
    throw new InputValidationError(`Unknown domain '${raw}'.`, {
      problems: [`domain: must be one of ${DOMAINS.join(', ')}`],
      hint: 'Choose General, Stock Market Education, Business, or Technology.'
    })
  }
  return slug
}

export function horizonLabel(months) {
  if (months < 12) return `${months} month${months !== 1 ? 's' : ''}`
  const years = Math.floor(months / 12)
  const remainder = months % 12
  const parts = [`${years} year${years !== 1 ? 's' : ''}`]
  if (remainder) parts.push(`${remainder} month${remainder !== 1 ? 's' : ''}`)
  return parts.join(' ')
}

function validateHttpUrl(value, path, problems) {
  if (value == null || value === '') return null
  if (typeof value !== 'string') {
    problems.push(`${path}: must be a string URL`)
    return null
  }
  let parsed
  try {
    parsed = new URL(value.trim())
  } catch {
    problems.push(`${path}: must be a valid http(s) URL`)
    return null
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.host) {
    problems.push(`${path}: must be a valid http(s) URL`)
    return null
  }
  return value.trim()
}

function normalizeEvidence(rawEvidence, problems) {
  if (rawEvidence == null) return []
  if (!Array.isArray(rawEvidence)) {
    problems.push('evidence: must be a list of evidence items')
    return []
  }
  if (rawEvidence.length > MAX_EVIDENCE_ITEMS) {
    problems.push(
      `evidence: at most ${MAX_EVIDENCE_ITEMS} items are allowed (found ${rawEvidence.length})`
    )
    return []
  }
  const normalized = []
  rawEvidence.forEach((rawItem, index) => {
    const path = `evidence[${index}]`
    const item = typeof rawItem === 'string' ? { text: rawItem } : rawItem
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      problems.push(`${path}: must be an object with a 'text' field`)
      return
    }
    const text = item.text
    if (typeof text !== 'string' || text.trim().length < 3) {
      problems.push(`${path}.text: must be at least 3 characters`)
      return
    }
    if (text.length > MAX_EVIDENCE_TEXT_LENGTH) {
      problems.push(`${path}.text: must be at most ${MAX_EVIDENCE_TEXT_LENGTH} characters`)
      return
    }
    const kind = item.kind ?? 'user_supplied_fact'
    if (!PROVENANCE_KINDS.includes(kind)) {
      problems.push(`${path}.kind: must be one of ${PROVENANCE_KINDS.join(', ')}`)
      return
    }
    const sourceUri = validateHttpUrl(item.source_uri, `${path}.source_uri`, problems)
    if (item.source_uri != null && item.source_uri !== '' && sourceUri === null) {
      return // invalid URL already reported
    }
    if (kind === 'sourced_fact' && !sourceUri) {
      problems.push(
        `${path}: kind 'sourced_fact' requires a source_uri ` +
          '(claims must not carry fabricated provenance)'
      )
      return
    }
    const note = item.note == null ? null : String(item.note).trim()
    normalized.push({
      id: `e${index + 1}`,
      text: text.trim(),
      kind,
      source_uri: sourceUri,
      note: note || null
    })
  })
  return normalized
}

export function validateRequest({ question, domain, horizonMonths, evidence = [] }) {
  const problems = []

  let cleanedQuestion = ''
  if (typeof question !== 'string') {
    problems.push('question: must be a string')
  } else {
    cleanedQuestion = question.replace(/\s+/g, ' ').trim()
    if (cleanedQuestion.length < MIN_QUESTION_LENGTH) {
      problems.push(
        `question: must be at least ${MIN_QUESTION_LENGTH} characters ` +
          '(describe what you want to explore)'
      )
    } else if (cleanedQuestion.length > MAX_QUESTION_LENGTH) {
      problems.push(`question: must be at most ${MAX_QUESTION_LENGTH} characters`)
    }
  }

  let cleanedDomain = null
  try {
    cleanedDomain = normalizeDomain(domain)
  } catch (err) {
    problems.push(...(err.problems?.length ? err.problems : [err.message]))
  }

  let months = null
  let parsedHorizon = horizonMonths
  if (typeof parsedHorizon === 'string' && /^\d+$/.test(parsedHorizon.trim())) {
    parsedHorizon = parseInt(parsedHorizon.trim(), 10)
  }
  if (typeof parsedHorizon === 'boolean') {
    problems.push('horizon_months: must be an integer number of months')
  } else if (Number.isInteger(parsedHorizon)) {
    if (parsedHorizon < MIN_HORIZON_MONTHS || parsedHorizon > MAX_HORIZON_MONTHS) {
      problems.push(
        `horizon_months: must be between ${MIN_HORIZON_MONTHS} and ` +
          `${MAX_HORIZON_MONTHS} (found ${parsedHorizon})`
      )
    } else {
      months = parsedHorizon
    }
  } else {
    problems.push('horizon_months: must be an integer number of months')
  }

  const normalizedEvidence = normalizeEvidence(evidence, problems)

  if (problems.length) {
    throw new InputValidationError(
      `The scenario request is invalid: ${problems.length} problem(s) found.`,
      { problems, hint: 'Fix the highlighted fields and try again.' }
    )
  }

  return {
    question: cleanedQuestion,
    domain: cleanedDomain,
    horizon: { months, label: horizonLabel(months) },
    evidence: normalizedEvidence
  }
}
