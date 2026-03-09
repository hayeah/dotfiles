import type { Page } from "puppeteer-core";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";

export function htmlToMarkdown(html: string): string {
	const turndown = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });
	turndown.use(gfm);
	turndown.addRule("removeEmptyLinks", {
		filter: (node) => node.nodeName === "A" && !node.textContent?.trim(),
		replacement: () => "",
	});
	return turndown
		.turndown(html)
		.replace(/\[\\?\[\s*\\?\]\]\([^)]*\)/g, "")
		.replace(/ +/g, " ")
		.replace(/\s+,/g, ",")
		.replace(/\s+\./g, ".")
		.replace(/\n{3,}/g, "\n\n")
		.trim();
}

export async function pageOuterHTML(page: Page): Promise<string> {
	const client = await page.createCDPSession();
	try {
		const { root } = await client.send("DOM.getDocument", { depth: -1, pierce: true });
		const { outerHTML } = await client.send("DOM.getOuterHTML", {
			nodeId: root.nodeId,
		});
		return outerHTML;
	} finally {
		await client.detach();
	}
}
