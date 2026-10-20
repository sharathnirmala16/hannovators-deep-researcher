import { useId } from 'react';

import type { RequestedDomainMode } from '@/domains/workspace';
import { Segmented, type SegmentOption } from '@/shared/ui/segmented';
import { Switch } from '@/shared/ui/switch';

const MODES: readonly SegmentOption<RequestedDomainMode>[] = [
  { value: 'AUTO', label: 'Auto' },
  { value: 'MEDICAL', label: 'Medical' },
  { value: 'GENERAL', label: 'General' },
];

interface RunOptionsProps {
  mode: RequestedDomainMode;
  onModeChange: (mode: RequestedDomainMode) => void;
  autoContinue: boolean;
  onAutoContinueChange: (value: boolean) => void;
  disabled: boolean;
}

/** The composer's controls: research mode and whether to pause on the scope. */
export function RunOptions({
  mode,
  onModeChange,
  autoContinue,
  onAutoContinueChange,
  disabled,
}: RunOptionsProps) {
  const switchId = useId();
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <Segmented
        label="Research mode"
        value={mode}
        options={MODES}
        onChange={onModeChange}
      />
      <span className="inline-flex items-center gap-2">
        <Switch
          id={switchId}
          checked={!autoContinue}
          onCheckedChange={(review) => onAutoContinueChange(!review)}
          disabled={disabled}
        />
        <label htmlFor={switchId} className="text-xs text-muted-foreground">
          Review the scope first
        </label>
      </span>
    </div>
  );
}
