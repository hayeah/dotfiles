import type { Page } from "puppeteer-core";
import { chatGPTContentExtractor } from "./extractors/chatgpt.js";
import { defaultContentExtractor } from "./extractors/default.js";
import type { ContentExtractor, ExtractedContent } from "./types.js";

const DEFAULT_EXTRACTOR_ID = defaultContentExtractor.id;

export const contentExtractors = new Map<string, ContentExtractor>([
	[chatGPTContentExtractor.id, chatGPTContentExtractor],
	[defaultContentExtractor.id, defaultContentExtractor],
]);

function extractionOrder(url: URL): ContentExtractor[] {
	const specialized = Array.from(contentExtractors.values()).filter(
		(extractor) => extractor.id !== DEFAULT_EXTRACTOR_ID && extractor.matches(url),
	);
	const fallback = contentExtractors.get(DEFAULT_EXTRACTOR_ID);
	return fallback ? [...specialized, fallback] : specialized;
}

export async function extractContent(page: Page, finalURL: string): Promise<ExtractedContent | null> {
	let url: URL;
	try {
		url = new URL(finalURL);
	} catch {
		return null;
	}

	for (const extractor of extractionOrder(url)) {
		const result = await extractor.extract(page, url);
		if (result) return result;
	}

	return null;
}
