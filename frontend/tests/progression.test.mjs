import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  actionLabel, barHeights, canAct, choiceText, formatSetList, parseEdit, recommendationTarget, recordText, sparkline, trendText,
} from '../js/progression.js';

const rec = (o = {}) => ({ weight_kg: 82.5, rep_min: 8, rep_max: 10, reps_goal: 8, sets: 3, ...o });

test('formats the last session the way the spec shows it', () => {
  const sets = [{ weight_kg: 80, reps: 10 }, { weight_kg: 80, reps: 10 }, { weight_kg: 80, reps: 10 }];
  assert.equal(formatSetList(sets, 'metric'), '80 kg × 10 / 10 / 10');
});

test('formats mixed weights, bodyweight and timed sets', () => {
  assert.equal(formatSetList([{ weight_kg: 80, reps: 8 }, { weight_kg: 75, reps: 10 }], 'metric'), '80 kg × 8 · 75 kg × 10');
  assert.equal(formatSetList([{ weight_kg: null, reps: 20 }, { weight_kg: null, reps: 18 }], 'metric'), '20 / 18 reps');
  assert.equal(formatSetList([{ weight_kg: null, reps: 30 }], 'metric', true), '30 sec');
  assert.equal(formatSetList([], 'metric'), '');
});

test('shows pounds for imperial users', () => {
  assert.equal(formatSetList([{ weight_kg: 61.23, reps: 5 }], 'imperial'), '135 lb × 5');
});

test('recommendation target shows weight, rep range and sets', () => {
  assert.deepEqual(recommendationTarget(rec(), 'metric'), { weight: '82.5 kg', reps: '8–10 reps', sets: '3 sets', goal: 'Aim for 8+ on every set' });
  const t = recommendationTarget(rec({ weight_kg: null, reps_goal: null, sets: 1, rep_min: 30, rep_max: 60 }), 'metric', true);
  assert.deepEqual(t, { weight: null, reps: '30–60 sec', sets: '1 set', goal: null });
});

test('only recommendations with something concrete can be accepted', () => {
  assert.equal(canAct(rec()), true);
  assert.equal(canAct(rec({ weight_kg: null, reps_goal: 9 })), true);
  assert.equal(canAct(rec({ weight_kg: null, reps_goal: null })), false);
});

test('labels', () => {
  assert.equal(actionLabel('increase_weight'), 'Add weight');
  assert.equal(actionLabel('nope'), 'Suggestion');
  assert.match(choiceText('ignored'), /ignore/);
  assert.equal(choiceText('pending'), '');
});

test('edit parsing converts to kilograms and requires something', () => {
  assert.deepEqual(parseEdit({ weight: '81', reps: '9' }, 'metric'), { ok: true, errors: {}, payload: { choice: 'edited', weight_kg: 81, reps: 9 } });
  assert.equal(parseEdit({ weight: '135', reps: '' }, 'imperial').payload.weight_kg, 61.23);
  assert.equal(parseEdit({ weight: '', reps: '' }, 'metric').errors.form, 'Enter a weight or reps to use instead.');
  assert.equal(parseEdit({ weight: '', reps: '12' }, 'metric').payload.weight_kg, undefined);
});

test('edit parsing rejects bad numbers', () => {
  assert.match(parseEdit({ weight: 'abc', reps: '' }, 'metric').errors.weight, /number/);
  assert.match(parseEdit({ weight: '-1', reps: '' }, 'metric').errors.weight, /negative/);
  assert.match(parseEdit({ weight: '5000', reps: '' }, 'metric').errors.weight, /too heavy/);
  assert.match(parseEdit({ weight: '', reps: '2.5' }, 'metric').errors.reps, /whole/);
  assert.match(parseEdit({ weight: '', reps: '0' }, 'metric').errors.reps, /at least 1/);
  assert.match(parseEdit({ weight: '', reps: '5000' }, 'metric').errors.reps, /1000/);
});

test('bodyweight edits ignore the weight field', () => {
  const r = parseEdit({ weight: '50', reps: '12' }, 'metric', { allowWeight: false });
  assert.equal(r.payload.weight_kg, undefined);
  assert.equal(r.payload.reps, 12);
});

test('PR text matches the spec example', () => {
  assert.equal(recordText({ record_type: 'weight', exercise_name: 'Bench Press', weight_kg: 82.5, reps: 8, value: 82.5 }, 'metric'), 'Bench Press — 82.5 kg × 8');
  assert.equal(recordText({ record_type: 'reps', exercise_name: 'Push-up', weight_kg: null, reps: 22, value: 22 }, 'metric'), 'Push-up — 22 reps');
  assert.equal(recordText({ record_type: 'reps', exercise_name: 'Bench Press', weight_kg: 80, reps: 11, value: 11 }, 'metric'), 'Bench Press — 11 reps at 80 kg');
  assert.equal(recordText({ record_type: 'volume', exercise_name: 'Squat', weight_kg: null, reps: null, value: 3200 }, 'metric'), 'Squat — 3200 kg in one workout');
});

test('trend text', () => {
  assert.equal(trendText({ direction: 'improving', percent_change: 4.2 }), 'Trending up (+4.2%)');
  assert.equal(trendText({ direction: 'declining', percent_change: -6 }), 'Trending down (-6%)');
  assert.match(trendText({ direction: 'insufficient_data', percent_change: null }), /Not enough/);
});

test('sparkline geometry stays inside the box', () => {
  const { coords } = sparkline([10, 20, 15], 100, 40, 5);
  assert.equal(coords.length, 3);
  for (const c of coords) { assert.ok(c.x >= 5 && c.x <= 95); assert.ok(c.y >= 5 && c.y <= 35); }
  assert.ok(coords[1].y < coords[0].y); // higher value is drawn higher up
  assert.equal(sparkline([], 100, 40).points, '');
  assert.equal(sparkline([7], 100, 40).coords[0].x, 50);
  assert.ok(Number.isFinite(sparkline([5, 5, 5], 100, 40).coords[0].y)); // flat data does not divide by zero
});

test('bar heights scale to the largest value and handle all zeros', () => {
  assert.deepEqual(barHeights([0, 50, 100], 40), [0, 20, 40]);
  assert.deepEqual(barHeights([0, 0], 40), [0, 0]);
});
