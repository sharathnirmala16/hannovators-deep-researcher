import type { ReactNode } from 'react';

interface SectionTitleProps {
  title: string;
  meta?: string | null | undefined;
  actions?: ReactNode;
}

/** The one section-header pattern of the panel: title, meta, actions. */
export function SectionTitle({ title, meta, actions }: SectionTitleProps) {
  return (
    <div className="flex items-baseline gap-2">
      <h3 className="text-[13px] font-medium">{title}</h3>
      {meta ? (
        <span className="text-xs text-muted-foreground tabular-nums">
          {meta}
        </span>
      ) : null}
      {actions ? <div className="ml-auto flex gap-1">{actions}</div> : null}
    </div>
  );
}
