import { useCallback, useMemo, useRef } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import { useWorkspace, type TrajectoryStepSummary } from '@/domains/workspace';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/shared/ui/resizable';

import type { TrajectorySource } from '../api/trajectorySource';
import { NO_FILTERS } from '../model/filters';
import { useTrajectoryController } from '../model/useTrajectoryController';
import { StageStrip } from './StageStrip';
import { StepDetail } from './StepDetail';
import type { StepContext } from './stepContext';
import { StepTable } from './StepTable';
import { TrajectoryBodyState } from './TrajectoryBodyState';
import { TrajectoryEmptyRow } from './TrajectoryEmptyRow';
import { TrajectoryToolbar } from './TrajectoryToolbar';

interface TrajectoryWorkspaceProps {
  source: TrajectorySource;
  onOpenSource?: ((sourceId: string) => void) | undefined;
}

function useSourceTitles(): (sourceId: string) => string | null {
  const { load } = useWorkspace();
  const titles = useMemo(() => {
    const sources = load.status === 'ready' ? load.state.sources : [];
    return new Map(sources.map((item) => [item.id, item.title]));
  }, [load]);
  return useCallback((sourceId) => titles.get(sourceId) ?? null, [titles]);
}

export function TrajectoryWorkspace({
  source,
  onOpenSource,
}: TrajectoryWorkspaceProps) {
  const view = useTrajectoryController(source);
  const { selectSource } = useEvidenceSelection();
  const sourceTitle = useSourceTitles();
  const gridRef = useRef<HTMLTableElement>(null);
  const { data, filters, setFilters, close } = view;

  const openSource = useCallback(
    (sourceId: string, step: TrajectoryStepSummary) => {
      selectSource(sourceId);
      source.record({
        name: 'user.source.open',
        summary: `Opened ${sourceTitle(sourceId) ?? sourceId} from trajectory step #${step.id}.`,
        source_ids: [sourceId],
        details: { from: 'trajectory', step_id: step.id },
      });
      onOpenSource?.(sourceId);
    },
    [selectSource, source, sourceTitle, onOpenSource],
  );

  const closeDetail = useCallback(() => {
    close();
    gridRef.current?.focus();
  }, [close]);

  const context: StepContext = useMemo(
    () => ({
      steps: data.steps,
      byId: view.byId,
      origin: view.origin,
      sourceTitle,
      onOpenStep: view.open,
      onOpenSource: openSource,
    }),
    [data.steps, view.byId, view.origin, sourceTitle, view.open, openSource],
  );

  const paging = useMemo(
    () => ({
      hasMore: data.nextAfter !== null,
      loadingMore: data.loadingMore,
      error: data.moreError,
      onLoadMore: data.loadMore,
    }),
    [data.nextAfter, data.loadingMore, data.moreError, data.loadMore],
  );

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <TrajectoryToolbar
        filters={filters}
        onChange={setFilters}
        kindCounts={view.kindCounts}
        live={view.live}
        liveStatus={data.liveStatus}
        onLiveChange={view.setLive}
        shown={view.rows.length}
        total={data.total}
      />
      <StageStrip
        summary={view.stages}
        active={filters.stage}
        onSelect={(stage) => setFilters({ ...filters, stage })}
      />
      <div className="min-h-0 flex-1">
        {data.load.phase === 'ready' ? (
          <ResizablePanelGroup orientation="horizontal" className="h-full">
            <ResizablePanel id="trajectory-table" minSize="30%">
              <StepTable
                rows={view.rows}
                origin={view.origin}
                range={view.range}
                cursorId={view.cursorId}
                openId={view.openId}
                onCursor={view.moveCursor}
                onOpen={view.open}
                onClose={closeDetail}
                paging={paging}
                gridRef={gridRef}
                empty={
                  <TrajectoryEmptyRow
                    filters={filters}
                    loaded={data.steps.length}
                    onClear={() => setFilters(NO_FILTERS)}
                  />
                }
              />
            </ResizablePanel>
            {view.openId !== null ? (
              <>
                <ResizableHandle />
                <ResizablePanel
                  id="trajectory-detail"
                  defaultSize="42%"
                  minSize="25%"
                >
                  <StepDetail
                    stepId={view.openId}
                    summary={view.openSummary}
                    detail={view.detail}
                    context={context}
                    onClose={closeDetail}
                  />
                </ResizablePanel>
              </>
            ) : null}
          </ResizablePanelGroup>
        ) : (
          <TrajectoryBodyState load={data.load} onRetry={data.retry} />
        )}
      </div>
    </div>
  );
}
