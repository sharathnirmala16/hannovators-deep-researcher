/**
 * Inline markdown: `code`, **bold**, *italic*, [links](https://...), `[n]`
 * citation markers (also `[1, 2]`), and backslash escapes. Images (markdown
 * and `<img>` tags) are dropped. Links keep only http(s) and mailto targets;
 * anything else renders as plain text.
 */

export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'strong'; children: Inline[] }
  | { kind: 'em'; children: Inline[] }
  | { kind: 'link'; href: string; children: Inline[] }
  | { kind: 'cite'; n: number };

const IMAGE = /!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>/gi;
const EMPTY_LINK = /\[\s*\]\([^)]*\)/g;
const SAFE_HREF = /^(?:https?:\/\/|mailto:)/i;

const INLINE = new RegExp(
  [
    /\\([\\`*_[\]()#+\-.!|>~])/.source,
    /`([^`]+)`/.source,
    /\[([^\]]+)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)/.source,
    /\*\*(.+?)\*\*/.source,
    /__(.+?)__/.source,
    /\*([^*\s](?:[^*]*[^*\s])?)\*/.source,
    /\b_([^_\s](?:[^_]*[^_\s])?)_\b/.source,
    /\[(\d{1,3}(?:\s*[,;]\s*\d{1,3})*)\]/.source,
  ].join('|'),
  'g',
);

function citations(group: string): Inline[] {
  return group
    .split(/[,;]/)
    .map((part) => ({ kind: 'cite', n: Number(part.trim()) }) as const);
}

function link(label: string, href: string): Inline[] {
  const children = parseInlineText(label);
  return SAFE_HREF.test(href) ? [{ kind: 'link', href, children }] : children;
}

function token(match: RegExpMatchArray): Inline[] {
  const [, escaped, code, label, href, bold, boldAlt, em, emAlt, cites] = match;
  if (escaped !== undefined) return [{ kind: 'text', text: escaped }];
  if (code !== undefined) return [{ kind: 'code', text: code }];
  if (label !== undefined) return link(label, href ?? '');
  const strong = bold ?? boldAlt;
  if (strong !== undefined) {
    return [{ kind: 'strong', children: parseInlineText(strong) }];
  }
  const italic = em ?? emAlt;
  if (italic !== undefined) {
    return [{ kind: 'em', children: parseInlineText(italic) }];
  }
  return citations(cites ?? '');
}

function pushText(out: Inline[], text: string): void {
  if (!text) return;
  const last = out[out.length - 1];
  if (last?.kind === 'text') last.text += text;
  else out.push({ kind: 'text', text });
}

function parseInlineText(text: string): Inline[] {
  const out: Inline[] = [];
  let cursor = 0;
  for (const match of text.matchAll(INLINE)) {
    pushText(out, text.slice(cursor, match.index));
    for (const inline of token(match)) {
      if (inline.kind === 'text') pushText(out, inline.text);
      else out.push(inline);
    }
    cursor = match.index + match[0].length;
  }
  pushText(out, text.slice(cursor));
  return out;
}

/** Parses one line or paragraph of inline markdown. */
export function parseInline(text: string): Inline[] {
  return parseInlineText(text.replace(IMAGE, '').replace(EMPTY_LINK, ''));
}
