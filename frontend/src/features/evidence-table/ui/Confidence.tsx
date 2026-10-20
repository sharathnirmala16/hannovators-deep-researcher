/** Model confidence as a short bar and a percentage. */
export function Confidence({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-xs text-muted-foreground">Not rated</span>;
  }
  const percent = Math.round(value * 100);
  return (
    <span
      className="inline-flex items-center gap-2 text-xs tabular-nums"
      aria-label={`Confidence ${percent}%`}
    >
      <span
        aria-hidden
        className="h-1 w-10 overflow-hidden rounded-full bg-shade-2"
      >
        <span
          className="block h-full rounded-full bg-shade-5"
          style={{ width: `${percent}%` }}
        />
      </span>
      <span aria-hidden>{percent}%</span>
    </span>
  );
}
