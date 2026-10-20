import { cn } from '@/shared/lib/cn';

interface FilterSelectProps<T extends string> {
  label: string;
  value: T | null;
  allLabel: string;
  options: readonly T[];
  labels: Record<T, string>;
  /** Narrows the raw `<select>` value to `T`. */
  parse: (raw: string) => raw is T;
  onChange: (value: T | null) => void;
}

/** A compact native select with an "all" option that clears the filter. */
export function FilterSelect<T extends string>({
  label,
  value,
  allLabel,
  options,
  labels,
  parse,
  onChange,
}: FilterSelectProps<T>) {
  return (
    <select
      aria-label={label}
      value={value ?? ''}
      onChange={(event) => {
        const raw = event.target.value;
        onChange(parse(raw) ? raw : null);
      }}
      className={cn(
        'h-7 rounded-md border border-input bg-background px-1.5 text-xs transition-colors hover:bg-shade-0',
        value === null
          ? 'text-muted-foreground'
          : 'border-shade-5 font-medium text-foreground',
      )}
    >
      <option value="">{allLabel}</option>
      {options.map((option) => (
        <option key={option} value={option}>
          {labels[option]}
        </option>
      ))}
    </select>
  );
}
