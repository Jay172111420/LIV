import { api } from '../api.js';
import { h, mount } from '../dom.js';
import { navigate } from '../router.js';
import { state } from '../store.js';
import { formatDate, formatMetric } from '../units.js';
import { Button, Empty, loadInto } from '../ui/components.js';
import { startWorkout } from './startWorkout.js';
import { openMetricModal } from '../ui/metricModal.js';

const localISODate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

const homePanel = (title, text, action) =>
  h('section', { class: 'panel', 'aria-label': title }, h('div', { class: 'empty' }, h('h2', {}, title), h('p', {}, text), action));

/** The training day after the one you last completed from this plan (wrapping around), else the first. */
function nextWorkout(plan, sessions) {
  const days = plan.days.filter((d) => !d.is_rest && d.exercises.length > 0);
  if (days.length === 0) return null;
  const last = sessions.find((s) => s.plan_id === plan.id && days.some((d) => d.id === s.plan_day_id));
  const idx = last ? days.findIndex((d) => d.id === last.plan_day_id) : -1;
  return days[(idx + 1) % days.length];
}

export function renderHome(root) {
  const units = state.profile.unit_preference;
  const content = h('div', { class: 'stack' });
  mount(root, h('div', { class: 'stack' },
    h('div', {}, h('h1', {}, greeting()),
      h('p', {}, new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }))),
    content));

  loadInto(content, async () => {
    const [sessions, nutrition, weights, active, plans] = await Promise.all([
      api.sessions({ limit: 10, status: 'completed' }), api.nutritionProfile(),
      api.bodyMetrics({ metric_type: 'weight', limit: 1 }), api.activeSession(), api.plans({ kind: 'generated' }),
    ]);
    const current = plans.find((p) => p.is_active);
    const plan = current ? await api.plan(current.id) : null;
    return { sessions, nutrition, weights, active, plan };
  }, ({ sessions, nutrition, weights, active, plan }) => {
    const doneToday = sessions.find((s) => s.performed_on === localISODate());
    const next = plan ? nextWorkout(plan, sessions) : null;

    let workout;
    if (active) {
      workout = homePanel("Workout in progress", `${active.name || 'Workout'} is waiting for you.`,
        Button('Resume workout', { variant: 'on-ink', onClick: () => navigate(`/workout/session/${active.id}`) }));
    } else if (next) {
      workout = homePanel(doneToday ? 'Next up' : "Today's workout",
        `${next.name}: ${next.exercises.length} exercises${next.estimated_minutes ? `, about ${next.estimated_minutes} min` : ''}.`,
        Button('Start workout', { variant: 'on-ink', onClick: () => startWorkout(next.id) }));
    } else {
      workout = homePanel('No workout plan yet', 'Generate a plan from your goal, schedule and equipment.',
        Button('Generate a plan', { variant: 'on-ink', onClick: () => navigate('/workout/generate') }));
    }

    const n = nutrition;
    const nutritionCard = h('section', { class: 'card', 'aria-label': 'Nutrition' },
      h('h2', { class: 'section-title-sm' }, 'Calories and macros'),
      n.calorie_target
        ? [h('div', { class: 'stat' }, n.calorie_target.toLocaleString(), h('small', {}, 'kcal target')),
           h('p', {}, [n.protein_g != null && `Protein ${n.protein_g} g`, n.carbs_g != null && `carbs ${n.carbs_g} g`, n.fat_g != null && `fat ${n.fat_g} g`].filter(Boolean).join(', '))]
        : Empty({ title: 'No targets yet', text: 'Calorie and macro tracking arrives in a later update.' }));

    const latest = weights[0];
    const progressCard = h('section', { class: 'card', 'aria-label': 'Progress' },
      h('h2', { class: 'section-title-sm' }, 'Current weight'),
      latest
        ? h('div', { class: 'empty' }, h('div', { class: 'stat' }, formatMetric(latest, units)),
            h('p', {}, `Logged ${formatDate(latest.recorded_at)}`),
            Button('Log weight', { variant: 'secondary', size: 'sm', onClick: logWeight }))
        : Empty({ title: 'No weight logged yet', text: 'Log your weight to start a trend.',
            action: Button('Log weight', { variant: 'secondary', size: 'sm', onClick: logWeight }) }));

    const activityCard = h('section', { class: 'card', 'aria-label': 'Daily activity' },
      h('h2', { class: 'section-title-sm' }, 'Steps and activity'),
      Empty({ title: 'No activity data', text: 'Steps and activity show up here once a phone or wearable is connected.' }));

    return [workout, h('div', { class: 'grid-2' }, nutritionCard, progressCard), activityCard];
  });

  function logWeight() {
    openMetricModal({ types: ['weight'], units, onSaved: () => renderHome(root) });
  }
}
