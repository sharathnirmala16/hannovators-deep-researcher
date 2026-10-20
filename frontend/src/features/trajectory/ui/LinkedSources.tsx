import { FileText } from 'lucide-react';

import type { TrajectoryStepSummary } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { SectionHeader } from '@/shared/ui/section-header';

import type { StepContext } from '../model/stepContext';

interface LinkedSourcesProps {
  step: TrajectoryStepSummary;
  context: StepContext;
}

/** Sources the step touched; each opens in the Research tab. */
export function LinkedSources({ step, context }: LinkedSourcesProps) {
  if (step.source_ids.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <SectionHeader
        title="Linked sources"
        meta={<span>{step.source_ids.length}</span>}
      />
      <p className="text-xs text-muted-foreground">
        Select a source to open it in the Research tab.
      </p>
      <ul className="flex flex-col">
        {step.source_ids.map((sourceId) => {
          const title = context.sourceTitle(sourceId);
          return (
            <li key={sourceId} className="-mx-2">
              <button
                type="button"
                onClick={() => context.onOpenSource(sourceId, step)}
                className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-desk"
              >
                <FileText
                  aria-hidden
                  className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                />
                <span
                  className={cn(
                    'min-w-0 text-link',
                    !title && 'font-mono text-xs break-all',
                  )}
                >
                  {title ?? sourceId}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
