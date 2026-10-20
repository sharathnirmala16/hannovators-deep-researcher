import { EVIDENCE_LEVEL, STANCE, type SourceView } from '@/domains/workspace';
import { Tag } from '@/shared/ui/tag';

/** Evidence level (or the reported design), stance, and indirectness. */
export function StudyTags({ source }: { source: SourceView }) {
  const stance = source.stance ? STANCE[source.stance] : null;
  const level = source.evidence_level
    ? EVIDENCE_LEVEL[source.evidence_level]
    : null;
  const design = level ? null : source.study_design;
  if (!level && !design && !stance && source.directness !== 'INDIRECT') {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-1">
      {level ? <Tag>{level}</Tag> : null}
      {design ? (
        <span className="text-xs text-muted-foreground">{design}</span>
      ) : null}
      {stance ? <Tag tone={stance.tone}>{stance.label}</Tag> : null}
      {source.directness === 'INDIRECT' ? (
        <Tag tone="caution">Indirect</Tag>
      ) : null}
    </div>
  );
}
