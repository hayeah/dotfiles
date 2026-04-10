/**
 * Non-interactive fuzzy path matcher inspired by fzf extended-search syntax.
 *
 * Deterministic boolean filter — no scoring, no ranking. Paths are matched
 * case-insensitively with forward-slash normalization.
 *
 * Term syntax:
 *   [!]['][^]<text>[$][']
 *
 * Expression composition:
 *   term1 term2       — implicit AND (all terms must match)
 *   expr | expr       — compound AND (intersection, lower precedence)
 *   expr ; expr       — union OR (higher precedence)
 */

export class MatchError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MatchError";
  }
}

// ---------------------------------------------------------------------------
// Word-boundary helpers
// ---------------------------------------------------------------------------

function isWordChar(ch: string): boolean {
  // Letter or digit. Underscore is NOT a word char (unlike regex \w).
  // Use Unicode-aware checks.
  const code = ch.codePointAt(0)!;
  // Check for ASCII digits
  if (code >= 0x30 && code <= 0x39) return true;
  // Check for ASCII letters
  if ((code >= 0x41 && code <= 0x5a) || (code >= 0x61 && code <= 0x7a))
    return true;
  // For non-ASCII, use regex for Unicode letter/digit categories
  if (code > 0x7f) {
    return /\p{L}|\p{N}/u.test(ch);
  }
  return false;
}

function hasWordBoundary(s: string, idx: number, size: number): boolean {
  const leftOK = idx === 0 || !isWordChar(s[idx - 1]);
  const rightOK = idx + size === s.length || !isWordChar(s[idx + size]);
  return leftOK && rightOK;
}

export function containsWordExact(s: string, needle: string): boolean {
  if (!needle) return false;
  let start = 0;
  while (start <= s.length - needle.length) {
    const idx = s.indexOf(needle, start);
    if (idx < 0) break;
    if (hasWordBoundary(s, idx, needle.length)) return true;
    start = idx + 1;
  }
  return false;
}

export function containsWordPrefix(s: string, needle: string): boolean {
  if (!needle) return false;
  let start = 0;
  while (start <= s.length - needle.length) {
    const idx = s.indexOf(needle, start);
    if (idx < 0) break;
    if (idx === 0 || !isWordChar(s[idx - 1])) return true;
    start = idx + 1;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Term
// ---------------------------------------------------------------------------

interface Term {
  raw: string;
  text: string;
  anchorHead: boolean;
  anchorTail: boolean;
  wordPrefix: boolean;
  wordExact: boolean;
  neg: boolean;
}

function parseTerm(raw: string): Term {
  const t: Term = {
    raw,
    text: "",
    anchorHead: false,
    anchorTail: false,
    wordPrefix: false,
    wordExact: false,
    neg: false,
  };
  let p = raw;

  // negation
  if (p.startsWith("!")) {
    t.neg = true;
    p = p.slice(1);
    if (!p) throw new MatchError(`empty term after negation in '${raw}'`);
  }

  // word-boundary quotes
  if (p.startsWith("'")) {
    p = p.slice(1);
    if (!p) throw new MatchError(`empty term after leading quote in '${raw}'`);
    if (p.endsWith("'")) {
      t.wordExact = true;
      p = p.slice(0, -1);
      if (!p) throw new MatchError(`empty term in '${raw}'`);
    } else {
      t.wordPrefix = true;
    }
  }

  // ./ as ^ anchor
  if (p.startsWith("./")) {
    t.anchorHead = true;
    p = p.slice(2);
  }

  // ^ / $ anchors
  if (p.startsWith("^")) {
    t.anchorHead = true;
    p = p.slice(1);
  }
  if (p.endsWith("$")) {
    t.anchorTail = true;
    p = p.slice(0, -1);
  }

  if (!p) {
    throw new MatchError(
      `empty term after stripping modifiers in '${raw}'`,
    );
  }

  t.text = p.toLowerCase().replace(/\\/g, "/");
  return t;
}

function termMatches(t: Term, path: string): boolean {
  // exact path fast path
  if (t.anchorHead && t.anchorTail && !t.wordExact && !t.wordPrefix) {
    return path === t.text;
  }

  let sub = path;
  if (t.anchorHead) {
    if (!path.startsWith(t.text)) return false;
    sub = path.slice(0, t.text.length);
  }
  if (t.anchorTail) {
    if (!path.endsWith(t.text)) return false;
    sub = path.slice(path.length - t.text.length);
  }

  if (t.wordExact) {
    return containsWordExact(sub, t.text);
  } else if (t.wordPrefix) {
    return containsWordPrefix(sub, t.text);
  } else {
    return sub.includes(t.text);
  }
}

// ---------------------------------------------------------------------------
// Matcher
// ---------------------------------------------------------------------------

export interface Matcher {
  match(paths: string[]): string[];
}

export class FuzzyMatcher implements Matcher {
  pattern: string;
  private terms: Term[];

  constructor(pattern: string, terms: Term[] = []) {
    this.pattern = pattern;
    this.terms = terms;
  }

  match(paths: string[]): string[] {
    if (this.terms.length === 0) return [...paths];

    const out: string[] = [];
    for (const path of paths) {
      const normal = path.toLowerCase().replace(/\\/g, "/");
      let ok = true;
      for (const term of this.terms) {
        let m = termMatches(term, normal);
        if (term.neg) m = !m;
        if (!m) {
          ok = false;
          break;
        }
      }
      if (ok) out.push(path);
    }
    return out;
  }
}

export class CompoundMatcher implements Matcher {
  matchers: Matcher[];

  constructor(matchers: Matcher[]) {
    this.matchers = matchers;
  }

  match(paths: string[]): string[] {
    let current = paths;
    for (const m of this.matchers) {
      current = m.match(current);
    }
    return current;
  }
}

export class UnionMatcher implements Matcher {
  matchers: Matcher[];

  constructor(matchers: Matcher[]) {
    this.matchers = matchers;
  }

  match(paths: string[]): string[] {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const m of this.matchers) {
      for (const p of m.match(paths)) {
        if (!seen.has(p)) {
          seen.add(p);
          out.push(p);
        }
      }
    }
    return out;
  }
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

function newFuzzyMatcher(pattern: string): FuzzyMatcher {
  pattern = pattern.trim();
  if (!pattern) return new FuzzyMatcher(pattern);
  const terms = pattern.split(/\s+/).map(parseTerm);
  return new FuzzyMatcher(pattern, terms);
}

export function parseMatcher(pattern: string): Matcher {
  pattern = pattern.trim();

  // pipe = AND (lower precedence — checked first)
  if (pattern.includes("|")) {
    const parts = pattern.split("|");
    const matchers = parts
      .filter((p) => p.trim())
      .map((p) => parseMatcher(p));
    if (!matchers.length) {
      throw new MatchError("compound pattern contains no valid patterns");
    }
    if (matchers.length === 1) return matchers[0];
    return new CompoundMatcher(matchers);
  }

  // semicolon = OR (higher precedence)
  if (pattern.includes(";")) {
    const parts = pattern.split(";");
    const matchers = parts
      .filter((p) => p.trim())
      .map((p) => parseMatcher(p));
    if (!matchers.length) {
      throw new MatchError("union pattern contains no valid patterns");
    }
    if (matchers.length === 1) return matchers[0];
    return new UnionMatcher(matchers);
  }

  return newFuzzyMatcher(pattern);
}
