import type { ReactNode } from 'react';

import { ScrollArea } from '@/shared/ui/scroll-area';

interface PaneProps {
  label: string;
  children: ReactNode;
}

export function Pane({ label, children }: PaneProps) {
  return (
    <section aria-label={label} className="h-full">
      <ScrollArea className="h-full">
        <div className="flex flex-col gap-4 p-4">{children}</div>
      </ScrollArea>
    </section>
  );
}
