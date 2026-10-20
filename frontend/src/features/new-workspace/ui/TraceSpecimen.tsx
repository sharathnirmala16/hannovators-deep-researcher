/**
 * What an answer looks like: a plain finding with its number marked, the way
 * the source viewer marks it in the paper.
 */
export function TraceSpecimen() {
  return (
    <figure className="flex flex-col gap-2 border-t border-border pt-6">
      <blockquote className="reading max-w-[56ch] text-base leading-7 text-foreground">
        People who took vitamin D every day were{' '}
        <span className="marked">about 12% less likely to catch a cold</span>.
      </blockquote>
      <figcaption className="max-w-[60ch] text-xs text-muted-foreground">
        An example of how answers read. Every finding is marked in the paper it
        came from, so you can check it in one click.
      </figcaption>
    </figure>
  );
}
