import type { TrajectoryStepSummary } from '@/domains/workspace';

type Step = TrajectoryStepSummary;

/** Index of the first step whose id is >= `id` (steps are sorted by id). */
function lowerBound(steps: readonly Step[], id: number): number {
  let low = 0;
  let high = steps.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    const step = steps[mid];
    if (step && step.id < id) low = mid + 1;
    else high = mid;
  }
  return low;
}

/**
 * Inserts new steps and replaces known ones by id (a step is resent when it
 * closes, for example RUNNING -> OK). Keeps the list sorted by id and returns
 * the same array when nothing changed.
 */
export function upsertSteps(
  current: readonly Step[],
  incoming: readonly Step[],
): readonly Step[] {
  if (incoming.length === 0) return current;
  const next = current.slice();
  for (const step of incoming) {
    const last = next[next.length - 1];
    if (!last || step.id > last.id) {
      next.push(step);
      continue;
    }
    const index = lowerBound(next, step.id);
    if (next[index]?.id === step.id) next[index] = step;
    else next.splice(index, 0, step);
  }
  return next;
}

export function lastId(steps: readonly Step[]): number {
  return steps[steps.length - 1]?.id ?? 0;
}

/** Cursor to resume after a pause: the oldest open step, else the newest. */
export function resumeCursor(steps: readonly Step[]): number {
  const running = steps.find((step) => step.status === 'RUNNING');
  return running ? running.id - 1 : lastId(steps);
}

export function indexById(steps: readonly Step[]): Map<number, Step> {
  return new Map(steps.map((step) => [step.id, step]));
}

export function childrenOf(steps: readonly Step[], id: number): Step[] {
  return steps.filter((step) => step.parent_id === id);
}

/** Parent chain from the root down to the step's direct parent. */
export function ancestorIds(
  byId: ReadonlyMap<number, Step>,
  step: Step,
): number[] {
  const chain: number[] = [];
  const seen = new Set<number>([step.id]);
  let parent = step.parent_id;
  while (parent !== null && !seen.has(parent)) {
    chain.unshift(parent);
    seen.add(parent);
    parent = byId.get(parent)?.parent_id ?? null;
  }
  return chain;
}
