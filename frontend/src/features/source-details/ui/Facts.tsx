import { cn } from '@/shared/lib/cn';

import type { Fact } from '../model/record';

/** A definition list: quiet labels on the left, values on the right. */
export function Facts({ facts }: { facts: readonly (Fact | null)[] }) {
  const shown = facts.filter((fact): fact is Fact => fact !== null);
  if (shown.length === 0) return null;
  return (
    <dl className="grid grid-cols-[minmax(7rem,max-content)_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-sm">
      {shown.map((fact) => (
        <div key={fact.label} className="contents">
          <dt className="text-xs leading-5 text-muted-foreground">
            {fact.label}
          </dt>
          <dd
            className={cn(
              'min-w-0 text-foreground tabular-nums',
              fact.mono && 'font-mono text-xs leading-5 break-words',
            )}
          >
            {fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
