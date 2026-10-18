import type { ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

interface NoticeProps {
  title: string;
  children?: ReactNode;
  tone?: 'neutral' | 'error';
  action?: ReactNode;
  className?: string | undefined;
}

/** Empty, unavailable, and error states: what happened and what to do. */
export function Notice({
  title,
  children,
  tone = 'neutral',
  action,
  className,
}: NoticeProps) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex flex-col items-start gap-2 px-6 py-8 text-sm',
        className,
      )}
    >
      <p
        className={cn('font-medium', tone === 'error' && 'text-tone-negative')}
      >
        {title}
      </p>
      {children ? (
        <div className="max-w-prose text-[13px] text-muted-foreground">
          {children}
        </div>
      ) : null}
      {action}
    </div>
  );
}
