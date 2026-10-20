import type { SourceDetail } from '@/domains/workspace';
import { SectionHeader } from '@/shared/ui/section-header';

import { appraisalFacts } from '../model/appraisalFacts';
import { criteriaOf, objectAt } from '../model/record';
import { CriteriaList } from './CriteriaList';
import { Facts } from './Facts';
import { RobDomains } from './RobDomains';

/** Appraisal: M-score and directness, RoB 2 by domain, the criteria. */
export function AppraisalRecord({
  detail,
  needed,
}: {
  detail: SourceDetail;
  /** The workspace's appraisal threshold M. */
  needed: number | null;
}) {
  const facts = appraisalFacts(detail, needed);
  const criteria = criteriaOf(detail.appraisal);
  const { rob2 } = detail.source;
  if (facts.length === 0 && criteria.length === 0 && !rob2) return null;
  return (
    <section aria-labelledby="source-appraisal" className="flex flex-col gap-3">
      <SectionHeader id="source-appraisal" title="Appraisal" />
      <Facts facts={facts} />
      {rob2 ? (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Risk of bias (RoB 2)
          </h4>
          <RobDomains
            rob2={rob2}
            rationale={objectAt(detail.appraisal, 'rob2_rationale')}
          />
        </div>
      ) : null}
      {criteria.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Eligibility criteria
          </h4>
          <CriteriaList criteria={criteria} />
        </div>
      ) : null}
    </section>
  );
}
