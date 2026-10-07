// A finished workout: date, duration, and every set that was logged.
import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { state } from '../store.js';
import { formatDate, formatReps, formatWeight } from '../units.js';
import { RECORD_LABELS, recommendationTarget, recordText } from '../progression.js';
import { Empty, loadInto } from '../ui/components.js';

export function renderSessionDetail(root, { id }) {
  const content = h('div');
  mount(root, h('div', { class: 'stack' }, h('a', { class: 'back-link', href: '#/workout' }, '← Workout'), content));
  const units = state.profile.unit_preference;

  loadInto(content, () => api.session(id), (s) => {
    const sets = s.exercises.reduce((n, e) => n + e.sets.length, 0);
    const volume = s.exercises.reduce((sum, e) => sum + e.sets.reduce((v, x) => v + (x.weight_kg || 0) * (x.reps || 0), 0), 0);
    return h('div', { class: 'stack' },
      h('div', {}, h('h1', {}, s.name || 'Workout'), h('p', {}, formatDate(`${s.performed_on}T12:00:00`))),
      h('div', { class: 'stats-row' },
        stat(s.duration_minutes ? `${s.duration_minutes}` : '–', 'minutes'), stat(String(s.exercises.length), 'exercises'),
        stat(String(sets), 'sets'), stat(volume ? formatWeight(volume, units) : '–', 'total lifted')),
      s.records && s.records.length > 0 && h('section', { class: 'pr-banner', 'aria-label': 'New personal records' },
        h('h2', {}, s.records.length === 1 ? 'New PR' : 'New PRs'),
        s.records.map((r) => h('div', { class: 'pr-row' }, h('span', { class: 'badge badge-mint' }, RECORD_LABELS[r.record_type]),
          h('strong', {}, recordText(r, units, s.exercises.find((e) => e.exercise.id === r.exercise_id)?.exercise.is_timed))))),
      s.notes && h('p', {}, s.notes),
      s.status !== 'completed' && h('p', { class: 'note' }, 'This workout was not finished.'),
      s.exercises.length === 0 ? Empty({ title: 'No sets were logged' })
        : s.exercises.map((e) => h('section', { class: 'card' },
            h('div', { class: 'list-row' }, h('h2', { class: 'section-title-sm' }, e.exercise.name),
              h('a', { class: 'btn btn-ghost btn-sm', href: `#/progress/exercise/${e.exercise.id}` }, 'History')),
            e.recommendation && h('p', { class: 'hint' }, `Suggested: ${suggestion(e.recommendation, units, e.exercise.is_timed)}${e.recommendation.performed_weight_kg != null && e.recommendation.followed === false ? ' · you chose a different weight' : ''}`),
            h('ol', { class: 'logged-sets' }, e.sets.map((x, i) => h('li', {},
              h('span', { class: 'set-no' }, i + 1),
              h('strong', {}, `${x.weight_kg ? `${formatWeight(x.weight_kg, units)} × ` : ''}${formatReps(x.reps ?? 0, x.reps ?? 0, e.exercise.is_timed)}`),
              [x.rpe != null && `RPE ${x.rpe}`, x.rir != null && `RIR ${x.rir}`].filter(Boolean).map((t) => h('span', { class: 'badge badge-soft' }, t)),
              x.notes && h('small', {}, x.notes)))))));
  });
}

function suggestion(rec, units, timed) {
  const t = recommendationTarget(rec, units, timed);
  return [t.weight, t.reps, t.sets].filter(Boolean).join(' · ');
}

const stat = (value, label) => h('div', { class: 'stat-box' }, h('strong', {}, value), h('small', {}, label));
