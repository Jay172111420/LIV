// Minimal app state: who is logged in, their profile, and cached lookup lists.
import { api } from './api.js';

export const state = { user: null, profile: null, goals: null, equipment: null };

export async function loadSession() {
  try {
    state.user = await api.me();
  } catch (e) {
    if (e.status === 401) { state.user = null; state.profile = null; return null; }
    throw e;
  }
  state.profile = await api.profile();
  return state.user;
}

export async function refreshProfile() {
  state.profile = await api.profile();
  return state.profile;
}

export async function referenceData() {
  if (!state.goals || !state.equipment) {
    [state.goals, state.equipment] = await Promise.all([api.goals(), api.equipment()]);
  }
  return { goals: state.goals, equipment: state.equipment };
}

export function clearSession() {
  state.user = null;
  state.profile = null;
}
