import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { Alert, Button, Field, Tabs } from '../ui/components.js';

export function renderAuth(root, { onAuthed }) {
  let mode = 'login';
  const card = h('div', { class: 'card card-lift auth-card' });

  function form() {
    const registering = mode === 'register';
    const email = Field({ label: 'Email', name: 'email', type: 'email', autocomplete: 'email', required: true });
    const password = Field({
      label: 'Password', name: 'password', type: 'password', required: true,
      autocomplete: registering ? 'new-password' : 'current-password',
      hint: registering ? 'At least 10 characters.' : undefined,
    });
    const feedback = h('div');
    const submit = Button(registering ? 'Create account' : 'Log in', { type: 'submit', block: true });

    const el = h('form', {
      class: 'form-stack', novalidate: true,
      onSubmit: async (e) => {
        e.preventDefault();
        email.setError(''); password.setError(''); mount(feedback);
        if (!email.input.value.trim()) return email.setError('Enter your email.');
        if (!password.input.value) return password.setError('Enter your password.');
        if (registering && password.input.value.length < 10) return password.setError('Use at least 10 characters.');
        submit.disabled = true;
        try {
          const call = registering ? api.register : api.login;
          await call(email.input.value.trim(), password.input.value);
          await onAuthed();
        } catch (err) {
          const fields = err.fieldErrors;
          if (fields.email) email.setError(fields.email);
          if (fields.password) password.setError(fields.password);
          if (!fields.email && !fields.password) mount(feedback, Alert(err.message));
          submit.disabled = false;
        }
      },
    }, email.el, password.el, feedback, submit);
    return el;
  }

  const panel = h('div', { class: 'tab-panel' });
  const render = () => mount(panel, form());
  const tabs = Tabs({
    items: [{ id: 'login', label: 'Log in' }, { id: 'register', label: 'Create account' }],
    active: mode,
    onSelect: (id) => { mode = id; render(); },
  });
  mount(card, tabs, panel);

  mount(root, h('div', { class: 'auth' },
    h('div', {}, h('div', { class: 'brand' }, 'Liv'), h('p', {}, 'Your health, quantified.')),
    card));
}
