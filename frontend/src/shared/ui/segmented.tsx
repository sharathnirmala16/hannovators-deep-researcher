import { useRef, type KeyboardEvent, type ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  /** Optional count shown after the label. */
  count?: number | undefined;
  disabled?: boolean;
}

interface SegmentedProps<T extends string> {
  value: T;
  options: readonly SegmentOption<T>[];
  onChange: (value: T) => void;
  /** Accessible name of the group. */
  label: string;
  size?: 'sm' | 'md';
  className?: string;
}

const STEP: Record<string, number> = {
  ArrowRight: 1,
  ArrowDown: 1,
  ArrowLeft: -1,
  ArrowUp: -1,
};

/** A radio group drawn as one segmented control. Arrow keys move the choice. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  size = 'sm',
  className,
}: SegmentedProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const enabled = options.filter((option) => !option.disabled);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = STEP[event.key];
    if (step === undefined || enabled.length === 0) return;
    event.preventDefault();
    const at = enabled.findIndex((option) => option.value === value);
    const next = enabled[(at + step + enabled.length) % enabled.length];
    if (!next) return;
    onChange(next.value);
    refs.current[options.indexOf(next)]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn(
        'inline-flex shrink-0 items-center gap-0.5 rounded-md bg-shade-1 p-0.5 ring-1 ring-shade-2 ring-inset',
        className,
      )}
    >
      {options.map((option, index) => {
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            disabled={option.disabled}
            tabIndex={checked ? 0 : -1}
            onClick={() => onChange(option.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-[4px] px-2.5 font-medium whitespace-nowrap text-muted-foreground transition-colors',
              'hover:text-foreground disabled:opacity-40',
              size === 'sm' ? 'h-6 text-xs' : 'h-7 text-sm',
              checked &&
                'bg-background font-semibold text-foreground shadow-[0_1px_2px_rgba(24,34,58,0.14),0_0_0_1px_rgba(24,34,58,0.06)]',
            )}
          >
            {option.label}
            {option.count !== undefined ? (
              <span className="font-normal text-muted-foreground tabular-nums">
                {option.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
