// "Recommended today": the progression engine's suggestion with Accept / Edit / Ignore.
import { h, mount } from '../dom.js';
import { actionLabel, canAct, choiceText, formatSetList, parseEdit, recommendationTarget, shortDate } from '../progression.js';
import { weightToDisplay, weightUnit } from '../units.js';
import { Alert, Button, Field, openModal } from './components.js';

const ACTION_TONE = { increase_weight: 'badge-mint', increase_reps: 'badge-mint', reduce_weight: 'badge-ember', deload: 'badge-ember' };

/**
 * rec: RecommendationOut. onRespond(body) -> Promise, called with {choice, weight_kg?, reps?}.
 * Omit onRespond for a read-only preview (the exercise history page).
 */
export function RecommendationCard({ rec, units, timed = false, title = 'Recommended today', onRespond }) {
  const target = recommendationTarget(rec, units, timed);
  const last = rec.last_session;
  const message = h('div', { 'aria-live': 'polite' });

  const respond = async (body) => {
    mount(message, null);
    try { await onRespond(body); } catch (e) { mount(message, Alert(e.message)); }
  };
  const edit = () => openEditor({ rec, units, timed, onSave: (body) => respond(body) });

  const numbers = h('div', { class: 'rec-numbers' },
    target.weight && h('div', { class: 'rec-num' }, h('strong', {}, target.weight), h('small', {}, rec.action === 'start' ? 'choose your own' : 'weight')),
    h('div', { class: 'rec-num' }, h('strong', {}, target.reps), h('small', {}, 'target')),
    h('div', { class: 'rec-num' }, h('strong', {}, target.sets), h('small', {}, 'planned')));

  return h('section', { class: 'rec-card', 'aria-label': title },
    h('div', { class: 'rec-head' },
      h('h3', {}, title),
      h('span', { class: `badge ${ACTION_TONE[rec.action] || 'badge-soft'}` }, actionLabel(rec.action))),
    numbers,
    target.goal && h('p', { class: 'rec-goal' }, target.goal),
    last && h('p', { class: 'rec-last' }, h('strong', {}, 'Last session: '), `${formatSetList(last.sets, units, timed)} · ${shortDate(last.performed_on)}`),
    h('p', { class: 'rec-reason' }, rec.reason),
    rec.flags.map((f) => h('p', { class: `rec-flag rec-flag-${f.level}` }, f.message, f.detail && h('small', {}, ` ${f.detail}`))),
    rec.confidence === 'low' && rec.action !== 'start' && h('p', { class: 'hint' }, 'Based on limited history, so treat this as a starting point.'),
    onRespond && canAct(rec) && h('div', { class: 'rec-actions' },
      Button(rec.user_choice === 'accepted' ? 'Used ✓' : 'Use this', { size: 'sm', variant: rec.user_choice === 'accepted' ? 'secondary' : 'primary', onClick: () => respond({ choice: 'accepted' }) }),
      Button(rec.user_choice === 'edited' ? 'Edited ✓' : 'Edit', { size: 'sm', variant: 'secondary', onClick: edit }),
      Button(rec.user_choice === 'ignored' ? 'Ignored ✓' : 'Ignore', { size: 'sm', variant: 'ghost', onClick: () => respond({ choice: 'ignored' }) })),
    onRespond && rec.user_choice !== 'pending' && h('p', { class: 'hint' }, choiceText(rec.user_choice)),
    message);
}

function openEditor({ rec, units, timed, onSave }) {
  const unit = weightUnit(units);
  const bodyweight = rec.weight_kg == null && rec.action !== 'start' && !rec.increment_kg;
  const weight = Field({ label: `Weight (${unit})`, name: 'weight', type: 'number', inputmode: 'decimal', step: units === 'imperial' ? 5 : 2.5, min: 0,
    value: weightToDisplay(rec.chosen_weight_kg ?? rec.weight_kg, units) });
  const reps = Field({ label: timed ? 'Seconds per set' : 'Reps per set', name: 'reps', type: 'number', inputmode: 'numeric', step: 1, min: 1,
    value: rec.chosen_reps ?? rec.reps_goal ?? rec.rep_min });
  const form = h('div', { class: 'stack' },
    h('p', { class: 'hint' }, 'These replace the suggestion for sets you haven\'t finished yet.'), bodyweight ? null : weight.el, reps.el);
  let modal;
  const save = () => {
    const { ok, errors, payload } = parseEdit({ weight: weight.input.value, reps: reps.input.value }, units, { allowWeight: !bodyweight });
    weight.setError(errors.weight); reps.setError(errors.reps || errors.form);
    if (!ok) return;
    modal.close();
    onSave(payload);
  };
  modal = openModal({ title: 'Use your own numbers', body: form, actions: [
    Button('Cancel', { variant: 'ghost', onClick: () => modal.close() }), Button('Save', { onClick: save })] });
}
