const EXAMPLES = [
  'Does vitamin D prevent colds?',
  'Does coffee raise blood pressure?',
  'Is remote work productive?',
] as const;

interface ExampleQuestionsProps {
  onPick: (question: string) => void;
  disabled: boolean;
}

/** A few plain questions to start from; one click fills the composer. */
export function ExampleQuestions({ onPick, disabled }: ExampleQuestionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-0.5 text-xs text-muted-foreground">Try</span>
      {EXAMPLES.map((question) => (
        <button
          key={question}
          type="button"
          disabled={disabled}
          onClick={() => onPick(question)}
          className="h-7 rounded-md border border-border bg-background px-2.5 text-xs text-foreground transition-colors hover:border-shade-3 hover:bg-desk disabled:opacity-50"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
