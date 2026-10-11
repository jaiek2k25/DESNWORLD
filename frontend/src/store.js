/**
 * DESNWORLD frontend state store (dependency-free reactive store).
 *
 * The web interface is a static SPA: it never holds credentials. Generation
 * happens through a DESNWORLD API endpoint (same-origin `/api` via the dev
 * proxy, or a user-configured secure backend) — or through the GitHub Actions
 * workflow, whose JSON report artifact is imported here for exploration.
 */
import { reactive, computed } from 'vue'
import { loadSampleReport, fetchHealth, generateReport, expandBranch } from './lib/api.js'
import { validateImportedReport, findScenarioNode } from './lib/report.js'

const API_BASE_KEY = 'desnworld.apiBase'

export const store = reactive({
  // 'empty' | 'loading' | 'error' | 'completed'
  status: 'empty',
  error: null,
  loadingMessage: '',
  report: null,
  selectedScenarioId: null,
  mode: 'explore', // 'explore' | 'compare'
  apiBase: localStorage.getItem(API_BASE_KEY) || '', // '' = same-origin /api
  apiEnabled: false,
  apiHealth: null, // null = unknown, health payload when checked
  busyExpanding: null, // scenario id currently expanding
  _loadingTimer: null
})

export const selectedScenario = computed(() => {
  if (!store.report || !store.selectedScenarioId) return null
  return findScenarioNode(store.report, store.selectedScenarioId)
})

export function setApiBase(value) {
  store.apiBase = (value || '').trim().replace(/\/+$/, '')
  if (store.apiBase) localStorage.setItem(API_BASE_KEY, store.apiBase)
  else localStorage.removeItem(API_BASE_KEY)
  store.apiHealth = null
  store.apiEnabled = false
}

export async function checkHealth() {
  try {
    store.apiHealth = await fetchHealth(store.apiBase)
    store.apiEnabled = store.apiHealth?.status === 'ok'
  } catch (err) {
    store.apiHealth = { status: 'unreachable', message: String(err.message || err) }
    store.apiEnabled = false
  }
  return store.apiHealth
}

/** Probe the same-origin endpoint (dev proxy / same-origin backend). */
export async function probeSameOrigin() {
  try {
    const health = await fetchHealth('')
    if (health?.status === 'ok') {
      store.apiBase = ''
      store.apiHealth = health
      store.apiEnabled = true
      return true
    }
  } catch {
    /* no same-origin API — static mode */
  }
  return false
}

const LOADING_STAGES = [
  'Validating your question…',
  'Collecting evidence and establishing the baseline…',
  'Generating three alternative branches…',
  'Identifying triggers, uncertainties, and missing evidence…',
  'Validating structured output…',
  'Writing the comparison report…'
]

function startLoading() {
  store.status = 'loading'
  store.error = null
  let i = 0
  store.loadingMessage = LOADING_STAGES[0]
  store._loadingTimer = setInterval(() => {
    i = Math.min(i + 1, LOADING_STAGES.length - 1)
    store.loadingMessage = LOADING_STAGES[i]
  }, 2500)
}

function stopLoading() {
  if (store._loadingTimer) clearInterval(store._loadingTimer)
  store._loadingTimer = null
}

function applyReport(report) {
  store.report = report
  store.status = 'completed'
  store.selectedScenarioId = report.baseline?.id || 'baseline'
  store.mode = 'explore'
  store.error = null
}

export function loadDemo() {
  startLoading()
  loadSampleReport()
    .then((report) => {
      const check = validateImportedReport(report)
      if (!check.valid) throw new Error(check.problems.join('; '))
      applyReport(report)
    })
    .catch((err) => {
      store.status = 'error'
      store.error = { message: `Could not load the demo report: ${err.message || err}` }
    })
    .finally(stopLoading)
}

export async function generate(request) {
  if (!store.apiEnabled) {
    store.status = 'error'
    store.error = {
      message: 'No DESNWORLD API endpoint is connected.',
      hint:
        'GitHub Pages is a static host and cannot run the scenario engine. ' +
        'Either connect a DESNWORLD API (local dev server or your deployed secure backend), ' +
        'or run the GitHub Actions workflow and import the report artifact. ' +
        'You can also explore the bundled demo report.'
    }
    return
  }
  startLoading()
  try {
    const { report } = await generateReport(store.apiBase, request)
    const check = validateImportedReport(report)
    if (!check.valid) throw new Error(check.problems.join('; '))
    applyReport(report)
  } catch (err) {
    store.status = 'error'
    store.error = {
      message: `Scenario generation failed: ${err.message || err}`,
      hint: err.hint || 'Check the API endpoint, credentials on the server side, and try again.'
    }
  } finally {
    stopLoading()
  }
}

export async function expand(scenarioId) {
  if (!store.apiEnabled || !store.report) {
    store.status = 'error'
    store.error = {
      message: 'Branch expansion needs a connected DESNWORLD API endpoint.',
      hint: 'Connect a backend, or run the workflow with --expand and import the updated report.'
    }
    return
  }
  store.busyExpanding = scenarioId
  try {
    const { report } = await expandBranch(store.apiBase, store.report, scenarioId)
    const check = validateImportedReport(report)
    if (!check.valid) throw new Error(check.problems.join('; '))
    applyReport(report)
    store.selectedScenarioId = scenarioId
  } catch (err) {
    store.status = 'error'
    store.error = {
      message: `Branch expansion failed: ${err.message || err}`,
      hint: err.hint || 'Try again, or expand a different branch.'
    }
  } finally {
    store.busyExpanding = null
  }
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
  applyReport(report)
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
  store.mode = 'explore'
}
