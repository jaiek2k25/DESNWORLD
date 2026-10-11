<script setup>
import { computed } from 'vue'
import { store, selectScenario, selectedScenario } from '../store.js'
import { stanceClass, STANCE_LABELS } from '../lib/report.js'

/**
 * Layout: the question fans out to the baseline and three alternative
 * branches; expanded sub-branches fan out further. Hand-rolled layout (no
 * charting library): depth-first leaf packing with bezier links.
 */
const PALETTE = {
  root: '#e8a33d',
  baseline: '#e8a33d',
  'alt-1': '#5ec8d8',
  'alt-2': '#e06b7b',
  'alt-3': '#b48be0'
}

function branchColor(node, fallback) {
  if (!node) return fallback
  if (PALETTE[node.id]) return PALETTE[node.id]
  // inherit from the top-level ancestor id prefix (alt-1.c2 → alt-1)
  const rootId = String(node.id).split('.')[0]
  return PALETTE[rootId] || fallback
}

const V_GAP = 116
const H_STEP = 310
const NODE_R = 26

const layout = computed(() => {
  const report = store.report
  if (!report) return null

  const nodes = []
  const links = []
  let leafIndex = 0

  const question = report.request?.question || 'Question'
  const root = {
    id: '__root__',
    label: question.length > 46 ? question.slice(0, 46) + '…' : question,
    fullLabel: question,
    depth: 0,
    x: 170,
    y: 0,
    color: PALETTE.root,
    isRoot: true,
    stance: null
  }

  function place(node, depth, parent, color) {
    const entry = {
      id: node.id,
      label: node.title || node.id,
      fullLabel: node.title || node.id,
      depth,
      x: 170 + depth * H_STEP,
      y: 0,
      color,
      isRoot: false,
      stance: node.stance?.qualitative || 'plausible',
      hasChildren: (node.children || []).length > 0,
      node
    }
    const children = node.children || []
    if (children.length) {
      const ys = children.map((child) =>
        place(child, depth + 1, entry, branchColor(child, color))
      )
      entry.y = ys.reduce((a, b) => a + b, 0) / ys.length
    } else {
      entry.y = 90 + leafIndex * V_GAP
      leafIndex += 1
    }
    nodes.push(entry)
    if (parent) {
      links.push({
        key: `${parent.id}->${entry.id}`,
        x1: parent.x + NODE_R,
        y1: parent.y,
        x2: entry.x - NODE_R,
        y2: entry.y,
        color
      })
    }
    return entry.y
  }

  const topNodes = [report.baseline, ...(report.alternatives || [])].filter(Boolean)
  const rootYs = topNodes.map((n) => place(n, 1, root, branchColor(n, PALETTE.root)))
  root.y = rootYs.reduce((a, b) => a + b, 0) / (rootYs.length || 1)
  nodes.push(root)

  const maxDepth = Math.max(...nodes.map((n) => n.depth), 1)
  const width = 170 + (maxDepth + 1) * H_STEP + 120
  const height = 90 + Math.max(leafIndex, 1) * V_GAP + 60

  // draw links first (under nodes)
  links.sort((a, b) => (a.y1 + a.y2) - (b.y1 + b.y2))

  return { nodes, links, width, height }
})

function linkPath(link) {
  const dx = (link.x2 - link.x1) * 0.5
  return `M ${link.x1} ${link.y1} C ${link.x1 + dx} ${link.y1}, ${link.x2 - dx} ${link.y2}, ${link.x2} ${link.y2}`
}

function isSelected(id) {
  return id === '__root__' ? false : store.selectedScenarioId === id
}

function nodeLabel(node) {
  const text = node.label || ''
  return text.length > 26 ? text.slice(0, 25) + '…' : text
}

function onClick(node) {
  if (node.isRoot) return
  selectScenario(node.id)
}

// decorative starfield (deterministic)
const STARS = Array.from({ length: 42 }, (_, i) => ({
  x: (i * 167 + 40) % 1600,
  y: (i * 211 + 60) % 900,
  r: (i % 3) * 0.6 + 0.6,
  o: 0.08 + (i % 4) * 0.05
}))
</script>

<template>
  <div class="tree-shell panel">
    <div class="tree-head">
      <div>
        <div class="eyebrow">Scenario tree</div>
        <div class="faint">
          Click any branch to inspect its assumptions, triggers and consequences. Baseline fans to three
          alternatives; each can be expanded into sub-branches.
        </div>
      </div>
      <div class="legend">
        <span class="legend-item" v-for="(label, key) in { baseline: 'Baseline', 'alt-1': 'Alt 1', 'alt-2': 'Alt 2', 'alt-3': 'Alt 3' }" :key="key">
          <span class="swatch" :style="{ background: PALETTE[key] }"></span>{{ label }}
        </span>
      </div>
    </div>

    <div v-if="layout" class="tree-scroll">
      <svg
        class="tree-svg"
        :viewBox="`0 0 ${layout.width} ${layout.height}`"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Scenario tree"
      >
        <defs>
          <radialGradient id="nodeGlow" cx="50%" cy="40%" r="65%">
            <stop offset="0%" stop-color="rgba(255,255,255,0.24)" />
            <stop offset="100%" stop-color="rgba(255,255,255,0.02)" />
          </radialGradient>
          <filter id="softGlow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="7" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g aria-hidden="true">
          <circle
            v-for="(s, i) in STARS"
            :key="'s' + i"
            :cx="s.x"
            :cy="s.y"
            :r="s.r"
            fill="#f2ede3"
            :opacity="s.o"
          />
        </g>

        <!-- links -->
        <g>
          <path
            v-for="link in layout.links"
            :key="link.key"
            :d="linkPath(link)"
            fill="none"
            :stroke="link.color"
            stroke-width="2.4"
            stroke-opacity="0.5"
            stroke-linecap="round"
          />
        </g>

        <!-- nodes -->
        <g
          v-for="node in layout.nodes"
          :key="node.id"
          class="node-group"
          :class="{ selectable: !node.isRoot, selected: isSelected(node.id) }"
          :tabindex="node.isRoot ? -1 : 0"
          role="button"
          :aria-label="`${node.fullLabel} — open details`"
          @click="onClick(node)"
          @keydown.enter.prevent="onClick(node)"
          @keydown.space.prevent="onClick(node)"
        >
          <circle
            v-if="isSelected(node.id)"
            :cx="node.x"
            :cy="node.y"
            :r="NODE_R + 10"
            :fill="'none'"
            :stroke="node.color"
            stroke-width="1.6"
            stroke-opacity="0.55"
            filter="url(#softGlow)"
          />
          <circle
            :cx="node.x"
            :cy="node.y"
            :r="NODE_R"
            :fill="'url(#nodeGlow)'"
            :stroke="node.color"
            :stroke-width="isSelected(node.id) ? 3.4 : 2.2"
            :filter="isSelected(node.id) ? 'url(#softGlow)' : undefined"
          />
          <circle :cx="node.x" :cy="node.y" :r="10" :fill="node.color" :opacity="node.isRoot ? 0.9 : 0.85" />

          <text
            class="node-label"
            :x="node.x"
            :y="node.y + NODE_R + 22"
            text-anchor="middle"
            :fill="isSelected(node.id) ? '#f2ede3' : '#c8cfdd'"
          >
            {{ nodeLabel(node) }}
          </text>
          <text
            v-if="!node.isRoot && node.stance"
            class="node-sub"
            :x="node.x"
            :y="node.y + NODE_R + 38"
            text-anchor="middle"
            :fill="node.color"
            opacity="0.85"
          >
            {{ STANCE_LABELS[node.stance] || node.stance }}
          </text>
          <g v-if="node.hasChildren">
            <text class="node-sub" :x="node.x" :y="node.y - NODE_R - 10" text-anchor="middle" :fill="node.color" opacity="0.8">
              {{ (node.node.children || []).length }} sub-branches
            </text>
          </g>
        </g>
      </svg>
    </div>

    <div class="tree-footnote faint">
      Branches are conditional possibilities distinguished by their triggers — thickness and placement
      carry no probability meaning. Stances are qualitative only.
    </div>
  </div>
</template>

<style scoped>
.tree-shell {
  padding: 18px 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tree-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  flex-wrap: wrap;
}

.legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--text-muted);
}

.swatch {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.tree-scroll {
  overflow: auto;
  border-radius: var(--radius-md);
  background:
    radial-gradient(700px 320px at 20% 0%, rgba(232, 163, 61, 0.05), transparent 60%),
    rgba(8, 12, 22, 0.35);
  border: 1px solid var(--border);
}

.tree-svg {
  display: block;
  width: 100%;
  min-width: 680px;
  height: auto;
  min-height: 420px;
}

.node-group {
  cursor: default;
}

.node-group.selectable {
  cursor: pointer;
}

.node-group:focus {
  outline: none;
}

.node-group:focus-visible circle {
  stroke: var(--gold-bright);
}

.node-label {
  font-family: var(--font-ui);
  font-size: 13.5px;
  font-weight: 600;
  pointer-events: none;
}

.node-sub {
  font-family: var(--font-ui);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  pointer-events: none;
}

.tree-footnote {
  padding: 2px 6px 6px;
}
</style>
