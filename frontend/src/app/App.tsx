import { Toaster } from '@/shared/ui/sonner';
import { TooltipProvider } from '@/shared/ui/tooltip';

import { WorkspacePage } from './pages/WorkspacePage';
import { WorkspacesPage } from './pages/WorkspacesPage';
import { useRoute } from './router/hashRoute';

export default function App() {
  const route = useRoute();
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-full flex-col overflow-hidden bg-background">
        {route.page === 'workspace' ? (
          <WorkspacePage
            key={route.id}
            workspaceId={route.id}
            tab={route.tab}
            step={route.step}
          />
        ) : (
          <WorkspacesPage />
        )}
      </div>
      <Toaster position="bottom-right" />
    </TooltipProvider>
  );
}
