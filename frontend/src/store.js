/**
 * DESNWORLD frontend state store (dependency-free reactive store).
 *
 * Users can run the entire scenario pipeline inside the website:
 *  - 'demo'   — deterministic offline demo engine (no credentials);
 *  - 'browser'— the user's own AI endpoint, called directly from their
 *               browser with a key the user supplies at runtime (never
 *               embedded in this codebase);
 *  - 'api'    — a connected DESNWORLD API server (local dev server or a
 *               deployed secure backend).
 * The GitHub Actions workflow remains the batch path; its report artifacts
 * can be imported here.
 */
import { reactive, computed } from 'vue'
import { loadSampleReport, fetchHealth, generateReport, expandBranch } from './lib/api.js'
import { validateImportedReport, findScenarioNode } from './lib/report.js'
import { generate, expandBranch as expandInBrowser } from './engine/pipeline.js'
import { MockScenarioProvider } from './engine/mock.js'
import { BrowserLLMProvider } from './engine/providers.js'
import { STAGES } from './engine/pipeline.js'

const API_BASE_KEY = 'desnworld.apiBase'
const HISTORY_KEY = 'desnworld.history'
const BROWSER_SETTINGS_KEY = 'desnworld.browser'
const API_KEY_STORAGE = 'desnworld.apiKey'
const MAX_HISTORY = 10

function loadJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function saveJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* quota exceeded — history persistence is best-effort */
  }
}

const browserSaved = loadJSON(BROWSER_SETTINGS_KEY, {})

export const store = reactive({
  // 'empty' | 'loading' | 'error' | 'completed'
  status: 'empty',
  error: null,
  loadingMessage: '',
  stageProgress: [],
  report: null,
  selectedScenarioId: null,
  mode: 'overview', // 'overview' | 'explore' | 'compare' | 'report'

  run: {
    kind: browserSaved.kind || 'demo', // 'demo' | 'browser' | 'api'
    browser: {
      baseUrl: browserSaved.baseUrl || 'https://api.openai.com/v1',
      model: browserSaved.model || 'gpt-4o-mini',
      rememberKey: Boolean(browserSaved.rememberKey),
      apiKey: browserSaved.rememberKey ? localStorage.getItem(API_KEY_STORAGE) || '' : ''
    },
    apiBase: localStorage.getItem(API_BASE_KEY) || '',
    apiHealth: null
  },

  history: loadJSON(HISTORY_KEY, []),
  busyExpanding: null,
  _loadingTimer: null
})

export const selectedScenario = computed(() => {
  if (!store.report || !store.selectedScenarioId) return null
  return findScenarioNode(store.report, store.selectedScenarioId)
})

/* ------------------------------------------------------------------ */
/* run settings                                                        */
/* ------------------------------------------------------------------ */

export function configureRun(patch = {}) {
  if (patch.kind) store.run.kind = patch.kind
  if (patch.browser) {
    const b = { ...store.run.browser, ...patch.browser }
    if (typeof patch.browser.apiKey === 'string') b.apiKey = patch.browser.apiKey.trim()
    b.baseUrl = (b.baseUrl || '').trim().replace(/\/+$/, '')
    store.run.browser = b
    saveJSON(BROWSER_SETTINGS_KEY, {
      kind: store.run.kind,
      baseUrl: b.baseUrl,
      model: b.model,
      rememberKey: b.rememberKey
    })
    try {
      if (b.rememberKey && b.apiKey) localStorage.setItem(API_KEY_STORAGE, b.apiKey)
      else localStorage.removeItem(API_KEY_STORAGE)
    } catch {
      /* ignore */
    }
  }
  if (patch.apiBase !== undefined) {
    store.run.apiBase = (patch.apiBase || '').trim().replace(/\/+$/, '')
    if (store.run.apiBase) localStorage.setItem(API_BASE_KEY, store.run.apiBase)
    else localStorage.removeItem(API_BASE_KEY)
    store.run.apiHealth = null
  }
}

export async function checkApiHealth() {
  try {
    store.run.apiHealth = await fetchHealth(store.run.apiBase)
  } catch (err) {
    store.run.apiHealth = { status: 'unreachable', message: String(err.message || err) }
  }
  return store.run.apiHealth
}

/** Test the user's browser-LLM settings with a minimal request. */
export async function testBrowserConnection() {
  const { apiKey, baseUrl, model } = store.run.browser
  try {
    const provider = new BrowserLLMProvider({ apiKey, baseUrl, model, timeoutMs: 20000 })
    await provider.chatJSON([
      { role: 'user', content: '# stage: baseline\n\nReply with {"ok": true} as a JSON object.' }
    ])
    return { ok: true, message: `Connected to ${baseUrl} with model ${model}.` }
  } catch (err) {
    return { ok: false, message: err.message || String(err), hint: err.hint || '' }
  }
}

/* ------------------------------------------------------------------ */
/* loading + history helpers                                           */
/* ------------------------------------------------------------------ */

function initialStageProgress(extraLabel) {
  return STAGES.map(([stage, label]) => ({ stage, label, state: 'pending' })).concat(
    extraLabel ? [{ stage: 'finalize', label: extraLabel, state: 'pending' }] : []
  )
}

function startLoading(stageProgress, firstMessage) {
  store.status = 'loading'
  store.error = null
  store.stageProgress = stageProgress
  store.loadingMessage = firstMessage
  let i = 0
  store._loadingTimer = setInterval(() => {
    i = Math.min(i + 1, stageProgress.length - 1)
    store.loadingMessage = stageProgress[i].label
  }, 4000)
}

function stopLoading() {
  if (store._loadingTimer) clearInterval(store._loadingTimer)
  store._loadingTimer = null
}

function onStageEvent({ stage, state }) {
  const entry = store.stageProgress.find((s) => s.stage === stage)
  if (entry) entry.state = state
  if (state === 'active') store.loadingMessage = entry?.label || store.loadingMessage
  if (state === 'repairing') store.loadingMessage = `${entry?.label || stage} — repairing model output…`
}

function pushHistory(report) {
  const entry = {
    id: report.report_id,
    savedAt: new Date().toISOString(),
    question: report.request?.question ?? '',
    domain: report.request?.domain ?? '',
    mock: Boolean(report.generator?.mock),
    report
  }
  const history = [entry, ...store.history.filter((h) => h.id !== entry.id)].slice(0, MAX_HISTORY)
  store.history = history
  saveJSON(HISTORY_KEY, history)
}

function applyReport(report, { toHistory = true } = {}) {
  store.report = report
  store.status = 'completed'
  store.selectedScenarioId = report.baseline?.id || 'baseline'
  store.mode = 'overview'
  store.error = null
  if (toHistory) pushHistory(report)
}

/* ------------------------------------------------------------------ */
/* actions                                                             */
/* ------------------------------------------------------------------ */

function makeProvider() {
  if (store.run.kind === 'demo') return new MockScenarioProvider()
  if (store.run.kind === 'browser') {
    const { apiKey, baseUrl, model } = store.run.browser
    return new BrowserLLMProvider({ apiKey, baseUrl, model })
  }
  return null // api mode runs the pipeline server-side
}

function requestForMode(request) {
  // api mode expects horizon_months; browser/demo expect horizonMonths
  if (store.run.kind === 'api') {
    return {
      question: request.question,
      domain: request.domain,
      horizon_months: request.horizonMonths ?? request.horizon_months,
      evidence: (request.evidence ?? []).map((e) => ({
        text: e.text,
        source_uri: e.source_uri || undefined,
        kind: e.kind || (e.source_uri ? 'sourced_fact' : 'user_supplied_fact')
      }))
    }
  }
  return request
}

export async function runGenerate(request) {
  startLoading(initialStageProgress('Finalizing the report'), STAGES[0][1])
  try {
    let report
    if (store.run.kind === 'api') {
      if (!store.run.apiBase && store.run.apiHealth?.status !== 'ok') {
        // same-origin attempt
        store.run.apiHealth = await fetchHealth('').catch(() => null)
      }
      const response = await generateReport(store.run.apiBase, requestForMode(request))
      report = response.report
    } else {
      const provider = makeProvider()
      report = await generate(requestForMode(request), provider, { onStage: onStageEvent })
    }
    const check = validateImportedReport(report)
    if (!check.valid) throw new Error(check.problems.join('; '))
    applyReport(report)
  } catch (err) {
    store.status = 'error'
    store.error = {
      message: err.message || String(err),
      hint:
        err.hint ||
        (err.name === 'MissingCredentialsError'
          ? 'Open Run settings and add your API key, or switch to the Demo engine.'
          : 'Check your run settings and try again.'),
      problems: err.problems || []
    }
  } finally {
    stopLoading()
  }
}

export async function runExpand(scenarioId) {
  if (!store.report) return
  store.busyExpanding = scenarioId
  store.stageProgress = [
    { stage: `sub_branch:${scenarioId}`, label: `Expanding ${scenarioId} into 3 sub-branches…`, state: 'active' }
  ]
  store.status = 'loading'
  store.loadingMessage = `Expanding ${scenarioId} into 3 sub-branches…`
  try {
    let report
    if (store.run.kind === 'api') {
      const response = await expandBranch(store.run.apiBase, store.report, scenarioId)
      report = response.report
    } else {
      const provider = makeProvider()
      report = await expandInBrowser(store.report, scenarioId, provider, { onStage: onStageEvent })
    }
    const check = validateImportedReport(report)
    if (!check.valid) throw new Error(check.problems.join('; '))
    applyReport(report)
    store.selectedScenarioId = scenarioId
    store.mode = 'explore'
  } catch (err) {
    store.status = 'completed'
    store.error = {
      message: `Branch expansion failed: ${err.message || err}`,
      hint: err.hint || 'Try again, or expand a different branch.',
      problems: err.problems || []
    }
  } finally {
    store.busyExpanding = null
    stopLoading()
  }
}

export function loadSample() {
  startLoading(initialStageProgress(), 'Loading the bundled demo report…')
  loadSampleReport()
    .then((report) => {
      const check = validateImportedReport(report)
      if (!check.valid) throw new Error(check.problems.join('; '))
      applyReport(report, { toHistory: false })
    })
    .catch((err) => {
      store.status = 'error'
      store.error = { message: `Could not load the demo report: ${err.message || err}` }
    })
    .finally(stopLoading)
}

export function loadHistoryReport(id) {
  const entry = store.history.find((h) => h.id === id)
  if (!entry) return
  applyReport(entry.report, { toHistory: false })
}

export function deleteHistory(id) {
  const history = store.history.filter((h) => h.id !== id)
  store.history = history
  saveJSON(HISTORY_KEY, history)
}

export function selectScenario(id) {
  store.selectedScenarioId = id
  store.mode = 'explore'
}

export function setMode(mode) {
  store.mode = mode
}

export function importReportObject(report) {
  const check = validateImportedReport(report)
  if (!check.valid) {
    store.status = 'error'
    store.error = {
      message: 'The imported file is not a valid DESNWORLD scenario report.',
      hint: check.problems.slice(0, 6).join(' · ')
    }
    return false
  }
  applyReport(report, { toHistory: false })
  return true
}

export function dismissError() {
  store.error = null
  if (!store.report) store.status = 'empty'
  else store.status = 'completed'
}

export function resetAll() {
  stopLoading()
  store.status = 'empty'
  store.error = null
  store.report = null
  store.selectedScenarioId = null
  store.mode = 'overview'
}
