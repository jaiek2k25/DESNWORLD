<script setup>
import { computed } from 'vue'
import { store, selectScenario } from '../store.js'
import { stanceClass, STANCE_LABELS, KIND_LABELS } from '../lib/report.js'

const report = computed(() => store.report)
const nodes = computed(() => {
  const r = report.value
  if (!r) return []
  return [r.baseline, ...(r.alternatives || [])].filter(Boolean)
})

function allScenariosFlat() {
  const out = []
  const walk = (node, depth) => {
    if (!node) return
    out.push({ node, depth })
    for (const child of node.children || []) walk(child, depth + 1)
  }
  walk(report.value?.baseline, 0)
  for (const alt of report.value?.alternatives || []) walk(alt, 0)
  return out
}

function evidenceById(id) {
  return (report.value?.request?.evidence || []).find((e) => e.id === id) || null
}
</script>

<template>
  <div v-if="report" class="report">
    <section class="panel">
      <div class="eyebrow">Full report</div>
      <h2 class="display report-title">{{ report.request.question }}</h2>
      <div class="meta-row">
        <span class="mono faint">{{ report.report_id }}</span>
        <span class="faint">{{ report.generated_at }}</span>
        <span class="badge" :class="report.generator?.mock ? 'stance-less' : 'stance-more'">
          <span class="dot"></span>
          {{ report.generator?.provider }} · {{ report.generator?.model }}
          <template v-if="report.generator?.runtime"> · {{ report.generator.runtime }}</template>
        </span>
      </div>
      <div class="notice notice-warn">{{ report.disclaimer }}</div>
      <div class="notice" :class="report.data_status?.live_market_data_checked ? 'notice-info' : ''">
        <strong>Data status:</strong> {{ report.data_status?.message }}
        <div v-if="report.data_status?.sources?.length" class="faint">
          Sources referenced from your evidence:
          <span v-for="(s, i) in report.data_status.sources" :key="i"><a :href="s" target="_blank" rel="noopener">{{ s }}</a><span v-if="i < report.data_status.sources.length - 1"> · </span></span>
        </div>
      </div>
    </section>

    <section class="panel">
      <h3 class="section-title">Assumptions across scenarios</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Assumption</th>
              <th>Provenance</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in allScenariosFlat()" :key="row.node.id">
              <tr v-for="(a, i) in row.node.assumptions" :key="row.node.id + a.id + i">
                <td>
                  <button class="linklike scenario-link" @click="selectScenario(row.node.id)">
                    <span :style="{ opacity: row.depth ? 0.7 : 1 }">
                      {{ row.depth ? '↳ ' : '' }}{{ row.node.label }}: {{ row.node.title }}
                    </span>
                  </button>
                </td>
                <td>
                  {{ a.text }}
                  <div v-if="a.evidence_ref && evidenceById(a.evidence_ref)" class="faint">
                    Based on your evidence {{ a.evidence_ref }}: “{{ evidenceById(a.evidence_ref).text.slice(0, 110) }}…”
                  </div>
                  <div v-else-if="a.source_uri" class="faint">
                    Source: <a :href="a.source_uri" target="_blank" rel="noopener">{{ a.source_uri }}</a>
                  </div>
                </td>
                <td><span class="kind-chip" :class="`kind-${a.kind}`">{{ KIND_LABELS[a.kind] || a.kind }}</span></td>
                <td>{{ a.confidence }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h3 class="section-title">Triggers — what selects each branch</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Trigger event</th>
              <th>How it pushes the future</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in allScenariosFlat()" :key="'t' + row.node.id">
              <tr v-for="(t, i) in row.node.triggers" :key="'t' + row.node.id + t.id + i">
                <td>
                  <button class="linklike scenario-link" @click="selectScenario(row.node.id)">
                    {{ row.node.label }}: {{ row.node.title }}
                  </button>
                </td>
                <td><strong>{{ t.event }}</strong></td>
                <td>{{ t.description }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h3 class="section-title">Consequences &amp; indicators</h3>
      <div class="consequence-grid">
        <div v-for="row in allScenariosFlat()" :key="'c' + row.node.id" class="consequence-card">
          <button class="linklike scenario-link" @click="selectScenario(row.node.id)">
            <strong>{{ row.node.label }}: {{ row.node.title }}</strong>
          </button>
          <div class="mini-label">Possible consequences</div>
          <ul class="bullets">
            <li v-for="(c, i) in row.node.possible_consequences" :key="i">{{ c }}</li>
          </ul>
          <div class="mini-label">Indicators to watch</div>
          <ul class="bullets">
            <li v-for="(c, i) in row.node.indicators_to_watch" :key="i">{{ c }}</li>
          </ul>
        </div>
      </div>
    </section>

    <section class="panel">
      <h3 class="section-title">Uncertainties, missing evidence &amp; consequences</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Uncertainty</th>
              <th>Impact</th>
              <th>Missing evidence</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in report.uncertainties || []" :key="u.id">
              <td>{{ u.statement }}</td>
              <td>
                <span
                  class="badge"
                  :class="u.impact === 'high' ? 'stance-unlikely' : u.impact === 'medium' ? 'stance-less' : 'stance-plausible'"
                >{{ u.impact }}</span>
              </td>
              <td>{{ u.missing_evidence }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="two-col">
      <section class="panel">
        <h3 class="section-title">Missing information</h3>
        <ul class="bullets">
          <li v-for="(item, i) in report.missing_information || []" :key="i">{{ item }}</li>
        </ul>
      </section>
      <section class="panel">
        <h3 class="section-title">Limitations of this analysis</h3>
        <ul class="bullets">
          <li v-for="(item, i) in report.limitations || []" :key="i">{{ item }}</li>
        </ul>
      </section>
    </div>

    <section class="panel">
      <h3 class="section-title">Evidence ledger</h3>
      <p class="faint">
        Every claim DESNWORLD works from is registered here. <strong>Sourced facts</strong> carry a
        real URL or point to your evidence; <strong>user-supplied facts</strong> are what you
        provided; <strong>AI assumptions</strong> are model reasoning and nothing more.
      </p>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Provenance</th>
              <th>Content</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, i) in report.evidence_ledger || []" :key="i">
              <td class="mono">{{ item.id }}</td>
              <td><span class="kind-chip" :class="`kind-${item.kind}`">{{ KIND_LABELS[item.kind] || item.kind }}</span></td>
              <td>{{ item.text }}<div v-if="item.note" class="faint">{{ item.note }}</div></td>
              <td>
                <a v-if="item.source_uri" :href="item.source_uri" target="_blank" rel="noopener">{{ item.source_uri }}</a>
                <span v-else class="faint">—</span>
              </td>
            </tr>
            <tr v-if="!(report.evidence_ledger || []).length">
              <td colspan="4" class="faint">No evidence items were supplied for this run.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.report {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.report-title {
  font-size: 20px;
  line-height: 1.35;
  margin: 6px 0 10px;
  max-width: 900px;
}

.meta-row {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.section-title {
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--gold);
  margin: 0 0 12px;
}

.table-scroll {
  overflow-x: auto;
}

.consequence-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 14px;
}

.consequence-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 13px;
  background: var(--overlay-soft);
}

.mini-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  margin: 10px 0 6px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.scenario-link {
  text-align: left;
}

@media (max-width: 860px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}
</style>
