import type { Page, Browser } from "puppeteer-core";
import { writeFileSync } from "node:fs";

export default async function setup({ page }: { page: Page; browser: Browser }) {
	return {
		async save(path: string) {
			const msgs = await page.evaluate(() => {
				const els = document.querySelectorAll("[data-message-id]");
				return Array.from(els).map((el) => ({
					id: el.getAttribute("data-message-id") ?? "",
					role: el.getAttribute("data-message-author-role") ?? "unknown",
					text: (el.querySelector(".markdown") ?? el).textContent?.trim() ?? "",
				}));
			});
			writeFileSync(path, JSON.stringify(msgs, null, 2));
			return { saved: path, count: msgs.length };
		},

		async screenshot(selector: string, path: string) {
			const el = await page.$(selector);
			if (!el) throw new Error(`Element not found: ${selector}`);
			await el.screenshot({ path });
			return { screenshot: path };
		},
	};
}
