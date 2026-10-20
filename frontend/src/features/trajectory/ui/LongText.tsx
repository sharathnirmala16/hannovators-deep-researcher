import { useState } from 'react';

import { cn } from '@/shared/lib/cn';

const LONG = 900;

interface LongTextProps {
  /** Short sentence-case label above the block, for example "System prompt". */
  label: string;
  text: string;
}

/**
 * A labeled prompt or reply block in a readable measure. Long text starts
 * clipped with a "Show all" toggle.
 */
export function LongText({ label, text }: LongTextProps) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > LONG;
  return (
    <div className="flex max-w-prose flex-col items-start gap-1.5">
      <h4 className="text-xs font-semibold text-muted-foreground">{label}</h4>
      <p
        className={cn(
          'w-full rounded-md bg-shade-0 px-3 py-2 text-sm leading-6 break-words whitespace-pre-wrap text-foreground',
          long && !expanded && 'max-h-60 overflow-hidden',
        )}
      >
        {text}
      </p>
      {long ? (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="rounded-sm text-xs text-link underline-offset-2 hover:underline"
        >
          {expanded
            ? 'Show less'
            : `Show all ${text.length.toLocaleString()} characters`}
        </button>
      ) : null}
    </div>
  );
}
