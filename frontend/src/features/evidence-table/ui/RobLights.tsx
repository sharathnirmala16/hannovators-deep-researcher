import type { RobJudgement, SourceView } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

import { humanize } from './findings';

/** robvis traffic lights: green low, amber some concerns, red high. */
const DOT: Record<RobJudgement, string> = {
  LOW: 'bg-rob-low',
  SOME_CONCERNS: 'bg-rob-some',
  HIGH: 'bg-rob-high',
};

/** Text tone for the overall judgement (the amber dot is too light for text). */
const TEXT: Record<RobJudgement, string> = {
  LOW: 'text-tone-positive',
  SOME_CONCERNS: 'text-tone-caution',
  HIGH: 'text-tone-negative',
};

const JUDGEMENT: Record<RobJudgement, string> = {
  LOW: 'Low risk',
  SOME_CONCERNS: 'Some concerns',
  HIGH: 'High risk',
};

/** RoB 2: one dot per domain (D1 to D5), then the overall judgement. */
export function RobLights({ rob2 }: { rob2: SourceView['rob2'] }) {
  if (!rob2) {
    return <span className="text-xs text-muted-foreground">Not assessed</span>;
  }
  const domains = Object.entries(rob2.domains).map(([domain, judgement]) => ({
    name: humanize(domain),
    judgement,
  }));
  const label = [
    ...domains.map(
      ({ name, judgement }) => `${name}: ${JUDGEMENT[judgement].toLowerCase()}`,
    ),
    `overall: ${JUDGEMENT[rob2.overall].toLowerCase()}`,
  ].join('; ');
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          role="img"
          aria-label={`Risk of bias (RoB 2). ${label}`}
          className="inline-flex flex-col items-start gap-1 rounded-sm"
        >
          <span aria-hidden className="inline-flex items-center gap-1">
            {domains.map(({ name, judgement }) => (
              <span
                key={name}
                className={cn('size-2.5 rounded-full', DOT[judgement])}
              />
            ))}
          </span>
          <span
            aria-hidden
            className={cn(
              'text-xs font-medium whitespace-nowrap',
              TEXT[rob2.overall],
            )}
          >
            {JUDGEMENT[rob2.overall]}
          </span>
        </span>
      </TooltipTrigger>
      <TooltipContent side="left" className="text-left">
        <dl className="grid grid-cols-[max-content_max-content] gap-x-3 gap-y-0.5">
          {domains.map(({ name, judgement }, index) => (
            <div key={name} className="contents">
              <dt>
                D{index + 1} {name}
              </dt>
              <dd className="font-semibold">{JUDGEMENT[judgement]}</dd>
            </div>
          ))}
          <dt>Overall</dt>
          <dd className="font-semibold">{JUDGEMENT[rob2.overall]}</dd>
        </dl>
      </TooltipContent>
    </Tooltip>
  );
}
