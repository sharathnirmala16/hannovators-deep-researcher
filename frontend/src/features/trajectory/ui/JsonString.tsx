import { useState } from 'react';

/** Strings longer than this collapse behind "Show all". */
const LONG_STRING = 280;

/** A JSON string value in the positive tone; long ones start clipped. */
export function JsonString({ value }: { value: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = value.length > LONG_STRING;
  const shown = long && !expanded ? `${value.slice(0, LONG_STRING)}…` : value;
  return (
    <span className="min-w-0 whitespace-pre-wrap text-tone-positive">
      &quot;{shown}&quot;
      {long ? (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="ml-2 rounded-sm font-sans text-xs text-link underline-offset-2 hover:underline"
        >
          {expanded
            ? 'Show less'
            : `Show all ${value.length.toLocaleString()} characters`}
        </button>
      ) : null}
    </span>
  );
}
