import { XIcon } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@/shared/lib/cn';

interface ScopeChipsProps {
  label: string;
  values: readonly string[];
  editable: boolean;
  onAdd: (value: string) => void;
  onRemove: (index: number) => void;
}

/** One list field as quiet chips; at the checkpoint chips can be removed or added. */
export function ScopeChips({
  label,
  values,
  editable,
  onAdd,
  onRemove,
}: ScopeChipsProps) {
  const [text, setText] = useState('');
  if (!editable && values.length === 0) {
    return <span className="text-xs text-muted-foreground">Not set</span>;
  }
  const commit = () => {
    if (!text.trim()) return;
    onAdd(text);
    setText('');
  };
  return (
    <ul className="flex min-w-0 flex-wrap gap-1">
      {values.map((value, index) => (
        <li
          key={`${value}-${index}`}
          className={cn(
            'reading inline-flex max-w-full min-w-0 items-center gap-0.5 rounded-[3px] px-1.5 py-px text-sm leading-5 text-foreground',
            editable
              ? 'bg-background pr-0.5 ring-1 ring-shade-2 ring-inset'
              : 'bg-desk',
          )}
        >
          <span className="min-w-0 break-words">{value}</span>
          {editable ? (
            <button
              type="button"
              onClick={() => onRemove(index)}
              aria-label={`Remove ${value} from ${label}`}
              title="Remove"
              className="inline-flex size-5 shrink-0 items-center justify-center rounded-[3px] text-muted-foreground transition-colors hover:bg-tone-negative-tint hover:text-tone-negative"
            >
              <XIcon className="size-3.5" />
            </button>
          ) : null}
        </li>
      ))}
      {editable ? (
        <li className="max-w-full min-w-0">
          <input
            value={text}
            aria-label={`Add to ${label}`}
            placeholder="Add"
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || !text.trim()) return;
              event.preventDefault();
              commit();
            }}
            onBlur={commit}
            className="h-6 w-20 max-w-full min-w-0 rounded-[3px] bg-transparent px-1.5 text-xs text-foreground ring-1 ring-shade-3 transition-colors ring-inset placeholder:text-muted-foreground hover:bg-background focus:w-40 focus:bg-background focus-visible:ring-ring"
          />
        </li>
      ) : null}
    </ul>
  );
}
