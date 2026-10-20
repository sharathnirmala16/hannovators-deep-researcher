import type { StepContext } from '../model/stepContext';
import { StepLink } from './StepLink';

interface ChainEntryProps {
  id: number;
  context: StepContext;
}

/** An ancestor; it may sit on a page that is not loaded yet. */
export function ChainEntry({ id, context }: ChainEntryProps) {
  const loaded = context.byId.get(id);
  if (loaded) return <StepLink step={loaded} onOpen={context.onOpenStep} />;
  return (
    <button
      type="button"
      onClick={() => context.onOpenStep(id)}
      className="flex h-8 items-center gap-2 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:bg-desk"
    >
      Step {id} (not loaded yet)
    </button>
  );
}
