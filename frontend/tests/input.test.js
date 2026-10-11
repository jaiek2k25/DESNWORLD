import { describe, it, expect } from 'vitest'
import { validateRequest, normalizeDomain, horizonLabel } from '../src/engine/input.js'
import { InputValidationError } from '../src/engine/errors.js'

const Q = 'A perfectly reasonable question here'

describe('question validation', () => {
  it('normalizes whitespace', () => {
    const req = validateRequest({ question: '   How might\t AI regulation \n affect markets?  ', domain: 'general', horizonMonths: 12 })
    expect(req.question).toBe('How might AI regulation affect markets?')
  })

  it('rejects short questions', () => {
    expect(() => validateRequest({ question: 'Too short', domain: 'general', horizonMonths: 12 }))
      .toThrow(InputValidationError)
  })

  it('rejects non-string questions', () => {
    expect(() => validateRequest({ question: 123, domain: 'general', horizonMonths: 12 }))
      .toThrow(InputValidationError)
  })
})

describe('domain normalization', () => {
  it.each([
    ['general', 'general'],
    ['Stock Market Education', 'stock_market_education'],
    ['stock-market-education', 'stock_market_education'],
    ['tech', 'technology']
  ])('%s -> %s', (raw, expected) => {
    expect(normalizeDomain(raw)).toBe(expected)
  })

  it('rejects unknown domains', () => {
    expect(() => normalizeDomain('underwater basket weaving')).toThrow(InputValidationError)
  })
})

describe('horizon validation', () => {
  it.each([1, 6, 12, 36, 120])('accepts %s months', (months) => {
    const req = validateRequest({ question: Q, domain: 'general', horizonMonths: months })
    expect(req.horizon.months).toBe(months)
  })

  it('accepts numeric strings', () => {
    const req = validateRequest({ question: Q, domain: 'general', horizonMonths: '24' })
    expect(req.horizon.months).toBe(24)
  })

  it.each([0, -3, 121, 1000])('rejects %s months', (months) => {
    expect(() => validateRequest({ question: Q, domain: 'general', horizonMonths: months }))
      .toThrow(InputValidationError)
  })

  it('rejects booleans', () => {
    expect(() => validateRequest({ question: Q, domain: 'general', horizonMonths: true }))
      .toThrow(InputValidationError)
  })

  it('builds labels', () => {
    expect(horizonLabel(1)).toBe('1 month')
    expect(horizonLabel(3)).toBe('3 months')
    expect(horizonLabel(12)).toBe('1 year')
    expect(horizonLabel(18)).toBe('1 year 6 months')
    expect(horizonLabel(24)).toBe('2 years')
  })
})

describe('evidence validation', () => {
  it('accepts string items', () => {
    const req = validateRequest({ question: Q, domain: 'general', horizonMonths: 12, evidence: ['A simple evidence note'] })
    expect(req.evidence[0].kind).toBe('user_supplied_fact')
    expect(req.evidence[0].id).toBe('e1')
  })

  it('requires a source_uri for sourced facts', () => {
    try {
      validateRequest({
        question: Q, domain: 'general', horizonMonths: 12,
        evidence: [{ text: 'A claim that pretends to be sourced.', kind: 'sourced_fact' }]
      })
      throw new Error('should have thrown')
    } catch (err) {
      expect(err).toBeInstanceOf(InputValidationError)
      expect(err.problems.some((p) => p.includes('source_uri'))).toBe(true)
    }
  })

  it('accepts sourced facts with a URL', () => {
    const req = validateRequest({
      question: Q, domain: 'general', horizonMonths: 12,
      evidence: [{ text: 'A properly sourced claim.', kind: 'sourced_fact', source_uri: 'https://example.com/data' }]
    })
    expect(req.evidence[0].source_uri).toBe('https://example.com/data')
  })

  it('rejects invalid URLs', () => {
    expect(() => validateRequest({
      question: Q, domain: 'general', horizonMonths: 12,
      evidence: [{ text: 'Claim with a bogus URL.', source_uri: 'not-a-url' }]
    })).toThrow(InputValidationError)
  })

  it('caps evidence items', () => {
    const items = Array.from({ length: 30 }, (_, i) => ({ text: `Evidence item number ${i}` }))
    expect(() => validateRequest({ question: Q, domain: 'general', horizonMonths: 12, evidence: items }))
      .toThrow(InputValidationError)
  })
})
