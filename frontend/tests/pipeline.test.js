import { describe, it, expect } from 'vitest'
import { generate, expandBranch, STAGES } from '../src/engine/pipeline.js'
import { MockScenarioProvider, alternativeScenarios, baselineScenario, comparisonBundle, uncertaintyBundle, childScenarios } from '../src/engine/mock.js'
import { ScriptedProvider } from '../src/engine/providers.js'
import {
  MalformedResponseError,
  MissingCredentialsError,
  RateLimitError,
  SchemaValidationError
} from '../src/engine/errors.js'
import { BrowserLLMProvider } from '../src/engine/providers.js'
import { validateReport } from '../src/engine/schema.js'

const REQUEST = {
  question: 'How might AI regulation affect semiconductor stocks over the next year?',
  domain: 'stock_market_education',
  horizonMonths: 12,
  evidence: [{ text: 'Recent commentary focuses on rate sensitivity of valuations.' }]
}

describe('generate (demo engine)', () => {
  it('produces a valid report with baseline + exactly 3 alternatives', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    expect(validateReport(report)).toEqual([])
    expect(report.baseline.id).toBe('baseline')
    expect(report.alternatives.map((a) => a.id)).toEqual(['alt-1', 'alt-2', 'alt-3'])
  })

  it('emits stage progress events', async () => {
    const events = []
    await generate(REQUEST, new MockScenarioProvider(), {
      onStage: (e) => events.push(`${e.stage}:${e.state}`)
    })
    for (const [stage] of STAGES) {
      expect(events).toContain(`${stage}:active`)
      expect(events).toContain(`${stage}:done`)
    }
  })

  it('marks demo reports as mock and states the data status honestly', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    expect(report.generator.mock).toBe(true)
    expect(report.generator.runtime).toBe('browser')
    expect(report.data_status.live_market_data_checked).toBe(false)
    expect(report.limitations.some((l) => l.includes('demo engine'))).toBe(true)
    expect(report.disclaimer).toContain('not price predictions')
  })

  it('tags provenance and backs every sourced fact', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    for (const node of [report.baseline, ...report.alternatives]) {
      for (const a of node.assumptions) {
        expect(['sourced_fact', 'user_supplied_fact', 'ai_assumption']).toContain(a.kind)
        if (a.kind === 'sourced_fact') {
          expect(a.source_uri || a.evidence_ref).toBeTruthy()
        }
      }
    }
  })

  it('keeps alternatives meaningfully different', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    const titles = report.alternatives.map((a) => a.title.toLowerCase())
    expect(new Set(titles).size).toBe(3)
  })

  it('rejects invalid requests before calling the model', async () => {
    await expect(
      generate({ ...REQUEST, question: 'short' }, new MockScenarioProvider())
    ).rejects.toMatchObject({ code: 'input_validation_error' })
  })
})

describe('expandBranch', () => {
  it('adds exactly 3 children with correct parent links', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    const expanded = await expandBranch(report, 'alt-1', new MockScenarioProvider())
    expect(validateReport(expanded)).toEqual([])
    const node = expanded.alternatives.find((a) => a.id === 'alt-1')
    expect(node.children.map((c) => c.id)).toEqual(['alt-1.c1', 'alt-1.c2', 'alt-1.c3'])
    expect(node.children.every((c) => c.parent_id === 'alt-1')).toBe(true)
  })

  it('does not mutate the input report', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    const snapshot = JSON.stringify(report)
    await expandBranch(report, 'alt-2', new MockScenarioProvider())
    expect(JSON.stringify(report)).toBe(snapshot)
  })

  it('supports grandchild expansion and then enforces the depth cap', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    const deeper = await expandBranch(report, 'alt-1', new MockScenarioProvider())
    const withGrandchildren = await expandBranch(deeper, 'alt-1.c1', new MockScenarioProvider())
    const grandchild = withGrandchildren.alternatives[0].children[0]
    expect(grandchild.children.length).toBe(3)
    await expect(
      expandBranch(withGrandchildren, 'alt-1.c1.c1', new MockScenarioProvider())
    ).rejects.toBeInstanceOf(SchemaValidationError)
  })

  it('rejects unknown scenario ids', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    await expect(expandBranch(report, 'alt-99', new MockScenarioProvider())).rejects.toMatchObject({
      code: 'schema_validation_error'
    })
  })
})

describe('repair loop and error handling', () => {
  it('repairs duplicate alternative titles once', async () => {
    const broken = alternativeScenarios('q')
    broken[1].title = broken[0].title
    const fixed = alternativeScenarios('q')
    const provider = new ScriptedProvider([
      { scenario: baselineScenario('q') },
      { alternatives: broken },
      { alternatives: fixed },
      uncertaintyBundle(),
      { comparison: comparisonBundle() }
    ])
    const report = await generate(REQUEST, provider)
    expect(validateReport(report)).toEqual([])
    expect(provider.calls.length).toBe(5)
  })

  it('fails with schema problems when repair also fails', async () => {
    const broken = alternativeScenarios('q')
    broken[1].title = broken[0].title
    const provider = new ScriptedProvider([
      { scenario: baselineScenario('q') },
      { alternatives: broken },
      { alternatives: broken }
    ])
    await expect(generate(REQUEST, provider)).rejects.toBeInstanceOf(SchemaValidationError)
  })

  it('propagates provider errors', async () => {
    const provider = new ScriptedProvider([new RateLimitError('rate limited')])
    await expect(generate(REQUEST, provider)).rejects.toBeInstanceOf(RateLimitError)
  })

  it('propagates malformed responses', async () => {
    const provider = new ScriptedProvider([new MalformedResponseError('not json')])
    await expect(generate(REQUEST, provider)).rejects.toBeInstanceOf(MalformedResponseError)
  })

  it('downgrades unbacked sourced facts instead of failing the stage', async () => {
    const provider = new ScriptedProvider([
      {
        scenario: {
          ...baselineScenario('q'),
          assumptions: [
            { id: 'a1', text: 'A claim with fake sourcing.', kind: 'sourced_fact', confidence: 'medium' }
          ]
        }
      },
      { alternatives: alternativeScenarios('q') },
      uncertaintyBundle(),
      { comparison: comparisonBundle() }
    ])
    const report = await generate(REQUEST, provider)
    expect(report.baseline.assumptions.map((a) => a.kind)).toEqual(['ai_assumption'])
  })

  it('requires credentials for browser LLM generation', () => {
    expect(() => new BrowserLLMProvider({ apiKey: '' })).toThrow(MissingCredentialsError)
  })

  it('repairs malformed sub-branch output during expansion', async () => {
    const report = await generate(REQUEST, new MockScenarioProvider())
    const children = childScenarios('alt-1', 'q')
    const broken = structuredClone(children)
    broken[1].title = broken[0].title
    const provider = new ScriptedProvider([
      { children: broken, child_comparison: null },
      { children, child_comparison: null }
    ])
    const expanded = await expandBranch(report, 'alt-1', provider)
    expect(expanded.alternatives[0].children.length).toBe(3)
    expect(provider.calls.length).toBe(2)
  })
})
