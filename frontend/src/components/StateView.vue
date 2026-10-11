<script setup>
import { store, dismissError, loadSample, resetAll } from '../store.js'
import StageProgress from './StageProgress.vue'
</script>

<template>
  <div class="panel state-panel">
    <!-- LOADING -->
    <template v-if="store.status === 'loading'">
      <div class="orbit" aria-hidden="true">
        <div class="orbit-ring ring-a"></div>
        <div class="orbit-ring ring-b"></div>
        <div class="orbit-core"></div>
        <div class="orbit-node n1"></div>
        <div class="orbit-node n2"></div>
        <div class="orbit-node n3"></div>
      </div>
      <h2 class="display state-title">Exploring possible futures…</h2>
      <p class="state-msg">{{ store.loadingMessage }}</p>
      <StageProgress />
      <p class="faint state-hint">
        The engine validates every stage of structured output and repairs malformed responses in a
        bounded loop — it never invents sources or truncated JSON.
      </p>
    </template>

    <!-- ERROR -->
    <template v-else-if="store.status === 'error'">
      <div class="state-icon" aria-hidden="true">⚠</div>
      <h2 class="display state-title">Something interrupted the exploration</h2>
      <div class="notice notice-error">
        {{ store.error?.message || 'Unknown error.' }}
      </div>
      <ul v-if="store.error?.problems?.length" class="bullets problems">
        <li v-for="(p, i) in store.error.problems" :key="i"><code>{{ p }}</code></li>
      </ul>
      <p v-if="store.error?.hint" class="state-msg">{{ store.error.hint }}</p>
      <div class="btn-row state-actions">
        <button class="btn" @click="dismissError">Back</button>
        <button v-if="!store.report" class="btn btn-primary" @click="loadSample">
          Explore the demo report
        </button>
      </div>
    </template>

    <!-- EMPTY -->
    <template v-else>
      <div class="empty-hero">
        <svg viewBox="0 0 420 240" class="empty-svg" aria-hidden="true">
          <path
            d="M70 120 C 130 120, 150 60, 220 60"
            fill="none"
            stroke="rgba(232,163,61,0.55)"
            stroke-width="2.5"
            stroke-dasharray="5 7"
          />
          <path
            d="M70 120 C 130 120, 160 120, 240 120"
            fill="none"
            stroke="rgba(94,200,216,0.55)"
            stroke-width="2.5"
            stroke-dasharray="5 7"
          />
          <path
            d="M70 120 C 130 120, 150 180, 220 180"
            fill="none"
            stroke="rgba(224,107,123,0.55)"
            stroke-width="2.5"
            stroke-dasharray="5 7"
          />
          <circle cx="70" cy="120" r="16" fill="rgba(232,163,61,0.25)" stroke="#e8a33d" stroke-width="2.5" />
          <circle cx="220" cy="60" r="11" fill="rgba(94,200,216,0.22)" stroke="#5ec8d8" stroke-width="2" />
          <circle cx="240" cy="120" r="11" fill="rgba(180,139,224,0.22)" stroke="#b48be0" stroke-width="2" />
          <circle cx="220" cy="180" r="11" fill="rgba(224,107,123,0.22)" stroke="#e06b7b" stroke-width="2" />
          <circle cx="320" cy="60" r="7" fill="rgba(94,200,216,0.18)" stroke="#5ec8d8" stroke-width="1.5" />
          <circle cx="340" cy="180" r="7" fill="rgba(224,107,123,0.18)" stroke="#e06b7b" stroke-width="1.5" />
        </svg>
      </div>
      <h2 class="display state-title">Every question holds more than one future</h2>
      <p class="state-msg">
        Compose a question on the left and press <strong>Generate Scenarios</strong> — the entire
        pipeline runs inside this page. You'll get a baseline, three alternative branches, their
        triggers, an honest account of what is still unknown, and a comparison you can explore.
      </p>
      <div class="btn-row state-actions">
        <button class="btn btn-primary" @click="loadSample">Explore the demo report</button>
        <button v-if="store.report" class="btn" @click="resetAll">Clear</button>
      </div>
      <div class="empty-steps">
        <div class="step">
          <span class="step-num">1</span>
          <div>
            <strong>Ask</strong>
            <div class="faint">A question, a domain, a time horizon — plus any evidence you already trust.</div>
          </div>
        </div>
        <div class="step">
          <span class="step-num">2</span>
          <div>
            <strong>Run</strong>
            <div class="faint">Demo engine, your own AI key, or a DESNWORLD API — your choice, all in this UI.</div>
          </div>
        </div>
        <div class="step">
          <span class="step-num">3</span>
          <div>
            <strong>See everything</strong>
            <div class="faint">Overview, scenario tree, side-by-side comparison, and the full report — then expand any branch.</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.state-panel {
  min-height: 560px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 30px;
  gap: 12px;
}

.state-title {
  font-size: 24px;
  margin: 10px 0 0;
  max-width: 560px;
}

.state-msg {
  color: var(--text-muted);
  max-width: 560px;
  margin: 4px 0;
}

.state-hint {
  max-width: 480px;
}

.state-actions {
  justify-content: center;
  margin-top: 10px;
}

.state-icon {
  font-size: 42px;
  color: var(--rose);
}

.problems {
  text-align: left;
  max-width: 560px;
}

/* orbit loader */
.orbit {
  position: relative;
  width: 120px;
  height: 120px;
  margin-bottom: 8px;
}

.orbit-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1.5px dashed rgba(232, 163, 61, 0.5);
  animation: spin 12s linear infinite;
}

.ring-b {
  inset: 22px;
  border-color: rgba(94, 200, 216, 0.45);
  animation-duration: 8s;
  animation-direction: reverse;
}

.orbit-core {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 26px;
  height: 26px;
  margin: -13px 0 0 -13px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, var(--gold-bright), var(--gold));
  box-shadow: var(--shadow-glow-gold);
}

.orbit-node {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.n1 { background: var(--cyan); top: -5px; left: 55px; animation: bob 3s ease-in-out infinite; }
.n2 { background: var(--violet); bottom: 8px; left: 6px; animation: bob 3s ease-in-out 0.6s infinite; }
.n3 { background: var(--rose); bottom: 8px; right: 6px; animation: bob 3s ease-in-out 1.2s infinite; }

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

/* empty hero */
.empty-svg {
  width: min(420px, 90%);
  height: auto;
  opacity: 0.9;
}

.empty-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  max-width: 720px;
  margin-top: 18px;
  text-align: left;
}

.step {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
}

.step-num {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(232, 163, 61, 0.18);
  color: var(--gold-bright);
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 720px) {
  .empty-steps {
    grid-template-columns: 1fr;
  }
}
</style>
