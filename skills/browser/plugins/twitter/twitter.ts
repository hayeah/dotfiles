export default function setup() {
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

	function extractFromArticle(article: Element): Tweet | null {
		const timeEl = article.querySelector("time");
		const textEl = article.querySelector("[data-testid='tweetText']");
		const link = article.querySelector("a[href*='/status/']") as HTMLAnchorElement | null;
		const socialContext = article.querySelector("[data-testid='socialContext']");
		const userNameEl = article.querySelector("[data-testid='User-Name']");

		// Pull tweet ID from the first status link
		const tweetId = link?.href?.match(/\/status\/(\d+)/)?.[1];
		if (!tweetId) return null;

		// Author handle: find profile link (not a status link)
		const profileLink = userNameEl
			? Array.from(userNameEl.querySelectorAll("a")).find(
					(a) => !a.href.includes("/status/"),
				)
			: null;
		const handle = profileLink?.href?.split("/").pop() ?? "";

		// Display name: first nested span with actual text
		const displayName =
			(userNameEl?.querySelector("span > span") as HTMLElement | null)?.textContent?.trim() ??
			"";

		// Media images
		const images = Array.from(article.querySelectorAll("img[alt]"))
			.map((i) => (i as HTMLImageElement).src)
			.filter((s) => s.includes("pbs.twimg.com/media"));

		return {
			id: tweetId,
			author: handle,
			displayName,
			text: textEl?.textContent?.trim() ?? "",
			time: timeEl?.getAttribute("datetime") ?? "",
			url: `https://x.com/${handle}/status/${tweetId}`,
			retweet: socialContext?.textContent?.trim() ?? null,
			images,
		};
	}

	/** Extract all currently visible tweets from the DOM. */
	function tweets(): Tweet[] {
		const articles = document.querySelectorAll("article[data-testid='tweet']");
		return Array.from(articles)
			.map(extractFromArticle)
			.filter((t): t is Tweet => t !== null);
	}

	/** Get IDs of currently visible tweets. */
	function visibleIds(): string[] {
		return tweets().map((t) => t.id);
	}

	/** Scroll the page down by one viewport height. Returns new scrollY. */
	function scrollDown(amount?: number): number {
		const delta = amount ?? window.innerHeight;
		window.scrollBy({ top: delta, behavior: "smooth" });
		return window.scrollY;
	}

	/** Scroll to absolute position. */
	function scrollTo(y: number): void {
		window.scrollTo({ top: y, behavior: "smooth" });
	}

	/** Current scroll state. */
	function scrollState(): { scrollY: number; scrollHeight: number; atBottom: boolean } {
		const scrollY = window.scrollY;
		const scrollHeight = document.documentElement.scrollHeight;
		const clientHeight = window.innerHeight;
		return {
			scrollY,
			scrollHeight,
			atBottom: scrollY + clientHeight >= scrollHeight - 200,
		};
	}

	/** Check if current page is a list timeline. */
	function isListPage(): boolean {
		return window.location.pathname.includes("/i/lists/");
	}

	/** Page title / list name. */
	function pageTitle(): string {
		return document.title;
	}

	return { tweets, visibleIds, scrollDown, scrollTo, scrollState, isListPage, pageTitle };
}
