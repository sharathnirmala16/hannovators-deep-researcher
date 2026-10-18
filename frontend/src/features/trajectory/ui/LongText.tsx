import { useState } from 'react';

import { cn } from '@/shared/lib/cn';

import { FOCUS_RING } from './statusStyles';

const LONG = 900;

/** Prompt or reply text; long text starts clipped with a "Show all" toggle. */
export function LongText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > LONG;
  return (
    <div className="flex flex-col items-start gap-1">
      <pre
        className={cn(
          'w-full rounded-md bg-muted px-3 py-2 font-mono text-xs leading-5 break-words whitespace-pre-wrap',
          long && !expanded && 'max-h-60 overflow-hidden',
        )}
      >
        {text}
      </pre>
      {long ? (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className={cn(
            'rounded-sm text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground',
            FOCUS_RING,
          )}
        >
          {expanded
            ? 'Show less'
            : `Show all ${text.length.toLocaleString()} characters`}
        </button>
      ) : null}
    </div>
  );
}
