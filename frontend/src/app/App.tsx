import { WorkspaceProvider } from '@/domains/workspace';

import { WorkbenchLayout } from './WorkbenchLayout';

export default function App() {
  return (
    <WorkspaceProvider>
      <WorkbenchLayout />
    </WorkspaceProvider>
  );
}
