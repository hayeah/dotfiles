import type { Page, Browser } from "puppeteer-core";
import { writeFileSync } from "node:fs";

interface Tweet {
	id: string;
	author: string;
	displayName: string;
	text: string;
	time: string;
	url: string;
	retweet: string | null;
	images: string[];
}

interface FetchOptions {
	/** Max number of tweets to collect (default: 100) */
	limit?: number;
	/** Stop collecting tweets older than this ISO date string */
	until?: string;
	/** Milliseconds to wait after each scroll for new tweets to load (default: 1500) */
	delay?: number;
	/** Pixels to scroll each step (default: window.innerHeight) */
	scrollAmount?: number;
	/** Max scroll attempts with no new tweets before stopping (default: 5) */
	maxStalls?: number;
	/** Log progress to stderr */
	verbose?: boolean;
}

interface FetchResult {
	tweets: Tweet[];
	scrollCount: number;
	stoppedReason: "limit" | "until" | "bottom" | "stalled";
}

// Serialized as a string so tsx/esbuild helpers don't bleed into page.evaluate()
const EXTRACT_TWEETS_SRC = `
(function() {
  function extractFromArticle(article) {
    var timeEl = article.querySelector("time");
    var textEl = article.querySelector("[data-testid='tweetText']");
    var link = article.querySelector("a[href*='/status/']");
    var socialContext = article.querySelector("[data-testid='socialContext']");
    var userNameEl = article.querySelector("[data-testid='User-Name']");
    var m = link && link.href.match(/\\/status\\/(\\d+)/);
    var tweetId = m && m[1];
    if (!tweetId) return null;
    var anchors = userNameEl ? Array.from(userNameEl.querySelectorAll("a")) : [];
    var profileLink = anchors.find(function(a) { return !a.href.includes("/status/"); });
    var handle = profileLink ? profileLink.href.split("/").pop() : "";
    var nameSpan = userNameEl && userNameEl.querySelector("span > span");
    var displayName = nameSpan ? (nameSpan.textContent || "").trim() : "";
    var images = Array.from(article.querySelectorAll("img[alt]"))
      .map(function(i) { return i.src; })
      .filter(function(s) { return s.includes("pbs.twimg.com/media"); });
    return {
      id: tweetId,
      author: handle,
      displayName: displayName,
      text: textEl ? (textEl.textContent || "").trim() : "",
      time: timeEl ? timeEl.getAttribute("datetime") : "",
      url: "https://x.com/" + handle + "/status/" + tweetId,
      retweet: socialContext ? (socialContext.textContent || "").trim() || null : null,
      images: images,
    };
  }
  var articles = document.querySelectorAll("article[data-testid='tweet']");
  return Array.from(articles).map(extractFromArticle).filter(function(t) { return t !== null; });
})()
`;

function extractTweets(page: Page): Promise<Tweet[]> {
	return page.evaluate(EXTRACT_TWEETS_SRC) as Promise<Tweet[]>;
}

function sleep(ms: number): Promise<void> {
	return new Promise((r) => setTimeout(r, ms));
}

export default async function setup({ page }: { page: Page; browser: Browser }) {
	/**
	 * Scroll through the current Twitter/X page and collect tweets.
	 *
	 * Twitter uses a virtual DOM — tweets are added/removed as you scroll.
	 * This function scrolls incrementally, collecting unique tweets by ID.
	 */
	async function fetch(options: FetchOptions = {}): Promise<FetchResult> {
		const limit = options.limit ?? 100;
		const until = options.until ? new Date(options.until).getTime() : null;
		const delay = options.delay ?? 1500;
		const maxStalls = options.maxStalls ?? 5;
		const verbose = options.verbose ?? false;

		const collected = new Map<string, Tweet>();
		let scrollCount = 0;
		let stallCount = 0;
		let stoppedReason: FetchResult["stoppedReason"] = "bottom";

		const log = verbose ? (...args: unknown[]) => process.stderr.write(args.join(" ") + "\n") : () => {};

		// Initial collection
		const initial = await extractTweets(page);
		for (const t of initial) collected.set(t.id, t);
		log(`Initial: ${collected.size} tweets`);

		while (true) {
			// Check limit
			if (collected.size >= limit) {
				stoppedReason = "limit";
				break;
			}

			// Check until date (tweets are roughly in reverse-chron but lists may vary)
			if (until) {
				const oldest = Array.from(collected.values()).reduce((min, t) => {
					const ts = t.time ? new Date(t.time).getTime() : Infinity;
					return ts < min ? ts : min;
				}, Infinity);
				if (oldest !== Infinity && oldest < until) {
					stoppedReason = "until";
					break;
				}
			}

			// Check if at bottom
			const { atBottom, scrollY, scrollHeight } = await page.evaluate(() => {
				const scrollY = window.scrollY;
				const scrollHeight = document.documentElement.scrollHeight;
				const clientHeight = window.innerHeight;
				return { scrollY, scrollHeight, atBottom: scrollY + clientHeight >= scrollHeight - 200 };
			});

			if (atBottom) {
				// Wait a bit in case there's lazy loading
				await sleep(delay * 2);
				const { atBottom: stillAtBottom } = await page.evaluate(() => ({
					atBottom:
						window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 200,
				}));
				if (stillAtBottom) {
					stoppedReason = "bottom";
					break;
				}
			}

			// Scroll down
			const scrollAmount = options.scrollAmount;
			await page.evaluate((amount) => {
				window.scrollBy({ top: amount ?? window.innerHeight, behavior: "smooth" });
			}, scrollAmount ?? null);

			scrollCount++;
			log(`Scroll ${scrollCount}: scrollY=${scrollY}, scrollH=${scrollHeight}`);

			// Wait for new content
			await sleep(delay);

			// Collect new tweets
			const visible = await extractTweets(page);
			const beforeSize = collected.size;
			for (const t of visible) {
				if (!collected.has(t.id)) {
					collected.set(t.id, t);
				}
			}
			const newCount = collected.size - beforeSize;
			log(`After scroll ${scrollCount}: +${newCount} new, total=${collected.size}`);

			if (newCount === 0) {
				stallCount++;
				log(`Stall ${stallCount}/${maxStalls}`);
				if (stallCount >= maxStalls) {
					stoppedReason = "stalled";
					break;
				}
				// Wait longer on stall
				await sleep(delay * 2);
			} else {
				stallCount = 0;
			}
		}

		// Sort by time descending (newest first)
		const tweets = Array.from(collected.values()).sort((a, b) => {
			const ta = a.time ? new Date(a.time).getTime() : 0;
			const tb = b.time ? new Date(b.time).getTime() : 0;
			return tb - ta;
		});

		return { tweets, scrollCount, stoppedReason };
	}

	/**
	 * Scroll and collect tweets, then save as JSON.
	 * @param path Output file path
	 * @param options Same as fetch()
	 */
	async function save(path: string, options: FetchOptions = {}): Promise<{ saved: string; count: number; scrollCount: number; stoppedReason: string }> {
		const result = await fetch(options);
		writeFileSync(path, JSON.stringify(result.tweets, null, 2));
		return {
			saved: path,
			count: result.tweets.length,
			scrollCount: result.scrollCount,
			stoppedReason: result.stoppedReason,
		};
	}

	/**
	 * Format collected tweets as readable markdown.
	 */
	async function fetchMarkdown(options: FetchOptions = {}): Promise<string> {
		const result = await fetch(options);
		const lines: string[] = [];
		for (const t of result.tweets) {
			const rt = t.retweet ? ` *(${t.retweet})*` : "";
			lines.push(`### @${t.author} — ${t.time}${rt}`);
			if (t.displayName && t.displayName !== t.author) {
				lines.push(`**${t.displayName}**`);
			}
			lines.push("");
			lines.push(t.text || "*(no text)*");
			if (t.images.length > 0) {
				for (const img of t.images) {
					lines.push(`![image](${img})`);
				}
			}
			lines.push("");
			lines.push(`[${t.url}](${t.url})`);
			lines.push("");
			lines.push("---");
			lines.push("");
		}
		return lines.join("\n");
	}

	return { fetch, save, fetchMarkdown };
}
