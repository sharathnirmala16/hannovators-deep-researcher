import type { RobJudgement, SourceView } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { humanize, textAt, type JsonObject } from '../model/record';

const DOT: Record<RobJudgement, string> = {
  LOW: 'bg-rob-low',
  SOME_CONCERNS: 'bg-rob-some',
  HIGH: 'bg-rob-high',
};

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

interface RobDomainsProps {
  rob2: NonNullable<SourceView['rob2']>;
  /** Per-domain reasons from the appraisal, keyed like `rob2.domains`. */
  rationale: JsonObject;
}

/** RoB 2: overall judgement, then each domain with its traffic light and reason. */
export function RobDomains({ rob2, rationale }: RobDomainsProps) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm">
        <span className="text-muted-foreground">Overall </span>
        <span className={cn('font-semibold', TEXT[rob2.overall])}>
          {JUDGEMENT[rob2.overall]}
        </span>
      </p>
      <ul className="flex flex-col gap-2">
        {Object.entries(rob2.domains).map(([domain, judgement], index) => {
          // "abstract-only: ..." repeats the appraisal basis shown above.
          const reason = textAt(rationale, domain)?.replace(
            /^[a-z]+(?:-[a-z]+)*:\s+/,
            '',
          );
          return (
            <li key={domain} className="flex gap-2">
              <span
                aria-hidden
                className={cn(
                  'mt-[5px] size-2.5 shrink-0 rounded-full',
                  DOT[judgement],
                )}
              />
              <div className="flex min-w-0 flex-col">
                <span className="text-sm text-foreground">
                  D{index + 1} {humanize(domain)}:{' '}
                  <span className={cn('font-medium', TEXT[judgement])}>
                    {JUDGEMENT[judgement]}
                  </span>
                </span>
                {reason ? (
                  <span className="text-xs text-muted-foreground">
                    {reason}
                  </span>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
