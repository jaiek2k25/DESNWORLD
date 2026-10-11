/**
 * DESNWORLD theme service — smooth theme switching with persistence.
 */
import { reactive } from 'vue'

export const THEMES = [
  {
    id: 'ivory',
    name: 'Ivory',
    swatch: 'linear-gradient(135deg, #f6e8c8, #c79a3f)',
    description: 'Warm gallery white with bronze grandeur'
  },
  {
    id: 'noir',
    name: 'Noir',
    swatch: 'linear-gradient(135deg, #1b2233, #e8a33d)',
    description: 'Grand midnight with gold light'
  },
  {
    id: 'sage',
    name: 'Sage',
    swatch: 'linear-gradient(135deg, #dfe9cf, #6d8f4e)',
    description: 'Soft botanical calm'
  },
  {
    id: 'rose',
    name: 'Rose',
    swatch: 'linear-gradient(135deg, #f6d9d2, #b06a52)',
    description: 'Blush atelier warmth'
  }
]

const STORAGE_KEY = 'desnworld.theme'

function initialTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && THEMES.some((t) => t.id === saved)) return saved
  } catch {
    /* ignore */
  }
  return 'ivory'
}

export const themeState = reactive({
  current: initialTheme()
})

export function applyTheme(id) {
  const theme = THEMES.find((t) => t.id === id) ? id : 'ivory'
  themeState.current = theme
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* ignore */
  }
}

// ensure the attribute is set even when the pre-paint script missed it
applyTheme(themeState.current)
