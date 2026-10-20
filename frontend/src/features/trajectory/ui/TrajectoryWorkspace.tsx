import { useCallback, useMemo, useRef } from 'react';

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/shared/ui/resizable';

import type { TrajectorySource } from '../api/trajectorySource';
import { NO_FILTERS } from '../model/filters';
import { useStepContext } from '../model/useStepContext';
import { useTrajectoryController } from '../model/useTrajectoryController';
import { StageStrip } from './StageStrip';
import { StepDetail } from './StepDetail';
import { StepTable } from './StepTable';
import { TrajectoryBodyState } from './TrajectoryBodyState';
import { TrajectoryEmptyRow } from './TrajectoryEmptyRow';
import { TrajectoryToolbar } from './TrajectoryToolbar';

interface TrajectoryWorkspaceProps {
  source: TrajectorySource;
  onOpenSource?: ((sourceId: string) => void) | undefined;
  step?: number | null | undefined;
}

/** Toolbar, stage strip, the step table, and the detail panel. */
export function TrajectoryWorkspace({
  source,
  onOpenSource,
  step = null,
}: TrajectoryWorkspaceProps) {
  const view = useTrajectoryController(source, step);
  const gridRef = useRef<HTMLTableElement>(null);
  const { data, filters, setFilters, close } = view;

  const closeDetail = useCallback(() => {
    close();
    gridRef.current?.focus();
  }, [close]);

  const context = useStepContext({
    source,
    steps: data.steps,
    byId: view.byId,
    origin: view.origin,
    onOpenStep: view.open,
    onOpenSource,
  });

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
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <div className="flex shrink-0 flex-col gap-3 border-b bg-background px-4 py-3">
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
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
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
