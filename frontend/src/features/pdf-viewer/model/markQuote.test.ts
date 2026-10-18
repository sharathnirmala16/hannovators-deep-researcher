import { describe, expect, it } from 'vitest';

import { markQuote } from './markQuote';

describe('markQuote', () => {
  it('matches across re-wrapped whitespace and case', () => {
    const segments = markQuote(
      'Prices reached 87\n  USD/kWh in 2025.',
      'reached 87 usd/kwh',
    );
    expect(segments).toEqual([
      { text: 'Prices ', marked: false },
      { text: 'reached 87\n  USD/kWh', marked: true },
      { text: ' in 2025.', marked: false },
    ]);
  });

  it('escapes regex characters in the quote', () => {
    const segments = markQuote('HR 0.74 (95% CI [0.65]).', '(95% CI [0.65])');
    expect(segments.filter((segment) => segment.marked)).toEqual([
      { text: '(95% CI [0.65])', marked: true },
    ]);
  });

  it('leaves the text unmarked for a missing, blank, or absent quote', () => {
    expect(markQuote('abc', null)).toEqual([{ text: 'abc', marked: false }]);
    expect(markQuote('abc', '   ')).toEqual([{ text: 'abc', marked: false }]);
    expect(markQuote('abc', 'xyz')).toEqual([{ text: 'abc', marked: false }]);
    expect(markQuote('', 'abc')).toEqual([]);
  });
});
