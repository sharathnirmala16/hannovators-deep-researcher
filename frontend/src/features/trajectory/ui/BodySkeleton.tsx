/** Loading placeholder for a step body. */
export function BodySkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-2 px-4 py-3">
      {[72, 56, 88, 40].map((width) => (
        <span
          key={width}
          className="h-3 rounded-sm bg-muted motion-safe:animate-pulse"
          style={{ width: `${width}%` }}
        />
      ))}
    </div>
  );
}
