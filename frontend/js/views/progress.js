import { api } from '../api.js';
import { h } from '../dom.js';
import { state } from '../store.js';
import { RECORD_LABELS, recordText, shortDate } from '../progression.js';
import { formatDate, formatMetric, formatWeight, labelFor, lbToKg, weightToDisplay, weightUnit } from '../units.js';
import { Alert, Button, Empty, Field, SectionHeader, Select, Tabs, confirmModal, loadInto } from '../ui/components.js';
import { BarChart } from '../ui/charts.js';
import { openMetricModal } from '../ui/metricModal.js';

const MEASUREMENTS = ['body_fat', 'waist', 'chest', 'arm', 'thigh', 'hip', 'neck'];

export function renderProgress(root) {
  const units = state.profile.unit_preference;
  const panel = h('div', { class: 'tab-panel' });
  const tabs = Tabs({
    items: [{ id: 'lifts', label: 'Lifts' }, { id: 'records', label: 'Records' }, { id: 'volume', label: 'Volume' },
      { id: 'weight', label: 'Body weight' }, { id: 'measurements', label: 'Measurements' }],
    active: 'lifts',
    onSelect: (id) => show(id),
  });
  root.replaceChildren(h('div', {}, SectionHeader('Progress', 'Your lifts, records and body measurements over time.'), tabs, panel));

  function show(tab) {
    if (tab === 'lifts') return showLifts();
    if (tab === 'records') return showRecords();
    if (tab === 'volume') return showVolume();
    const weight = tab === 'weight';
    const reload = () => show(tab);
    const add = Button(weight ? 'Log weight' : 'Log measurement', {
      variant: 'secondary', size: 'sm',
      onClick: () => openMetricModal({ types: weight ? ['weight'] : MEASUREMENTS, units, onSaved: reload }),
    });

    loadInto(panel, async () => {
      const all = await api.bodyMetrics(weight ? { metric_type: 'weight', limit: 100 } : { limit: 200 });
      return weight ? all : all.filter((m) => m.metric_type !== 'weight');
    }, (items) => h('div', { class: 'stack' },
      h('div', {}, add),
      items.length === 0
        ? Empty({
            title: weight ? 'No weight logged yet' : 'No measurements yet',
            text: weight ? 'Log your weight to start building a trend.' : 'Log body fat and tape measurements to see how your shape changes.',
          })
        : h('div', { class: 'card' }, items.map((m) => h('div', { class: 'list-row' },
            h('div', {}, h('strong', {}, `${weight ? '' : `${m.custom_label || labelFor(m.metric_type)}: `}${formatMetric(m, units)}`),
              h('small', {}, formatDate(m.recorded_at))),
            Button('Delete', {
              variant: 'ghost', size: 'sm',
              onClick: () => confirmModal({
                title: 'Delete this entry?', message: 'This removes the measurement from your history.',
                confirmLabel: 'Delete', danger: true,
                onConfirm: async () => { try { await api.deleteBodyMetric(m.id); } finally { reload(); } },
              }),
            }))))));
  }

  // ---------------------------------------------------------------- Phase 2: lifts, records, volume
  function showLifts() {
    loadInto(panel, async () => {
      const [exercises, flags, increments] = await Promise.all([api.trainedExercises(), api.flagReport(), api.increments()]);
      return { exercises, flags, increments };
    }, ({ exercises, flags, increments }) => h('div', { class: 'stack' },
      flags.overall && h('div', { class: 'rec-flag rec-flag-mild notice' }, h('strong', {}, flags.overall.message), h('small', {}, ` ${flags.overall.detail}`)),
      exercises.length === 0
        ? Empty({ title: 'No lifts logged yet', text: 'Finish a workout and each exercise will get its own history, records and next-session suggestion.' })
        : h('div', { class: 'card' }, exercises.map((e) => h('a', { class: 'list-row list-link', href: `#/progress/exercise/${e.exercise_id}` },
          h('div', {}, h('strong', {}, e.name),
            h('small', {}, `${e.muscle_group} · ${e.session_count} ${e.session_count === 1 ? 'session' : 'sessions'} · last ${shortDate(e.last_performed_on)}`)),
          h('div', { class: 'row-end' },
            e.flagged && h('span', { class: 'badge badge-ember' }, 'Below trend'),
            e.best_weight_kg != null && h('span', { class: 'badge badge-soft' }, `Best ${formatWeight(e.best_weight_kg, units)}`))))),
      incrementsCard(increments)));
  }

  function incrementsCard(items) {
    const unit = weightUnit(units);
    const status = h('div', { 'aria-live': 'polite' });
    const labels = { barbell: 'Barbell', dumbbells: 'Dumbbells', kettlebell: 'Kettlebell', machines: 'Machines', cable_machine: 'Cable machine' };
    const fields = items.map((i) => ({ item: i, field: Field({ label: labels[i.category] || labelFor(i.category), name: i.category, type: 'number', inputmode: 'decimal', min: 0, step: 0.5,
      value: weightToDisplay(i.custom_kg, units), hint: `Default ${weightToDisplay(i.default_kg, units)} ${unit}` }) }));
    const save = async () => {
      mount(status, null);
      try {
        for (const { item, field } of fields) {
          const raw = field.input.value.trim();
          const n = raw === '' ? null : Number(raw);
          if (n !== null && (!Number.isFinite(n) || n <= 0)) { field.setError('Enter a positive number, or leave empty.'); return; }
          field.setError('');
          const kg = n === null ? null : Number((units === 'imperial' ? lbToKg(n) : n).toFixed(2));
          if (kg !== item.custom_kg) await api.saveIncrement(item.category, kg);
        }
        mount(status, Alert('Saved. Suggestions use these steps from your next workout.', 'success'));
      } catch (e) { mount(status, Alert(e.message)); }
    };
    return h('section', { class: 'card stack' },
      h('div', {}, h('h2', { class: 'section-title-sm' }, 'Weight steps'),
        h('p', { class: 'hint' }, `How much Liv adds when you're ready to go heavier (${unit}). You can also set a step for a single exercise on its page.`)),
      h('div', { class: 'step-grid' }, fields.map((f) => f.field.el)), status, h('div', {}, Button('Save steps', { variant: 'secondary', size: 'sm', onClick: save })));
  }

  function showRecords() {
    loadInto(panel, () => api.records({ limit: 50 }), (records) => records.length === 0
      ? Empty({ title: 'No records yet', text: 'Your first session of an exercise sets the baseline. Beat it and the record shows up here.' })
      : h('div', { class: 'card' }, records.map((r) => h('a', { class: 'list-row list-link', href: `#/progress/exercise/${r.exercise_id}` },
        h('div', {}, h('strong', {}, recordText(r, units)), h('small', {}, shortDate(r.achieved_on))),
        h('span', { class: 'badge badge-mint' }, RECORD_LABELS[r.record_type])))));
  }

  function showVolume(weeks = 8) {
    const picker = Select({ label: 'Period', name: 'weeks', value: weeks, options: [4, 8, 12, 26].map((w) => ({ value: w, label: `Last ${w} weeks` })),
      onChange: (v) => showVolume(Number(v)) });
    loadInto(panel, () => api.volumeReport(weeks), (r) => {
      const rows = (items) => items.map((x) => h('div', { class: 'list-row' }, h('strong', {}, x.label.split('|')[0]),
        h('span', { class: 'row-end' }, h('small', {}, `${x.sets} sets · ${x.reps} reps`), h('span', { class: 'badge badge-soft' }, x.volume_kg ? formatWeight(x.volume_kg, units) : '—'))));
      const empty = r.by_exercise.length === 0;
      return h('div', { class: 'stack' }, picker.el,
        empty ? Empty({ title: 'No training volume yet', text: 'Finish a workout to see weekly totals here.' }) : [
          h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'Weekly volume'),
            BarChart(r.by_week.map((w) => ({ label: shortDate(w.key), value: w.volume_kg })), { label: 'Weekly training volume' }),
            h('small', { class: 'hint' }, 'Weeks start on Monday. Bodyweight sets count as sets and reps but not volume.')),
          h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'By muscle group'), rows(r.by_muscle_group),
            h('small', { class: 'hint' }, 'Counted towards the primary muscle only.')),
          h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'By exercise'), rows(r.by_exercise)),
          h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'By workout'),
            r.by_workout.map((x) => { const [name, date] = x.label.split('|'); return h('a', { class: 'list-row list-link', href: `#/workout/history/${x.key}` },
              h('div', {}, h('strong', {}, name), h('small', {}, shortDate(date))), h('span', { class: 'badge badge-soft' }, x.volume_kg ? formatWeight(x.volume_kg, units) : `${x.sets} sets`)); }))],
        h('p', { class: 'hint' }, r.note));
    });
  }
}
