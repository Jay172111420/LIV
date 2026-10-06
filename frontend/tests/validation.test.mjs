import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validatePrescription, validateSet } from '../js/validation.js';

const set = (o) => ({ weight: '', reps: '', rpe: '', rir: '', ...o });

test('accepts a normal set and returns kilograms', () => {
  const r = validateSet(set({ weight: '82.5', reps: '8', rpe: '8.5', rir: '1' }));
  assert.equal(r.ok, true);
  assert.deepEqual(r.values, { weight_kg: 82.5, reps: 8, rpe: 8.5, rir: 1 });
});

test('converts pounds to kilograms', () => {
  const r = validateSet(set({ weight: '135', reps: '5' }), { units: 'imperial' });
  assert.equal(r.values.weight_kg, 61.23);
});

test('negative weight and reps are rejected with clear messages', () => {
  const r = validateSet(set({ weight: '-5', reps: '-1' }));
  assert.equal(r.ok, false);
  assert.equal(r.errors.weight, "Weight can't be negative.");
  assert.equal(r.errors.reps, "Reps can't be negative.");
});

test('non-numeric, fractional and absurd values are rejected', () => {
  assert.match(validateSet(set({ weight: 'abc' })).errors.weight, /number/);
  assert.match(validateSet(set({ reps: '2.5' })).errors.reps, /whole number/);
  assert.match(validateSet(set({ weight: '5000' })).errors.weight, /too heavy/);
  assert.match(validateSet(set({ reps: '5000' })).errors.reps, /1000 or fewer/);
});

test('completing a set requires at least one rep', () => {
  assert.match(validateSet(set({ weight: '50' }), { completing: true }).errors.reps, /Enter your reps/);
  assert.match(validateSet(set({ reps: '0' }), { completing: true }).errors.reps, /at least 1 rep/);
  assert.equal(validateSet(set({ reps: '0' })).ok, true); // saving without completing is fine
  assert.equal(validateSet(set({ reps: '1' }), { completing: true }).ok, true);
});

test('bodyweight sets may leave weight empty', () => {
  const r = validateSet(set({ reps: '12' }), { completing: true });
  assert.equal(r.ok, true);
  assert.equal(r.values.weight_kg, null);
});

test('RPE and RIR ranges', () => {
  assert.match(validateSet(set({ rpe: '11' })).errors.rpe, /between 1 and 10/);
  assert.match(validateSet(set({ rpe: '0' })).errors.rpe, /between 1 and 10/);
  assert.match(validateSet(set({ rpe: '7.3' })).errors.rpe, /0\.5/);
  assert.match(validateSet(set({ rir: '-1' })).errors.rir, /between 0 and 10/);
  assert.match(validateSet(set({ rir: '1.5' })).errors.rir, /whole number/);
  assert.equal(validateSet(set({ rpe: '7.5', rir: '2' })).ok, true);
});

test('comma decimals are accepted', () => {
  assert.equal(validateSet(set({ weight: '82,5' })).values.weight_kg, 82.5);
});

test('prescription validation', () => {
  assert.equal(validatePrescription({ sets: 3, repMin: 8, repMax: 12, rest: 90 }).ok, true);
  const bad = validatePrescription({ sets: 0, repMin: 12, repMax: 8, rest: -5 });
  assert.equal(bad.ok, false);
  assert.match(bad.errors.sets, /1 to 10/);
  assert.match(bad.errors.repMax, /lower than min/);
  assert.match(bad.errors.rest, /0 and 600/);
  assert.match(validatePrescription({ sets: 3, repMin: 'x', repMax: 8, rest: 60 }).errors.repMin, /whole number/);
});
