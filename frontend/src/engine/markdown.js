/**
 * Markdown rendering of a DESNWORLD report (client-side port of
 * engine/desnworld/report.py::report_to_markdown) for export.
 */

function escapeCell(value) {
  return String(value ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ')
}

export function reportToMarkdown(report) {
  const request = report.request ?? {}
  const horizon = request.horizon ?? {}
  const baseline = report.baseline ?? {}
  const lines = [
    `# DESNWORLD scenario report — ${report.report_id ?? ''}`,
    '',
    `*Generated: ${report.generated_at ?? ''} · ` +
      `engine ${report.generator?.engine_version ?? '?'} · ` +
      `provider \`${report.generator?.provider ?? '?'}\` ` +
      `model \`${report.generator?.model ?? '?'}\`${report.generator?.mock ? ' · MOCK' : ''}*`,
    '',
    `**Question:** ${request.question ?? ''}`,
    `**Domain:** ${request.domain ?? ''} · **Horizon:** ${horizon.label ?? ''}`,
    '',
    `> ${report.disclaimer ?? ''}`,
    '',
    `**Data status:** ${report.data_status?.message ?? ''}`,
    '',
    '## Baseline',
    `**${baseline.title ?? ''}** (${baseline.stance?.qualitative ?? ''})`,
    '',
    baseline.narrative ?? '',
    '',
    '## Alternatives'
  ]
  for (const alt of report.alternatives ?? []) {
    lines.push(
      `### ${alt.label ?? ''}: ${alt.title ?? ''} (${alt.stance?.qualitative ?? ''})`,
      '',
      alt.narrative ?? '',
      '',
      '**Triggers:**'
    )
    for (const trig of alt.triggers ?? []) {
      lines.push(`- *${trig.event}* — ${trig.description}`)
    }
    lines.push('')
  }

  const comparison = report.comparison ?? {}
  lines.push('## Comparison', '', comparison.summary ?? '', '', '**Key differences:**')
  for (const item of comparison.key_differences ?? []) lines.push(`- ${item}`)
  lines.push('', '**What would change the outlook:**')
  for (const item of comparison.what_would_change_the_outlook ?? []) lines.push(`- ${item}`)

  lines.push('', '## Uncertainties')
  for (const u of report.uncertainties ?? []) {
    lines.push(`- (${u.impact}) ${u.statement} — missing evidence: ${u.missing_evidence}`)
  }

  lines.push('', '## Missing information')
  for (const item of report.missing_information ?? []) lines.push(`- ${item}`)

  lines.push('', '## Limitations')
  for (const item of report.limitations ?? []) lines.push(`- ${item}`)

  lines.push('', '## Evidence ledger')
  for (const item of report.evidence_ledger ?? []) {
    const uri = item.source_uri ? ` — ${item.source_uri}` : ''
    lines.push(`- \`[${item.kind}]\` ${item.text}${uri}`)
  }

  // comparison dimensions table
  if (Array.isArray(comparison.dimensions) && comparison.dimensions.length) {
    const altIds = (report.alternatives ?? []).map((a) => a.id)
    lines.push(
      '',
      '## Comparison dimensions',
      '',
      `| Dimension | Baseline | ${altIds.map((id) => escapeCell(id)).join(' | ')} |`,
      `| --- | --- | ${altIds.map(() => '---').join(' | ')} |`
    )
    for (const dim of comparison.dimensions) {
      const cells = altIds.map((id) => escapeCell(dim.alternatives?.[id] ?? '—'))
      lines.push(`| ${escapeCell(dim.dimension)} | ${escapeCell(dim.baseline)} | ${cells.join(' | ')} |`)
    }
  }

  lines.push('')
  return lines.join('\n')
}
