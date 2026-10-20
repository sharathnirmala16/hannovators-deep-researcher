import { useId } from 'react';

import type { RequestedDomainMode } from '@/domains/workspace';
import { Segmented, type SegmentOption } from '@/shared/ui/segmented';
import { Switch } from '@/shared/ui/switch';

const MODES: readonly SegmentOption<RequestedDomainMode>[] = [
  { value: 'AUTO', label: 'Auto' },
  { value: 'MEDICAL', label: 'Medical' },
  { value: 'GENERAL', label: 'General' },
];

const MODE_HINT: Record<RequestedDomainMode, string> = {
  AUTO: 'Picks medical or general from the question.',
  MEDICAL: 'PICOTS scope, RoB 2 appraisal, and a GRADE evidence profile.',
  GENERAL: 'Entities and claims, credibility checks, and a claim matrix.',
};

interface RunOptionsProps {
  mode: RequestedDomainMode;
  onModeChange: (mode: RequestedDomainMode) => void;
  autoContinue: boolean;
  onAutoContinueChange: (value: boolean) => void;
  disabled: boolean;
}

/** Research mode and auto-continue, as a label and value list. */
export function RunOptions({
  mode,
  onModeChange,
  autoContinue,
  onAutoContinueChange,
  disabled,
}: RunOptionsProps) {
  const switchId = useId();
  return (
    <dl className="grid grid-cols-[8rem_minmax(0,1fr)] items-center gap-x-6 gap-y-5">
      <dt className="text-sm font-semibold">Mode</dt>
      <dd className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmented
          label="Research mode"
          size="md"
          value={mode}
          options={MODES}
          onChange={onModeChange}
        />
        <span className="text-xs text-muted-foreground">{MODE_HINT[mode]}</span>
      </dd>
      <dt>
        <label htmlFor={switchId} className="text-sm font-semibold">
          Auto-continue
        </label>
      </dt>
      <dd className="flex items-center gap-4">
        <Switch
          id={switchId}
          checked={autoContinue}
          onCheckedChange={onAutoContinueChange}
          disabled={disabled}
        />
        <span className="text-xs text-muted-foreground">
          {autoContinue
            ? 'Runs straight through to the synthesis.'
            : 'Pauses after the scope so you can edit it.'}
        </span>
      </dd>
    </dl>
  );
}
