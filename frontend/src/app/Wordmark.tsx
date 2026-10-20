/** The product name, set like a journal masthead with a highlighter tick. */
export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <a
      href="#/"
      className="flex shrink-0 items-center gap-2.5 rounded-sm text-foreground"
      aria-label="Hannovators Deep Researcher, all workspaces"
    >
      <span
        aria-hidden
        className="h-4 w-1.5 -skew-x-12 rounded-[2px] bg-marker shadow-[inset_0_0_0_1px_#e6c63a]"
      />
      {compact ? null : (
        <span className="flex items-baseline gap-2">
          <span className="reading text-lg font-semibold tracking-[-0.01em]">
            Hannovators
          </span>
          <span className="text-sm text-muted-foreground">Deep Researcher</span>
        </span>
      )}
    </a>
  );
}
