// A finished workout: date, duration, and every set that was logged.
import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { state } from '../store.js';
import { formatDate, formatReps, formatWeight } from '../units.js';
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
      s.notes && h('p', {}, s.notes),
      s.status !== 'completed' && h('p', { class: 'note' }, 'This workout was not finished.'),
      s.exercises.length === 0 ? Empty({ title: 'No sets were logged' })
        : s.exercises.map((e) => h('section', { class: 'card' },
            h('h2', { class: 'section-title-sm' }, e.exercise.name),
            h('ol', { class: 'logged-sets' }, e.sets.map((x, i) => h('li', {},
              h('span', { class: 'set-no' }, i + 1),
              h('strong', {}, `${x.weight_kg ? `${formatWeight(x.weight_kg, units)} × ` : ''}${formatReps(x.reps ?? 0, x.reps ?? 0, e.exercise.is_timed)}`),
              [x.rpe != null && `RPE ${x.rpe}`, x.rir != null && `RIR ${x.rir}`].filter(Boolean).map((t) => h('span', { class: 'badge badge-soft' }, t)),
              x.notes && h('small', {}, x.notes)))))));
  });
}

const stat = (value, label) => h('div', { class: 'stat-box' }, h('strong', {}, value), h('small', {}, label));
