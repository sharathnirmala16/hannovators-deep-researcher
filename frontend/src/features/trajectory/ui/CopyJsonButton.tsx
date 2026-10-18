import { Check, Copy } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/shared/ui/button';

/** Copies the body as formatted JSON, for reproducing a call elsewhere. */
export function CopyJsonButton({ value }: { value: unknown }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);
  const copy = () => {
    void navigator.clipboard.writeText(JSON.stringify(value, null, 2)).then(
      () => setCopied(true),
      () => undefined,
    );
  };
  return (
    <Button variant="ghost" size="xs" onClick={copy}>
      {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
      {copied ? 'Copied' : 'Copy JSON'}
    </Button>
  );
}
