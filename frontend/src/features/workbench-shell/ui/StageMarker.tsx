import { CheckIcon, XIcon } from 'lucide-react';

import type { StageState } from '@/domains/workspace';
import { ToneDot } from '@/shared/ui/tag';

/** The node of one stage on the timeline line. */
export function StageMarker({ state }: { state: StageState }) {
  return (
    <span
      aria-hidden
      className="relative z-10 mt-0.5 flex size-4 items-center justify-center rounded-full bg-background"
    >
      {state === 'done' ? (
        <CheckIcon className="size-3.5 text-tone-positive" strokeWidth={2.5} />
      ) : null}
      {state === 'failed' ? (
        <XIcon className="size-3.5 text-tone-negative" strokeWidth={2.5} />
      ) : null}
      {state === 'active' ? (
        <ToneDot
          tone="info"
          live
          className="size-2 ring-[3px] ring-tone-info-tint"
        />
      ) : null}
      {state === 'review' ? (
        <ToneDot
          tone="caution"
          className="size-2 ring-[3px] ring-tone-caution-tint"
        />
      ) : null}
      {state === 'pending' ? (
        <span className="size-2 rounded-full bg-background ring-[1.5px] ring-shade-3 ring-inset" />
      ) : null}
    </span>
  );
}
