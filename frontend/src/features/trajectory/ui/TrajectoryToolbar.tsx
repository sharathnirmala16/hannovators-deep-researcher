import { Search, X } from 'lucide-react';

import type { TrajectoryKind } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';

import {
  NO_FILTERS,
  hasFilters,
  type TrajectoryFilters,
} from '../model/filters';
import type { LiveStatus } from '../model/useTrajectory';
import { formatCount } from '../model/timing';
import {
  ACTORS,
  ACTOR_LABEL,
  OUTCOMES,
  OUTCOME_LABEL,
  STAGES,
  STAGE_LABEL,
  isActor,
  isOutcome,
  isStage,
} from '../model/vocabulary';
import { FilterSelect } from './FilterSelect';
import { KindChips } from './KindChips';
import { LiveToggle } from './LiveToggle';
import { FOCUS_RING } from './statusStyles';

interface TrajectoryToolbarProps {
  filters: TrajectoryFilters;
  onChange: (filters: TrajectoryFilters) => void;
  kindCounts: ReadonlyMap<TrajectoryKind, number>;
  live: boolean;
  liveStatus: LiveStatus;
  onLiveChange: (live: boolean) => void;
  shown: number;
  total: number;
}

export function TrajectoryToolbar({
  filters,
  onChange,
  kindCounts,
  live,
  liveStatus,
  onLiveChange,
  shown,
  total,
}: TrajectoryToolbarProps) {
  const set = (patch: Partial<TrajectoryFilters>) =>
    onChange({ ...filters, ...patch });
  return (
    <div className="flex flex-col gap-2 border-b px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative">
          <span className="sr-only">Filter steps</span>
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={filters.q}
            onChange={(event) => set({ q: event.target.value })}
            placeholder="Filter by name, URL, or model"
            className="h-7 w-64 pl-7 text-xs md:text-xs"
          />
        </label>
        <FilterSelect
          label="Actor"
          value={filters.actor}
          allLabel="All actors"
          options={ACTORS}
          labels={ACTOR_LABEL}
          parse={isActor}
          onChange={(actor) => set({ actor })}
        />
        <FilterSelect
          label="Stage"
          value={filters.stage}
          allLabel="All stages"
          options={STAGES}
          labels={STAGE_LABEL}
          parse={isStage}
          onChange={(stage) => set({ stage })}
        />
        <FilterSelect
          label="Outcome"
          value={filters.outcome}
          allLabel="Any outcome"
          options={OUTCOMES}
          labels={OUTCOME_LABEL}
          parse={isOutcome}
          onChange={(outcome) => set({ outcome })}
        />
        <button
          type="button"
          aria-pressed={filters.errorsOnly}
          onClick={() => set({ errorsOnly: !filters.errorsOnly })}
          className={cn(
            'inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs transition-colors',
            filters.errorsOnly
              ? 'bg-shade-2 font-medium text-tone-negative'
              : 'text-foreground hover:bg-muted',
            FOCUS_RING,
          )}
        >
          <span
            aria-hidden
            className={cn(
              'size-1.5 rounded-full',
              filters.errorsOnly ? 'bg-tone-negative' : 'bg-shade-4',
            )}
          />
          Errors only
        </button>
        {hasFilters(filters) ? (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => onChange(NO_FILTERS)}
            className="text-muted-foreground"
          >
            <X aria-hidden />
            Clear filters
          </Button>
        ) : null}
        <p
          aria-live="polite"
          className="ml-auto text-xs text-muted-foreground tabular-nums"
        >
          {formatCount(shown)} shown of {formatCount(total)}
        </p>
        <LiveToggle live={live} status={liveStatus} onChange={onLiveChange} />
      </div>
      <KindChips
        selected={filters.kinds}
        counts={kindCounts}
        onChange={(kinds) => set({ kinds })}
      />
    </div>
  );
}
