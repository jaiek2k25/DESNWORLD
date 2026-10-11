import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The frontend is a static SPA. `base: './'` keeps asset URLs relative so the
// same build works at the domain root (local dev) and under a GitHub Pages
// project path (https://<user>.github.io/DESNWORLD/) without configuration.
export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // Local dev convenience: forward API calls to the DESNWORLD dev server
      // (`python -m desnworld.server`). GitHub Pages cannot proxy anything —
      // see README "Deployment architecture and limitations".
      '/api': {
        target: `http://127.0.0.1:${process.env.DESNWORLD_PORT || 8787}`,
        changeOrigin: true
      }
    }
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.DESNWORLD_PORT || 8787}`,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false
  }
})
