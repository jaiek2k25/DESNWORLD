// @vitest-environment happy-dom
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import App from '../src/App.vue'
import { store, runGenerate, importReportObject, selectScenario, setMode, configureRun, resetAll } from '../src/store.js'

const REQUEST = {
  question: 'How might AI adoption affect regional bank profits over two years?',
  domain: 'stock_market_education',
  horizonMonths: 24,
  evidence: [{ text: 'A user observation about cost pressure on branches.' }]
}

async function generateDemo() {
  configureRun({ kind: 'demo' })
  await runGenerate(REQUEST)
  await flushPromises()
}

describe('DESNWORLD UI smoke', () => {
  beforeEach(() => {
    resetAll()
  })

  it('renders the empty workspace with composer and run settings', () => {
    const wrapper = mount(App)
    expect(wrapper.text()).toContain('DESNWORLD')
    expect(wrapper.text()).toContain('What future do you want to examine?')
    expect(wrapper.text()).toContain('Run settings')
    expect(wrapper.text()).toContain('Demo engine')
    expect(wrapper.text()).toContain('Your AI model')
    expect(wrapper.text()).toContain('DESNWORLD API')
    expect(wrapper.find('textarea#question').exists()).toBe(true)
    expect(wrapper.find('select#domain').exists()).toBe(true)
  })

  it('runs the full demo pipeline from the store and shows overview results', async () => {
    await generateDemo()
    const wrapper = mount(App)
    await flushPromises()
    expect(store.status).toBe('completed')
    expect(wrapper.text()).toContain('Scenario overview')
    expect(wrapper.text()).toContain(REQUEST.question)
    // baseline + 3 alternatives cards
    expect(wrapper.text()).toContain('Continuation of visible conditions')
    expect(wrapper.text()).toContain('Upside drift beyond trend')
    expect(wrapper.text()).toContain('Downside stress episode')
    expect(wrapper.text()).toContain('Structural regime shift')
    // honesty markers
    expect(wrapper.text()).toContain('Data status:')
    expect(wrapper.text()).toContain('Demo engine')
  })

  it('switches between all result views', async () => {
    await generateDemo()
    const wrapper = mount(App)
    await flushPromises()

    // Scenario tree
    await wrapper.findAll('button.chip').find((b) => b.text() === 'Scenario tree').trigger('click')
    await flushPromises()
    expect(wrapper.find('svg.tree-svg').exists()).toBe(true)

    // Compare
    await wrapper.findAll('button.chip').find((b) => b.text() === 'Compare').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Side-by-side comparison')
    expect(wrapper.text()).toContain('What would change the outlook')

    // Full report
    await wrapper.findAll('button.chip').find((b) => b.text() === 'Full report').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Assumptions across scenarios')
    expect(wrapper.text()).toContain('Triggers — what selects each branch')
    expect(wrapper.text()).toContain('Evidence ledger')
    expect(wrapper.text()).toContain('Limitations of this analysis')
    expect(wrapper.text()).toContain('Uncertainties, missing evidence')
  })

  it('shows scenario details when a branch is selected', async () => {
    await generateDemo()
    selectScenario('alt-2')
    await flushPromises()
    const wrapper = mount(App)
    await flushPromises()
    expect(store.mode).toBe('explore')
    expect(wrapper.text()).toContain('Downside stress episode')
    expect(wrapper.text()).toContain('Assumptions')
    expect(wrapper.text()).toContain('Triggers — what would push toward this branch')
  })

  it('surfaces provider errors in the UI', async () => {
    configureRun({ kind: 'browser', browser: { apiKey: '' } })
    await runGenerate(REQUEST)
    await flushPromises()
    const wrapper = mount(App)
    await flushPromises()
    expect(store.status).toBe('error')
    expect(wrapper.text()).toContain('Something interrupted the exploration')
    expect(wrapper.text()).toContain('AI API key')
  })

  it('rejects invalid imported reports with a clear error', () => {
    const ok = importReportObject({ schema_version: '1.0.0', nonsense: true })
    expect(ok).toBe(false)
    expect(store.status).toBe('error')
    expect(store.error.message).toContain('not a valid DESNWORLD scenario report')
    expect(store.error.hint.length).toBeGreaterThan(0)
  })

  it('shows run history entries after generating', async () => {
    await generateDemo()
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.text()).toContain('Run history')
    expect(wrapper.text()).toContain(REQUEST.question)
  })
})
