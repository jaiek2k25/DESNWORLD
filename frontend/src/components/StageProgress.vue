<script setup>
import { store } from '../store.js'

const ICON = {
  pending: '○',
  active: '◔',
  repairing: '◐',
  done: '●',
  error: '✕'
}
</script>

<template>
  <ul class="stages" aria-live="polite">
    <li v-for="item in store.stageProgress" :key="item.stage" :class="`state-${item.state}`">
      <span class="stage-icon">{{ ICON[item.state] || '○' }}</span>
      <span class="stage-label">{{ item.label }}</span>
      <span v-if="item.state === 'active'" class="stage-pulse" aria-hidden="true"></span>
    </li>
  </ul>
</template>

<style scoped>
.stages {
  list-style: none;
  margin: 18px auto 6px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(460px, 100%);
  text-align: left;
}

.stages li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13.5px;
  color: var(--text-faint);
  transition: color 0.25s ease;
}

.stage-icon {
  width: 22px;
  text-align: center;
  font-size: 15px;
  color: var(--text-faint);
}

.stage-label {
  flex: 1;
}

.state-active {
  color: var(--text);
}

.state-active .stage-icon {
  color: var(--gold-bright);
}

.state-repairing {
  color: var(--gold-bright);
}

.state-repairing .stage-icon {
  color: var(--gold-bright);
}

.state-done {
  color: var(--text-muted);
}

.state-done .stage-icon {
  color: var(--green);
}

.state-error {
  color: var(--rose);
}

.state-error .stage-icon {
  color: var(--rose);
}

.stage-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--gold);
  animation: pulse 1.1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}
</style>
