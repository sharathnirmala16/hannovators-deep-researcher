import { Fragment } from 'react';

import type { UiComponentId } from '@/domains/workspace';

import { uiComponentRegistry, type PaneId } from './uiComponentRegistry';

interface PaneEntriesProps {
  pane: PaneId;
  /** `ui_components` from the workspace state, in backend order. */
  components: readonly UiComponentId[];
}

/** Mounts the feature entries that the backend chose for one pane. */
export function PaneEntries({ pane, components }: PaneEntriesProps) {
  return components
    .filter((id) => uiComponentRegistry[id].pane === pane)
    .map((id) => (
      <Fragment key={id}>{uiComponentRegistry[id].render()}</Fragment>
    ));
}
