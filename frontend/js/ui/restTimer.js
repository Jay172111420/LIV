// Rest timer. The logic (RestTimer) has no DOM and takes a clock, so it can be tested in Node.
// It stores an absolute end time, so it stays accurate when the tab is throttled or the phone sleeps.
import { h, mount } from '../dom.js';
import { formatDuration } from '../units.js';
import { Button } from './components.js';

const STEP = 15;
const MAX_SECONDS = 60 * 60;

export class RestTimer {
  constructor(now = () => Date.now()) {
    this.now = now;
    this.state = 'idle'; // idle | running | paused | done
    this.endsAt = 0;
    this.remainingMs = 0;
    this.listeners = new Set();
  }

  onChange(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit() { for (const fn of this.listeners) fn(this); }

  /** Seconds left (rounded up so the display reads 00:01 until it truly ends). */
  get remaining() {
    const ms = this.state === 'running' ? this.endsAt - this.now() : this.remainingMs;
    return Math.max(0, Math.ceil(ms / 1000));
  }

  start(seconds) {
    const s = Math.max(1, Math.min(MAX_SECONDS, Math.round(seconds)));
    this.total = s;
    this.remainingMs = s * 1000;
    this.endsAt = this.now() + this.remainingMs;
    this.state = 'running';
    this.emit();
  }

  pause() {
    if (this.state !== 'running') return;
    this.remainingMs = Math.max(0, this.endsAt - this.now());
    this.state = 'paused';
    this.emit();
  }

  resume() {
    if (this.state !== 'paused') return;
    this.endsAt = this.now() + this.remainingMs;
    this.state = 'running';
    this.emit();
  }

  toggle() { if (this.state === 'running') this.pause(); else if (this.state === 'paused') this.resume(); }

  skip() { this.state = 'idle'; this.remainingMs = 0; this.emit(); }

  /** Adds or removes seconds. Never below 0 or above one hour; reaching 0 finishes the rest. */
  adjust(seconds) {
    if (this.state !== 'running' && this.state !== 'paused') return;
    const current = this.state === 'running' ? this.endsAt - this.now() : this.remainingMs;
    const next = Math.max(0, Math.min(MAX_SECONDS * 1000, current + seconds * 1000));
    if (next === 0) { this.finish(); return; }
    if (this.state === 'running') this.endsAt = this.now() + next; else this.remainingMs = next;
    this.emit();
  }

  /** Call on a tick. Moves a running timer to `done` when time is up (listeners fire only then). */
  tick() {
    if (this.state === 'running' && this.endsAt - this.now() <= 0) this.finish();
  }

  finish() { this.state = 'done'; this.remainingMs = 0; this.emit(); }

  dismiss() { this.state = 'idle'; this.emit(); }
}

/** The on-screen rest bar. Returns { el, timer, destroy }. */
export function RestBar(timer = new RestTimer()) {
  const bar = h('section', { class: 'rest-bar', 'aria-label': 'Rest timer', hidden: true });
  const clock = h('output', { class: 'rest-clock', 'aria-live': 'off' });
  const announcer = h('span', { class: 'visually-hidden', role: 'status' });
  const label = h('span', { class: 'rest-label' }, 'REST');
  let interval = null;

  const render = () => {
    const { state } = timer;
    bar.hidden = state === 'idle';
    bar.dataset.state = state;
    if (state === 'idle') { announcer.textContent = ''; return; }
    clock.textContent = formatDuration(timer.remaining);
    label.textContent = state === 'done' ? 'READY' : state === 'paused' ? 'PAUSED' : 'REST';
    const done = state === 'done';
    mount(bar, h('div', { class: 'rest-main' }, label, clock),
      h('div', { class: 'rest-actions' },
        !done && Button(`−${STEP}s`, { variant: 'ghost', size: 'sm', onClick: () => timer.adjust(-STEP) }),
        !done && Button(state === 'paused' ? 'Start' : 'Pause', { variant: 'secondary', size: 'sm', onClick: () => timer.toggle() }),
        !done && Button(`+${STEP}s`, { variant: 'ghost', size: 'sm', onClick: () => timer.adjust(STEP) }),
        Button(done ? 'Next set' : 'Skip', { variant: done ? 'primary' : 'ghost', size: 'sm', onClick: () => (done ? timer.dismiss() : timer.skip()) })),
      announcer);
    if (done) announcer.textContent = 'Rest finished. Time for your next set.';
  };

  const stop = timer.onChange(() => {
    render();
    if (timer.state === 'running' && !interval) interval = setInterval(() => { timer.tick(); if (timer.state === 'running') clock.textContent = formatDuration(timer.remaining); }, 250);
    if (timer.state !== 'running' && interval) { clearInterval(interval); interval = null; }
  });
  timer.onChange((t) => { if (t.state === 'done' && navigator.vibrate) navigator.vibrate([200, 100, 200]); });
  render();

  return { el: bar, timer, destroy: () => { stop(); if (interval) clearInterval(interval); } };
}
