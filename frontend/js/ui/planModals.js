// Modals used when editing a workout: rename, prescription, add exercise, swap exercise.
import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { validatePrescription } from '../validation.js';
import { formatRest } from '../units.js';
import { Alert, Button, Empty, Field, Loading, openModal } from './components.js';

/** Asks for a name. onSave(name) may throw; the message is shown in the dialog. */
export function namePromptModal({ title, label = 'Name', value = '', confirmLabel = 'Save', onSave }) {
  const field = Field({ label, name: 'name', value });
  const feedback = h('div');
  let modal;
  const submit = async () => {
    const name = field.input.value.trim();
    if (!name) { field.setError('Enter a name.'); return; }
    if (name.length > 120) { field.setError('Names can be up to 120 characters.'); return; }
    field.setError(null);
    try { await onSave(name); modal.close(); } catch (e) { mount(feedback, Alert(e.message)); }
  };
  field.input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
  modal = openModal({
    title, body: h('div', { class: 'form-stack' }, field.el, feedback),
    actions: [Button('Cancel', { variant: 'ghost', onClick: () => modal.close() }), Button(confirmLabel, { onClick: submit })],
  });
  field.input.focus();
}

/** Edit sets, reps and rest for one plan exercise. onSave(values) may throw. */
export function prescriptionModal({ item, onSave }) {
  const timed = item.exercise.is_timed;
  const sets = Field({ label: 'Sets', name: 'sets', type: 'number', inputmode: 'numeric', min: 1, max: 10, value: item.sets });
  const repMin = Field({ label: timed ? 'Min seconds' : 'Min reps', name: 'rep_min', type: 'number', inputmode: 'numeric', min: 1, value: item.rep_min });
  const repMax = Field({ label: timed ? 'Max seconds' : 'Max reps', name: 'rep_max', type: 'number', inputmode: 'numeric', min: 1, value: item.rep_max });
  const rest = Field({ label: 'Rest between sets (seconds)', name: 'rest', type: 'number', inputmode: 'numeric', min: 0, max: 600, step: 5, value: item.rest_seconds, hint: `Currently ${formatRest(item.rest_seconds)}` });
  const feedback = h('div');
  let modal;
  const submit = async () => {
    const result = validatePrescription({ sets: sets.input.value, repMin: repMin.input.value, repMax: repMax.input.value, rest: rest.input.value });
    sets.setError(result.errors.sets); repMin.setError(result.errors.repMin);
    repMax.setError(result.errors.repMax); rest.setError(result.errors.rest);
    if (!result.ok) return;
    try { await onSave(result.values); modal.close(); } catch (e) { mount(feedback, Alert(e.message)); }
  };
  modal = openModal({
    title: item.exercise.name,
    body: h('div', { class: 'form-stack' }, sets.el, h('div', { class: 'form-row' }, repMin.el, repMax.el), rest.el, feedback),
    actions: [Button('Cancel', { variant: 'ghost', onClick: () => modal.close() }), Button('Save', { onClick: submit })],
  });
}

/** Search the library and pick an exercise to add. Defaults to exercises the user's equipment allows. */
export function exercisePickerModal({ excludeIds = [], onPick }) {
  let query = '';
  let onlyMine = true;
  let timer;
  const results = h('div', { class: 'picker-results' });
  const feedback = h('div');
  const excluded = new Set(excludeIds);

  const refresh = async () => {
    mount(results, Loading('Searching'));
    try {
      const items = (await api.exercises({ q: query, available_only: onlyMine ? 'true' : '', limit: 60 })).filter((e) => !excluded.has(e.id));
      mount(results, items.length === 0
        ? Empty({ title: 'No exercises found', text: onlyMine ? 'Try another search, or untick "Only my equipment".' : 'Try another search.' })
        : items.map((ex) => h('button', { class: 'picker-item', type: 'button', onClick: () => choose(ex) },
            h('strong', {}, ex.name),
            h('small', {}, `${ex.primary_muscle_group.name} · ${ex.equipment.length ? ex.equipment.map((e) => e.name).join(', ') : 'No equipment'}`))));
    } catch (e) { mount(results, Alert(e.message)); }
  };
  const choose = async (ex) => {
    try { await onPick(ex); modal.close(); } catch (e) { mount(feedback, Alert(e.message)); }
  };
  const search = h('input', {
    class: 'input', type: 'search', placeholder: 'Search exercises', 'aria-label': 'Search exercises',
    onInput: (e) => { query = e.target.value; clearTimeout(timer); timer = setTimeout(refresh, 250); },
  });
  const toggle = h('label', { class: 'check' },
    h('input', { type: 'checkbox', checked: true, onChange: (e) => { onlyMine = e.target.checked; refresh(); } }), ' Only my equipment');
  const modal = openModal({
    title: 'Add exercise',
    body: h('div', { class: 'form-stack' }, search, toggle, feedback, results),
    actions: [Button('Close', { variant: 'ghost', onClick: () => modal.close() })],
  });
  modal.dialog.classList.add('modal-wide');
  refresh();
}

/** Lists valid replacements for one plan exercise (same muscle and movement, usable equipment). */
export function substituteModal({ planId, dayId, item, onReplace }) {
  const body = h('div', { class: 'form-stack' }, Loading('Finding alternatives'));
  const feedback = h('div');
  const modal = openModal({
    title: `Swap ${item.exercise.name}`, body,
    actions: [Button('Cancel', { variant: 'ghost', onClick: () => modal.close() })],
  });
  modal.dialog.classList.add('modal-wide');
  api.planSubstitutes(planId, dayId, item.id).then((subs) => {
    mount(body, h('p', { class: 'hint' }, 'Alternatives train the same muscle with the same kind of movement, using equipment you have. Sets, reps and rest stay the same.'),
      feedback,
      subs.length === 0
        ? Empty({ title: 'No alternatives available', text: 'Nothing else matches your equipment and experience for this exercise.' })
        : subs.map((s) => h('button', { class: 'picker-item', type: 'button', onClick: async () => {
            try { await onReplace(s.exercise); modal.close(); } catch (e) { mount(feedback, Alert(e.message)); }
          } }, h('strong', {}, s.exercise.name), h('small', {}, s.reasons.join(' · ')))));
  }).catch((e) => mount(body, Alert(e.message)));
}
