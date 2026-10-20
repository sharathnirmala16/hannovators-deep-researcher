import { Loader2Icon, SendHorizontalIcon } from 'lucide-react';
import { useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react';

import { Button } from '@/shared/ui/button';
import { Textarea } from '@/shared/ui/textarea';

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
  /** True while an answer is generated. */
  sending: boolean;
  disabled: boolean;
}

/** Question box pinned under the messages: Enter sends, Shift+Enter breaks. */
export function Composer({
  value,
  onChange,
  onSubmit,
  sending,
  disabled,
}: ComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const locked = sending || disabled;
  const canSend = !locked && value.trim().length > 0;

  useEffect(() => {
    if (!locked) inputRef.current?.focus({ preventScroll: true });
  }, [locked]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (canSend) onSubmit(value);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return;
    if (event.nativeEvent.isComposing) return;
    event.preventDefault();
    submit();
  };

  return (
    <form
      onSubmit={submit}
      aria-label="Ask a question"
      className="flex items-end gap-2 border-t border-border bg-background px-4 py-3"
    >
      <label htmlFor="research-chat-question" className="sr-only">
        Question
      </label>
      <Textarea
        id="research-chat-question"
        ref={inputRef}
        value={value}
        disabled={locked}
        rows={1}
        placeholder={
          sending
            ? 'Writing the answer...'
            : 'Ask about the evidence. Enter sends, Shift+Enter adds a line.'
        }
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        className="max-h-40 min-h-9 resize-none"
      />
      <Button
        type="submit"
        size="icon"
        disabled={!canSend}
        aria-label={sending ? 'Sending' : 'Send question'}
      >
        {sending ? (
          <Loader2Icon aria-hidden className="motion-safe:animate-spin" />
        ) : (
          <SendHorizontalIcon aria-hidden />
        )}
      </Button>
    </form>
  );
}
