/**
 * DESNWORLD API client.
 *
 * Talks to a DESNWORLD endpoint in one of two ways:
 *  - same-origin relative URLs (`/api/...`) — used by the local dev server
 *    proxy and by any same-origin deployment of a secure backend;
 *  - a user-configured base URL — for a separately hosted secure backend.
 *
 * The static GitHub Pages build never embeds tokens or API keys and never
 * hard-codes localhost: if no API answers, the interface stays in static mode
 * (import/explore/demo only) — see README "Deployment architecture and
 * limitations".
 */

function apiUrl(apiBase, path) {
  const base = (apiBase || '').replace(/\/+$/, '')
  return `${base}${path}`
}

async function postJSON(url, body) {
  let response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
  } catch (err) {
    const error = new Error(
      `Cannot reach the DESNWORLD API (${err.message || err}). Is the endpoint running?`
    )
    error.hint =
      'Start the local dev server (python -m desnworld.server) or check your deployed backend URL.'
    throw error
  }
  let payload = null
  try {
    payload = await response.json()
  } catch {
    throw new Error(`DESNWORLD API returned a non-JSON response (HTTP ${response.status}).`)
  }
  if (!response.ok) {
    const error = new Error(payload?.message || `Request failed with HTTP ${response.status}.`)
    error.hint = payload?.hint || ''
    error.problems = payload?.problems || []
    error.code = payload?.error || 'request_failed'
    throw error
  }
  return payload
}

export async function fetchHealth(apiBase) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 2500)
  try {
    const response = await fetch(apiUrl(apiBase, '/api/health'), { signal: controller.signal })
    if (!response.ok) throw new Error(`Health check failed (HTTP ${response.status}).`)
    return await response.json()
  } finally {
    clearTimeout(timer)
  }
}

export async function generateReport(apiBase, request) {
  return postJSON(apiUrl(apiBase, '/api/generate'), request)
}

export async function expandBranch(apiBase, report, scenarioId) {
  return postJSON(apiUrl(apiBase, '/api/expand'), { report, scenario_id: scenarioId })
}

export async function loadSampleReport() {
  const response = await fetch('./sample-report.json')
  if (!response.ok) {
    throw new Error(`Sample report not found (HTTP ${response.status}).`)
  }
  return response.json()
}
