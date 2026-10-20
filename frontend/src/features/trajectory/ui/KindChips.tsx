import type { TrajectoryKind } from '@/domains/workspace';

import { toggleKind } from '../model/filters';
import { formatCount } from '../model/timing';
import { KINDS, KIND_LABEL } from '../model/vocabulary';
import { FilterChip } from './FilterChip';
import { KIND_ICON } from './kindIcons';

interface KindChipsProps {
  selected: readonly TrajectoryKind[];
  counts: ReadonlyMap<TrajectoryKind, number>;
  onChange: (kinds: TrajectoryKind[]) => void;
}

/** Multi-select kind filter. No chip pressed means every kind. */
export function KindChips({ selected, counts, onChange }: KindChipsProps) {
  return (
    <div role="group" aria-label="Kinds" className="flex flex-wrap gap-1">
      <FilterChip pressed={selected.length === 0} onToggle={() => onChange([])}>
        All kinds
      </FilterChip>
      {KINDS.map((kind) => {
        const Icon = KIND_ICON[kind];
        const count = counts.get(kind) ?? 0;
        return (
          <FilterChip
            key={kind}
            pressed={selected.includes(kind)}
            onToggle={() => onChange(toggleKind(selected, kind))}
            count={count > 0 ? formatCount(count) : null}
          >
            <Icon aria-hidden className="size-3.5" />
            {KIND_LABEL[kind]}
          </FilterChip>
        );
      })}
    </div>
  );
}
