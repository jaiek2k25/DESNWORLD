<script setup>
import { computed } from 'vue'
import { store, selectScenario, setMode } from '../store.js'
import { stanceClass, STANCE_LABELS, KIND_LABELS } from '../lib/report.js'

const report = computed(() => store.report)
const cards = computed(() => {
  const r = report.value
  if (!r) return []
  return [r.baseline, ...(r.alternatives || [])].filter(Boolean)
})

const palette = {
  baseline: 'var(--gold)',
  'alt-1': 'var(--cyan)',
  'alt-2': 'var(--rose)',
  'alt-3': 'var(--violet)'
}

function cardColor(id) {
  return palette[id] || 'var(--gold)'
}

function headlineTrigger(node) {
  return node.triggers?.[0]?.event || ''
}

function openScenario(id) {
  selectScenario(id)
}

function kindCount(node) {
  const counts = { sourced_fact: 0, user_supplied_fact: 0, ai_assumption: 0 }
  for (const a of node.assumptions || []) {
    if (a.kind in counts) counts[a.kind] += 1
  }
  return counts
}
</script>

<template>
  <div v-if="report" class="overview">
    <div class="panel hero-panel">
      <div class="hero-top">
        <div>
          <div class="eyebrow">Scenario overview</div>
          <h2 class="display hero-question">{{ report.request.question }}</h2>
          <div class="hero-meta">
            <span class="badge">{{ report.request.domain.replace(/_/g, ' ') }}</span>
            <span class="badge">{{ report.request.horizon.label }}</span>
            <span class="badge" :class="report.generator?.mock ? 'stance-less' : 'stance-more'">
              <span class="dot"></span>{{ report.generator?.mock ? 'Demo engine' : report.generator?.model || 'AI model' }}
            </span>
            <span class="faint">{{ report.report_id }}</span>
          </div>
        </div>
      </div>
      <div class="notice" :class="report.data_status?.live_market_data_checked ? 'notice-info' : 'notice-warn'">
        <strong>Data status:</strong> {{ report.data_status?.message }}
      </div>
    </div>

    <div class="cards">
      <button
        v-for="node in cards"
        :key="node.id"
        type="button"
        class="panel card"
        :style="{ '--card-color': cardColor(node.id) }"
        @click="openScenario(node.id)"
      >
        <div class="card-top">
          <span class="card-label">{{ node.label }}</span>
          <span class="badge" :class="stanceClass(node.stance?.qualitative)">
            {{ STANCE_LABELS[node.stance?.qualitative] || node.stance?.qualitative }}
          </span>
        </div>
        <h3 class="display card-title">{{ node.title }}</h3>
        <p class="card-narrative">{{ node.narrative.slice(0, 170) }}{{ node.narrative.length > 170 ? '…' : '' }}</p>
        <div class="card-trigger" v-if="headlineTrigger(node)">
          <span class="card-trigger-label">Trigger</span> {{ headlineTrigger(node) }}
        </div>
        <div class="card-kinds">
          <span class="kind-chip kind-sourced_fact">{{ kindCount(node).sourced_fact }} sourced</span>
          <span class="kind-chip kind-user_supplied_fact">{{ kindCount(node).user_supplied_fact }} user</span>
          <span class="kind-chip kind-ai_assumption">{{ kindCount(node).ai_assumption }} AI</span>
          <span v-if="node.children?.length" class="kind-chip kind-user_supplied_fact">
            {{ node.children.length }} sub-branches
          </span>
        </div>
      </button>
    </div>

    <div class="panel">
      <div class="eyebrow">Comparison at a glance</div>
      <p class="summary">{{ report.comparison?.summary }}</p>
      <div class="glance-grid">
        <section>
          <h4 class="section-title">Key differences</h4>
          <ul class="bullets">
            <li v-for="(item, i) in report.comparison?.key_differences || []" :key="i">{{ item }}</li>
          </ul>
          <button class="btn btn-small" @click="setMode('compare')">Full comparison →</button>
        </section>
        <section>
          <h4 class="section-title">What would change the outlook</h4>
          <ul class="bullets">
            <li v-for="(item, i) in report.comparison?.what_would_change_the_outlook || []" :key="i">{{ item }}</li>
          </ul>
        </section>
        <section>
          <h4 class="section-title">Top uncertainties</h4>
          <ul class="bullets">
            <li v-for="u in (report.uncertainties || []).slice(0, 3)" :key="u.id">
              <strong>{{ u.impact }}</strong> — {{ u.statement }}
            </li>
          </ul>
          <button class="btn btn-small" @click="setMode('report')">Full report →</button>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-panel {
  padding: 22px;
}

.hero-question {
  font-size: 21px;
  line-height: 1.35;
  margin: 6px 0 12px;
  max-width: 900px;
}

.hero-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
}

.card {
  text-align: left;
  cursor: pointer;
  padding: 16px;
  border-top: 3px solid var(--card-color);
  transition: transform 0.14s ease, border-color 0.14s ease;
  color: var(--text-muted);
  font-family: var(--font-ui);
}

.card:hover {
  transform: translateY(-2px);
  border-color: var(--card-color);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-label {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--card-color);
}

.card-title {
  font-size: 16px;
  margin: 0 0 8px;
  color: var(--text);
  line-height: 1.3;
}

.card-narrative {
  font-size: 12.5px;
  line-height: 1.55;
  margin: 0 0 10px;
}

.card-trigger {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.card-trigger-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--card-color);
  margin-right: 6px;
}

.card-kinds {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.summary {
  color: var(--text-muted);
  font-size: 13.8px;
  line-height: 1.65;
  max-width: 900px;
  margin: 8px 0 16px;
}

.glance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
}

.section-title {
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--gold);
  margin: 0 0 10px;
}

.btn-small {
  margin-top: 10px;
}
</style>
