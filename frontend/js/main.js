// App bootstrap: session check, route guards, and the persistent navigation shell.
import { onUnauthorized } from './api.js';
import { h, icon, mount } from './dom.js';
import { currentPath, matchRoute, navigate } from './router.js';
import { clearSession, loadSession, state } from './store.js';
import { ErrorState, Loading } from './ui/components.js';
import { renderAuth } from './views/auth.js';
import { renderHome } from './views/home.js';
import { renderNutrition } from './views/nutrition.js';
import { renderOnboarding } from './views/onboarding.js';
import { renderProfile } from './views/profile.js';
import { renderExerciseHistory } from './views/exerciseHistory.js';
import { renderProgress } from './views/progress.js';
import { renderWorkout } from './views/workout.js';
import { renderGenerator } from './views/generator.js';
import { renderPlan } from './views/plan.js';
import { renderSession } from './views/session.js';
import { renderSessionDetail } from './views/sessionDetail.js';

const root = document.getElementById('app');

const NAV = [
  { path: '/home', label: 'Home', icon: 'home' },
  { path: '/workout', label: 'Workout', icon: 'workout' },
  { path: '/nutrition', label: 'Nutrition', icon: 'nutrition' },
  { path: '/progress', label: 'Progress', icon: 'progress' },
  { path: '/profile', label: 'Profile', icon: 'profile' },
];

let shell = null; // { nav, main } while logged in, so tab changes don't rebuild it
let cleanup = null; // set by views that run timers; called before the next screen is drawn

const VIEWS = {
  '/home': renderHome,
  '/workout': renderWorkout,
  '/workout/generate': renderGenerator,
  '/workout/plan/:id': renderPlan,
  '/workout/session/:id': renderSession,
  '/workout/history/:id': renderSessionDetail,
  '/nutrition': renderNutrition,
  '/progress': renderProgress,
  '/progress/exercise/:id': renderExerciseHistory,
  '/profile': (el) => renderProfile(el, { onLoggedOut: () => { shell = null; navigate('/login'); } }),
};

function buildShell() {
  const main = h('main', { class: 'main', id: 'main', tabindex: '-1' });
  const nav = h('nav', { class: 'nav', 'aria-label': 'Primary' },
    h('div', { class: 'brand' }, 'Liv'),
    h('div', { class: 'nav-list' }, NAV.map((item) =>
      h('a', { class: 'nav-link', href: `#${item.path}`, 'data-path': item.path }, icon(item.icon), item.label))));
  mount(root, h('div', { class: 'shell' }, nav, main));
  return { nav, main };
}

function markActive(path) {
  const section = `/${path.split('/')[1]}`;
  for (const link of shell.nav.querySelectorAll('.nav-link')) {
    if (link.dataset.path === section) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
}

function route() {
  if (cleanup) { cleanup(); cleanup = null; }
  const path = currentPath();

  // Guard 1: logged-out users can only see the login screen.
  if (!state.user) {
    shell = null;
    if (path !== '/login') { navigate('/login'); return; }
    renderAuth(root, { onAuthed: afterAuth });
    return;
  }
  if (path === '/login') { navigate('/home'); return; }

  // Guard 2: finish onboarding before using the app.
  const onboardingDone = state.profile.onboarding_complete;
  if (!onboardingDone && path !== '/onboarding') { navigate('/onboarding'); return; }
  if (onboardingDone && path === '/onboarding') { navigate('/home'); return; }

  if (path === '/onboarding') { shell = null; renderOnboarding(root); return; }
  if (path === '/profile/edit') { shell = null; renderOnboarding(root, { editing: true }); return; }

  const matched = matchRoute(path, VIEWS);
  if (!matched) { navigate('/home'); return; }
  if (!shell || !root.contains(shell.main)) shell = buildShell();
  markActive(path);
  const result = matched.view(shell.main, matched.params);
  cleanup = typeof result === 'function' ? result : null; // async views return a Promise, which is not cleanup
  window.scrollTo(0, 0);
}

async function afterAuth() {
  await loadSession();
  const target = state.profile.onboarding_complete ? '/home' : '/onboarding';
  if (currentPath() === target) route(); else navigate(target);
}

async function boot() {
  mount(root, Loading('Starting Liv'));
  onUnauthorized(() => { clearSession(); shell = null; if (currentPath() === '/login') route(); else navigate('/login'); });
  try {
    await loadSession();
  } catch (e) {
    mount(root, ErrorState(e.message, boot));
    return;
  }
  window.addEventListener('hashchange', route, { once: false });
  if (!location.hash) location.hash = state.user ? '/home' : '/login';
  else route();
}

boot();
