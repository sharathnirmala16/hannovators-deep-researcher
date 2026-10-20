import { Fragment } from 'react';

import type { Funnel } from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { ToneDot } from '@/shared/ui/tag';

import { funnelSteps } from '../model/funnel';
import { PrismaExit } from './PrismaExit';
import { PrismaStep } from './PrismaStep';

/** UI wording for the records leaving the flow before each step. */
const EXIT_LABEL: Record<string, string> = {
  screened: 'Screened out',
  'full-text': 'No full text',
  included: 'Excluded after reading',
};

const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** PRISMA-style flow: kept records down the line, removed records branching off. */
export function PrismaFlow({ funnel }: { funnel: Funnel }) {
  const steps = funnelSteps(funnel);
  const max = steps[0]?.count ?? 0;
  return (
    <div className="flex min-w-0 flex-col gap-2">
      {funnel.seeds > 0 ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ToneDot tone="info" />
          Plus {plural(funnel.seeds, 'seed')} you added
        </p>
      ) : null}
      <ol aria-label="Screening flow" className="flex min-w-0 flex-col">
        {steps.map((step, index) => (
          <Fragment key={step.id}>
            {step.removed ? (
              <PrismaExit
                label={EXIT_LABEL[step.id] ?? sentence(step.removed.label)}
                count={step.removed.count}
              />
            ) : null}
            <PrismaStep
              label={step.label}
              count={step.count}
              removed={step.removed?.count ?? 0}
              max={max}
              kept={index > 0}
            />
          </Fragment>
        ))}
      </ol>
    </div>
  );
}
