import { Loader2Icon } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/shared/ui/button';
import { ErrorState } from '@/shared/ui/states';

import type { PendingTurn } from '../model/useChat';
import { UserTurn } from './ChatMessage';

function useElapsedSeconds(): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return seconds;
}

function WorkingRow() {
  const seconds = useElapsedSeconds();
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-md bg-muted px-3 py-2 text-sm"
    >
      <Loader2Icon
        aria-hidden
        className="mt-0.5 size-4 shrink-0 text-muted-foreground motion-safe:animate-spin"
      />
      <div className="flex flex-col gap-0.5">
        <p className="font-medium text-foreground">
          Reading the sources and writing a cited answer
        </p>
        <p className="text-xs text-muted-foreground tabular-nums">
          {seconds} s elapsed. This usually takes 10 to 60 seconds.
        </p>
      </div>
    </div>
  );
}

interface TurnStatusProps {
  pending: PendingTurn;
  onRetry: () => void;
  /** Drop the failed turn and put the question back in the composer. */
  onEdit: (question: string) => void;
}

/** The question in flight with a working row, or its failed answer. */
export function TurnStatus({ pending, onRetry, onEdit }: TurnStatusProps) {
  return (
    <>
      <UserTurn content={pending.question} />
      {pending.status === 'sending' ? (
        <WorkingRow />
      ) : (
        <ErrorState
          title="The answer failed"
          message={pending.message}
          onRetry={onRetry}
        >
          <Button
            size="xs"
            variant="ghost"
            className="mt-1 px-0 underline underline-offset-4"
            onClick={() => onEdit(pending.question)}
          >
            Edit the question
          </Button>
        </ErrorState>
      )}
    </>
  );
}
