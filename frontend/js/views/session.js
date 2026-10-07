// The workout screen. Built for speed: every set of every exercise is visible and editable in place,
// and one tap on the check completes a set and starts the rest timer.
import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { navigate } from '../router.js';
import { state } from '../store.js';
import { formatReps, formatRest, weightToDisplay, weightUnit } from '../units.js';
import { validateSet } from '../validation.js';
import { Alert, Button, ErrorState, Loading, confirmModal } from '../ui/components.js';
import { RecommendationCard } from '../ui/recommendation.js';
import { RestBar, RestTimer } from '../ui/restTimer.js';

const DEFAULT_REST = 90;

const clock = (seconds) => {
  const s = Math.max(0, Math.floor(seconds));
  const hrs = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return hrs ? `${hrs}:${mm}:${ss}` : `${mm}:${ss}`;
};

export function renderSession(root, { id }) {
  const units = state.profile.unit_preference;
  const unit = weightUnit(units);
  const timer = new RestTimer();
  const restBar = RestBar(timer);
  let session = null;
  let ticker = null;
  const cleanup = () => { if (ticker) clearInterval(ticker); restBar.destroy(); };

  const banner = h('div', { 'aria-live': 'polite' });
  const progress = h('div', { class: 'session-progress' });
  const elapsed = h('output', { class: 'elapsed', 'aria-label': 'Elapsed time' });
  const list = h('div', { class: 'stack' });
  const cards = new Map(); // workout_exercise id -> element

  mount(root, Loading('Opening workout'));
  load();
  return cleanup;

  async function load() {
    try { session = await api.session(id); } catch (e) {
      mount(root, e.status === 404
        ? h('div', { class: 'stack' }, h('a', { class: 'back-link', href: '#/workout' }, '← Workout'), h('p', {}, 'That workout no longer exists.'))
        : ErrorState(e.message, load));
      return;
    }
    if (session.status !== 'in_progress') { navigate(`/workout/history/${session.id}`); return; }
    draw();
  }

  // ---------------------------------------------------------------- layout
  function flash(message) { mount(banner, Alert(message)); banner.scrollIntoView?.({ block: 'nearest' }); }

  function draw() {
    const start = new Date(session.started_at).getTime();
    const tick = () => { elapsed.textContent = clock((Date.now() - start) / 1000); };
    tick();
    ticker = setInterval(tick, 1000);
    mount(root, h('div', { class: 'session' },
      h('div', { class: 'session-head' },
        h('div', {}, h('a', { class: 'back-link', href: '#/workout' }, '← Workout'), h('h1', {}, session.name || 'Workout'), elapsed),
        h('div', { class: 'row-actions' },
          Button('Discard', { variant: 'ghost', size: 'sm', onClick: discard }),
          Button('Finish', { size: 'sm', onClick: finish }))),
      progress, banner, list, restBar.el));
    session.exercises.forEach((we) => { const el = exerciseCard(we); cards.set(we.id, el); list.append(el); });
    updateProgress();
  }

  function allSets() { return session.exercises.flatMap((e) => e.sets); }
  function updateProgress() {
    const done = allSets().filter((s) => s.is_completed).length;
    const total = allSets().length;
    const meter = h('div', { class: 'meter', role: 'progressbar', 'aria-label': 'Sets completed', 'aria-valuemin': 0, 'aria-valuemax': total, 'aria-valuenow': done }, h('i'));
    meter.style.setProperty('--value', String(total ? (done / total) * 100 : 0)); // CSSOM, so it works under the page's CSP
    mount(progress, meter, h('small', {}, `${done} of ${total} sets done`));
  }

  // ---------------------------------------------------------------- exercise card
  function exerciseCard(we) {
    const ex = we.exercise;
    const first = we.sets[0];
    const target = first && first.target_reps_min ? `${we.sets.length} × ${formatReps(first.target_reps_min, first.target_reps_max, ex.is_timed)}` : `${we.sets.length} sets`;
    return h('section', { class: 'exercise-card', 'aria-label': ex.name },
      h('div', { class: 'exercise-head' },
        h('div', {}, h('h2', {}, ex.name),
          h('small', {}, `${ex.primary_muscle_group.name} · target ${target} · rest ${formatRest(we.rest_seconds ?? DEFAULT_REST)}`)),
        ex.instructions && h('details', { class: 'how' }, h('summary', {}, 'How'), h('p', {}, ex.instructions))),
      we.recommendation && RecommendationCard({
        rec: we.recommendation, units, timed: ex.is_timed,
        onRespond: async (body) => { adopt(await api.respondToRecommendation(session.id, we.id, body)); redrawCard(weOf(we.id)); updateProgress(); },
      }),
      h('div', { class: 'set-table' },
        h('div', { class: 'set-labels', 'aria-hidden': 'true' }, h('span', {}, 'Set'), h('span', {}, unit), h('span', {}, ex.is_timed ? 'Sec' : 'Reps'), h('span'), h('span')),
        we.sets.map((set, i) => setRow(we, set, i + 1))),
      h('div', { class: 'exercise-foot' }, Button('Add set', { variant: 'ghost', size: 'sm', onClick: () => addSet(we) })));
  }

  function redrawCard(we) {
    const next = exerciseCard(we);
    cards.get(we.id).replaceWith(next);
    cards.set(we.id, next);
  }

  // Replace the local copy from a server response without touching the DOM.
  function adopt(updated) {
    session = updated;
  }
  function weOf(weId) { return session.exercises.find((e) => e.id === weId); }

  async function addSet(we) {
    mount(banner, null);
    try { adopt(await api.addSet(session.id, we.id)); redrawCard(weOf(we.id)); updateProgress(); } catch (e) { flash(e.message); }
  }

  async function removeSet(we, set) {
    mount(banner, null);
    try { adopt(await api.deleteSet(session.id, we.id, set.id)); redrawCard(weOf(we.id)); updateProgress(); } catch (e) { flash(e.message); }
  }

  // ---------------------------------------------------------------- one set
  function setRow(we, set, number) {
    const ex = we.exercise;
    let current = set; // latest server copy of this set
    const num = (name, value, props = {}) => h('input', {
      class: 'input set-input', type: 'number', inputmode: 'decimal', name, value, 'aria-label': `Set ${number} ${props.label}`,
      min: 0, step: props.step, placeholder: props.placeholder, ...props.attrs,
    });
    const weight = num('weight', weightToDisplay(set.weight_kg, units), { label: `weight in ${unit}`, step: units === 'imperial' ? 5 : 2.5, placeholder: unit });
    const reps = num('reps', set.reps ?? '', { label: ex.is_timed ? 'seconds' : 'reps', step: 1,
      placeholder: set.target_reps_min ? formatReps(set.target_reps_min, set.target_reps_max) : '' });
    const rpe = num('rpe', set.rpe ?? '', { label: 'RPE', step: 0.5, placeholder: '1–10' });
    const rir = num('rir', set.rir ?? '', { label: 'RIR', step: 1, placeholder: '0–10' });
    const notes = h('input', { class: 'input', type: 'text', maxlength: 500, value: set.notes ?? '', placeholder: 'Notes for this set', 'aria-label': `Set ${number} notes` });
    const error = h('div', { class: 'set-error', 'aria-live': 'polite' });
    const more = h('div', { class: 'set-more', hidden: true },
      h('label', {}, 'RPE', rpe), h('label', {}, 'RIR', rir), h('label', { class: 'set-notes' }, 'Notes', notes),
      Button('Remove set', { variant: 'ghost', size: 'sm', onClick: () => removeSet(we, current) }));
    const moreBtn = h('button', { class: 'icon-btn', type: 'button', 'aria-expanded': 'false', 'aria-label': `More for set ${number}: RPE, RIR, notes`,
      onClick: () => { more.hidden = !more.hidden; moreBtn.setAttribute('aria-expanded', String(!more.hidden)); } }, '⋯');
    const check = h('button', { class: 'check-btn', type: 'button', 'aria-pressed': String(current.is_completed), 'aria-label': `Complete set ${number}`, onClick: toggle }, '✓');
    const row = h('div', { class: `set${current.is_completed ? ' done' : ''}` },
      h('div', { class: 'set-main' }, h('span', { class: 'set-no' }, number), weight, reps, moreBtn, check), more, error);

    const raw = () => ({ weight: weight.value, reps: reps.value, rpe: rpe.value, rir: rir.value });
    const showErrors = (errors) => {
      for (const [field, input] of Object.entries({ weight, reps, rpe, rir })) input.setAttribute('aria-invalid', errors[field] ? 'true' : 'false');
      mount(error, Object.values(errors).map((m) => h('span', { class: 'field-error' }, m)));
      if (errors.rpe || errors.rir) { more.hidden = false; moreBtn.setAttribute('aria-expanded', 'true'); }
    };
    const payload = (values) => ({ weight_kg: values.weight_kg, reps: values.reps, rpe: values.rpe, rir: values.rir, notes: notes.value.trim() || null });
    const sync = (updated) => { adopt(updated); current = weOf(we.id).sets.find((s) => s.id === set.id); };

    // Typing saves quietly so nothing is lost if the screen closes. It never completes the set.
    async function autosave() {
      const { ok, errors, values } = validateSet(raw(), { units, completing: current.is_completed });
      showErrors(errors);
      if (!ok) return;
      try { sync(await api.updateSet(session.id, set.id, payload(values))); } catch (e) { showErrors({ server: e.message }); }
    }
    for (const input of [weight, reps, rpe, rir, notes]) input.addEventListener('change', autosave);

    async function toggle() {
      mount(banner, null);
      if (current.is_completed) {
        try { sync(await api.updateSet(session.id, set.id, { is_completed: false })); row.classList.remove('done'); check.setAttribute('aria-pressed', 'false'); updateProgress(); } catch (e) { showErrors({ server: e.message }); }
        return;
      }
      const { ok, errors, values } = validateSet(raw(), { units, completing: true });
      showErrors(errors);
      if (!ok) { (errors.reps ? reps : weight).focus(); return; }
      check.disabled = true;
      try {
        sync(await api.updateSet(session.id, set.id, { ...payload(values), is_completed: true }));
        row.classList.add('done');
        check.setAttribute('aria-pressed', 'true');
        updateProgress();
        const remaining = allSets().some((s) => !s.is_completed);
        if (remaining) timer.start(current.rest_seconds ?? we.rest_seconds ?? DEFAULT_REST);
        else timer.skip();
      } catch (e) { showErrors({ server: e.message }); } finally { check.disabled = false; }
    }
    return row;
  }

  // ---------------------------------------------------------------- finish / discard
  function finish() {
    const done = allSets().filter((s) => s.is_completed).length;
    const total = allSets().length;
    if (done === 0) { flash('Complete at least one set before finishing, or discard this workout.'); return; }
    confirmModal({
      title: 'Finish workout?',
      message: done < total ? `You've completed ${done} of ${total} sets. Sets you skipped won't be saved.` : `All ${total} sets done. Nice work.`,
      confirmLabel: 'Finish',
      onConfirm: async () => {
        try { const finished = await api.completeSession(session.id, {}); timer.skip(); navigate(`/workout/history/${finished.id}`); } catch (e) { flash(e.message); }
      },
    });
  }

  function discard() {
    confirmModal({
      title: 'Discard this workout?', danger: true, confirmLabel: 'Discard',
      message: 'Everything logged in this workout will be deleted. This can\'t be undone.',
      onConfirm: async () => { try { await api.discardSession(session.id); navigate('/workout'); } catch (e) { flash(e.message); } },
    });
  }
}
