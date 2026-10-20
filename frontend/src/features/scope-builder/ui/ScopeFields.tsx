import type { ReactNode } from 'react';

import { withEntry, withoutEntry, type ScopeField } from '../model/scopeFields';
import { ScopeChips } from './ScopeChips';
import { ScopeTextValue } from './ScopeTextValue';

interface ScopeFieldsProps<D> {
  fields: readonly ScopeField<D>[];
  value: D;
  /** The research question, shown read-only as the first row. */
  question: string | null;
  editable: boolean;
  onChange: (next: D) => void;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="col-span-2 grid grid-cols-subgrid items-baseline border-b py-2 first:pt-0 last:border-0 last:pb-0">
      <dt className="text-xs break-words text-muted-foreground">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

/** The protocol box: a label column and the values in the reading face. */
export function ScopeFields<D>({
  fields,
  value,
  question,
  editable,
  onChange,
}: ScopeFieldsProps<D>) {
  return (
    <dl className="grid min-w-0 grid-cols-[minmax(0,6rem)_minmax(0,1fr)] gap-x-3">
      {question ? (
        <Row label="Question">
          <p
            className="reading line-clamp-4 text-sm leading-5 break-words text-foreground"
            title={question}
          >
            {question}
          </p>
        </Row>
      ) : null}
      {fields.map((field) => (
        <Row key={field.id} label={field.label}>
          {field.kind === 'text' ? (
            <ScopeTextValue
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
        </Row>
      ))}
    </dl>
  );
}
