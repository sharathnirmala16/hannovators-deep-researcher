import { ChevronDown, ChevronUp } from 'lucide-react';

import { cn } from '@/shared/lib/cn';

import type { Sort, SortKey } from '../model/sources';

interface SortButtonProps {
  label: string;
  sortKey: SortKey;
  sort: Sort;
  onSort: (key: SortKey) => void;
}

/** A column sort control: click to sort, click again to reverse. */
export function SortButton({ label, sortKey, sort, onSort }: SortButtonProps) {
  const active = sort.key === sortKey;
  const Icon = sort.direction === 'asc' ? ChevronUp : ChevronDown;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      aria-label={
        active
          ? `${label}, sorted ${sort.direction === 'asc' ? 'ascending' : 'descending'}. Reverse the order`
          : `Sort by ${label.toLowerCase()}`
      }
      className={cn(
        'inline-flex h-6 items-center gap-0.5 rounded-sm text-xs font-medium transition-colors hover:text-foreground',
        active ? 'text-foreground' : 'text-muted-foreground',
      )}
    >
      {label}
      {active ? (
        <Icon aria-hidden className="size-3.5" />
      ) : (
        <span aria-hidden className="size-3.5" />
      )}
    </button>
  );
}
