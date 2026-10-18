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

/** One list field as chips; at the checkpoint chips can be removed or added. */
export function ScopeChips({
  label,
  values,
  editable,
  onAdd,
  onRemove,
}: ScopeChipsProps) {
  const [text, setText] = useState('');
  if (!editable && values.length === 0) {
    return <span className="text-xs text-muted-foreground">None</span>;
  }
  return (
    <ul className="flex flex-wrap gap-1">
      {values.map((value, index) => (
        <li
          key={`${value}-${index}`}
          className={cn(
            'inline-flex min-h-6 max-w-full items-center gap-1 rounded-sm bg-background px-2 py-0.5 text-xs leading-4 text-foreground',
            editable && 'pr-0.5',
          )}
        >
          <span className="break-words">{value}</span>
          {editable ? (
            <button
              type="button"
              onClick={() => onRemove(index)}
              aria-label={`Remove ${value} from ${label}`}
              className="inline-flex size-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <XIcon className="size-3" />
            </button>
          ) : null}
        </li>
      ))}
      {editable ? (
        <li>
          <input
            value={text}
            aria-label={`Add to ${label}`}
            placeholder="Add"
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || !text.trim()) return;
              event.preventDefault();
              onAdd(text);
              setText('');
            }}
            onBlur={() => {
              if (!text.trim()) return;
              onAdd(text);
              setText('');
            }}
            className="h-6 w-24 rounded-sm bg-transparent px-2 text-xs placeholder:text-muted-foreground focus:w-40 focus:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          />
        </li>
      ) : null}
    </ul>
  );
}
