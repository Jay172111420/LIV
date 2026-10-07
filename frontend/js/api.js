// All network access goes through here so errors look the same everywhere.
export class ApiError extends Error {
  constructor(message, { status = 0, code = 'error', details = null } = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Server validation problems keyed by field name, e.g. { email: "..." }. */
  get fieldErrors() {
    const out = {};
    if (Array.isArray(this.details)) {
      for (const d of this.details) if (d && d.field) out[d.field] = d.message;
    }
    return out;
  }
}

let unauthorizedHandler = () => {};
export const onUnauthorized = (fn) => { unauthorizedHandler = fn; };

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Can't reach Liv. Check your connection and try again.", { code: 'network_error' });
  }
  if (res.status === 204) return null;

  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error body */ }

  if (!res.ok) {
    const err = data && data.error;
    const error = new ApiError(
      (err && err.message) || 'Something went wrong. Try again in a moment.',
      { status: res.status, code: (err && err.code) || 'error', details: err && err.details },
    );
    if (res.status === 401 && error.code === 'not_authenticated') unauthorizedHandler();
    throw error;
  }
  return data;
}

const localDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const qs = (params) => {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) if (v !== undefined && v !== null && v !== '') q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : '';
};

export const api = {
  register: (email, password) => request('POST', '/auth/register', { email, password }),
  login: (email, password) => request('POST', '/auth/login', { email, password }),
  logout: () => request('POST', '/auth/logout'),
  me: () => request('GET', '/auth/me'),
  profile: () => request('GET', '/profile'),
  updateProfile: (data) => request('PUT', '/profile', data),
  goals: () => request('GET', '/goals'),
  equipment: () => request('GET', '/equipment'),
  muscleGroups: () => request('GET', '/exercises/muscle-groups'),
  exercises: (params) => request('GET', `/exercises${qs(params)}`),
  plans: (params) => request('GET', `/workouts${qs(params)}`),
  plan: (id) => request('GET', `/workouts/${id}`),
  generatePlan: (data) => request('POST', '/workouts/generate', data),
  createCustomWorkout: (data) => request('POST', '/workouts/custom', data),
  updatePlan: (id, data) => request('PATCH', `/workouts/${id}`, data),
  deletePlan: (id) => request('DELETE', `/workouts/${id}`),
  renameDay: (planId, dayId, name) => request('PATCH', `/workouts/${planId}/days/${dayId}`, { name }),
  addPlanExercise: (planId, dayId, data) => request('POST', `/workouts/${planId}/days/${dayId}/exercises`, data),
  updatePlanExercise: (planId, dayId, id, data) => request('PATCH', `/workouts/${planId}/days/${dayId}/exercises/${id}`, data),
  removePlanExercise: (planId, dayId, id) => request('DELETE', `/workouts/${planId}/days/${dayId}/exercises/${id}`),
  reorderDay: (planId, dayId, ids) => request('PUT', `/workouts/${planId}/days/${dayId}/order`, { plan_exercise_ids: ids }),
  planSubstitutes: (planId, dayId, id) => request('GET', `/workouts/${planId}/days/${dayId}/exercises/${id}/substitutes`),
  replacePlanExercise: (planId, dayId, id, exerciseId) =>
    request('POST', `/workouts/${planId}/days/${dayId}/exercises/${id}/replace`, { exercise_id: exerciseId }),
  startSession: (planDayId) => request('POST', '/workout-sessions/start', { plan_day_id: planDayId, performed_on: localDate() }),
  activeSession: () => request('GET', '/workout-sessions/active'),
  session: (id) => request('GET', `/workout-sessions/${id}`),
  updateSet: (sessionId, setId, data) => request('PATCH', `/workout-sessions/${sessionId}/sets/${setId}`, data),
  addSet: (sessionId, exerciseId) => request('POST', `/workout-sessions/${sessionId}/exercises/${exerciseId}/sets`),
  deleteSet: (sessionId, exerciseId, setId) => request('DELETE', `/workout-sessions/${sessionId}/exercises/${exerciseId}/sets/${setId}`),
  completeSession: (id, data = {}) => request('POST', `/workout-sessions/${id}/complete`, data),
  discardSession: (id) => request('DELETE', `/workout-sessions/${id}`),
  sessions: (params) => request('GET', `/workout-sessions${qs(params)}`),
  respondToRecommendation: (sessionId, workoutExerciseId, body) =>
    request('POST', `/workout-sessions/${sessionId}/exercises/${workoutExerciseId}/recommendation`, body),
  exerciseHistory: (id, params) => request('GET', `/exercises/${id}/history${qs(params)}`),
  exerciseRecommendation: (id, params) => request('GET', `/exercises/${id}/recommendation${qs(params)}`),
  progressionSettings: (id) => request('GET', `/exercises/${id}/progression-settings`),
  saveProgressionSettings: (id, data) => request('PUT', `/exercises/${id}/progression-settings`, data),
  trainedExercises: () => request('GET', '/progress/exercises'),
  records: (params) => request('GET', `/progress/records${qs(params)}`),
  volumeReport: (weeks) => request('GET', `/progress/volume${qs({ weeks })}`),
  flagReport: () => request('GET', '/progress/flags'),
  increments: () => request('GET', '/progress/increments'),
  saveIncrement: (category, incrementKg) => request('PUT', `/progress/increments/${category}`, { increment_kg: incrementKg }),
  bodyMetrics: (params) => request('GET', `/body-metrics${qs(params)}`),
  addBodyMetric: (data) => request('POST', '/body-metrics', data),
  deleteBodyMetric: (id) => request('DELETE', `/body-metrics/${id}`),
  nutritionProfile: () => request('GET', '/nutrition/profile'),
};
