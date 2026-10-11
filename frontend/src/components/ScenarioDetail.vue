<script setup>
import { computed } from 'vue'
import { store, selectedScenario, runExpand } from '../store.js'
import { stanceClass, STANCE_LABELS, KIND_LABELS } from '../lib/report.js'

const scenario = selectedScenario

const canExpand = computed(() => {
  const node = scenario.value
  if (!node || !store.apiEnabled) return false
  if (node.children && node.children.length) return false
  // engine supports two expansion levels below the report root
  const depth = String(node.id).split('.').length - 1
  return depth < 2
})

const expanding = computed(() => store.busyExpanding === scenario.value?.id)

function evidenceById(id) {
  const items = store.report?.request?.evidence || []
  return items.find((e) => e.id === id) || null
}
</script>

<template>
  <div v-if="scenario" class="panel detail">
    <div class="eyebrow">
      {{ scenario.id === 'baseline' ? 'Baseline scenario' : `Branch · ${scenario.id}` }}
    </div>
    <h2 class="display detail-title">{{ scenario.title }}</h2>

    <div class="stance-row">
      <span class="badge" :class="stanceClass(scenario.stance?.qualitative)">
        <span class="dot"></span>{{ STANCE_LABELS[scenario.stance?.qualitative] || 'Unknown' }}
      </span>
      <span class="faint">{{ scenario.stance?.note }}</span>
    </div>

    <p class="narrative">{{ scenario.narrative }}</p>

    <div v-if="scenario.parent_id" class="notice">
      Sub-branch of <code>{{ scenario.parent_id }}</code>
    </div>

    <section class="detail-section">
      <h3 class="section-title">Assumptions</h3>
      <div v-for="a in scenario.assumptions" :key="a.id" class="claim">
        <div class="claim-head">
          <span class="kind-chip" :class="`kind-${a.kind}`">{{ KIND_LABELS[a.kind] || a.kind }}</span>
          <span class="faint">confidence: {{ a.confidence || '—' }}</span>
        </div>
        <div class="claim-text">{{ a.text }}</div>
        <div v-if="a.source_uri" class="faint">
          Source:
          <a :href="a.source_uri" target="_blank" rel="noopener noreferrer">{{ a.source_uri }}</a>
        </div>
        <div v-else-if="a.evidence_ref && evidenceById(a.evidence_ref)" class="faint">
          Based on your evidence {{ a.evidence_ref }}: “{{ evidenceById(a.evidence_ref).text.slice(0, 120) }}…”
        </div>
      </div>
    </section>

    <section class="detail-section">
      <h3 class="section-title">Triggers — what would push toward this branch</h3>
      <div v-for="t in scenario.triggers" :key="t.id" class="trigger">
        <div class="trigger-event">{{ t.event }}</div>
        <div class="faint">{{ t.description }}</div>
      </div>
    </section>

    <section class="detail-section">
      <h3 class="section-title">Possible consequences</h3>
      <ul class="bullets">
        <li v-for="(c, i) in scenario.possible_consequences" :key="i">{{ c }}</li>
      </ul>
    </section>

    <section class="detail-section">
      <h3 class="section-title">Indicators to watch</h3>
      <ul class="bullets">
        <li v-for="(c, i) in scenario.indicators_to_watch" :key="i">{{ c }}</li>
      </ul>
    </section>

    <section v-if="scenario.children && scenario.children.length" class="detail-section">
      <h3 class="section-title">Sub-branches</h3>
      <div class="sub-row">
        <button
          v-for="child in scenario.children"
          :key="child.id"
          type="button"
          class="chip"
          :class="{ active: store.selectedScenarioId === child.id }"
          @click="store.selectedScenarioId = child.id"
        >
          {{ child.title }}
        </button>
      </div>
    </section>

    <div class="expand-row">
      <button v-if="canExpand" class="btn btn-small" :disabled="!!store.busyExpanding" @click="runExpand(scenario.id)">
        <template v-if="expanding">Expanding…</template>
        <template v-else>＋ Expand into 3 sub-branches</template>
      </button>
      <span v-else-if="!store.apiEnabled" class="faint">
        Branch expansion needs a connected API — or run the workflow with <code>--expand</code>.
      </span>
      <span v-else-if="scenario.children && scenario.children.length" class="faint">
        This branch is already expanded.
      </span>
    </div>
  </div>
</template>

<style scoped>
.detail {
  padding: 20px;
  max-height: calc(100vh - 140px);
  overflow: auto;
  position: sticky;
  top: 96px;
}

.detail-title {
  font-size: 20px;
  line-height: 1.3;
  margin: 6px 0 10px;
}

.stance-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.narrative {
  color: var(--text-muted);
  font-size: 13.8px;
  line-height: 1.65;
}

.detail-section {
  margin-top: 18px;
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

.claim {
  border-left: 2px solid var(--border-strong);
  padding: 4px 0 4px 12px;
  margin-bottom: 12px;
}

.claim-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
  flex-wrap: wrap;
}

.claim-text {
  font-size: 13.5px;
  color: var(--text);
  margin-bottom: 4px;
}

.trigger {
  margin-bottom: 11px;
}

.trigger-event {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
}

.sub-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.expand-row {
  margin-top: 18px;
}

@media (max-width: 1280px) {
  .detail {
    position: static;
    max-height: none;
  }
}
</style>
