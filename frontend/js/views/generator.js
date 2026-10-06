import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { navigate } from '../router.js';
import { referenceData, state } from '../store.js';
import { Alert, Button, ChoiceList, Chips, Loading, SectionHeader, Select } from '../ui/components.js';

const EXPERIENCE = [
  { value: 'beginner', label: 'Beginner' }, { value: 'intermediate', label: 'Intermediate' }, { value: 'advanced', label: 'Advanced' },
];
const LOCATIONS = [
  { value: 'commercial_gym', label: 'Commercial gym', description: 'Machines, cables and free weights.' },
  { value: 'home_gym', label: 'Home gym', description: 'Whatever equipment you own.' },
  { value: 'home_bodyweight', label: 'Home, bodyweight', description: 'No equipment, bands or a pull-up bar only.' },
];
const SPLITS = [
  { value: 'auto', label: 'Let Liv choose (recommended)' },
  { value: 'full_body', label: 'Full body' },
  { value: 'upper_lower', label: 'Upper / lower' },
  { value: 'push_pull_legs', label: 'Push / pull / legs' },
  { value: 'push_pull', label: 'Push / pull' },
  { value: 'bro_split', label: 'Body-part split (one muscle group a day)' },
];
const DURATIONS = [20, 30, 45, 60, 75, 90];

export async function renderGenerator(root) {
  mount(root, Loading());
  let ref;
  try { ref = await referenceData(); } catch (e) {
    mount(root, Alert(e.message), Button('Back', { variant: 'ghost', onClick: () => navigate('/workout') }));
    return;
  }
  const p = state.profile;
  // Start from the profile; anything changed here applies to this plan only.
  const d = {
    goalId: p.goal?.id ?? null, experience: p.experience_level ?? null, days: p.training_days_per_week ?? null,
    minutes: p.preferred_workout_minutes ?? null, location: p.training_location ?? null,
    equipmentIds: p.equipment.map((e) => e.id), split: 'auto',
  };

  const feedback = h('div', { 'aria-live': 'polite' });
  const submit = Button('Generate plan', { block: true, onClick: generate });

  const goal = ChoiceList({ label: 'Goal', value: d.goalId, onChange: (v) => { d.goalId = v; },
    options: ref.goals.map((g) => ({ value: g.id, label: g.name, description: g.description })) });
  const experience = Chips({ label: 'Experience', value: d.experience, options: EXPERIENCE, onChange: (v) => { d.experience = v; } });
  const days = Chips({ label: 'Training days per week', value: d.days, onChange: (v) => { d.days = v; },
    options: [1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: n, label: String(n) })) });
  const minutes = Chips({ label: 'Session length', value: d.minutes, onChange: (v) => { d.minutes = v; },
    options: DURATIONS.map((n) => ({ value: n, label: `${n} min` })) });
  const location = ChoiceList({ label: 'Where you train', value: d.location, options: LOCATIONS, onChange: (v) => { d.location = v; } });
  const equipment = Chips({ label: 'Available equipment', multiple: true, value: d.equipmentIds, onChange: (v) => { d.equipmentIds = v; },
    options: ref.equipment.map((e) => ({ value: e.id, label: e.name })) });
  const split = Select({ label: 'Training style', name: 'split', options: SPLITS, value: d.split, onChange: (v) => { d.split = v; } });

  mount(root, h('div', { class: 'stack generator' },
    h('a', { class: 'back-link', href: '#/workout' }, '← Workout'),
    SectionHeader('Generate a plan', 'Liv builds a weekly plan from these answers. Only equipment you select is ever used.'),
    h('div', { class: 'form-stack' }, goal.el, experience.el, days.el, minutes.el, location.el, equipment.el,
      h('div', {}, split.el, h('p', { class: 'hint' }, 'A split divides your week into days that each focus on certain muscles. Auto picks one that suits your goal, level and number of days.'))),
    feedback, submit));

  function check() {
    if (!d.goalId) return 'Choose a goal.';
    if (!d.experience) return 'Choose your experience level.';
    if (!d.days) return 'Choose how many days a week you can train.';
    if (!d.minutes) return 'Choose a session length.';
    if (!d.location) return 'Choose where you train.';
    if (d.equipmentIds.length === 0) return 'Select at least one option. Choose Bodyweight if you have no equipment.';
    return null;
  }

  async function generate() {
    const problem = check();
    if (problem) { mount(feedback, Alert(problem)); return; }
    submit.disabled = true;
    submit.textContent = 'Building your plan';
    mount(feedback, null);
    try {
      const plan = await api.generatePlan({
        goal_id: d.goalId, experience_level: d.experience, days_per_week: d.days, duration_minutes: d.minutes,
        training_location: d.location, equipment_ids: d.equipmentIds, split_preference: d.split,
      });
      navigate(`/workout/plan/${plan.id}`);
    } catch (e) {
      submit.disabled = false;
      submit.textContent = 'Generate plan';
      mount(feedback, Alert(e.message));
    }
  }
}
