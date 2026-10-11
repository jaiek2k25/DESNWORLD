<script setup>
import { ref } from 'vue'
import { THEMES, themeState, applyTheme } from '../theme.js'

const open = ref(false)
</script>

<template>
  <div class="theme-switcher">
    <button
      class="theme-toggle"
      type="button"
      :aria-expanded="open"
      aria-label="Choose a theme"
      @click="open = !open"
    >
      <span
        class="theme-dot current"
        :style="{ background: THEMES.find((t) => t.id === themeState.current)?.swatch }"
      ></span>
      <span class="theme-name">{{ THEMES.find((t) => t.id === themeState.current)?.name }}</span>
      <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true" :class="{ flipped: open }">
        <path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" />
      </svg>
    </button>
    <transition name="pop">
      <div v-if="open" class="theme-menu" role="listbox">
        <button
          v-for="theme in THEMES"
          :key="theme.id"
          type="button"
          class="theme-option"
          :class="{ active: themeState.current === theme.id }"
          role="option"
          :aria-selected="themeState.current === theme.id"
          @click="applyTheme(theme.id); open = false"
        >
          <span class="theme-dot" :style="{ background: theme.swatch }"></span>
          <span>
            <span class="theme-option-name">{{ theme.name }}</span>
            <span class="theme-option-desc">{{ theme.description }}</span>
          </span>
        </button>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.theme-switcher {
  position: relative;
}

.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  padding: 7px 13px;
  cursor: pointer;
  color: var(--text);
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  box-shadow: var(--shadow-soft);
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.theme-toggle:hover {
  border-color: var(--gold);
  transform: translateY(-1px);
}

.theme-toggle svg {
  transition: transform 0.2s ease;
}

.theme-toggle svg.flipped {
  transform: rotate(180deg);
}

.theme-dot {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 1px solid var(--border-strong);
  display: inline-block;
  flex: 0 0 auto;
}

.theme-name {
  letter-spacing: 0.06em;
}

.theme-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-panel);
  padding: 7px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 230px;
  z-index: 60;
}

.theme-option {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 11px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-ui);
  transition: background 0.14s ease;
}

.theme-option:hover {
  background: var(--overlay-soft);
}

.theme-option.active {
  background: color-mix(in srgb, var(--gold) 12%, transparent);
}

.theme-option-name {
  display: block;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--text);
}

.theme-option-desc {
  display: block;
  font-size: 11px;
  color: var(--text-faint);
}

.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(-5px) scale(0.98);
}
</style>
