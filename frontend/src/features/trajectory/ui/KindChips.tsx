import type { TrajectoryKind } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { toggleKind } from '../model/filters';
import { formatCount } from '../model/timing';
import { KINDS, KIND_LABEL } from '../model/vocabulary';
import { KIND_ICON } from './kindIcons';
import { FOCUS_RING } from './statusStyles';

interface KindChipsProps {
  selected: readonly TrajectoryKind[];
  counts: ReadonlyMap<TrajectoryKind, number>;
  onChange: (kinds: TrajectoryKind[]) => void;
}

/** Multi-select kind filter. No chip pressed means every kind. */
export function KindChips({ selected, counts, onChange }: KindChipsProps) {
  return (
    <div role="group" aria-label="Kinds" className="flex flex-wrap gap-1">
      <button
        type="button"
        aria-pressed={selected.length === 0}
        onClick={() => onChange([])}
        className={cn(chipClass(selected.length === 0), FOCUS_RING)}
      >
        All kinds
      </button>
      {KINDS.map((kind) => {
        const Icon = KIND_ICON[kind];
        const pressed = selected.includes(kind);
        const count = counts.get(kind) ?? 0;
        return (
          <button
            key={kind}
            type="button"
            aria-pressed={pressed}
            onClick={() => onChange(toggleKind(selected, kind))}
            className={cn(chipClass(pressed), FOCUS_RING)}
          >
            <Icon aria-hidden className="size-3.5" />
            {KIND_LABEL[kind]}
            {count > 0 ? (
              <span
                className={cn(
                  'tabular-nums',
                  pressed ? 'opacity-70' : 'text-muted-foreground',
                )}
              >
                {formatCount(count)}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function chipClass(pressed: boolean): string {
  return cn(
    'inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-xs transition-colors',
    pressed
      ? 'bg-foreground text-background'
      : 'bg-muted/60 text-foreground/80 hover:bg-muted',
  );
}
