// View a plan (or custom workout) and edit it: swap, add, remove, reorder, change sets/reps/rest, rename.
import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { navigate } from '../router.js';
import { formatReps, formatRest } from '../units.js';
import { Alert, Button, Empty, ErrorState, Loading, confirmModal } from '../ui/components.js';
import { exercisePickerModal, namePromptModal, prescriptionModal, substituteModal } from '../ui/planModals.js';
import { startWorkout } from './startWorkout.js';
import { planBadges } from './workout.js';

export async function renderPlan(root, { id }) {
  mount(root, Loading());
  let plan;
  try { plan = await api.plan(id); } catch (e) {
    mount(root, h('div', { class: 'stack' }, h('a', { class: 'back-link', href: '#/workout' }, '← Workout'),
      e.status === 404 ? Empty({ title: 'Workout not found', text: 'It may have been deleted.' }) : ErrorState(e.message, () => renderPlan(root, { id }))));
    return;
  }

  const editing = new Set(); // day ids currently in edit mode
  const notice = h('div', { 'aria-live': 'polite' });
  const dayEls = new Map();
  const isCustom = plan.kind === 'custom';
  const flash = (message, kind = 'error') => { mount(notice, Alert(message, kind)); notice.scrollIntoView?.({ block: 'nearest' }); };

  const header = h('div');
  const body = h('div', { class: 'stack' });
  mount(root, h('div', { class: 'stack' }, h('a', { class: 'back-link', href: '#/workout' }, '← Workout'), header, notice, body));
  drawHeader();
  plan.days.forEach((day) => { const el = renderDay(day); dayEls.set(day.id, el); body.append(el); });

  function drawHeader() {
    mount(header, h('div', { class: 'plan-head' },
      h('div', {}, h('h1', {}, plan.name), h('div', { class: 'badges' }, planBadges(plan))),
      h('div', { class: 'row-actions' },
        Button('Rename', { variant: 'ghost', size: 'sm', onClick: rename }),
        Button('Delete', { variant: 'ghost', size: 'sm', onClick: remove }))),
      plan.warnings.map((w) => h('p', { class: 'note' }, w)),
      !isCustom && plan.is_active === false && h('p', { class: 'note' }, 'This is an earlier plan. Generate a new one to replace your current plan.'));
  }

  function rename() {
    namePromptModal({ title: 'Rename', value: plan.name, onSave: async (name) => {
      plan = await api.updatePlan(plan.id, { name });
      drawHeader();
      if (isCustom) refreshDay(plan.days[0]);
    } });
  }

  function remove() {
    confirmModal({
      title: `Delete ${plan.name}?`, danger: true, confirmLabel: 'Delete',
      message: 'This removes the workout. Workouts you already logged stay in your history.',
      onConfirm: async () => { try { await api.deletePlan(plan.id); navigate('/workout'); } catch (e) { flash(e.message); } },
    });
  }

  // Replace one day in local state and redraw just that card.
  function refreshDay(day) {
    const i = plan.days.findIndex((d) => d.id === day.id);
    plan.days[i] = day;
    const next = renderDay(day);
    dayEls.get(day.id).replaceWith(next);
    dayEls.set(day.id, next);
  }

  // Runs an API edit, then redraws the day. Errors are shown, not thrown, unless the caller wants them.
  async function edit(day, action, { rethrow = false } = {}) {
    mount(notice, null);
    try { refreshDay(await action()); } catch (e) { if (rethrow) throw e; flash(e.message); }
  }

  function renderDay(day) {
    if (day.is_rest) {
      return h('section', { class: 'day-card rest', 'aria-label': `Day ${day.day_index}, rest` },
        h('span', { class: 'week-day' }, `Day ${day.day_index}`), h('span', {}, 'Rest day. Recover and come back stronger.'));
    }
    const editingNow = editing.has(day.id);
    const items = day.exercises;
    return h('section', { class: 'day-card', 'aria-label': day.name },
      h('div', { class: 'day-head' },
        h('div', {}, !isCustom && h('span', { class: 'week-day' }, `Day ${day.day_index}`),
          h('h2', {}, day.name),
          h('small', {}, [day.focus, items.length && `${items.length} exercises`, day.estimated_minutes && `about ${day.estimated_minutes} min`].filter(Boolean).join(' · '))),
        h('div', { class: 'row-actions' },
          Button(editingNow ? 'Done' : 'Edit', { variant: 'secondary', size: 'sm', onClick: () => { editingNow ? editing.delete(day.id) : editing.add(day.id); refreshDay(day); } }),
          Button('Start', { size: 'sm', disabled: items.length === 0, onClick: () => startWorkout(day.id, { onError: flash }) }))),
      items.length === 0
        ? h('p', { class: 'hint' }, 'No exercises yet. Choose Edit, then Add exercise.')
        : h('ol', { class: 'plan-list' }, items.map((item, i) => planRow(day, item, i, items.length, editingNow))),
      editingNow && h('div', { class: 'day-tools' },
        Button('Add exercise', { variant: 'secondary', size: 'sm', onClick: () => addExercise(day) }),
        !isCustom && Button('Rename day', { variant: 'ghost', size: 'sm', onClick: () => renameDay(day) })));
  }

  function planRow(day, item, index, total, editingNow) {
    const ex = item.exercise;
    return h('li', { class: 'plan-row' },
      h('div', { class: 'plan-row-main' },
        h('strong', {}, ex.name),
        h('small', {}, `${item.sets} × ${formatReps(item.rep_min, item.rep_max, ex.is_timed)} · rest ${formatRest(item.rest_seconds)} · ${ex.primary_muscle_group.name}`),
        item.notes && h('small', { class: 'note-inline' }, item.notes)),
      editingNow && h('div', { class: 'row-actions wrap' },
        iconBtn('↑', `Move ${ex.name} up`, index === 0, () => move(day, index, -1)),
        iconBtn('↓', `Move ${ex.name} down`, index === total - 1, () => move(day, index, 1)),
        Button('Sets and reps', { variant: 'ghost', size: 'sm', onClick: () => prescriptionModal({ item, onSave: (values) => edit(day, () => api.updatePlanExercise(plan.id, day.id, item.id, values), { rethrow: true }) }) }),
        Button('Swap', { variant: 'ghost', size: 'sm', onClick: () => substituteModal({ planId: plan.id, dayId: day.id, item, onReplace: (replacement) => edit(day, () => api.replacePlanExercise(plan.id, day.id, item.id, replacement.id), { rethrow: true }) }) }),
        Button('Remove', { variant: 'ghost', size: 'sm', onClick: () => edit(day, () => api.removePlanExercise(plan.id, day.id, item.id)) })));
  }

  function iconBtn(label, aria, disabled, onClick) {
    return h('button', { class: 'icon-btn', type: 'button', 'aria-label': aria, disabled, onClick }, label);
  }

  function move(day, index, delta) {
    const ids = day.exercises.map((e) => e.id);
    const [moved] = ids.splice(index, 1);
    ids.splice(index + delta, 0, moved);
    edit(day, () => api.reorderDay(plan.id, day.id, ids));
  }

  function addExercise(day) {
    exercisePickerModal({
      excludeIds: day.exercises.map((e) => e.exercise.id),
      onPick: (ex) => edit(day, () => api.addPlanExercise(plan.id, day.id, { exercise_id: ex.id }), { rethrow: true }),
    });
  }

  function renameDay(day) {
    namePromptModal({ title: 'Rename day', value: day.name, onSave: (name) => edit(day, () => api.renameDay(plan.id, day.id, name), { rethrow: true }) });
  }
}
