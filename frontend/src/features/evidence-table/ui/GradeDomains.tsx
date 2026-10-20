import type { Synthesis } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { GRADE_DOMAINS, downgradeReasons } from '../model/evidence';

type GradeAssessment = Synthesis['pairwise_summaries'][number]['grade'];

/** The five GRADE domains; judgements that downgrade are in the caution tone. */
export function GradeDomains({ grade }: { grade: GradeAssessment }) {
  const downgraded = new Set(
    downgradeReasons(grade).map((reason) => reason.domain),
  );
  return (
    <dl className="grid max-w-[72ch] grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 rounded-md bg-shade-0 px-3 py-2 text-xs">
      {GRADE_DOMAINS.map(([key, domain]) => (
        <div key={key} className="contents">
          <dt className="text-muted-foreground">{domain}</dt>
          <dd
            className={cn(
              'text-foreground',
              downgraded.has(domain) && 'font-semibold text-tone-caution',
            )}
          >
            {grade[key] || 'Not assessed'}
          </dd>
        </div>
      ))}
    </dl>
  );
}
