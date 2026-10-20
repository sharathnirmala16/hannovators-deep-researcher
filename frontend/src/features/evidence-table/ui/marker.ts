/** The button around a traceable value: no chrome, the span carries the mark. */
export const MARK_BUTTON = 'group rounded-[2px] text-left';

/**
 * The highlighter language (PLAN.md section 10.3): a marker underline on a
 * traceable value, `marked-soft` on hover, `marked` when it is the selection.
 * Put it on an inline span so the stroke follows each wrapped line.
 */
export function markClasses(active: boolean, traceable: boolean): string {
  if (active) return 'marked transition-colors';
  return traceable
    ? 'rounded-[2px] underline decoration-marker decoration-2 underline-offset-[3px] transition-colors group-hover:marked-soft'
    : 'rounded-[2px] transition-colors group-hover:bg-desk';
}
