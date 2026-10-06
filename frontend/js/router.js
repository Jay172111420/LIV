export const navigate = (path) => { location.hash = path; };
export const currentPath = () => location.hash.slice(1).split('?')[0] || '/home';

/** Matches `/workout/plan/:id` style patterns. Returns { view, params } or null. */
export function matchRoute(path, routes) {
  for (const [pattern, view] of Object.entries(routes)) {
    const keys = [];
    const source = pattern.replace(/:([a-zA-Z]+)/g, (_, key) => { keys.push(key); return '([^/]+)'; });
    const match = new RegExp(`^${source}$`).exec(path);
    if (match) return { view, params: Object.fromEntries(keys.map((k, i) => [k, decodeURIComponent(match[i + 1])])) };
  }
  return null;
}
