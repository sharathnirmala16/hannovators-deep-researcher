import type { ReactNode } from 'react';

export interface Fact {
  label: string;
  value: ReactNode;
}

/** Label / value pairs in two aligned columns. Empty values are left out. */
export function FactList({ facts }: { facts: readonly Fact[] }) {
  const shown = facts.filter(
    (fact) => fact.value !== null && fact.value !== '' && fact.value !== false,
  );
  if (shown.length === 0) return null;
  return (
    <dl className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-4 gap-y-1.5 text-[13px]">
      {shown.map((fact) => (
        <div key={fact.label} className="contents">
          <dt className="text-muted-foreground">{fact.label}</dt>
          <dd className="min-w-0 break-words">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}
