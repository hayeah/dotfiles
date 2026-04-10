/**
 * hayeah-ts/shortid — short ID generation and prefix resolution.
 */

import { randomBytes } from "crypto";

export const ID_ALPHABET = "0123456789abcdefghijkmnpqrstuvwxyz";
const MIN_QUERY_LEN = 3;
const MIN_ID_LEN = 3;
const MAX_ID_LEN = 8;
const MAX_RETRIES = 10;

export class IDTooShortError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "IDTooShortError";
  }
}

export class AmbiguousIDError extends Error {
  query: string;
  matches: string[];

  constructor(query: string, matches: string[]) {
    super(`ambiguous prefix '${query}': matches ${JSON.stringify(matches)}`);
    this.name = "AmbiguousIDError";
    this.query = query;
    this.matches = matches;
  }
}

export class IDNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "IDNotFoundError";
  }
}

/**
 * Generate a unique short ID not in `existing`.
 *
 * Starts at 3 chars, grows up to 8 on collision (10 retries per length).
 * Uses `crypto.randomBytes` for cryptographic randomness.
 */
export function generate(existing: Set<string> | ReadonlySet<string>): string {
  for (let length = MIN_ID_LEN; length <= MAX_ID_LEN; length++) {
    for (let i = 0; i < MAX_RETRIES; i++) {
      const buf = randomBytes(length);
      let id = "";
      for (let j = 0; j < length; j++) {
        id += ID_ALPHABET[buf[j] % ID_ALPHABET.length];
      }
      if (!existing.has(id)) return id;
    }
  }
  throw new Error(
    `could not generate a unique id after exhausting retries (length up to ${MAX_ID_LEN})`,
  );
}

/**
 * Resolve a prefix `query` against `candidates`. Case-insensitive.
 *
 * Returns the single matching candidate. Throws on ambiguity, no match,
 * or too-short query.
 */
export function resolve(query: string, candidates: Iterable<string>): string {
  if (query.length < MIN_QUERY_LEN) {
    throw new IDTooShortError(
      `query '${query}' too short (minimum ${MIN_QUERY_LEN} characters)`,
    );
  }

  const q = query.toLowerCase();
  const matches: string[] = [];

  for (const c of candidates) {
    if (c.toLowerCase() === q) return c; // exact match
    if (c.toLowerCase().startsWith(q)) matches.push(c);
  }

  if (matches.length === 1) return matches[0];
  if (matches.length > 1) throw new AmbiguousIDError(query, matches);
  throw new IDNotFoundError(`no match for '${query}'`);
}
