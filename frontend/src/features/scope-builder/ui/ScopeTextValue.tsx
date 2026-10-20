import type { ScopeField } from '../model/scopeFields';

interface ScopeTextValueProps<D> {
  field: Extract<ScopeField<D>, { kind: 'text' }>;
  value: D;
  editable: boolean;
  onChange: (next: D) => void;
}

/** One free-text field: reading text, or an input at the checkpoint. */
export function ScopeTextValue<D>({
  field,
  value,
  editable,
  onChange,
}: ScopeTextValueProps<D>) {
  const text = field.get(value);
  if (!editable) {
    return text ? (
      <p className="reading text-sm leading-5 break-words text-foreground">
        {text}
      </p>
    ) : (
      <span className="text-xs text-muted-foreground">Not set</span>
    );
  }
  return (
    <input
      value={text}
      aria-label={field.label}
      placeholder="Not set"
      onChange={(event) => onChange(field.set(value, event.target.value))}
      className="reading h-7 w-full min-w-0 rounded-md bg-background px-2 text-sm text-foreground ring-1 ring-input transition-colors ring-inset placeholder:text-muted-foreground hover:ring-shade-4 focus-visible:ring-ring"
    />
  );
}
