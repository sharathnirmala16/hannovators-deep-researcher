import { cn } from '@/shared/lib/cn';
import { Skeleton } from '@/shared/ui/states';

import { HAIRLINE } from './columns';

const NAME_WIDTHS = ['w-48', 'w-36', 'w-56', 'w-40', 'w-32', 'w-44'];

/** Table-shaped loading placeholder: a header and a dozen hairline rows. */
export function SkeletonRows() {
  return (
    <div role="status" className="flex flex-col">
      <span className="sr-only">Loading steps</span>
      <div className={cn('h-8', HAIRLINE)} />
      {Array.from({ length: 12 }, (_, index) => (
        <div
          key={index}
          aria-hidden
          className={cn('flex h-8 items-center gap-4 px-4', HAIRLINE)}
        >
          <Skeleton className="h-2.5 w-6" />
          <Skeleton className="h-2.5 w-20" />
          <Skeleton
            className={cn('h-2.5', NAME_WIDTHS[index % NAME_WIDTHS.length])}
          />
          <Skeleton className="ml-auto h-1.5 w-40 rounded-full" />
        </div>
      ))}
    </div>
  );
}
