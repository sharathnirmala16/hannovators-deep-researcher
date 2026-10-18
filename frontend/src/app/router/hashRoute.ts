import { useSyncExternalStore } from 'react';

/**
 * A small hash router (PLAN.md section 10.1), no dependency:
 * `#/` is the workspaces page and `#/w/<id>?tab=research|trajectory` a
 * workspace. `step=<n>` asks the trajectory tab to open one step.
 */
export type WorkspaceTab = 'research' | 'trajectory';

export type Route =
  | { page: 'home' }
  | { page: 'workspace'; id: string; tab: WorkspaceTab; step: number | null };

const WORKSPACE_PATH = /^\/w\/([^/?#]+)\/?$/;

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, '') || '/';
  const [path = '/', query = ''] = raw.split('?');
  const match = WORKSPACE_PATH.exec(path);
  const id = match?.[1];
  if (!id) return { page: 'home' };
  const params = new URLSearchParams(query);
  const tab = params.get('tab') === 'trajectory' ? 'trajectory' : 'research';
  const step = Number(params.get('step'));
  return {
    page: 'workspace',
    id: decodeURIComponent(id),
    tab,
    step: Number.isInteger(step) && step > 0 ? step : null,
  };
}

export function routeHref(route: Route): string {
  if (route.page === 'home') return '#/';
  const params = new URLSearchParams({ tab: route.tab });
  if (route.step !== null) params.set('step', String(route.step));
  return `#/w/${encodeURIComponent(route.id)}?${params.toString()}`;
}

export function workspaceHref(
  id: string,
  tab: WorkspaceTab = 'research',
  step: number | null = null,
): string {
  return routeHref({ page: 'workspace', id, tab, step });
}

export function navigate(href: string, replace = false): void {
  if (window.location.hash === href) return;
  if (replace) {
    const url = new URL(window.location.href);
    url.hash = href;
    window.history.replaceState(window.history.state, '', url);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else {
    window.location.hash = href;
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

const readHash = () => window.location.hash;

/** The current route; re-renders on every hash change. */
export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, readHash, () => '');
  return parseHash(hash);
}
