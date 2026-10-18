import { useEvidenceSelection } from '@/domains/evidence';
import {
  EVIDENCE_LEVEL,
  STANCE,
  studyLabel,
  useWorkspace,
  type SourceView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Tag } from '@/shared/ui/tag';

/** Study name (opens the source), then its evidence level and stance. */
export function StudyCell({
  source,
  detail,
}: {
  source: SourceView;
  /** Extra line under the name, for example the venue. */
  detail?: string | null;
}) {
  const { selection, selectSource } = useEvidenceSelection();
  const { recordAction } = useWorkspace();
  const active = selection.kind !== 'none' && selection.sourceId === source.id;
  const open = () => {
    selectSource(source.id);
    recordAction({
      name: 'user.source.open',
      summary: `Opened ${studyLabel(source)}`,
      target: source.url,
      source_ids: [source.id],
    });
  };
  return (
    <div className="flex min-w-0 flex-col items-start gap-1">
      <button
        type="button"
        onClick={open}
        title={source.title}
        className={cn(
          'max-w-full truncate rounded-sm text-left font-medium hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
          active &&
            'underline decoration-marker-ink decoration-2 underline-offset-4',
        )}
      >
        {studyLabel(source)}
      </button>
      {detail ? (
        <span className="max-w-full truncate text-xs text-muted-foreground">
          {detail}
        </span>
      ) : null}
      <span className="flex flex-wrap gap-1">
        {source.evidence_level ? (
          <Tag>{EVIDENCE_LEVEL[source.evidence_level]}</Tag>
        ) : null}
        {source.stance ? (
          <Tag tone={STANCE[source.stance].tone}>
            {STANCE[source.stance].label}
          </Tag>
        ) : null}
      </span>
    </div>
  );
}
