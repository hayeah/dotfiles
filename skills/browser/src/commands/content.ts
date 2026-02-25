import type { CommandModule } from "yargs";
import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import { Browser } from "../browser.js";

interface Args {
	url: string;
}

function htmlToMarkdown(html: string): string {
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

export const contentCommand: CommandModule<{}, Args> = {
	command: "content <url>",
	describe: "Extract readable page content as markdown",
	builder: {
		url: {
			type: "string",
			describe: "URL to extract content from",
			demandOption: true,
		},
	},
	handler: async (argv) => {
		const TIMEOUT = 30_000;
		const timeoutId = setTimeout(() => {
			console.error("✗ Timeout after 30s");
			process.exit(1);
		}, TIMEOUT).unref();

		const browser = await new Browser().connect();
		try {
			const page = await browser.activePage();

			await Promise.race([
				page.goto(argv.url, { waitUntil: "networkidle2" }),
				new Promise((r) => setTimeout(r, 10_000)),
			]).catch(() => {});

			// Get HTML via CDP (works even with TrustedScriptURL restrictions)
			const client = await page.createCDPSession();
			const { root } = await client.send("DOM.getDocument", { depth: -1, pierce: true });
			const { outerHTML } = await client.send("DOM.getOuterHTML", {
				nodeId: root.nodeId,
			});
			await client.detach();

			const finalURL = page.url();

			// Extract with Readability
			const doc = new JSDOM(outerHTML, { url: finalURL });
			const reader = new Readability(doc.window.document);
			const article = reader.parse();

			let content: string;
			if (article?.content) {
				content = htmlToMarkdown(article.content);
			} else {
				const fallbackDoc = new JSDOM(outerHTML, { url: finalURL });
				const fallbackBody = fallbackDoc.window.document;
				fallbackBody
					.querySelectorAll("script, style, noscript, nav, header, footer, aside")
					.forEach((el) => el.remove());
				const main =
					fallbackBody.querySelector(
						"main, article, [role='main'], .content, #content",
					) || fallbackBody.body;
				const fallbackHTML = main?.innerHTML || "";
				content =
					fallbackHTML.trim().length > 100
						? htmlToMarkdown(fallbackHTML)
						: "(Could not extract content)";
			}

			console.log(`URL: ${finalURL}`);
			if (article?.title) console.log(`Title: ${article.title}`);
			console.log("");
			console.log(content);

			clearTimeout(timeoutId);
		} finally {
			await browser.disconnect();
		}
	},
};
