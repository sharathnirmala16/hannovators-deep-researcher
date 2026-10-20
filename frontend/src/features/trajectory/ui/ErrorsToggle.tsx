import { cn } from '@/shared/lib/cn';
import { ToneDot } from '@/shared/ui/tag';

interface ErrorsToggleProps {
  pressed: boolean;
  onChange: (pressed: boolean) => void;
}

/** "Errors only": quiet until pressed, then in the negative tone. */
export function ErrorsToggle({ pressed, onChange }: ErrorsToggleProps) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onChange(!pressed)}
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium whitespace-nowrap transition-colors',
        pressed
          ? 'bg-tone-negative-tint text-tone-negative'
          : 'bg-desk text-foreground hover:bg-shade-2',
      )}
    >
      <ToneDot tone={pressed ? 'negative' : 'neutral'} />
      Errors only
    </button>
  );
}
