// Reusable UI building blocks. Views compose these; they hold no business logic.
import { h, mount } from '../dom.js';

export function Button(label, { variant = 'primary', onClick, type = 'button', disabled = false, block = false, size } = {}) {
  const cls = ['btn', `btn-${variant}`, block && 'btn-block', size === 'sm' && 'btn-sm'].filter(Boolean).join(' ');
  return h('button', { class: cls, type, disabled, onClick }, label);
}

let fieldCounter = 0;

/** Labelled text/number input with an inline error slot. */
export function Field({ label, name, type = 'text', value = '', hint, autocomplete, min, max, step, inputmode, required = false }) {
  const id = `f${++fieldCounter}`;
  const input = h('input', { class: 'input', id, name, type, value, autocomplete, min, max, step, inputmode, required, 'aria-describedby': `${id}-msg` });
  const msg = h('div', { id: `${id}-msg`, 'aria-live': 'polite' });
  const el = h('div', { class: 'field' }, h('label', { for: id }, label), input, hint && h('span', { class: 'hint' }, hint), msg);
  const setError = (text) => {
    el.classList.toggle('invalid', Boolean(text));
    input.setAttribute('aria-invalid', text ? 'true' : 'false');
    mount(msg, text ? h('span', { class: 'field-error' }, text) : null);
  };
  return { el, input, setError };
}

/** Native dropdown. options: [{ value, label }] */
export function Select({ label, name, options, value = '', placeholder, onChange }) {
  const id = `f${++fieldCounter}`;
  const select = h('select', { class: 'select', id, name, onChange: (e) => onChange && onChange(e.target.value) },
    placeholder && h('option', { value: '' }, placeholder),
    options.map((o) => h('option', { value: o.value }, o.label)));
  select.value = String(value ?? '');
  const el = h('div', { class: 'field' }, label && h('label', { for: id }, label), select);
  return { el, select };
}

/** Pill buttons. multiple=false behaves like a radio group, multiple=true like checkboxes. */
export function Chips({ label, options, value, multiple = false, onChange }) {
  let current = multiple ? new Set(value || []) : value ?? null;
  const group = h('div', { class: 'chips', role: 'group', 'aria-label': label });
  const sync = () => {
    for (const btn of group.children) {
      const on = multiple ? [...current].some((v) => String(v) === btn.dataset.key) : String(current) === btn.dataset.key;
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
  };
  for (const o of options) {
    group.append(h('button', {
      class: 'chip', type: 'button', 'data-key': String(o.value),
      onClick: () => {
        if (multiple) { current.has(o.value) ? current.delete(o.value) : current.add(o.value); onChange([...current]); }
        else { current = o.value; onChange(o.value); }
        sync();
      },
    }, o.label));
  }
  sync();
  const api = { set: (v) => { current = multiple ? new Set(v) : v; sync(); } };
  return { el: h('div', { class: 'field' }, h('span', { class: 'label' }, label), group), ...api };
}

/** Single-choice list with a title and description per option. */
export function ChoiceList({ label, options, value, onChange }) {
  let current = value ?? null;
  const list = h('div', { class: 'choice-list', role: 'radiogroup', 'aria-label': label });
  const sync = () => {
    for (const btn of list.children) btn.setAttribute('aria-checked', String(current) === btn.dataset.key ? 'true' : 'false');
  };
  for (const o of options) {
    list.append(h('button', {
      class: 'choice', type: 'button', role: 'radio', 'data-key': String(o.value),
      onClick: () => { current = o.value; onChange(o.value); sync(); },
    }, h('strong', {}, o.label), o.description && h('span', {}, o.description)));
  }
  sync();
  return { el: h('div', { class: 'field' }, h('span', { class: 'label' }, label), list) };
}

/** Accessible tab strip. Caller renders the panel content in response to onSelect. */
export function Tabs({ items, active, onSelect }) {
  const bar = h('div', { class: 'tabs', role: 'tablist' });
  const select = (id, focus = false) => {
    for (const btn of bar.children) {
      const on = btn.dataset.id === id;
      btn.setAttribute('aria-selected', String(on));
      btn.tabIndex = on ? 0 : -1;
      if (on && focus) btn.focus();
    }
    onSelect(id);
  };
  items.forEach((item) => bar.append(h('button', {
    class: 'tab', type: 'button', role: 'tab', 'data-id': item.id,
    onClick: () => select(item.id),
    onKeydown: (e) => {
      const ids = items.map((i) => i.id);
      const i = ids.indexOf(item.id);
      if (e.key === 'ArrowRight') select(ids[(i + 1) % ids.length], true);
      if (e.key === 'ArrowLeft') select(ids[(i - 1 + ids.length) % ids.length], true);
    },
  }, item.label)));
  select(active);
  return bar;
}

/** Modal built on native <dialog> (focus trap, Esc to close). Returns { close, body }. */
export function openModal({ title, body, actions = [] }) {
  const dialog = h('dialog', { class: 'modal', 'aria-labelledby': 'modal-title' },
    h('h2', { id: 'modal-title' }, title), body, h('div', { class: 'modal-actions' }, actions));
  const close = () => { dialog.close(); dialog.remove(); };
  dialog.addEventListener('cancel', (e) => { e.preventDefault(); close(); });
  document.body.append(dialog);
  dialog.showModal();
  return { close, dialog };
}

export function confirmModal({ title, message, confirmLabel, danger = false, onConfirm }) {
  let modal;
  modal = openModal({
    title,
    body: h('p', {}, message),
    actions: [
      Button('Cancel', { variant: 'ghost', onClick: () => modal.close() }),
      Button(confirmLabel, { variant: danger ? 'danger' : 'primary', onClick: async () => { modal.close(); await onConfirm(); } }),
    ],
  });
}

export const Loading = (text = 'Loading') =>
  h('div', { class: 'state-center', role: 'status' }, h('div', { class: 'spinner' }), h('span', { class: 'hint' }, text));

export const ErrorState = (message, onRetry) =>
  h('div', { class: 'state-center', role: 'alert' }, h('h3', {}, "Couldn't load this"), h('p', {}, message),
    onRetry && Button('Try again', { variant: 'secondary', onClick: onRetry }));

export const Empty = ({ title, text, action }) =>
  h('div', { class: 'empty' }, h('h3', {}, title), text && h('p', {}, text), action);

export const SectionHeader = (title, subtitle, action) =>
  h('div', { class: 'section-header' }, h('div', {}, h('h1', {}, title), subtitle && h('p', {}, subtitle)), action);

export const Alert = (text, kind = 'error') => h('div', { class: kind === 'success' ? 'alert alert-success' : 'alert', role: 'alert' }, text);

export function Steps(total, done) {
  const el = h('div', { class: 'steps', role: 'progressbar', 'aria-valuemin': 1, 'aria-valuemax': total, 'aria-valuenow': done });
  for (let i = 1; i <= total; i += 1) el.append(h('i', { class: i <= done ? 'done' : '' }));
  return el;
}

/** Runs loader, shows spinner → content or error with retry. */
export async function loadInto(container, loader, render) {
  // A newer load into the same container (e.g. the user switched tabs) supersedes this one.
  const token = (container.loadToken = (container.loadToken || 0) + 1);
  mount(container, Loading());
  try {
    const data = await loader();
    if (container.loadToken !== token) return;
    mount(container, render(data));
  } catch (e) {
    if (container.loadToken !== token) return;
    mount(container, ErrorState(e.message, () => loadInto(container, loader, render)));
  }
}
