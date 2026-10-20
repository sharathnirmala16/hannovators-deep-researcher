import { cn } from '@/shared/lib/cn';

/** A stage lane tile: quiet on the desk tint, ink underline when it filters. */
export function laneClass(pressed: boolean): string {
  return cn(
    'flex flex-col items-start justify-between gap-1 rounded-md px-2 py-1.5 text-left transition-colors',
    pressed
      ? 'bg-accent shadow-[inset_0_-2px_0_rgba(24,34,58,1)]'
      : 'bg-desk hover:bg-shade-2',
  );
}
