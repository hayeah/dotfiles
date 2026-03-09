import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import type { ContentExtractor, ExtractedContent } from "../types.js";
import { htmlToMarkdown, pageOuterHTML } from "../utils.js";

export const defaultContentExtractor: ContentExtractor = {
	id: "extractor/default",
	matches: () => true,
	extract: async (page, url): Promise<ExtractedContent> => {
		const outerHTML = await pageOuterHTML(page);

		const doc = new JSDOM(outerHTML, { url: url.href });
		const reader = new Readability(doc.window.document);
		const article = reader.parse();

		if (article?.content) {
			return {
				title: article.title ?? undefined,
				content: htmlToMarkdown(article.content),
			};
		}

		const fallbackDoc = new JSDOM(outerHTML, { url: url.href });
		const fallbackBody = fallbackDoc.window.document;
		fallbackBody
			.querySelectorAll("script, style, noscript, nav, header, footer, aside")
			.forEach((el) => el.remove());
		const main =
			fallbackBody.querySelector("main, article, [role='main'], .content, #content") ||
			fallbackBody.body;
		const fallbackHTML = main?.innerHTML || "";

		return {
			content:
				fallbackHTML.trim().length > 100
					? htmlToMarkdown(fallbackHTML)
					: "(Could not extract content)",
		};
	},
};
