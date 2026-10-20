import { ScanIcon, ZoomInIcon, ZoomOutIcon } from 'lucide-react';

import { Button } from '@/shared/ui/button';

interface GraphControlsProps {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
}

/** Zoom and fit, stacked in the canvas corner. */
export function GraphControls({ zoomIn, zoomOut, fit }: GraphControlsProps) {
  return (
    <div
      role="toolbar"
      aria-label="Graph zoom"
      aria-orientation="vertical"
      className="absolute top-2 right-2 flex flex-col gap-0.5 rounded-md border border-border bg-background p-0.5"
    >
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Zoom in"
        title="Zoom in"
        onClick={zoomIn}
      >
        <ZoomInIcon className="size-3.5" />
      </Button>
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Zoom out"
        title="Zoom out"
        onClick={zoomOut}
      >
        <ZoomOutIcon className="size-3.5" />
      </Button>
      <div aria-hidden className="mx-1 h-px bg-border" />
      <Button
        size="icon-xs"
        variant="ghost"
        aria-label="Fit the graph"
        title="Fit the graph"
        onClick={fit}
      >
        <ScanIcon className="size-3.5" />
      </Button>
    </div>
  );
}
