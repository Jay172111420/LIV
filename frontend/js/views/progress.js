import { api } from '../api.js';
import { h } from '../dom.js';
import { state } from '../store.js';
import { formatDate, formatMetric, labelFor } from '../units.js';
import { Button, Empty, SectionHeader, Tabs, confirmModal, loadInto } from '../ui/components.js';
import { openMetricModal } from '../ui/metricModal.js';

const MEASUREMENTS = ['body_fat', 'waist', 'chest', 'arm', 'thigh', 'hip', 'neck'];

export function renderProgress(root) {
  const units = state.profile.unit_preference;
  const panel = h('div', { class: 'tab-panel' });
  const tabs = Tabs({
    items: [{ id: 'weight', label: 'Body weight' }, { id: 'measurements', label: 'Measurements' }],
    active: 'weight',
    onSelect: (id) => show(id),
  });
  root.replaceChildren(h('div', {}, SectionHeader('Progress', 'Track how your body changes over time.'), tabs, panel));

  function show(tab) {
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
}
