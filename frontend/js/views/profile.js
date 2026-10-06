import { api } from '../api.js';
import { h } from '../dom.js';
import { navigate } from '../router.js';
import { clearSession, state } from '../store.js';
import { WEEKDAYS, formatHeight, formatWeight, labelFor } from '../units.js';
import { Button, SectionHeader, confirmModal } from '../ui/components.js';

export function renderProfile(root, { onLoggedOut }) {
  const p = state.profile;
  const u = p.unit_preference;
  const row = (label, value) => [h('dt', {}, label), h('dd', {}, value ?? 'Not set')];

  const logout = () => confirmModal({
    title: 'Log out of Liv?', message: 'You will need to log in again to see your data.', confirmLabel: 'Log out',
    onConfirm: async () => {
      try { await api.logout(); } catch { /* the session is dropped locally either way */ }
      clearSession();
      onLoggedOut();
    },
  });

  root.replaceChildren(h('div', {},
    SectionHeader('Profile', state.user.email, Button('Edit profile', { variant: 'secondary', size: 'sm', onClick: () => navigate('/profile/edit') })),
    h('div', { class: 'stack' },
      h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'Body'),
        h('dl', { class: 'defs' }, row('Age', p.age), row('Sex', p.sex && labelFor(p.sex)),
          row('Height', formatHeight(p.height_cm, u)), row('Weight', formatWeight(p.weight_kg, u)),
          row('Units', labelFor(u)))),
      h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'Training'),
        h('dl', { class: 'defs' },
          row('Experience', p.experience_level && labelFor(p.experience_level)), row('Goal', p.goal?.name),
          row('Days per week', p.training_days_per_week), row('Session length', p.preferred_workout_minutes && `${p.preferred_workout_minutes} min`),
          row('Preferred days', p.preferred_training_days.length ? p.preferred_training_days.map((d) => WEEKDAYS[d]).join(', ') : 'Any'),
          row('Location', p.training_location && labelFor(p.training_location)))),
      h('section', { class: 'card' }, h('h2', { class: 'section-title-sm' }, 'Equipment'),
        p.equipment.length
          ? h('div', { class: 'chips' }, p.equipment.map((e) => h('span', { class: 'badge' }, e.name)))
          : h('p', {}, 'No equipment selected.')),
      h('div', {}, Button('Log out', { variant: 'ghost', onClick: logout })))));
}
