/**
 * A worked example of what every answer looks like: a finding with its number
 * marked, and the paper and page it was read from.
 */
export function TraceSpecimen() {
  return (
    <figure className="flex max-w-[60ch] flex-col gap-1.5 border-l-2 border-shade-3 pl-4">
      <blockquote className="reading text-base leading-7 text-foreground">
        Dapagliflozin reduced the risk of the primary composite outcome{' '}
        <span className="marked tabular-nums">
          (hazard ratio, 0.61; 95% CI, 0.51 to 0.72)
        </span>
        .
      </blockquote>
      <figcaption className="text-xs text-muted-foreground">
        Every finding links to the sentence it came from, like this one from the
        DAPA-CKD trial (Heerspink et al., N Engl J Med 2020).
      </figcaption>
    </figure>
  );
}
