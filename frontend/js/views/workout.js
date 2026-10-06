import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { navigate } from '../router.js';
import { formatDate, labelFor } from '../units.js';
import { Button, Empty, SectionHeader, Select, Tabs, loadInto } from '../ui/components.js';
import { namePromptModal } from '../ui/planModals.js';
import { resumeCard, startWorkout } from './startWorkout.js';

let lastTab = 'plan'; // remembered while the app is open, so Back returns to the same tab

const SPLIT_LABELS = {
  full_body: 'Full body', upper_lower: 'Upper / lower', push_pull_legs: 'Push / pull / legs',
  push_pull: 'Push / pull', bro_split: 'Body-part split', custom: 'Custom',
};

export function renderWorkout(root) {
  const panel = h('div', { class: 'tab-panel' });
  const banner = h('div');
  const tabs = Tabs({
    items: [
      { id: 'plan', label: 'Plan' }, { id: 'workouts', label: 'My workouts' },
      { id: 'history', label: 'History' }, { id: 'library', label: 'Exercises' },
    ],
    active: lastTab,
    onSelect: (id) => { lastTab = id; ({ plan, workouts, history, library })[id](); },
  });
  mount(root, h('div', {},
    SectionHeader('Workout', 'Generate a plan, build your own workouts, and log your training.',
      Button('Generate plan', { size: 'sm', onClick: () => navigate('/workout/generate') })),
    banner, tabs, panel));

  api.activeSession().then((s) => mount(banner, s ? resumeCard(s) : null)).catch(() => {});
  ({ plan, workouts, history, library })[lastTab]();

  // ---- plan tab: the plan you're following ----
  function plan() {
    loadInto(panel, async () => {
      const plans = await api.plans({ kind: 'generated' });
      const active = plans.find((p) => p.is_active) || plans[0];
      return { plans, detail: active ? await api.plan(active.id) : null };
    }, ({ plans, detail }) => {
      if (!detail) {
        return Empty({
          title: 'No plan yet',
          text: 'Tell Liv your goal, schedule and equipment and it will build a full weekly plan.',
          action: Button('Generate my plan', { onClick: () => navigate('/workout/generate') }),
        });
      }
      const others = plans.filter((p) => p.id !== detail.id);
      return h('div', { class: 'stack' },
        h('section', { class: 'card' },
          h('div', { class: 'plan-head' },
            h('div', {}, h('h2', { class: 'section-title-sm' }, detail.name),
              h('div', { class: 'badges' }, planBadges(detail))),
            Button('View and edit', { variant: 'secondary', size: 'sm', onClick: () => navigate(`/workout/plan/${detail.id}`) })),
          detail.warnings.map((w) => h('p', { class: 'note' }, w)),
          h('div', { class: 'week' }, detail.days.map((d) => weekRow(d, detail)))),
        others.length > 0 && h('section', { class: 'card' },
          h('h2', { class: 'section-title-sm' }, 'Earlier plans'),
          others.map((p) => h('div', { class: 'list-row' },
            h('div', {}, h('strong', {}, p.name), h('small', {}, `Created ${formatDate(p.created_at)}`)),
            Button('Open', { variant: 'ghost', size: 'sm', onClick: () => navigate(`/workout/plan/${p.id}`) })))));
    });
  }

  function weekRow(day, detail) {
    if (day.is_rest) return h('div', { class: 'week-row rest' }, h('span', { class: 'week-day' }, `Day ${day.day_index}`), h('span', {}, 'Rest'));
    return h('div', { class: 'week-row' },
      h('span', { class: 'week-day' }, `Day ${day.day_index}`),
      h('div', { class: 'week-main' }, h('strong', {}, day.name),
        h('small', {}, `${day.exercises.length} exercises${day.estimated_minutes ? `, about ${day.estimated_minutes} min` : ''}`)),
      Button('Start', { size: 'sm', onClick: () => startWorkout(day.id) }));
  }

  // ---- my workouts: custom workouts ----
  function workouts() {
    loadInto(panel, () => api.plans({ kind: 'custom' }), (items) => h('div', { class: 'stack' },
      h('div', {}, Button('New workout', { onClick: newWorkout })),
      items.length === 0
        ? Empty({ title: 'No custom workouts yet', text: 'Build a workout from any exercises, set the sets, reps and rest, and reuse it any time.' })
        : h('div', { class: 'card' }, items.map((p) => h('div', { class: 'list-row' },
            h('div', {}, h('strong', {}, p.name), h('small', {}, `${p.exercise_count} ${p.exercise_count === 1 ? 'exercise' : 'exercises'}`)),
            h('div', { class: 'row-actions' },
              Button('Edit', { variant: 'ghost', size: 'sm', onClick: () => navigate(`/workout/plan/${p.id}`) }),
              p.start_day_id && Button('Start', { size: 'sm', onClick: () => startWorkout(p.start_day_id) })))))));
  }

  function newWorkout() {
    namePromptModal({
      title: 'New workout', label: 'Workout name', confirmLabel: 'Create',
      onSave: async (name) => { const plan = await api.createCustomWorkout({ name, exercises: [] }); navigate(`/workout/plan/${plan.id}`); },
    });
  }

  // ---- history ----
  function history() {
    loadInto(panel, () => api.sessions({ limit: 50, status: 'completed' }), (items) => items.length === 0
      ? Empty({ title: 'No workouts logged yet', text: 'Finish a workout and it will appear here with every set.' })
      : h('div', { class: 'card' }, items.map((s) => {
          const sets = s.exercises.reduce((n, e) => n + e.sets.length, 0);
          return h('button', { class: 'list-row list-link', type: 'button', onClick: () => navigate(`/workout/history/${s.id}`) },
            h('div', {}, h('strong', {}, s.name || 'Workout'),
              h('small', {}, `${formatDate(`${s.performed_on}T12:00:00`)} · ${s.exercises.length} exercises · ${sets} sets${s.duration_minutes ? ` · ${s.duration_minutes} min` : ''}`)),
            h('span', { class: 'badge badge-mint' }, 'Done'));
        })));
  }

  // ---- exercise library ----
  function library() {
    loadInto(panel, () => api.muscleGroups(), (groups) => {
      let query = '';
      let muscle = '';
      let mine = false;
      let timer;
      const results = h('div');
      const refresh = () => loadInto(results, () => api.exercises({ q: query, muscle_group_id: muscle, available_only: mine ? 'true' : '', limit: 100 }), (items) =>
        items.length === 0
          ? Empty({ title: 'No exercises match', text: 'Try a different search or muscle group.' })
          : h('div', { class: 'card' }, items.map((ex) => h('details', { class: 'item' },
              h('summary', {}, h('strong', {}, ex.name), ' ',
                h('span', { class: 'badge' }, ex.primary_muscle_group.name), ' ',
                h('span', { class: 'badge badge-soft' }, labelFor(ex.difficulty)), ' ',
                ex.is_custom && h('span', { class: 'badge badge-mint' }, 'Custom')),
              ex.description && h('p', {}, ex.description),
              h('dl', { class: 'defs' },
                h('dt', {}, 'Type'), h('dd', {}, `${ex.is_compound ? 'Compound' : 'Isolation'}, ${labelFor(ex.movement_pattern).toLowerCase()}`),
                h('dt', {}, 'Muscles'), h('dd', {}, [ex.primary_muscle_group.name, ...ex.secondary_muscle_groups.map((m) => m.name)].join(', ')),
                h('dt', {}, 'Equipment'), h('dd', {}, ex.equipment.length ? ex.equipment.map((e) => e.name).join(', ') : 'None'),
                h('dt', {}, 'Suggested'), h('dd', {}, `${ex.recommended_sets} sets of ${ex.rep_min}–${ex.rep_max} ${ex.is_timed ? 'seconds' : 'reps'}`),
                h('dt', {}, 'Level'), h('dd', {}, `${labelFor(ex.min_experience_level)} and up`)),
              ex.instructions && h('p', {}, ex.instructions)))));
      const search = h('input', {
        class: 'input', type: 'search', placeholder: 'Search exercises', 'aria-label': 'Search exercises',
        onInput: (e) => { query = e.target.value; clearTimeout(timer); timer = setTimeout(refresh, 250); },
      });
      const filter = Select({
        name: 'muscle', placeholder: 'All muscle groups', value: '',
        options: groups.map((g) => ({ value: g.id, label: g.name })),
        onChange: (v) => { muscle = v; refresh(); },
      });
      const toggle = h('label', { class: 'check' },
        h('input', { type: 'checkbox', onChange: (e) => { mine = e.target.checked; refresh(); } }), ' Only my equipment');
      refresh();
      return h('div', { class: 'stack' }, h('div', { class: 'grid-2' }, search, filter.el), toggle, results);
    });
  }
}

export function planBadges(plan) {
  return [
    plan.goal && h('span', { class: 'badge' }, plan.goal.name),
    plan.split_type && h('span', { class: 'badge badge-soft' }, SPLIT_LABELS[plan.split_type] || labelFor(plan.split_type)),
    plan.days_per_week && h('span', { class: 'badge badge-soft' }, `${plan.days_per_week} days a week`),
    plan.duration_minutes && h('span', { class: 'badge badge-soft' }, `${plan.duration_minutes} min`),
    plan.experience_level && h('span', { class: 'badge badge-soft' }, labelFor(plan.experience_level)),
    !plan.is_active && plan.kind === 'generated' && h('span', { class: 'badge' }, 'Not active'),
  ];
}

