import { useEvidenceSelection } from '@/domains/evidence';
import {
  STANCE,
  studyLabel,
  useWorkspace,
  type SourceView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Tag } from '@/shared/ui/tag';

import { StudyTags } from './StudyTags';

/**
 * First author and year (opens the source), the venue, then the evidence
 * level and stance. Opposing and null stances keep their tone.
 */
export function StudyCell({
  source,
  compact = false,
}: {
  source: SourceView;
  /** One line: name and stance only (claim matrix rows). */
  compact?: boolean;
}) {
  const { selection, selectSource } = useEvidenceSelection();
  const { recordAction } = useWorkspace();
  const active =
    selection.kind === 'source' && selection.sourceId === source.id;
  const open = () => {
    selectSource(source.id);
    recordAction({
      name: 'user.source.open',
      summary: `Opened ${studyLabel(source)}`,
      target: source.url,
      source_ids: [source.id],
    });
  };
  const stance = compact && source.stance ? STANCE[source.stance] : null;
  const venue = compact ? null : source.venue;
  return (
    <div className="flex min-w-0 flex-col items-start gap-1">
      <div className="flex max-w-full min-w-0 items-baseline gap-2">
        <button
          type="button"
          onClick={open}
          aria-pressed={active}
          title={source.title}
          className={cn(
            'max-w-full shrink-0 truncate rounded-sm text-left text-sm font-semibold text-foreground underline-offset-[3px] transition-colors hover:underline',
            active && 'underline decoration-foreground decoration-2',
          )}
        >
          {studyLabel(source)}
        </button>
        {venue ? (
          <span
            className="min-w-0 truncate text-xs text-muted-foreground"
            title={venue}
          >
            {venue}
          </span>
        ) : null}
        {stance ? <Tag tone={stance.tone}>{stance.label}</Tag> : null}
      </div>
      {compact ? null : <StudyTags source={source} />}
    </div>
  );
}
