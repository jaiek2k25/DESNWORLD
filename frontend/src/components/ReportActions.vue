<script setup>
import { ref } from 'vue'
import { store, importReportObject } from '../store.js'
import { downloadReportJSON, readReportFile } from '../lib/report.js'

const fileInput = ref(null)
const flash = ref('')

function download() {
  if (!store.report) return
  downloadReportJSON(store.report)
  flash.value = 'Report JSON downloaded.'
  setTimeout(() => (flash.value = ''), 2500)
}

function openImport() {
  fileInput.value?.click()
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  try {
    const report = await readReportFile(file)
    if (importReportObject(report)) {
      flash.value = `Imported ${file.name}.`
      setTimeout(() => (flash.value = ''), 2500)
    }
  } catch (err) {
    flash.value = ''
    store.status = 'error'
    store.error = { message: `Could not import the report: ${err.message || err}` }
  }
}
</script>

<template>
  <div class="actions">
    <span v-if="flash" class="faint flash">{{ flash }}</span>
    <button class="btn btn-small" @click="openImport">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 18v2h16v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Import JSON
    </button>
    <button class="btn btn-small" @click="download">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 4v12m0 0l-4-4m4 4l4-4M4 18v2h16v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Download JSON
    </button>
    <input ref="fileInput" type="file" accept="application/json,.json" class="hidden-input" @change="onFileChange" />
  </div>
</template>

<style scoped>
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.flash {
  color: var(--green);
}

.hidden-input {
  display: none;
}
</style>
