var __browserPlugin = (function() {
	//#region plugins/twitter/twitter.ts
	function setup() {
		function extractFromArticle(article) {
			const timeEl = article.querySelector("time");
			const textEl = article.querySelector("[data-testid='tweetText']");
			const link = article.querySelector("a[href*='/status/']");
			const socialContext = article.querySelector("[data-testid='socialContext']");
			const userNameEl = article.querySelector("[data-testid='User-Name']");
			const tweetId = link?.href?.match(/\/status\/(\d+)/)?.[1];
			if (!tweetId) return null;
			const handle = (userNameEl ? Array.from(userNameEl.querySelectorAll("a")).find((a) => !a.href.includes("/status/")) : null)?.href?.split("/").pop() ?? "";
			const displayName = (userNameEl?.querySelector("span > span"))?.textContent?.trim() ?? "";
			const images = Array.from(article.querySelectorAll("img[alt]")).map((i) => i.src).filter((s) => s.includes("pbs.twimg.com/media"));
			return {
				id: tweetId,
				author: handle,
				displayName,
				text: textEl?.textContent?.trim() ?? "",
				time: timeEl?.getAttribute("datetime") ?? "",
				url: `https://x.com/${handle}/status/${tweetId}`,
				retweet: socialContext?.textContent?.trim() ?? null,
				images
			};
		}
		/** Extract all currently visible tweets from the DOM. */
		function tweets() {
			const articles = document.querySelectorAll("article[data-testid='tweet']");
			return Array.from(articles).map(extractFromArticle).filter((t) => t !== null);
		}
		/** Get IDs of currently visible tweets. */
		function visibleIds() {
			return tweets().map((t) => t.id);
		}
		/** Scroll the page down by one viewport height. Returns new scrollY. */
		function scrollDown(amount) {
			const delta = amount ?? window.innerHeight;
			window.scrollBy({
				top: delta,
				behavior: "smooth"
			});
			return window.scrollY;
		}
		/** Scroll to absolute position. */
		function scrollTo(y) {
			window.scrollTo({
				top: y,
				behavior: "smooth"
			});
		}
		/** Current scroll state. */
		function scrollState() {
			const scrollY = window.scrollY;
			const scrollHeight = document.documentElement.scrollHeight;
			return {
				scrollY,
				scrollHeight,
				atBottom: scrollY + window.innerHeight >= scrollHeight - 200
			};
		}
		/** Check if current page is a list timeline. */
		function isListPage() {
			return window.location.pathname.includes("/i/lists/");
		}
		/** Page title / list name. */
		function pageTitle() {
			return document.title;
		}
		return {
			tweets,
			visibleIds,
			scrollDown,
			scrollTo,
			scrollState,
			isListPage,
			pageTitle
		};
	}
	//#endregion
	return setup;
})();
