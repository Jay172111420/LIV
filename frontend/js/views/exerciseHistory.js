// One exercise's history: bests, estimated 1RM, PRs, recent sessions, trend, and its progression settings.
import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { state } from '../store.js';
import { RECORD_LABELS, STRATEGY_LABELS, formatSetList, recordText, shortDate, trendText } from '../progression.js';
import { formatWeight, lbToKg, weightToDisplay, weightUnit } from '../units.js';
import { Alert, Button, Empty, Field, Select, loadInto } from '../ui/components.js';
import { Sparkline } from '../ui/charts.js';
import { RecommendationCard } from '../ui/recommendation.js';

export function renderExerciseHistory(root, { id }) {
  const units = state.profile.unit_preference;
  const content = h('div');
  mount(root, h('div', { class: 'stack' }, h('a', { class: 'back-link', href: '#/progress' }, '← Progress'), content));

  loadInto(content, async () => {
    const [history, rec, settings] = await Promise.all([api.exerciseHistory(id), api.exerciseRecommendation(id), api.progressionSettings(id)]);
    return { history, rec, settings };
  }, ({ history: hi, rec, settings }) => {
    const timed = hi.is_timed;
    const best = hi.best;
    return h('div', { class: 'stack' },
      h('div', {}, h('h1', {}, hi.exercise_name), h('p', {}, trendText(hi.trend))),
      hi.flags.map((f) => h('div', { class: 'rec-flag rec-flag-mild notice' }, h('strong', {}, f.message), f.detail && h('small', {}, ` ${f.detail}`))),
      hi.session_count === 0
        ? Empty({ title: 'No sessions yet', text: 'Finish a workout with this exercise and your history will appear here.' })
        : null,
      RecommendationCard({ rec, units, timed, title: 'Next session' }),
      hi.session_count > 0 && h('div', { class: 'stats-row' },
        hi.uses_weight && stat(best.weight_kg != null ? `${formatWeight(best.weight_kg, units)} × ${best.weight_reps}` : '–', 'Best weight'),
        stat(best.reps != null ? `${best.reps}${timed ? ' sec' : ''}${best.reps_at_weight_kg ? ` @ ${formatWeight(best.reps_at_weight_kg, units)}` : ''}` : '–', 'Best reps (one set)'),
        hi.uses_weight && stat(best.estimated_1rm_kg != null ? `≈ ${formatWeight(best.estimated_1rm_kg, units)}` : '–', 'Estimated 1RM'),
        hi.uses_weight && stat(best.volume_kg != null ? formatWeight(best.volume_kg, units) : '–', 'Best workout volume'),
        stat(String(hi.session_count), 'Sessions'),
        hi.uses_weight && stat(formatWeight(hi.total_volume_kg, units), 'Total volume')),
      hi.trend.points.length > 1 && h('section', { class: 'card' },
        h('h2', { class: 'section-title-sm' }, hi.trend.metric === 'estimated_1rm_kg' ? 'Estimated 1RM per session' : 'Average reps per session'),
        Sparkline(hi.trend.points, { label: `${hi.exercise_name} trend: ${trendText(hi.trend)}` }),
        h('small', { class: 'hint' }, `${shortDate(hi.trend.dates[0])} → ${shortDate(hi.trend.dates.at(-1))}`)),
      hi.records.length > 0 && h('section', { class: 'card' },
        h('h2', { class: 'section-title-sm' }, 'Personal records'),
        hi.records.map((r) => h('div', { class: 'list-row' },
          h('div', {}, h('strong', {}, recordText(r, units, timed).replace(`${r.exercise_name} — `, '')), h('small', {}, shortDate(r.achieved_on))),
          h('span', { class: 'badge badge-mint' }, RECORD_LABELS[r.record_type])))),
      hi.recent_sessions.length > 0 && h('section', { class: 'card' },
        h('h2', { class: 'section-title-sm' }, 'Recent sessions'),
        hi.recent_sessions.map((s) => h('div', { class: 'list-row' },
          h('div', {}, h('strong', {}, formatSetList(s.sets, units, timed)),
            h('small', {}, [shortDate(s.performed_on), s.volume_kg ? `volume ${formatWeight(s.volume_kg, units)}` : null,
              s.best_estimated_1rm_kg ? `est. 1RM ≈ ${formatWeight(s.best_estimated_1rm_kg, units)}` : null].filter(Boolean).join(' · '))),
          h('a', { class: 'btn btn-ghost btn-sm', href: `#/workout/history/${s.session_id}` }, 'Open')))),
      settingsCard(id, settings, units),
      hi.notes.length > 0 && h('div', { class: 'hint-block' }, hi.notes.map((n) => h('p', { class: 'hint' }, n))));
  });
}

const stat = (value, label) => h('div', { class: 'stat-box' }, h('strong', {}, value), h('small', {}, label));

function settingsCard(id, settings, units) {
  const unit = weightUnit(units);
  const strategy = Select({
    label: 'How should Liv progress this exercise?', name: 'strategy', value: settings.strategy,
    options: Object.entries(STRATEGY_LABELS).map(([value, label]) => ({ value, label })),
  });
  const step = settings.uses_weight || settings.category === 'bodyweight'
    ? Field({ label: `Weight step (${unit})`, name: 'increment', type: 'number', inputmode: 'decimal', min: 0, step: 0.5,
      value: weightToDisplay(settings.increment_kg, units),
      hint: `Leave empty to use the default (${weightToDisplay(settings.default_increment_kg, units)} ${unit}).` })
    : null;
  const status = h('div', { 'aria-live': 'polite' });
  const save = async () => {
    const raw = step ? step.input.value.trim() : '';
    const n = raw === '' ? null : Number(raw);
    if (n !== null && (!Number.isFinite(n) || n <= 0)) { step.setError('Enter a positive number, or leave empty.'); return; }
    step?.setError('');
    try {
      await api.saveProgressionSettings(id, { strategy: strategy.select.value, increment_kg: n === null ? null : Number((units === 'imperial' ? lbToKg(n) : n).toFixed(2)) });
      mount(status, Alert('Saved. Your next workout will use this.', 'success'));
    } catch (e) { mount(status, Alert(e.message)); }
  };
  return h('section', { class: 'card stack' },
    h('h2', { class: 'section-title-sm' }, 'Progression settings'),
    strategy.el, step?.el, status, h('div', {}, Button('Save', { variant: 'secondary', size: 'sm', onClick: save })));
}
