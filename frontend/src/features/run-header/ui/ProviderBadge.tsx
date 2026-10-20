import { useEffect, useState } from 'react';

import { useWorkspace } from '@/domains/workspace';
import { Tag, ToneDot, type Tone } from '@/shared/ui/tag';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

import { fetchProviders, type ProviderHealth } from '../api/fetchProviders';

function summary(health: ProviderHealth): { label: string; tone: Tone } {
  const ports = Object.values(health.ports);
  const real = ports.filter((port) => port.implementation === 'real').length;
  if (ports.length > 0 && real === ports.length) {
    return { label: 'Live providers', tone: 'positive' };
  }
  if (real === 0) return { label: 'Fake providers', tone: 'caution' };
  return { label: `${real} of ${ports.length} live`, tone: 'caution' };
}

/** Real or fake model, search, and literature ports, from the API health. */
export function ProviderBadge() {
  const { client } = useWorkspace();
  const [health, setHealth] = useState<ProviderHealth | null>(null);
  const live = client.source === 'http';

  useEffect(() => {
    if (!live) return undefined;
    const controller = new AbortController();
    void fetchProviders(controller.signal).then((result) => {
      if (!controller.signal.aborted) setHealth(result);
    });
    return () => controller.abort();
  }, [live]);

  if (!live) return <Tag tone="caution">Recorded fixtures</Tag>;
  if (!health) return null;
  const { label, tone } = summary(health);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="rounded-sm">
          <Tag tone={tone}>{label}</Tag>
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" align="end">
        <ul className="flex flex-col gap-1 py-1">
          {Object.entries(health.ports).map(([port, status]) => (
            <li key={port} className="flex items-center gap-2">
              <ToneDot
                tone={status.implementation === 'real' ? 'positive' : 'caution'}
              />
              <span className="w-20">{port}</span>
              <span className="text-shade-3">
                {status.implementation}, {status.provider}
              </span>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
