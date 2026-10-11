<script setup>
import { reactive, ref, computed } from 'vue'
import { store, generate, setApiBase, checkHealth, loadDemo } from '../store.js'

const form = reactive({
  question: '',
  domain: 'stock_market_education',
  horizonMonths: 12,
  evidence: []
})

const HORIZONS = [
  { months: 3, label: '3 months' },
  { months: 6, label: '6 months' },
  { months: 12, label: '1 year' },
  { months: 24, label: '2 years' },
  { months: 60, label: '5 years' }
]

const DOMAINS = [
  { value: 'stock_market_education', label: 'Stock Market Education' },
  { value: 'general', label: 'General' },
  { value: 'business', label: 'Business' },
  { value: 'technology', label: 'Technology' }
]

const showEvidence = ref(false)
const showConnection = ref(false)
const apiDraft = ref(store.apiBase)
const showActionsHelp = ref(false)

const questionOk = computed(() => form.question.trim().length >= 10)
const canGenerate = computed(() => questionOk.value && store.status !== 'loading')

function addEvidence() {
  if (form.evidence.length >= 20) return
  form.evidence.push({ text: '', source_uri: '' })
  showEvidence.value = true
}

function removeEvidence(index) {
  form.evidence.splice(index, 1)
}

function pickHorizon(months) {
  form.horizonMonths = months
}

async function saveConnection() {
  setApiBase(apiDraft.value)
  await checkHealth()
  showConnection.value = false
}

function submit() {
  if (!canGenerate.value) return
  const evidence = form.evidence
    .filter((e) => e.text.trim().length >= 3)
    .map((e) => ({
      text: e.text.trim(),
      source_uri: e.source_uri.trim() || undefined,
      kind: e.source_uri.trim() ? 'sourced_fact' : 'user_supplied_fact'
    }))
  generate({
    question: form.question.trim(),
    domain: form.domain,
    horizon_months: form.horizonMonths,
    evidence
  })
}

function workflowInputs() {
  return [
    `question: ${form.question.trim() || '<your question>'}`,
    `domain: ${form.domain}`,
    `horizon_months: ${form.horizonMonths}`,
    `evidence: ${form.evidence.filter((e) => e.text.trim()).map((e) => e.text.trim()).join(' | ') || '<optional evidence>'}`
  ].join('\n')
}

async function copyWorkflowInputs() {
  try {
    await navigator.clipboard.writeText(workflowInputs())
    showActionsHelp.value = true
  } catch {
    showActionsHelp.value = true
  }
}
</script>

<template>
  <div class="panel composer">
    <div class="eyebrow">Explore a question</div>
    <h2 class="display composer-title">What future do you want to examine?</h2>

    <div class="field">
      <label for="question">Question</label>
      <textarea
        id="question"
        v-model="form.question"
        placeholder="e.g. How might AI regulation affect semiconductor stocks over the next year?"
        rows="3"
      ></textarea>
      <div class="faint">
        DESNWORLD will produce a baseline, three alternative branches, triggers, uncertainties and a
        comparison report — never a single predicted answer.
      </div>
    </div>

    <div class="field">
      <label for="domain">Domain</label>
      <select id="domain" v-model="form.domain">
        <option v-for="d in DOMAINS" :key="d.value" :value="d.value">{{ d.label }}</option>
      </select>
    </div>

    <div class="field">
      <label>Time horizon</label>
      <div class="chip-row">
        <button
          v-for="h in HORIZONS"
          :key="h.months"
          type="button"
          class="chip"
          :class="{ active: form.horizonMonths === h.months }"
          @click="pickHorizon(h.months)"
        >
          {{ h.label }}
        </button>
      </div>
    </div>

    <div class="field">
      <div class="label-row">
        <label>Evidence (optional)</label>
        <button type="button" class="btn btn-ghost btn-small" @click="showEvidence = !showEvidence">
          {{ showEvidence ? 'Hide' : form.evidence.length ? `Show (${form.evidence.length})` : 'Add' }}
        </button>
      </div>
      <div v-if="showEvidence">
        <div v-for="(item, index) in form.evidence" :key="index" class="evidence-item">
          <textarea
            v-model="item.text"
            placeholder="Paste a fact, historical note, or observation. Claims with an http(s) source URL are tagged as sourced facts; everything else is user-supplied."
            rows="2"
          ></textarea>
          <div class="evidence-row">
            <input
              type="url"
              v-model="item.source_uri"
              placeholder="https://… source URL (optional)"
            />
            <button type="button" class="btn btn-ghost btn-small" @click="removeEvidence(index)">
              Remove
            </button>
          </div>
        </div>
        <button type="button" class="btn btn-ghost btn-small" @click="addEvidence">+ Add evidence item</button>
        <div class="faint">
          Nothing is fetched from the web during generation: the engine only sees your question and this
          evidence. Gaps are reported as missing information instead of being invented.
        </div>
      </div>
    </div>

    <button class="btn btn-primary generate" :disabled="!canGenerate" @click="submit">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      Generate Scenarios
    </button>

    <div v-if="!store.apiEnabled" class="notice notice-info gen-help">
      <strong>How generation works:</strong> this interface is static (GitHub Pages) and cannot run the
      AI engine by itself. Choose one:
      <ol class="help-list">
        <li>
          <strong>GitHub Actions (no server):</strong>
          <button type="button" class="linklike" @click="copyWorkflowInputs">Copy workflow inputs</button>,
          run the <code>Generate Scenarios</code> workflow, then import the downloaded report here.
        </li>
        <li>
          <strong>Connect a DESNWORLD API:</strong>
          <button type="button" class="linklike" @click="showConnection = !showConnection">configure endpoint</button>
          (local dev server <code>python -m desnworld.server</code>, or your deployed secure backend).
        </li>
        <li><strong>Just looking around?</strong> <button type="button" class="linklike" @click="loadDemo">Explore the demo report</button>.</li>
      </ol>
      <div v-if="showActionsHelp" class="copy-flash">
        Workflow inputs copied. Actions → “Generate Scenarios” → Run workflow, paste them into the
        matching fields, then import the <code>desnworld-report</code> artifact when it finishes.
      </div>
    </div>

    <div v-if="showConnection" class="notice connection">
      <label class="conn-label" for="api-base">DESNWORLD API base URL</label>
      <div class="evidence-row">
        <input id="api-base" type="url" v-model="apiDraft" placeholder="empty = same-origin /api (dev proxy)" />
        <button type="button" class="btn btn-small" @click="saveConnection">Save</button>
      </div>
      <div class="faint">
        Leave empty to use this site's origin (works with the local dev proxy). The endpoint must
        allow this page's origin (CORS). Keys stay on the server — never put API keys in this field
        or in frontend code.
      </div>
    </div>

    <div v-else-if="store.apiEnabled" class="notice">
      Generation via API {{ store.apiBase ? `at ${store.apiBase}` : '(same origin)' }}
      <button type="button" class="linklike" @click="showConnection = true">change</button>
    </div>
  </div>
</template>

<style scoped>
.composer-title {
  font-size: 21px;
  line-height: 1.3;
  margin: 6px 0 18px;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.evidence-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px;
  margin-bottom: 10px;
  background: rgba(8, 12, 22, 0.35);
}

.evidence-item textarea {
  margin-bottom: 8px;
}

.evidence-row {
  display: flex;
  gap: 8px;
}

.evidence-row input {
  flex: 1;
}

.generate {
  width: 100%;
  justify-content: center;
  padding: 13px 18px;
  font-size: 15px;
  margin: 6px 0 14px;
}

.gen-help {
  font-size: 12.5px;
}

.help-list {
  margin: 8px 0 0;
  padding-left: 18px;
}

.help-list li {
  margin-bottom: 6px;
}

.copy-flash {
  margin-top: 10px;
  padding: 9px 11px;
  border-radius: 8px;
  background: rgba(94, 200, 216, 0.12);
  color: var(--cyan);
}

.conn-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
}
</style>
