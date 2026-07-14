export const RELATIONSHIP_TYPES = ['depends_on', 'extends', 'used_with', 'replaces']

export const EDGE_COLORS = {
  depends_on: '#b91c1c',
  extends: '#1d4ed8',
  used_with: '#047857',
  replaces: '#b45309',
}

export const CATEGORY_PALETTE = [
  '#0e7490',
  '#7c3aed',
  '#b45309',
  '#15803d',
  '#be185d',
  '#1d4ed8',
  '#a16207',
  '#475569',
]

export const UNCATEGORIZED_COLOR = '#64748b'

// Force-directed layout tuned for spread + overlap avoidance. Reused by the
// initial render and the "re-spread" control.
export const GRAPH_LAYOUT = {
  name: 'fcose',
  quality: 'proof',
  randomize: true,
  animate: true,
  animationDuration: 450,
  fit: true,
  padding: 45,
  nodeRepulsion: 9000,
  idealEdgeLength: 130,
  nodeSeparation: 90,
  packComponents: true,
  gravity: 0.25,
}

export function buildStylesheet() {
  return [
    {
      selector: 'node',
      style: {
        'background-color': 'data(color)',
        label: 'data(name)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 11,
        'text-valign': 'bottom',
        'text-margin-y': 6,
        'text-wrap': 'wrap',
        'text-max-width': '104px',
        color: '#14232b',
        'text-background-color': '#ffffff',
        'text-background-opacity': 0.85,
        'text-background-padding': 3,
        'text-background-shape': 'roundrectangle',
        width: 'data(size)',
        height: 'data(size)',
        'border-width': 2,
        'border-color': '#ffffff',
      },
    },
    {
      selector: 'node[status = "deprecated"]',
      style: {
        shape: 'octagon',
        'background-opacity': 0.55,
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-color': '#14232b',
        'border-width': 3,
      },
    },
    {
      selector: 'edge',
      style: {
        width: 2,
        'line-color': 'data(color)',
        'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.1,
        'curve-style': 'bezier',
        label: '',
        color: 'data(color)',
      },
    },
    // Per-type line style: a non-color cue so relationship types stay
    // distinguishable for color-blind users (depends_on stays solid).
    {
      selector: 'edge[type = "extends"]',
      style: { 'line-style': 'dashed' },
    },
    {
      selector: 'edge[type = "used_with"]',
      style: { 'line-style': 'dotted' },
    },
    {
      selector: 'edge[type = "replaces"]',
      style: { 'line-style': 'dashed', 'line-dash-pattern': [10, 3, 2, 3] },
    },
    {
      selector: 'edge.show-label',
      style: {
        label: 'data(type)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 9,
        'text-rotation': 'autorotate',
        'text-background-color': '#f2f5f4',
        'text-background-opacity': 0.95,
        'text-background-padding': 2,
      },
    },
    {
      selector: '.faded',
      style: {
        opacity: 0.12,
      },
    },
  ]
}
