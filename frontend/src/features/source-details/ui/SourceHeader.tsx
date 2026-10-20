import {
  EVIDENCE_LEVEL,
  SEARCH_INTENT,
  SOURCE_STATUS,
  STANCE,
  type SourceDetail,
} from '@/domains/workspace';
import { plainMath } from '@/shared/lib/plainMath';
import { Tag } from '@/shared/ui/tag';

import { Identifiers } from './Identifiers';

function authorLine(authors: readonly string[]): string | null {
  if (authors.length === 0) return null;
  if (authors.length <= 3) return authors.join(', ');
  return `${authors.slice(0, 3).join(', ')}, and ${authors.length - 3} more`;
}

/** Title, authors, venue and year, identifiers, then status tags. */
export function SourceHeader({ detail }: { detail: SourceDetail }) {
  const { source } = detail;
  const status = SOURCE_STATUS[source.status];
  const stance = source.stance ? STANCE[source.stance] : null;
  const intent = source.search_intent
    ? SEARCH_INTENT[source.search_intent]
    : null;
  const authors = authorLine(source.authors);
  return (
    <header className="flex flex-col gap-2">
      <h3 className="reading text-lg font-semibold text-foreground">
        {plainMath(source.title)}
      </h3>
      <div className="flex flex-col gap-0.5 text-sm text-muted-foreground">
        {authors ? <p>{authors}</p> : null}
        <p className="flex flex-wrap gap-x-3">
          {source.venue ? <span className="italic">{source.venue}</span> : null}
          {source.year ? (
            <span className="tabular-nums">{source.year}</span>
          ) : null}
          {source.study_design ? <span>{source.study_design}</span> : null}
        </p>
      </div>
      <Identifiers detail={detail} />
      <div className="flex flex-wrap items-center gap-1">
        <Tag tone={status.tone}>{status.label}</Tag>
        {source.evidence_level ? (
          <Tag>{EVIDENCE_LEVEL[source.evidence_level]}</Tag>
        ) : null}
        {stance ? <Tag tone={stance.tone}>{stance.label}</Tag> : null}
        {intent ? <Tag title={intent.hint}>{intent.label}</Tag> : null}
      </div>
    </header>
  );
}
