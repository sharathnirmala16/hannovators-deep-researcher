import { useWorkspace, type WorkspaceState } from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, SkeletonBlock } from '@/shared/ui/states';

import { PrismaFlow } from './PrismaFlow';
import { RemovalReasons } from './RemovalReasons';
import { SearchIntents } from './SearchIntents';

function FunnelMeta({ state }: { state: WorkspaceState | null }) {
  if (!state || state.sources.length === 0) return null;
  const included = state.funnel.appraise_promoted;
  return (
    <>
      <span>{plural(state.sources.length, 'source')}</span>
      {included > 0 ? (
        <span className="text-tone-positive">{included} included</span>
      ) : null}
    </>
  );
}

/** PRISMA-style funnel, search intents, and removal reasons. */
export function ScreeningFunnel() {
  const { load } = useWorkspace();
  if (load.status === 'error') return null;
  const state = load.status === 'ready' ? load.state : null;
  return (
    <section
      aria-labelledby="funnel-title"
      className="flex min-w-0 flex-col gap-3"
    >
      <SectionHeader
        id="funnel-title"
        title="Screening"
        meta={<FunnelMeta state={state} />}
      />
      {!state ? <SkeletonBlock lines={4} label="Loading the funnel" /> : null}
      {state && state.sources.length === 0 ? (
        <EmptyState title="No sources yet">
          The flow fills in as the search finds sources and screening sorts
          them.
        </EmptyState>
      ) : null}
      {state && state.sources.length > 0 ? (
        <div className="flex min-w-0 flex-col gap-4">
          <PrismaFlow funnel={state.funnel} />
          <SearchIntents sources={state.sources} />
          <RemovalReasons sources={state.sources} />
        </div>
      ) : null}
    </section>
  );
}
