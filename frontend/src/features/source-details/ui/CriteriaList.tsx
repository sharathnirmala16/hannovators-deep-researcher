import { Tag } from '@/shared/ui/tag';

import { criterionName, type Criterion } from '../model/record';

/** Appraisal criteria: met or not, and why. */
export function CriteriaList({ criteria }: { criteria: readonly Criterion[] }) {
  if (criteria.length === 0) return null;
  return (
    <ul className="flex flex-col gap-2">
      {criteria.map((item, index) => (
        <li
          key={`${item.criterion}-${index}`}
          className="flex flex-col gap-0.5"
        >
          <span className="flex items-center gap-2 text-sm text-foreground">
            {criterionName(item.criterion)}
            {item.matched === null ? null : (
              <Tag tone={item.matched ? 'positive' : 'negative'}>
                {item.matched ? 'Met' : 'Not met'}
              </Tag>
            )}
          </span>
          {item.rationale ? (
            <span className="text-xs text-muted-foreground">
              {item.rationale}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
