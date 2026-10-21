import { FileTextIcon } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import {
  SOURCE_STATUS,
  useWorkspace,
  type DeepResearchRecord,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { plural } from '@/shared/lib/format';
import { parseMarkdown } from '@/shared/lib/markdown';
import { Button } from '@/shared/ui/button';
import { MarkdownBlocks } from '@/shared/ui/markdown';
import { Tag } from '@/shared/ui/tag';

import { ReportSources } from './ReportSources';

type ReportSource = DeepResearchRecord['sources'][number];

/** The first paragraph of the report, shown as its summary. */
function useLead(content: string) {
  return useMemo(() => {
    const lead = parseMarkdown(content).find(
      (block) => block.kind === 'paragraph',
    );
    return lead ? [lead] : [];
  }, [content]);
}

/** The report source in the workspace state; reloads once when it is new. */
function useReportSource(sourceId: string | null) {
  const { load, reload } = useWorkspace();
  const sources = load.status === 'ready' ? load.state.sources : null;
  const source = sources?.find((item) => item.id === sourceId) ?? null;
  const missing = sourceId !== null && sources !== null && source === null;
  useEffect(() => {
    if (missing) reload();
  }, [missing, reload]);
  return source;
}

/**
 * A finished run: the summary, the action that opens the full report in the
 * Source pane (where it can be included or excluded), and the cited sources.
 */
export function DeepResearchSummary({
  record,
}: {
  record: DeepResearchRecord;
}) {
  const { recordAction } = useWorkspace();
  const { selectSource } = useEvidenceSelection();
  const lead = useLead(record.content);
  const [active, setActive] = useState<number | null>(null);
  const reportId = record.report_source_id;
  const report = useReportSource(reportId);
  const status = report ? SOURCE_STATUS[report.status] : null;

  const open = (n: number, source: ReportSource | undefined) => {
    setActive(n);
    recordAction({
      name: 'user.citation.open',
      summary: `Opened deep research source [${n}]`,
      target: source?.url ?? null,
      source_ids: source?.source_id ? [source.source_id] : [],
      details: { report: 'deep_research', n },
    });
    if (source?.source_id) selectSource(source.source_id);
  };
  const openReport = () => {
    if (!reportId) return;
    recordAction({
      name: 'user.deep_research.open_report',
      summary: 'Opened the deep research report in the sources',
      target: reportId,
      source_ids: [reportId],
      details: { report: 'deep_research' },
    });
    selectSource(reportId);
  };

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {lead.length > 0 ? (
        <MarkdownBlocks
          blocks={lead}
          className="reading text-sm leading-6 text-foreground"
          citation={(n) => (
            <button
              type="button"
              onClick={() => open(n, record.sources[n - 1])}
              aria-label={`Source ${n}`}
              className={cn(
                'mx-px rounded-[3px] font-sans text-xs font-semibold text-foreground tabular-nums underline decoration-marker decoration-2 underline-offset-[3px] transition-colors hover:marked-soft',
                active === n && 'marked',
              )}
            >
              [{n}]
            </button>
          )}
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={openReport}
          disabled={!reportId}
        >
          <FileTextIcon />
          Open report in sources
        </Button>
        {status ? <Tag tone={status.tone}>{status.label}</Tag> : null}
      </div>
      <p className="text-xs text-muted-foreground">
        {reportId
          ? 'The full report is now a source. Open it to read it, then include or exclude it under Details.'
          : 'The report is being added to the sources.'}{' '}
        It cites {plural(record.sources.length, 'source')}.
      </p>
      {record.sources.length > 0 ? (
        <ReportSources sources={record.sources} active={active} onOpen={open} />
      ) : null}
    </div>
  );
}
