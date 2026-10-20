import { CircleMinusIcon, CirclePlusIcon } from 'lucide-react';
import type { SyntheticEvent } from 'react';

import { studyLabel, type SourceView } from '@/domains/workspace';
import { Button } from '@/shared/ui/button';

import { useDecisionControl } from '../model/useDecisionControl';
import { DecisionDialog } from './DecisionDialog';

const stop = (event: SyntheticEvent) => event.stopPropagation();

/** A compact include/exclude button for a source table row. */
export function DecisionRowAction({ source }: { source: SourceView }) {
  const control = useDecisionControl(source);
  if (!control.kind) return null;
  const include = control.kind === 'INCLUDE';
  const label = `${include ? 'Include' : 'Exclude'} ${studyLabel(source)}`;
  return (
    // The row opens the source on click and Enter; the button must not.
    <span onClick={stop} onKeyDown={stop} className="inline-flex">
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label={label}
        title={control.unavailable ?? label}
        disabled={control.unavailable !== null}
        onClick={() => control.setOpen(true)}
      >
        {include ? (
          <CirclePlusIcon className="size-3.5" />
        ) : (
          <CircleMinusIcon className="size-3.5" />
        )}
      </Button>
      <DecisionDialog source={source} control={control} />
    </span>
  );
}
