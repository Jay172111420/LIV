import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { inToCm, labelFor, lbToKg } from '../units.js';
import { Alert, Button, Field, Select, openModal } from './components.js';

const unitFor = (type, units) => {
  if (type === 'weight') return units === 'imperial' ? 'lb' : 'kg';
  if (type === 'body_fat') return '%';
  return units === 'imperial' ? 'in' : 'cm';
};

const toMetric = (type, value, units) => {
  if (units !== 'imperial') return value;
  if (type === 'weight') return lbToKg(value);
  if (type === 'body_fat') return value;
  return inToCm(value);
};

/** Dialog for logging one measurement. types: e.g. ['weight'] or ['waist','chest',...]. */
export function openMetricModal({ types, units, onSaved }) {
  let type = types[0];
  const value = Field({ label: '', name: 'value', type: 'number', inputmode: 'decimal', step: '0.1', min: '0', required: true });
  const feedback = h('div');
  const labelEl = value.el.querySelector('label');
  const refreshLabel = () => { labelEl.textContent = `${labelFor(type)} (${unitFor(type, units)})`; };
  refreshLabel();

  const picker = types.length > 1
    ? Select({ label: 'Measurement', name: 'type', value: type, options: types.map((t) => ({ value: t, label: labelFor(t) })),
        onChange: (v) => { type = v; refreshLabel(); } })
    : null;

  let modal;
  const save = Button('Save', {
    onClick: async () => {
      const n = Number(value.input.value);
      value.setError('');
      if (!value.input.value || !Number.isFinite(n) || n <= 0) { value.setError('Enter a number greater than 0.'); return; }
      save.disabled = true;
      try {
        await api.addBodyMetric({ metric_type: type, value: Number(toMetric(type, n, units).toFixed(2)) });
        modal.close();
        onSaved();
      } catch (e) {
        mount(feedback, Alert(e.fieldErrors.value || e.message));
        save.disabled = false;
      }
    },
  });
  modal = openModal({
    title: types.length > 1 ? 'Log a measurement' : 'Log weight',
    body: h('div', { class: 'form-stack' }, picker && picker.el, value.el, feedback),
    actions: [Button('Cancel', { variant: 'ghost', onClick: () => modal.close() }), save],
  });
  value.input.focus();
}
