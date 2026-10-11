/**
 * Client-side helpers for DESNWORLD scenario reports.
 *
 * `validateImportedReport` runs the full schema-v1 validation (shared with the
 * in-browser engine) so a user dragging in a random JSON file gets a clear
 * explanation instead of a broken tree view.
 */

import { validateReport } from '../engine/schema.js'

export function validateImportedReport(doc) {
  const problems = validateReport(doc)
  return { valid: problems.length === 0, problems }
}

export function findScenarioNode(report, id) {
  if (!report) return null
  const stack = [report.baseline, ...(report.alternatives || [])]
  while (stack.length) {
    const node = stack.pop()
    if (!node || typeof node !== 'object') continue
    if (node.id === id) return node
    if (Array.isArray(node.children)) stack.push(...node.children)
  }
  return null
}

export function flattenScenarios(report) {
  if (!report) return []
  const out = []
  const walk = (node, depth) => {
    if (!node || typeof node !== 'object') return
    out.push({ node, depth })
    for (const child of node.children || []) walk(child, depth + 1)
  }
  walk(report.baseline, 0)
  for (const alt of report.alternatives || []) walk(alt, 0)
  return out
}

export function downloadReportJSON(report) {
  const text = JSON.stringify(report, null, 2)
  const blob = new Blob([text], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `desnworld-report-${report.report_id || 'export'}.json`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export async function readReportFile(file) {
  const text = await file.text()
  try {
    return JSON.parse(text)
  } catch (err) {
    throw new Error(`The selected file is not valid JSON (${err.message}).`)
  }
}

export const STANCE_LABELS = {
  more_likely: 'More likely',
  plausible: 'Plausible',
  less_likely: 'Less likely',
  unlikely: 'Unlikely'
}

export const KIND_LABELS = {
  sourced_fact: 'Sourced fact',
  user_supplied_fact: 'User-supplied fact',
  ai_assumption: 'AI assumption'
}

export function stanceClass(stance) {
  switch (stance) {
    case 'more_likely':
      return 'stance-more'
    case 'plausible':
      return 'stance-plausible'
    case 'less_likely':
      return 'stance-less'
    case 'unlikely':
      return 'stance-unlikely'
    default:
      return 'stance-plausible'
  }
}
