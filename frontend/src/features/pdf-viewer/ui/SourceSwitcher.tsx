import type { WorkspaceState } from '@/domains/workspace';

import { promotedSources } from '../model/resolveSource';

interface SourceSwitcherProps {
  state: WorkspaceState;
  value: string;
  onChange: (sourceId: string) => void;
}

/** Picks one of the seeds or promoted sources to read. */
export function SourceSwitcher({
  state,
  value,
  onChange,
}: SourceSwitcherProps) {
  const options = promotedSources(state);
  const known = options.some((source) => source.id === value);
  return (
    <label className="flex flex-col gap-1 text-xs text-muted-foreground">
      Source
      <select
        value={known ? value : ''}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 w-full min-w-0 truncate rounded-md border border-input bg-background px-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <option value="" disabled>
          {options.length > 0
            ? 'Choose a seed or promoted source'
            : 'No promoted sources yet'}
        </option>
        {options.map((source) => (
          <option key={source.id} value={source.id}>
            {source.title}
          </option>
        ))}
      </select>
    </label>
  );
}
