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
        'text-margin-y': 7,
        color: '#14232b',
        width: 34,
        height: 34,
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
        label: 'data(type)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 9,
        color: 'data(color)',
        'text-rotation': 'autorotate',
        'text-background-color': '#f2f5f4',
        'text-background-opacity': 0.9,
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
