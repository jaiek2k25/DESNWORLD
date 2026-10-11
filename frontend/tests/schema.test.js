import { describe, it, expect } from 'vitest'
import {
  SCHEMA_VERSION,
  isCompatibleVersion,
  validateReport,
  sanitizeProvenance,
  findScenarioNode
} from '../src/engine/schema.js'
import { generate } from '../src/engine/pipeline.js'
import { MockScenarioProvider } from '../src/engine/mock.js'

const Q = 'How might AI regulation affect semiconductor stocks over the next year?'

async function makeReport() {
  return generate(
    { question: Q, domain: 'stock_market_education', horizonMonths: 12, evidence: [] },
    new MockScenarioProvider()
  )
}

describe('schema versioning', () => {
  it('accepts the current version', () => {
    expect(isCompatibleVersion(SCHEMA_VERSION)).toBe(true)
  })
  it('accepts older minors', () => {
    expect(isCompatibleVersion('1.0.0')).toBe(true)
  })
  it('rejects newer minors and other majors', () => {
    expect(isCompatibleVersion('1.99.0')).toBe(false)
    expect(isCompatibleVersion('2.0.0')).toBe(false)
    expect(isCompatibleVersion('banana')).toBe(false)
  })
})

describe('validateReport', () => {
  it('accepts an engine-generated report', async () => {
    expect(validateReport(await makeReport())).toEqual([])
  })

  it('rejects non-objects', () => {
    expect(validateReport(['nope'])).toEqual(['report: must be a JSON object'])
  })

  it.each([0, 1, 2, 4])('rejects %s alternatives', async (count) => {
    const doc = await makeReport()
    const alts = doc.alternatives.slice(0, count)
    if (count === 4) alts.push(structuredClone(alts[alts.length - 1]))
    doc.alternatives = alts
    expect(validateReport(doc).some((p) => p.includes('exactly 3 alternative'))).toBe(true)
  })

  it('rejects duplicate alternative titles', async () => {
    const doc = await makeReport()
    doc.alternatives[1].title = doc.alternatives[0].title
    expect(validateReport(doc).some((p) => p.includes('meaningfully different'))).toBe(true)
  })

  it('rejects identical trigger sets', async () => {
    const doc = await makeReport()
    doc.alternatives[1].triggers = structuredClone(doc.alternatives[0].triggers)
    doc.alternatives[1].triggers[0].id = 'tX'
    expect(validateReport(doc).some((p) => p.includes('identical trigger set'))).toBe(true)
  })

  it('rejects unbacked sourced facts (fabricated provenance)', async () => {
    const doc = await makeReport()
    doc.baseline.assumptions[0] = {
      id: 'a1', text: 'An unbacked source claim.', kind: 'sourced_fact', confidence: 'medium'
    }
    expect(validateReport(doc).some((p) => p.includes('fabricated provenance'))).toBe(true)
  })

  it('rejects incompatible schema versions', async () => {
    const doc = await makeReport()
    doc.schema_version = '2.0.0'
    expect(validateReport(doc).some((p) => p.includes('schema_version'))).toBe(true)
  })

  it('rejects trees that are too deep', async () => {
    const doc = await makeReport()
    const build = (parentId, depth) => {
      const nodes = [1, 2, 3].map((i) => ({
        id: `${parentId}.c${i}`,
        label: `Sub ${i}`,
        title: `Title at ${parentId} ${i}`,
        narrative: 'A child narrative here.',
        stance: { qualitative: 'plausible', note: 'Qualitative only; not a probability estimate.' },
        assumptions: [{ id: 'x', text: 'An assumption here.', kind: 'ai_assumption', confidence: 'medium' }],
        triggers: [{ id: 'y', event: 'A trigger event', description: 'A description here.' }],
        possible_consequences: ['Something.'],
        indicators_to_watch: ['Indicator.'],
        parent_id: parentId,
        children: [],
        child_comparison: null
      }))
      if (depth > 0) {
        for (const node of nodes) node.children = build(node.id, depth - 1)
      }
      return nodes
    }
    doc.alternatives[0].children = build('alt-1', 2)
    expect(validateReport(doc).some((p) => p.includes('tree depth exceeds'))).toBe(true)
  })
})

describe('sanitizeProvenance', () => {
  it('downgrades unbacked sourced facts to ai assumptions', () => {
    const node = {
      assumptions: [
        { id: 'a1', text: 'claim', kind: 'sourced_fact' },
        { id: 'a2', text: 'claim', kind: 'sourced_fact', source_uri: 'https://x.test' },
        { id: 'a3', text: 'claim', kind: 'sourced_fact', evidence_ref: 'e1' }
      ]
    }
    sanitizeProvenance(node)
    expect(node.assumptions.map((a) => a.kind)).toEqual(['ai_assumption', 'sourced_fact', 'sourced_fact'])
  })
})

describe('findScenarioNode', () => {
  it('finds nodes in the tree', async () => {
    const doc = await makeReport()
    expect(findScenarioNode(doc, 'baseline')).not.toBeNull()
    expect(findScenarioNode(doc, 'alt-2')).not.toBeNull()
    expect(findScenarioNode(doc, 'nope')).toBeNull()
  })
})
