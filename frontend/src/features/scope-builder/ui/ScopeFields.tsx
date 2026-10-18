import { withEntry, withoutEntry, type ScopeField } from '../model/scopeFields';
import { ScopeChips } from './ScopeChips';

interface ScopeFieldsProps<D> {
  fields: readonly ScopeField<D>[];
  value: D;
  editable: boolean;
  onChange: (next: D) => void;
}

function TextValue<D>({
  field,
  value,
  editable,
  onChange,
}: {
  field: Extract<ScopeField<D>, { kind: 'text' }>;
  value: D;
  editable: boolean;
  onChange: (next: D) => void;
}) {
  const text = field.get(value);
  if (!editable) {
    return text ? (
      <span className="text-sm leading-5">{text}</span>
    ) : (
      <span className="text-xs text-muted-foreground">Not set</span>
    );
  }
  return (
    <input
      value={text}
      aria-label={field.label}
      onChange={(event) => onChange(field.set(value, event.target.value))}
      className="h-7 w-full rounded-sm bg-background px-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    />
  );
}

/** Label and value rows for PICOTS or the research scope. */
export function ScopeFields<D>({
  fields,
  value,
  editable,
  onChange,
}: ScopeFieldsProps<D>) {
  return (
    <dl className="grid grid-cols-[minmax(0,6.5rem)_minmax(0,1fr)] gap-x-4 gap-y-2">
      {fields.map((field) => (
        <div key={field.id} className="contents">
          <dt className="pt-0.5 text-xs text-muted-foreground">
            {field.label}
          </dt>
          <dd className="min-w-0">
            {field.kind === 'text' ? (
              <TextValue
                field={field}
                value={value}
                editable={editable}
                onChange={onChange}
              />
            ) : (
              <ScopeChips
                label={field.label}
                values={field.get(value)}
                editable={editable}
                onAdd={(entry) =>
                  onChange(field.set(value, withEntry(field.get(value), entry)))
                }
                onRemove={(index) =>
                  onChange(
                    field.set(value, withoutEntry(field.get(value), index)),
                  )
                }
              />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
