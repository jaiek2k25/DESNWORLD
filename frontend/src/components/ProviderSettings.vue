<script setup>
import { reactive, ref, computed } from 'vue'
import { store, configureRun, testBrowserConnection, checkApiHealth } from '../store.js'

const MODES = [
  {
    kind: 'demo',
    title: 'Demo engine',
    tagline: 'Runs fully in your browser — no credentials',
    description:
      'A deterministic offline engine. Perfect for exploring the complete workflow instantly. ' +
      'Output is clearly labelled as illustrative.'
  },
  {
    kind: 'browser',
    title: 'Your AI model',
    tagline: 'Bring your own API key — real scenarios in the browser',
    description:
      'Calls any OpenAI-compatible endpoint directly from your browser with a key you provide. ' +
      'The key is sent only to that endpoint and is never embedded in this site.'
  },
  {
    kind: 'api',
    title: 'DESNWORLD API',
    tagline: 'Local dev server or your deployed backend',
    description:
      'Uses a DESNWORLD server (python -m desnworld.server) via same-origin /api or a URL you configure.'
  }
]

const browserForm = reactive({
  baseUrl: store.run.browser.baseUrl,
  model: store.run.browser.model,
  apiKey: store.run.browser.apiKey,
  rememberKey: store.run.browser.rememberKey
})

// Endpoint presets — base URLs and suggested models only. API keys are never
// embedded here; users paste their own key at runtime.
const PRESETS = [
  {
    id: 'nvidia',
    label: 'NVIDIA NIM',
    baseUrl: 'https://integrate.api.nvidia.com/v1',
    model: 'meta/llama-3.3-70b-instruct',
    hint: 'build.nvidia.com — OpenAI-compatible NIM endpoints'
  },
  {
    id: 'openai',
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    hint: 'platform.openai.com'
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    baseUrl: 'https://openrouter.ai/api/v1',
    model: 'meta-llama/llama-3.3-70b-instruct',
    hint: 'openrouter.ai — many models behind one key'
  },
  {
    id: 'custom',
    label: 'Custom',
    baseUrl: '',
    model: '',
    hint: 'any OpenAI-compatible /chat/completions endpoint'
  }
]

function applyPreset(preset) {
  browserForm.baseUrl = preset.baseUrl
  if (preset.model) browserForm.model = preset.model
}
const apiDraft = ref(store.run.apiBase)
const testResult = ref(null)
const testing = ref(false)

const kind = computed(() => store.run.kind)

function pick(kindValue) {
  configureRun({ kind: kindValue })
}

function saveBrowser() {
  configureRun({
    kind: 'browser',
    browser: {
      baseUrl: browserForm.baseUrl,
      model: browserForm.model,
      apiKey: browserForm.apiKey,
      rememberKey: browserForm.rememberKey
    }
  })
  testResult.value = null
}

async function testBrowser() {
  saveBrowser()
  testing.value = true
  testResult.value = await testBrowserConnection()
  testing.value = false
}

async function saveApi() {
  configureRun({ kind: 'api', apiBase: apiDraft.value })
  testing.value = true
  const health = await checkApiHealth()
  testResult.value =
    health?.status === 'ok'
      ? { ok: true, message: `DESNWORLD API reachable${health.llm_configured ? ' (AI model configured on the server)' : ' (server will use its demo/mock output)'}.` }
      : { ok: false, message: 'Cannot reach the DESNWORLD API at that location.', hint: 'Start python -m desnworld.server or check the URL.' }
  testing.value = false
}
</script>

<template>
  <div class="panel settings">
    <div class="eyebrow">Run settings</div>
    <h2 class="display settings-title">How do you want to run this?</h2>

    <div class="mode-cards">
      <button
        v-for="mode in MODES"
        :key="mode.kind"
        type="button"
        class="mode-card"
        :class="{ active: kind === mode.kind }"
        @click="pick(mode.kind)"
      >
        <div class="mode-head">
          <span class="mode-radio" aria-hidden="true"></span>
          <span class="mode-title">{{ mode.title }}</span>
        </div>
        <div class="mode-tag">{{ mode.tagline }}</div>
      </button>
    </div>

    <p class="mode-desc">
      {{ MODES.find((m) => m.kind === kind)?.description }}
    </p>

    <div v-if="kind === 'browser'" class="mode-form">
      <div class="field">
        <label>Endpoint preset</label>
        <div class="chip-row">
          <button
            v-for="preset in PRESETS"
            :key="preset.id"
            type="button"
            class="chip"
            :class="{ active: browserForm.baseUrl === preset.baseUrl && preset.id !== 'custom' }"
            :title="preset.hint"
            @click="applyPreset(preset)"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>
      <div class="field">
        <label for="llm-base">Endpoint base URL</label>
        <input id="llm-base" type="url" v-model="browserForm.baseUrl" placeholder="https://api.openai.com/v1" />
      </div>
      <div class="field">
        <label for="llm-model">Model</label>
        <input id="llm-model" type="text" v-model="browserForm.model" placeholder="gpt-4o-mini" />
      </div>
      <div class="field">
        <label for="llm-key">API key</label>
        <input id="llm-key" type="password" v-model="browserForm.apiKey" placeholder="sk-…" autocomplete="off" />
        <label class="check-row">
          <input type="checkbox" v-model="browserForm.rememberKey" />
          <span class="faint">Remember the key on this device (localStorage). Leave off to keep it in memory only.</span>
        </label>
      </div>
      <div class="btn-row">
        <button class="btn btn-small" :disabled="testing" @click="testBrowser">
          {{ testing ? 'Testing…' : 'Save & test connection' }}
        </button>
      </div>
      <div class="faint key-note">
        Your key stays in your browser and is sent only to the endpoint above. Browser-side calls
        require the provider to allow CORS (NVIDIA NIM, OpenAI, OpenRouter, Groq and Together
        generally do). If yours blocks them, use the DESNWORLD API mode or the GitHub Actions
        workflow.
      </div>
    </div>

    <div v-if="kind === 'api'" class="mode-form">
      <div class="field">
        <label for="api-base">DESNWORLD API base URL</label>
        <div class="row">
          <input id="api-base" type="url" v-model="apiDraft" placeholder="empty = same-origin /api" />
          <button class="btn btn-small" :disabled="testing" @click="saveApi">
            {{ testing ? 'Testing…' : 'Save & test' }}
          </button>
        </div>
      </div>
      <div class="faint">
        Leave empty when using the local dev proxy (vite forwards /api to the DESNWORLD server).
        Keys stay on the server — never put API keys in this field.
      </div>
    </div>

    <div v-if="testResult" class="notice" :class="testResult.ok ? 'notice-info' : 'notice-error'">
      {{ testResult.message }}
      <div v-if="testResult.hint" class="faint">{{ testResult.hint }}</div>
    </div>

    <details class="actions-help">
      <summary>Prefer a batch run? Use the GitHub Actions workflow</summary>
      <p class="faint">
        The <code>Generate Scenarios</code> workflow runs the same pipeline with repository secrets
        and uploads a <code>desnworld-report</code> artifact — import it here with
        <strong>Import JSON</strong>. Secrets never touch the browser.
      </p>
    </details>
  </div>
</template>

<style scoped>
.settings-title {
  font-size: 18px;
  margin: 6px 0 14px;
}

.mode-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mode-card {
  text-align: left;
  background: rgba(8, 12, 22, 0.4);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 11px 13px;
  cursor: pointer;
  color: var(--text-muted);
  transition: border-color 0.15s ease, background 0.15s ease;
  font-family: var(--font-ui);
}

.mode-card:hover {
  border-color: var(--gold);
}

.mode-card.active {
  border-color: var(--gold);
  background: rgba(232, 163, 61, 0.1);
  color: var(--text);
}

.mode-head {
  display: flex;
  align-items: center;
  gap: 9px;
}

.mode-radio {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid var(--border-strong);
  flex: 0 0 auto;
}

.mode-card.active .mode-radio {
  border-color: var(--gold);
  background: radial-gradient(circle at 40% 35%, var(--gold-bright), var(--gold));
}

.mode-title {
  font-weight: 700;
  font-size: 13.5px;
}

.mode-tag {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--text-faint);
  padding-left: 22px;
}

.mode-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 12px 0;
}

.mode-form {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}

.row {
  display: flex;
  gap: 8px;
}

.row input {
  flex: 1;
}

.check-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  text-transform: none;
  letter-spacing: 0;
  font-size: 12px;
  font-weight: 400;
  cursor: pointer;
}

.check-row input {
  width: auto;
  margin-top: 3px;
}

.key-note {
  margin-top: 10px;
}

.actions-help {
  margin-top: 14px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

.actions-help summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.actions-help p {
  margin: 8px 0 0;
}
</style>
