import assert from 'node:assert/strict';
import { test } from 'node:test';
import { RestTimer } from '../js/ui/restTimer.js';

function make() {
  let t = 1_000_000;
  const timer = new RestTimer(() => t);
  return { timer, advance: (s) => { t += s * 1000; timer.tick(); } };
}

test('counts down from the starting value', () => {
  const { timer, advance } = make();
  timer.start(90);
  assert.equal(timer.state, 'running');
  assert.equal(timer.remaining, 90);
  advance(30);
  assert.equal(timer.remaining, 60);
});

test('finishes when time runs out', () => {
  const { timer, advance } = make();
  timer.start(10);
  advance(10);
  assert.equal(timer.state, 'done');
  assert.equal(timer.remaining, 0);
});

test('pause freezes the clock and resume continues', () => {
  const { timer, advance } = make();
  timer.start(60);
  advance(20);
  timer.pause();
  assert.equal(timer.state, 'paused');
  advance(100);
  assert.equal(timer.remaining, 40);
  timer.resume();
  advance(15);
  assert.equal(timer.remaining, 25);
});

test('toggle switches between pause and resume', () => {
  const { timer } = make();
  timer.start(60);
  timer.toggle(); assert.equal(timer.state, 'paused');
  timer.toggle(); assert.equal(timer.state, 'running');
});

test('add and subtract 15 seconds, running or paused', () => {
  const { timer, advance } = make();
  timer.start(60);
  timer.adjust(15); assert.equal(timer.remaining, 75);
  timer.adjust(-15); timer.adjust(-15); assert.equal(timer.remaining, 45);
  advance(5);
  timer.pause();
  timer.adjust(15); assert.equal(timer.remaining, 55);
  timer.resume();
  advance(5);
  assert.equal(timer.remaining, 50);
});

test('subtracting past zero ends the rest; adding is capped at an hour', () => {
  const { timer } = make();
  timer.start(10);
  timer.adjust(-15);
  assert.equal(timer.state, 'done');
  timer.start(3590);
  timer.adjust(15);
  assert.equal(timer.remaining, 3600);
});

test('skip ends the rest immediately and can be restarted', () => {
  const { timer } = make();
  timer.start(60);
  timer.skip();
  assert.equal(timer.state, 'idle');
  assert.equal(timer.remaining, 0);
  timer.start(45);
  assert.equal(timer.remaining, 45);
});

test('adjust does nothing when idle, and start clamps nonsense values', () => {
  const { timer } = make();
  timer.adjust(15);
  assert.equal(timer.state, 'idle');
  timer.start(-20);
  assert.equal(timer.remaining, 1);
  timer.start(99999);
  assert.equal(timer.remaining, 3600);
});

test('listeners are told about state changes', () => {
  const { timer } = make();
  const seen = [];
  const off = timer.onChange((t) => seen.push(t.state));
  timer.start(5); timer.pause(); timer.resume(); timer.skip();
  off();
  timer.start(5);
  assert.deepEqual(seen, ['running', 'paused', 'running', 'idle']);
});
