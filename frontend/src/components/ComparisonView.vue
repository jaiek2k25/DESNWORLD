<script setup>
import { computed } from 'vue'
import { store, selectScenario } from '../store.js'
import { stanceClass, STANCE_LABELS } from '../lib/report.js'

const comparison = computed(() => store.report?.comparison || null)
const columns = computed(() => {
  const report = store.report
  if (!report) return []
  return [report.baseline, ...(report.alternatives || [])].filter(Boolean)
})

const columnColors = {
  baseline: '#e8a33d',
  'alt-1': '#5ec8d8',
  'alt-2': '#e06b7b',
  'alt-3': '#b48be0'
}
</script>

<template>
  <div v-if="comparison" class="panel compare">
    <div class="eyebrow">Side-by-side comparison</div>
    <h2 class="display compare-title">How the scenarios differ</h2>
    <p class="summary">{{ comparison.summary }}</p>

    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th class="dim-col">Dimension</th>
            <th v-for="col in columns" :key="col.id">
              <button
                type="button"
                class="col-button"
                :style="{ borderColor: columnColors[col.id] || 'var(--border-strong)' }"
                @click="selectScenario(col.id)"
              >
                <span class="col-title">{{ col.title }}</span>
                <span class="col-label" :style="{ color: columnColors[col.id] || 'var(--text-muted)' }">
                  {{ col.label }} · {{ STANCE_LABELS[col.stance?.qualitative] || '' }}
                </span>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(dim, i) in comparison.dimensions" :key="i">
            <td class="dim-col">{{ dim.dimension }}</td>
            <td>{{ dim.baseline }}</td>
            <td v-for="col in columns.filter((c) => c.id !== 'baseline')" :key="col.id">
              {{ dim.alternatives?.[col.id] || '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="compare-grid">
      <section>
        <h3 class="section-title">Key differences</h3>
        <ul class="bullets">
          <li v-for="(item, i) in comparison.key_differences" :key="i">{{ item }}</li>
        </ul>
      </section>
      <section>
        <h3 class="section-title">What would change the outlook</h3>
        <ul class="bullets">
          <li v-for="(item, i) in comparison.what_would_change_the_outlook" :key="i">{{ item }}</li>
        </ul>
      </section>
    </div>

    <section v-if="store.report?.uncertainties?.length">
      <h3 class="section-title">Uncertainties &amp; missing evidence</h3>
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
            <tr v-for="u in store.report.uncertainties" :key="u.id">
              <td>{{ u.statement }}</td>
              <td>
                <span class="badge" :class="u.impact === 'high' ? 'stance-unlikely' : u.impact === 'medium' ? 'stance-less' : 'stance-plausible'">
                  {{ u.impact }}
                </span>
              </td>
              <td>{{ u.missing_evidence }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.compare {
  padding: 20px;
}

.compare-title {
  font-size: 21px;
  margin: 6px 0 10px;
}

.summary {
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.65;
  max-width: 900px;
}

.table-scroll {
  overflow-x: auto;
  margin: 14px 0 22px;
}

.dim-col {
  min-width: 150px;
}

.col-button {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
  background: rgba(8, 12, 22, 0.4);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  padding: 9px 11px;
  cursor: pointer;
  width: 100%;
  min-width: 150px;
  transition: border-color 0.15s ease;
}

.col-button:hover {
  border-color: var(--gold);
}

.col-title {
  color: var(--text);
  font-size: 12.5px;
  font-weight: 700;
  font-family: var(--font-ui);
}

.col-label {
  font-size: 10.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22px;
  margin-bottom: 20px;
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

@media (max-width: 860px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}
</style>
