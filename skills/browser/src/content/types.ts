import type { Page } from "puppeteer-core";

export interface ExtractedContent {
	title?: string;
	content: string;
}

export interface ContentExtractor {
	id: string;
	matches(url: URL): boolean;
	extract(page: Page, url: URL): Promise<ExtractedContent | null>;
}
