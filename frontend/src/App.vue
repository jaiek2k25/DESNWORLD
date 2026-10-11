<script setup>
import { store, setMode, dismissError } from './store.js'
import ThemeSwitcher from './components/ThemeSwitcher.vue'
import QuestionComposer from './components/QuestionComposer.vue'
import ProviderSettings from './components/ProviderSettings.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import ScenarioTree from './components/ScenarioTree.vue'
import ScenarioDetail from './components/ScenarioDetail.vue'
import ComparisonView from './components/ComparisonView.vue'
import OverviewView from './components/OverviewView.vue'
import ReportView from './components/ReportView.vue'
import StateView from './components/StateView.vue'
import ReportActions from './components/ReportActions.vue'

const TABS = [
  ['overview', 'Overview'],
  ['explore', 'Scenario tree'],
  ['compare', 'Compare'],
  ['report', 'Full report']
]
</script>

<template>
  <header class="site-header">
    <div class="brand">
      <svg class="brand-mark" viewBox="0 0 64 64" aria-hidden="true">
        <rect class="mark-bg" width="64" height="64" rx="18" />
        <path
          class="mark-lines"
          d="M32 46V26M32 26L20 16M32 26L44 16M32 34L18 28M32 34L46 28"
          stroke-width="3"
          stroke-linecap="round"
          fill="none"
        />
        <circle class="mark-root" cx="32" cy="46" r="4.5" />
        <circle class="mark-b2" cx="20" cy="16" r="4" />
        <circle class="mark-b2" cx="44" cy="16" r="4" />
        <circle class="mark-b4" cx="18" cy="28" r="3.5" />
        <circle class="mark-b4" cx="46" cy="28" r="3.5" />
      </svg>
      <div class="brand-text">
        <h1 class="brand-name display">DESNWORLD</h1>
        <div class="brand-tag">The scenario atelier — possibilities, not predictions</div>
      </div>
    </div>
    <div class="header-right">
      <span v-if="store.run.kind === 'demo'" class="badge stance-plausible"><span class="dot"></span>Demo engine</span>
      <span v-else-if="store.run.kind === 'browser'" class="badge stance-more"><span class="dot"></span>Your AI model</span>
      <span v-else class="badge stance-more"><span class="dot"></span>API mode</span>
      <ThemeSwitcher />
    </div>
  </header>

  <main class="layout" :class="{ 'has-report': store.status === 'completed' }">
    <section class="col col-composer">
      <QuestionComposer />
      <ProviderSettings />
      <HistoryPanel />
    </section>

    <section class="col col-main">
      <div v-if="store.error && store.status === 'completed'" class="notice notice-error error-banner">
        <div>
          <strong>{{ store.error.message }}</strong>
          <div v-if="store.error.hint" class="faint">{{ store.error.hint }}</div>
          <ul v-if="store.error.problems?.length" class="bullets">
            <li v-for="(p, i) in store.error.problems.slice(0, 6)" :key="i"><code>{{ p }}</code></li>
          </ul>
        </div>
        <button class="btn btn-small" @click="dismissError">Dismiss</button>
      </div>

      <StateView v-if="store.status !== 'completed'" />
      <template v-else>
        <div class="mode-tabs" role="tablist" aria-label="Result views">
          <button
            v-for="[id, label] in TABS"
            :key="id"
            role="tab"
            class="chip"
            :class="{ active: store.mode === id }"
            :aria-selected="store.mode === id"
            @click="setMode(id)"
          >
            {{ label }}
          </button>
          <div class="mode-spacer"></div>
          <ReportActions />
        </div>
        <OverviewView v-if="store.mode === 'overview'" />
        <template v-else-if="store.mode === 'explore'">
          <ScenarioTree />
        </template>
        <ComparisonView v-else-if="store.mode === 'compare'" />
        <ReportView v-else />
      </template>
    </section>

    <aside class="col col-detail" v-if="store.status === 'completed' && store.mode === 'explore'">
      <ScenarioDetail />
    </aside>
  </main>

  <footer class="site-footer">
    <div class="footer-inner">
      <p>
        <strong>DESNWORLD</strong> explores possible futures with documented assumptions, triggers and
        uncertainties. It does not predict the future with certainty. Stock-market content is
        educational — never price predictions, personalized investment advice, or guaranteed returns.
      </p>
      <p class="faint">
        Sourced facts, user-supplied facts and AI-generated assumptions are labelled throughout.
        · Derived in part from MiroFish (AGPL-3.0) · Schema v1
      </p>
    </div>
  </footer>
</template>

<style scoped>
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 30px;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 75%, transparent);
  backdrop-filter: blur(14px);
  position: sticky;
  top: 0;
  z-index: 30;
  transition: var(--transition-theme);
}

.mark-bg {
  fill: color-mix(in srgb, var(--gold) 12%, transparent);
}

.mark-lines {
  stroke: var(--gold);
}

.mark-root {
  fill: var(--gold);
}

.mark-b2 {
  fill: var(--cyan);
}

.mark-b4 {
  fill: var(--violet);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  flex: 0 0 auto;
}

.brand-name {
  margin: 0;
  font-size: 27px;
  font-weight: 550;
  letter-spacing: 0.18em;
  color: var(--text);
  line-height: 1.12;
  background: linear-gradient(120deg, var(--text) 55%, var(--gold) 115%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-tag {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 12.5px;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  gap: 10px;
  align-items: center;
}

.layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 22px;
  padding: 22px 28px 30px;
  align-items: start;
  width: 100%;
  max-width: 1780px;
  margin: 0 auto;
}

.layout.has-report {
  grid-template-columns: minmax(290px, 340px) minmax(0, 1fr);
}

.layout.has-report:has(.col-detail) {
  grid-template-columns: minmax(290px, 340px) minmax(0, 1fr) minmax(300px, 370px);
}

.col {
  min-width: 0;
}

.col-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 560px;
}

.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}

.mode-tabs {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.mode-spacer {
  flex: 1;
}

.site-footer {
  border-top: 1px solid var(--border);
  padding: 22px 30px 28px;
  background: color-mix(in srgb, var(--bg-1) 70%, transparent);
  transition: var(--transition-theme);
}

.footer-inner {
  max-width: 1100px;
  margin: 0 auto;
  font-size: 12.5px;
  color: var(--text-muted);
}

.footer-inner p {
  margin: 4px 0;
}

@media (max-width: 1280px) {
  .layout.has-report,
  .layout.has-report:has(.col-detail) {
    grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
  }
  .col-detail {
    grid-column: 1 / -1;
  }
}

@media (max-width: 980px) {
  .layout,
  .layout.has-report,
  .layout.has-report:has(.col-detail) {
    grid-template-columns: 1fr;
  }
  .site-header {
    padding: 14px 16px;
  }
  .layout {
    padding: 16px;
  }
  .brand-name {
    font-size: 19px;
  }
}
</style>
