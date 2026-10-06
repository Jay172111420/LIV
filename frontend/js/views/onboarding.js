import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { navigate } from '../router.js';
import { referenceData, refreshProfile, state } from '../store.js';
import { cmToFtIn, ftInToCm, kgToLb, labelFor, lbToKg } from '../units.js';
import { Alert, Button, ChoiceList, Chips, Field, Loading, Steps, loadInto } from '../ui/components.js';

const TOTAL_STEPS = 3;
const EXPERIENCE = [
  { value: 'beginner', label: 'Beginner', description: 'New to training, or coming back after a long break.' },
  { value: 'intermediate', label: 'Intermediate', description: 'Training regularly for a year or more.' },
  { value: 'advanced', label: 'Advanced', description: 'Several years of structured training.' },
];
const LOCATIONS = [
  { value: 'commercial_gym', label: 'Commercial gym', description: 'Full access to machines, cables and free weights.' },
  { value: 'home_gym', label: 'Home gym', description: 'Your own equipment at home.' },
  { value: 'home_bodyweight', label: 'Home, bodyweight', description: 'No equipment, or just a few basics.' },
];
const DURATIONS = [20, 30, 45, 60, 75, 90];

export async function renderOnboarding(root, { editing = false } = {}) {
  mount(root, Loading());
  let ref;
  try { ref = await referenceData(); } catch (e) {
    return mount(root, h('div', { class: 'onboarding' }, Alert(e.message), Button('Try again', { variant: 'secondary', onClick: () => renderOnboarding(root, { editing }) })));
  }

  const p = state.profile;
  const units = p.unit_preference || 'metric';
  // Working copy of the form, in the user's display units.
  const d = {
    units,
    age: p.age ?? '',
    sex: p.sex ?? null,
    heightCm: p.height_cm ?? null,
    weightKg: p.weight_kg ?? null,
    experience: p.experience_level ?? null,
    goalId: p.goal?.id ?? null,
    days: p.training_days_per_week ?? null,
    minutes: p.preferred_workout_minutes ?? null,
    location: p.training_location ?? null,
    equipmentIds: p.equipment.map((e) => e.id),
  };
  let step = 1;

  const frame = h('div', { class: 'onboarding' });

  function draw(error) {
    const builders = { 1: stepAbout, 2: stepTraining, 3: stepLocation };
    const { title, intro, content, validate } = builders[step]();
    const feedback = h('div', {}, error ? Alert(error) : null);
    const back = step > 1
      ? Button('Back', { variant: 'ghost', onClick: () => { step -= 1; draw(); } })
      : (editing ? Button('Cancel', { variant: 'ghost', onClick: () => navigate('/profile') }) : h('span'));
    const next = Button(step === TOTAL_STEPS ? (editing ? 'Save changes' : 'Finish setup') : 'Continue', {
      onClick: async () => {
        const problem = validate();
        if (problem) return draw(problem);
        if (step < TOTAL_STEPS) { step += 1; return draw(); }
        next.disabled = true;
        try { await save(); } catch (e) { draw(e.message); }
      },
    });
    mount(frame,
      Steps(TOTAL_STEPS, step),
      h('div', {}, h('p', { class: 'hint' }, `Step ${step} of ${TOTAL_STEPS}`), h('h1', {}, title), intro && h('p', {}, intro)),
      content, feedback, h('div', { class: 'onboarding-actions' }, back, next));
    frame.querySelector('h1').scrollIntoView?.({ block: 'start' });
  }

  async function save() {
    const payload = {
      unit_preference: d.units, age: Number(d.age), sex: d.sex, height_cm: d.heightCm, weight_kg: d.weightKg,
      experience_level: d.experience, goal_id: d.goalId, training_days_per_week: d.days,
      preferred_workout_minutes: d.minutes, training_location: d.location, equipment_ids: d.equipmentIds,
    };
    await api.updateProfile(payload);
    await refreshProfile();
    navigate(editing ? '/profile' : '/home');
  }

  // ---- step 1 ----
  function stepAbout() {
    const age = Field({ label: 'Age', name: 'age', type: 'number', inputmode: 'numeric', min: 13, max: 100, value: d.age });
    const imperial = d.units === 'imperial';
    const ftIn = d.heightCm != null ? cmToFtIn(d.heightCm) : { ft: '', inches: '' };
    const cm = Field({ label: 'Height (cm)', name: 'height', type: 'number', inputmode: 'decimal', value: d.heightCm != null ? Math.round(d.heightCm) : '' });
    const ft = Field({ label: 'Height (ft)', name: 'ft', type: 'number', inputmode: 'numeric', value: ftIn.ft });
    const inch = Field({ label: 'Height (in)', name: 'in', type: 'number', inputmode: 'numeric', value: ftIn.inches });
    const weight = Field({
      label: imperial ? 'Weight (lb)' : 'Weight (kg)', name: 'weight', type: 'number', inputmode: 'decimal', step: '0.1',
      value: d.weightKg != null ? Number((imperial ? kgToLb(d.weightKg) : d.weightKg).toFixed(1)) : '',
    });
    const sex = Chips({ label: 'Sex', options: ['male', 'female', 'other'].map((v) => ({ value: v, label: labelFor(v) })), value: d.sex, onChange: (v) => { d.sex = v; } });
    const units = Chips({
      label: 'Units', value: d.units, options: [{ value: 'metric', label: 'Metric (kg, cm)' }, { value: 'imperial', label: 'Imperial (lb, ft)' }],
      onChange: (v) => { capture(); d.units = v; draw(); },
    });

    function capture() {
      d.age = age.input.value;
      d.heightCm = imperial
        ? (ft.input.value || inch.input.value ? ftInToCm(Number(ft.input.value || 0), Number(inch.input.value || 0)) : null)
        : (cm.input.value ? Number(cm.input.value) : null);
      d.weightKg = weight.input.value ? (imperial ? lbToKg(Number(weight.input.value)) : Number(weight.input.value)) : null;
    }

    return {
      title: 'About you',
      intro: 'Liv uses this to set sensible starting points. You can change it any time.',
      content: h('div', { class: 'form-stack' }, units.el, h('div', { class: 'form-row' }, age.el, sex.el),
        imperial ? h('div', { class: 'form-row' }, ft.el, inch.el) : cm.el, weight.el),
      validate() {
        capture();
        const a = Number(d.age);
        if (!d.age || a < 13 || a > 100) return 'Enter an age between 13 and 100.';
        if (!d.sex) return 'Choose a sex option.';
        if (d.heightCm == null || d.heightCm < 90 || d.heightCm > 250) return 'Enter a height between 90 and 250 cm (about 3 ft to 8 ft 2 in).';
        if (d.weightKg == null || d.weightKg < 25 || d.weightKg > 400) return 'Enter a weight between 25 and 400 kg (about 55 to 880 lb).';
        return null;
      },
    };
  }

  // ---- step 2 ----
  function stepTraining() {
    const exp = ChoiceList({ label: 'Experience level', options: EXPERIENCE, value: d.experience, onChange: (v) => { d.experience = v; } });
    const goal = ChoiceList({
      label: 'Main goal', value: d.goalId, onChange: (v) => { d.goalId = v; },
      options: ref.goals.map((g) => ({ value: g.id, label: g.name, description: g.description })),
    });
    const days = Chips({ label: 'Training days per week', value: d.days, onChange: (v) => { d.days = v; },
      options: [1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: n, label: String(n) })) });
    const mins = Chips({ label: 'Session length', value: d.minutes, onChange: (v) => { d.minutes = v; },
      options: DURATIONS.map((n) => ({ value: n, label: `${n} min` })) });
    return {
      title: 'Your training',
      content: h('div', { class: 'form-stack' }, exp.el, goal.el, days.el, mins.el),
      validate() {
        if (!d.experience) return 'Choose your experience level.';
        if (!d.goalId) return 'Choose a main goal.';
        if (!d.days) return 'Choose how many days a week you can train.';
        if (!d.minutes) return 'Choose a session length.';
        return null;
      },
    };
  }

  // ---- step 3 ----
  function stepLocation() {
    const bySlug = Object.fromEntries(ref.equipment.map((e) => [e.slug, e.id]));
    const presets = { commercial_gym: ref.equipment.map((e) => e.id), home_bodyweight: [bySlug.bodyweight], home_gym: [] };
    let equipmentChips;
    const location = ChoiceList({
      label: 'Where do you train?', options: LOCATIONS, value: d.location,
      onChange: (v) => {
        // Suggest equipment for the place, but only if the user hasn't picked any yet.
        const untouched = d.equipmentIds.length === 0 || d.location == null;
        d.location = v;
        if (untouched) { d.equipmentIds = presets[v]; equipmentChips.set(d.equipmentIds); }
      },
    });
    equipmentChips = Chips({
      label: 'Equipment you can use', multiple: true, value: d.equipmentIds, onChange: (v) => { d.equipmentIds = v; },
      options: ref.equipment.map((e) => ({ value: e.id, label: e.name })),
    });
    return {
      title: 'Where you train',
      intro: 'Pick everything you have access to. Liv will only use equipment you select.',
      content: h('div', { class: 'form-stack' }, location.el, equipmentChips.el),
      validate() {
        if (!d.location) return 'Choose where you train.';
        if (d.equipmentIds.length === 0) return 'Select at least one option. Choose Bodyweight if you have no equipment.';
        return null;
      },
    };
  }

  mount(root, frame);
  draw();
}
