import { useEvidenceSelection } from '@/domains/evidence';
import { studyLabel, useWorkspace, type SourceView } from '@/domains/workspace';

import { MARK_BUTTON, markClasses } from './marker';

/** A citation in prose: the study name, marked, opens the source. */
export function SourceCitation({ source }: { source: SourceView }) {
  const { selection, selectSource } = useEvidenceSelection();
  const { recordAction } = useWorkspace();
  const active =
    selection.kind === 'source' && selection.sourceId === source.id;
  const label = studyLabel(source);
  const open = () => {
    selectSource(source.id);
    recordAction({
      name: 'user.source.open',
      summary: `Opened ${label} from the synthesis`,
      target: source.url,
      source_ids: [source.id],
    });
  };
  return (
    <button
      type="button"
      onClick={open}
      aria-pressed={active}
      title={source.title}
      className={MARK_BUTTON}
    >
      <span className={markClasses(active, true)}>{label}</span>
    </button>
  );
}
