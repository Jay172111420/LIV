// Validation for set entry. Pure functions (no DOM) so they can be tested in Node.
// Messages are written for the person logging a set, not for developers.
import { lbToKg } from './units.js';

const LIMITS = { weightKg: 1000, reps: 1000, rpe: 10, rir: 10 };

const blank = (v) => v === '' || v === null || v === undefined;

function number(raw) {
  const text = String(raw).trim().replace(',', '.');
  return text !== '' && Number.isFinite(Number(text)) ? Number(text) : NaN;
}

/**
 * Checks one set's raw input strings. Returns { ok, errors: {field: message}, values }.
 * `values.weight_kg` is always kilograms, converted from the user's unit.
 * When `completing` is true, reps are required (a done set needs at least 1 rep).
 */
export function validateSet({ weight, reps, rpe, rir }, { units = 'metric', completing = false } = {}) {
  const errors = {};
  const values = { weight_kg: null, reps: null, rpe: null, rir: null };
  const unit = units === 'imperial' ? 'lb' : 'kg';

  if (!blank(weight)) {
    const w = number(weight);
    if (Number.isNaN(w)) errors.weight = 'Enter the weight as a number.';
    else if (w < 0) errors.weight = "Weight can't be negative.";
    else if ((units === 'imperial' ? lbToKg(w) : w) > LIMITS.weightKg) errors.weight = `That's too heavy. Enter a weight under ${units === 'imperial' ? 2200 : 1000} ${unit}.`;
    else values.weight_kg = Math.round((units === 'imperial' ? lbToKg(w) : w) * 100) / 100;
  }

  if (blank(reps)) {
    if (completing) errors.reps = 'Enter your reps before completing the set.';
  } else {
    const r = number(reps);
    if (Number.isNaN(r)) errors.reps = 'Enter reps as a whole number.';
    else if (!Number.isInteger(r)) errors.reps = 'Reps must be a whole number.';
    else if (r < 0) errors.reps = "Reps can't be negative.";
    else if (r > LIMITS.reps) errors.reps = `Reps must be ${LIMITS.reps} or fewer.`;
    else if (completing && r < 1) errors.reps = 'A completed set needs at least 1 rep.';
    else values.reps = r;
  }

  if (!blank(rpe)) {
    const v = number(rpe);
    if (Number.isNaN(v)) errors.rpe = 'Enter RPE as a number from 1 to 10.';
    else if (v < 1 || v > LIMITS.rpe) errors.rpe = 'RPE must be between 1 and 10.';
    else if (v * 2 !== Math.floor(v * 2)) errors.rpe = 'RPE goes in steps of 0.5.';
    else values.rpe = v;
  }

  if (!blank(rir)) {
    const v = number(rir);
    if (Number.isNaN(v) || !Number.isInteger(v)) errors.rir = 'Enter RIR as a whole number.';
    else if (v < 0 || v > LIMITS.rir) errors.rir = 'RIR must be between 0 and 10.';
    else values.rir = v;
  }

  return { ok: Object.keys(errors).length === 0, errors, values };
}

/** Checks a plan-exercise prescription. Values are raw strings or numbers. */
export function validatePrescription({ sets, repMin, repMax, rest }) {
  const errors = {};
  const int = (v) => { const n = number(v); return Number.isInteger(n) ? n : NaN; };
  const s = int(sets); const lo = int(repMin); const hi = int(repMax); const r = int(rest);
  if (Number.isNaN(s) || s < 1 || s > 10) errors.sets = 'Sets must be a whole number from 1 to 10.';
  if (Number.isNaN(lo) || lo < 1 || lo > 300) errors.repMin = 'Min reps must be a whole number from 1 to 300.';
  if (Number.isNaN(hi) || hi < 1 || hi > 300) errors.repMax = 'Max reps must be a whole number from 1 to 300.';
  if (!errors.repMin && !errors.repMax && hi < lo) errors.repMax = "Max reps can't be lower than min reps.";
  if (Number.isNaN(r) || r < 0 || r > 600) errors.rest = 'Rest must be between 0 and 600 seconds.';
  return {
    ok: Object.keys(errors).length === 0, errors,
    values: { sets: s, rep_min: lo, rep_max: hi, rest_seconds: r },
  };
}
