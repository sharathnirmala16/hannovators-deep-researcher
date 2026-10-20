const SYMBOLS: Record<string, string> = {
  ge: '≥',
  geq: '≥',
  le: '≤',
  leq: '≤',
  neq: '≠',
  ne: '≠',
  approx: '≈',
  sim: '~',
  times: '×',
  cdot: '·',
  pm: '±',
  mu: 'μ',
  alpha: 'α',
  beta: 'β',
  gamma: 'γ',
  delta: 'δ',
  Delta: 'Δ',
  kappa: 'κ',
  lambda: 'λ',
  sigma: 'σ',
  chi: 'χ',
  to: '→',
  rightarrow: '→',
  leftarrow: '←',
  infty: '∞',
  degree: '°',
  circ: '°',
  lt: '<',
  gt: '>',
};

const SUPERSCRIPT: Record<string, string> = {
  '0': '⁰',
  '1': '¹',
  '2': '²',
  '3': '³',
  '4': '⁴',
  '5': '⁵',
  '6': '⁶',
  '7': '⁷',
  '8': '⁸',
  '9': '⁹',
  '+': '⁺',
  '-': '⁻',
};

const SUBSCRIPT: Record<string, string> = {
  '0': '₀',
  '1': '₁',
  '2': '₂',
  '3': '₃',
  '4': '₄',
  '5': '₅',
  '6': '₆',
  '7': '₇',
  '8': '₈',
  '9': '₉',
};

function mapChars(text: string, table: Record<string, string>): string {
  const chars = [...text];
  return chars.every((char) => table[char])
    ? chars.map((char) => table[char]).join('')
    : text;
}

/** Turns one TeX math run into plain Unicode text. */
function plainRun(tex: string): string {
  return tex
    .replace(
      /\\(?:text|mathrm|textrm|mathit|textit|mathbf|textbf|operatorname)\s*\{([^{}]*)\}/g,
      '$1',
    )
    .replace(/\\([%&$#_{}])/g, '$1')
    .replace(/\\[,;:! ]/g, ' ')
    .replace(/\\([A-Za-z]+)/g, (match, name: string) => SYMBOLS[name] ?? match)
    .replace(/\^\{([^{}]*)\}|\^(\S)/g, (_, group?: string, single?: string) =>
      mapChars(group ?? single ?? '', SUPERSCRIPT),
    )
    .replace(/_\{([^{}]*)\}|_(\d)/g, (_, group?: string, single?: string) =>
      mapChars(group ?? single ?? '', SUBSCRIPT),
    )
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ');
}

/**
 * Renders inline TeX (`$...$`, `\(...\)`) in plain text as readable Unicode,
 * for example `$\text{eGFR } 15\text{-}29\text{ mL/min/1.73 m}^2$` becomes
 * `eGFR 15-29 mL/min/1.73 m²`. Text without math is returned unchanged.
 */
export function plainMath(text: string): string {
  return text
    .replace(
      /\$\$([^$]+)\$\$|\$([^$]+)\$|\\\((.+?)\\\)/g,
      (match: string, a?: string, b?: string, c?: string) => {
        const run = a ?? b ?? c ?? '';
        // "$5 and $6" is prose, not math: math has a command, ^, _, or braces.
        return /[\\^_{}]/.test(run) ? plainRun(run).trim() : match;
      },
    )
    .replace(/[ \t]{2,}/g, ' ');
}
