import { api } from '../api.js';
import { navigate } from '../router.js';
import { Alert, confirmModal, openModal, Button } from '../ui/components.js';
import { h } from '../dom.js';

/** Starts a workout from a plan day and opens it. Offers to resume if one is already running. */
export async function startWorkout(planDayId, { onError } = {}) {
  try {
    const session = await api.startSession(planDayId);
    navigate(`/workout/session/${session.id}`);
  } catch (e) {
    if (e.code === 'workout_in_progress' && e.details && e.details.session_id) {
      confirmModal({
        title: 'Workout already in progress',
        message: 'You have an unfinished workout. Resume it before starting another.',
        confirmLabel: 'Resume workout',
        onConfirm: () => navigate(`/workout/session/${e.details.session_id}`),
      });
      return;
    }
    if (onError) onError(e.message);
    else { const modal = openModal({ title: "Couldn't start", body: Alert(e.message), actions: [Button('OK', { onClick: () => modal.close() })] }); }
  }
}

export const resumeCard = (session) => h('div', { class: 'resume-card' },
  h('div', {}, h('strong', {}, 'Workout in progress'), h('small', {}, session.name || 'Workout')),
  Button('Resume', { onClick: () => navigate(`/workout/session/${session.id}`) }));
