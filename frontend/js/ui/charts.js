// Tiny SVG charts. Drawn with presentation attributes only (no inline styles), so they work under the CSP.
import { barHeights, sparkline } from '../progression.js';

const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const c of children) node.append(typeof c === 'string' ? document.createTextNode(c) : c);
  return node;
};

/** Line chart of one value per session. `label` is read by screen readers. */
export function Sparkline(values, { label, width = 320, height = 110 } = {}) {
  const svg = el('svg', { class: 'chart', viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': label || 'Trend chart', preserveAspectRatio: 'none' });
  const { points, coords } = sparkline(values, width, height, 10);
  if (coords.length > 1) svg.append(el('polyline', { class: 'chart-line', points, fill: 'none', 'stroke-width': 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
  coords.forEach((c, i) => svg.append(el('circle', { class: i === coords.length - 1 ? 'chart-dot chart-dot-last' : 'chart-dot', cx: c.x, cy: c.y, r: i === coords.length - 1 ? 5 : 3.5 })));
  return svg;
}

/** Bar chart. items: [{ label, value }]. */
export function BarChart(items, { label, height = 120 } = {}) {
  const width = Math.max(items.length * 44, 120);
  const svg = el('svg', { class: 'chart', viewBox: `0 0 ${width} ${height + 22}`, role: 'img', 'aria-label': label || 'Bar chart' });
  const heights = barHeights(items.map((i) => i.value), height);
  items.forEach((item, i) => {
    const x = i * 44 + 8;
    const bar = heights[i];
    svg.append(
      el('rect', { class: bar ? 'chart-bar' : 'chart-bar chart-bar-empty', x, y: height - Math.max(bar, 2), width: 28, height: Math.max(bar, 2), rx: 6 }),
      el('text', { class: 'chart-label', x: x + 14, y: height + 16, 'text-anchor': 'middle' }, item.label));
  });
  return svg;
}
