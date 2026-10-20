import { plural } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { SectionHeader } from '@/shared/ui/section-header';

/** The trajectory steps that touched this source; each opens in Trajectory. */
export function TrajectoryLinks({
  stepIds,
  onOpenStep,
}: {
  stepIds: readonly number[];
  onOpenStep: (stepId: number) => void;
}) {
  return (
    <section aria-labelledby="source-steps" className="flex flex-col gap-2">
      <SectionHeader
        id="source-steps"
        title="Trajectory"
        meta={stepIds.length > 0 ? plural(stepIds.length, 'step') : null}
      />
      {stepIds.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No trajectory step references this source yet.
        </p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {stepIds.map((id) => (
            <Button
              key={id}
              variant="outline"
              size="xs"
              onClick={() => onOpenStep(id)}
              aria-label={`Open trajectory step ${id}`}
              className="tabular-nums"
            >
              Step {id}
            </Button>
          ))}
        </div>
      )}
    </section>
  );
}
