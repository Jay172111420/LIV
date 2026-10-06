// The API stores metric values only. These helpers convert for display and input.
const KG_PER_LB = 0.45359237;
const CM_PER_IN = 2.54;

export const kgToLb = (kg) => kg / KG_PER_LB;
export const lbToKg = (lb) => lb * KG_PER_LB;
export const cmToIn = (cm) => cm / CM_PER_IN;
export const inToCm = (inches) => inches * CM_PER_IN;
export const ftInToCm = (ft, inches) => (ft * 12 + inches) * CM_PER_IN;

export function cmToFtIn(cm) {
  const totalIn = Math.round(cm / CM_PER_IN);
  return { ft: Math.floor(totalIn / 12), inches: totalIn % 12 };
}

const round = (n, places = 1) => Number(n.toFixed(places));

export function formatWeight(kg, units) {
  if (kg == null) return '—';
  return units === 'imperial' ? `${round(kgToLb(kg))} lb` : `${round(kg)} kg`;
}

export function formatHeight(cm, units) {
  if (cm == null) return '—';
  if (units === 'imperial') { const { ft, inches } = cmToFtIn(cm); return `${ft} ft ${inches} in`; }
  return `${round(cm)} cm`;
}

export function formatMetric(metric, units) {
  if (metric.unit === 'kg') return formatWeight(metric.value, units);
  if (metric.unit === 'cm' && units === 'imperial') return `${round(cmToIn(metric.value))} in`;
  return `${round(metric.value)} ${metric.unit}`;
}

export function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function labelFor(value) {
  return String(value).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

/** Weight shown in the user's unit, tidy for inputs: 82.5, or 135 lb for 61.23 kg. */
export function weightToDisplay(kg, units) {
  if (kg == null) return '';
  return String(Number((units === 'imperial' ? kgToLb(kg) : kg).toFixed(1)));
}

export const weightUnit = (units) => (units === 'imperial' ? 'lb' : 'kg');

export function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/** "8", "8–10", or "30–60 sec" for timed exercises. */
export function formatReps(min, max, timed = false) {
  const range = min === max ? `${min}` : `${min}–${max}`;
  return timed ? `${range} sec` : range;
}

export function formatRest(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}
