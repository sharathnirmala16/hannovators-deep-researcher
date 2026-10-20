import { Search, X } from 'lucide-react';

import type { TrajectoryKind } from '@/domains/workspace';
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
import { ErrorsToggle } from './ErrorsToggle';
import { FilterSelect } from './FilterSelect';
import { KindChips } from './KindChips';
import { LiveToggle } from './LiveToggle';

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

/** Filters, the live toggle, and the row count; wraps on narrow widths. */
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
    <div className="flex flex-col gap-2">
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
        <ErrorsToggle
          pressed={filters.errorsOnly}
          onChange={(errorsOnly) => set({ errorsOnly })}
        />
        {hasFilters(filters) ? (
          <Button
            variant="ghost"
            size="xs"
            className="h-7"
            onClick={() => onChange(NO_FILTERS)}
          >
            <X aria-hidden />
            Clear filters
          </Button>
        ) : null}
        <div className="ml-auto flex items-center gap-3">
          <p
            aria-live="polite"
            className="text-xs whitespace-nowrap text-muted-foreground tabular-nums"
          >
            {formatCount(shown)} shown of {formatCount(total)}
          </p>
          <LiveToggle live={live} status={liveStatus} onChange={onLiveChange} />
        </div>
      </div>
      <KindChips
        selected={filters.kinds}
        counts={kindCounts}
        onChange={(kinds) => set({ kinds })}
      />
    </div>
  );
}
