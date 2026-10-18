import type { ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

import { Button } from './button';

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn('animate-pulse rounded-sm bg-muted', className)}
    />
  );
}

/** Loading placeholder: a few text-height bars of varying width. */
function SkeletonBlock({
  lines = 3,
  label = 'Loading',
  className,
}: {
  lines?: number;
  label?: string;
  className?: string;
}) {
  const widths = ['w-11/12', 'w-8/12', 'w-10/12', 'w-6/12', 'w-9/12'];
  return (
    <div role="status" className={cn('flex flex-col gap-2', className)}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          className={cn('h-3', widths[index % widths.length])}
        />
      ))}
    </div>
  );
}

interface StateProps {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Nothing to show yet: says why and what to do next. */
function EmptyState({ title, children, action, className }: StateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-start gap-1 rounded-md bg-muted px-4 py-4',
        className,
      )}
    >
      <p className="text-sm font-medium text-foreground">{title}</p>
      {children ? (
        <div className="text-xs text-muted-foreground">{children}</div>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

interface ErrorStateProps extends Omit<StateProps, 'action'> {
  message?: string;
  onRetry?: () => void;
}

/** A failed load: what failed, the server message, and a retry. */
function ErrorState({
  title,
  message,
  children,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-start gap-1 rounded-md bg-shade-2 px-4 py-4',
        className,
      )}
    >
      <p className="text-sm font-medium text-tone-negative">{title}</p>
      {message ? (
        <p className="text-xs break-words text-foreground">{message}</p>
      ) : null}
      {children ? (
        <div className="text-xs text-muted-foreground">{children}</div>
      ) : null}
      {onRetry ? (
        <Button size="xs" variant="outline" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export { EmptyState, ErrorState, Skeleton, SkeletonBlock };
