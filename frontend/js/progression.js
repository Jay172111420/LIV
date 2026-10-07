// Pure helpers for Phase 2 screens: formatting recommendations, parsing edits, chart geometry.
// No DOM here, so all of it is unit-tested under Node.
import { formatReps, formatWeight, lbToKg } from './units.js';

const round = (n, places = 1) => Number(n.toFixed(places));

export const ACTION_LABELS = {
  start: 'First time',
  increase_weight: 'Add weight',
  increase_reps: 'Add reps',
  maintain: 'Keep the weight',
  hold: 'Hold steady',
  reduce_weight: 'Go a little lighter',
  deload: 'Lighter week',
};

export const STRATEGY_LABELS = {
  auto: 'Automatic',
  double_progression: 'Double progression (reps, then weight)',
  weight_progression: 'Weight progression (fixed reps)',
  rep_progression: 'Rep progression (bodyweight)',
  hold: 'Hold (no progression)',
};

export const RECORD_LABELS = { weight: 'Weight PR', reps: 'Rep PR', volume: 'Volume PR' };

export const actionLabel = (action) => ACTION_LABELS[action] || 'Suggestion';

/** True when there is something concrete to accept (a weight or a rep target). */
export const canAct = (rec) => rec.weight_kg != null || rec.reps_goal != null;

/** "80 kg × 10 / 10 / 10", "20 / 18 / 15 reps", or each set when weights differ. */
export function formatSetList(sets, units, timed = false) {
  if (!sets || sets.length === 0) return '';
  const suffix = timed ? ' sec' : '';
  const weights = sets.map((s) => s.weight_kg ?? null);
  const reps = sets.map((s) => s.reps);
  if (weights.every((w) => w === null)) return `${reps.join(' / ')}${timed ? ' sec' : ' reps'}`;
  if (weights.every((w) => w === weights[0])) return `${formatWeight(weights[0], units)} × ${reps.join(' / ')}${suffix}`;
  return sets.map((s) => (s.weight_kg == null ? `${s.reps}${suffix}` : `${formatWeight(s.weight_kg, units)} × ${s.reps}${suffix}`)).join(' · ');
}

/** The numbers shown under "Recommended today". */
export function recommendationTarget(rec, units, timed = false) {
  const reps = formatReps(rec.rep_min, rec.rep_max, timed);
  return {
    weight: rec.weight_kg == null ? null : formatWeight(rec.weight_kg, units),
    reps: timed ? reps : `${reps} reps`,
    sets: `${rec.sets} ${rec.sets === 1 ? 'set' : 'sets'}`,
    goal: rec.reps_goal == null ? null : `Aim for ${rec.reps_goal}${timed ? ' sec' : '+'} on every set`,
  };
}

const CHOICE_TEXT = { accepted: 'You used this suggestion.', edited: 'You adjusted this suggestion.', ignored: 'You chose to ignore this suggestion.' };
export const choiceText = (choice) => CHOICE_TEXT[choice] || '';

/**
 * Validates the edit form. `input` holds raw strings in the user's units; the payload is metric.
 * At least one of weight or reps is required.
 */
export function parseEdit({ weight, reps }, units, { allowWeight = true } = {}) {
  const errors = {};
  const payload = { choice: 'edited' };
  const w = String(weight ?? '').trim();
  const r = String(reps ?? '').trim();
  if (allowWeight && w !== '') {
    const n = Number(w);
    if (!Number.isFinite(n)) errors.weight = 'Enter weight as a number.';
    else if (n < 0) errors.weight = "Weight can't be negative.";
    else {
      const kg = units === 'imperial' ? round(lbToKg(n), 2) : round(n, 2);
      if (kg > 1000) errors.weight = 'That is too heavy to log.';
      else payload.weight_kg = kg;
    }
  }
  if (r !== '') {
    const n = Number(r);
    if (!Number.isInteger(n)) errors.reps = 'Reps must be a whole number.';
    else if (n < 1) errors.reps = 'Reps must be at least 1.';
    else if (n > 1000) errors.reps = 'Reps must be 1000 or fewer.';
    else payload.reps = n;
  }
  if (!errors.weight && !errors.reps && payload.weight_kg === undefined && payload.reps === undefined) {
    errors.form = 'Enter a weight or reps to use instead.';
  }
  return { ok: Object.keys(errors).length === 0, errors, payload };
}

/** "Bench Press — 82.5 kg × 8" style text for a PR event. */
export function recordText(record, units, timed = false) {
  const set = record.weight_kg != null
    ? `${formatWeight(record.weight_kg, units)} × ${record.reps ?? ''}`.trim()
    : `${record.reps ?? ''}${timed ? ' sec' : ' reps'}`.trim();
  if (record.record_type === 'volume') return `${record.exercise_name} — ${formatWeight(record.value, units)} in one workout`;
  if (record.record_type === 'reps' && record.weight_kg != null) return `${record.exercise_name} — ${record.reps} reps at ${formatWeight(record.weight_kg, units)}`;
  return `${record.exercise_name} — ${set}`;
}

export function trendText(trend) {
  const pct = trend.percent_change == null ? '' : ` (${trend.percent_change > 0 ? '+' : ''}${trend.percent_change}%)`;
  switch (trend.direction) {
    case 'improving': return `Trending up${pct}`;
    case 'declining': return `Trending down${pct}`;
    case 'steady': return `Holding steady${pct}`;
    default: return 'Not enough sessions for a trend yet';
  }
}

/** Points for an SVG polyline inside a width × height box with padding. */
export function sparkline(values, width, height, pad = 8) {
  if (!values.length) return { points: '', coords: [] };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;
  const coords = values.map((v, i) => ({
    x: round(values.length > 1 ? pad + i * step : width / 2, 1),
    y: round(height - pad - ((v - min) / span) * (height - pad * 2), 1),
  }));
  return { points: coords.map((c) => `${c.x},${c.y}`).join(' '), coords };
}

/** Bar heights (0..height) scaled to the largest value. */
export function barHeights(values, height) {
  const max = Math.max(0, ...values);
  return values.map((v) => (max === 0 ? 0 : round((v / max) * height, 1)));
}

export function shortDate(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}
