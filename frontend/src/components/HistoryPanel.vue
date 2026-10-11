<script setup>
import { store, loadHistoryReport, deleteHistory, loadSample } from '../store.js'

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}
</script>

<template>
  <div class="panel history">
    <div class="history-head">
      <div class="eyebrow">Run history</div>
      <button class="linklike" @click="loadSample">Load demo report</button>
    </div>
    <p v-if="!store.history.length" class="faint">
      Reports you generate appear here (saved in this browser only — nothing is uploaded).
    </p>
    <ul class="history-list">
      <li v-for="entry in store.history" :key="entry.id">
        <button class="history-item" @click="loadHistoryReport(entry.id)">
          <div class="history-q">{{ entry.question }}</div>
          <div class="history-meta">
            <span>{{ formatDate(entry.savedAt) }}</span>
            <span class="badge" :class="entry.mock ? 'stance-less' : 'stance-plausible'">
              {{ entry.mock ? 'demo' : 'ai' }}
            </span>
            <span class="faint">{{ entry.domain?.replace(/_/g, ' ') }}</span>
          </div>
        </button>
        <button class="history-del linklike" title="Remove from history" @click="deleteHistory(entry.id)">✕</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.history {
  padding: 16px;
  margin-top: 16px;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.history-list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 260px;
  overflow: auto;
}

.history-list li {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.history-item {
  flex: 1;
  text-align: left;
  background: var(--input-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 9px 11px;
  cursor: pointer;
  color: var(--text-muted);
  font-family: var(--font-ui);
  transition: border-color 0.15s ease;
}

.history-item:hover {
  border-color: var(--gold);
}

.history-q {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 5px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.history-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 10.5px;
  flex-wrap: wrap;
}

.history-del {
  padding: 6px 8px;
  color: var(--text-faint);
}

.history-del:hover {
  color: var(--rose);
}
</style>
