import { Button } from '@/shared/ui/button';
import { ToneDot, type Tone } from '@/shared/ui/tag';

import type { LiveStatus } from '../model/useTrajectory';

const LABEL: Record<LiveStatus, string> = {
  off: 'Paused',
  connecting: 'Connecting',
  live: 'Live',
  interrupted: 'Stream interrupted',
};

const TONE: Record<LiveStatus, Tone> = {
  off: 'neutral',
  connecting: 'neutral',
  live: 'info',
  interrupted: 'caution',
};

interface LiveToggleProps {
  live: boolean;
  status: LiveStatus;
  onChange: (live: boolean) => void;
}

/** Pauses or resumes the live step stream; the dot pulses while connected. */
export function LiveToggle({ live, status, onChange }: LiveToggleProps) {
  return (
    <Button
      variant="outline"
      size="xs"
      aria-pressed={live}
      title={live ? 'Pause live updates' : 'Resume live updates'}
      onClick={() => onChange(!live)}
      className="h-7 px-2"
    >
      <ToneDot
        tone={TONE[status]}
        live={status === 'live' || status === 'connecting'}
      />
      {LABEL[status]}
    </Button>
  );
}
