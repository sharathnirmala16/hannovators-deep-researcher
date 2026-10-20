import { ExternalLink } from 'lucide-react';

const isWebUrl = (value: string) => /^https?:\/\//i.test(value);

/** A URL, model ID, or endpoint in monospace; web URLs open in a new tab. */
export function TargetValue({ target }: { target: string | null }) {
  if (!target) return null;
  if (!isWebUrl(target)) {
    return <span className="font-mono text-xs break-all">{target}</span>;
  }
  return (
    <a
      href={target}
      target="_blank"
      rel="noopener noreferrer"
      className="inline rounded-sm font-mono text-xs break-all text-link underline-offset-2 hover:underline"
    >
      {target}
      <ExternalLink aria-hidden className="ml-1 inline size-3 align-[-1px]" />
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
