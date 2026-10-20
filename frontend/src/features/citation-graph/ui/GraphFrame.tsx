import type { ReactNode } from 'react';

import { SectionHeader } from '@/shared/ui/section-header';

/** The graph view's header and padding, shared by every state. */
export function GraphFrame({
  meta,
  children,
}: {
  meta?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby="citation-graph-title"
      className="flex min-h-0 flex-1 flex-col gap-3 p-4"
    >
      <SectionHeader
        id="citation-graph-title"
        title="Citation graph"
        meta={meta}
      />
      {children}
    </section>
  );
}
