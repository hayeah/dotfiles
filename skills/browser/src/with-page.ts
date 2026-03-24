import type { Page } from "puppeteer-core";
import { Browser } from "./browser.js";
import { parseContextSpec, resolveContextSpec, type ResolvedSpec } from "./context-spec.js";
import { applySpecEmulation } from "./emulation.js";

export interface PageContext {
	page: Page;
	browser: Browser;
}

interface PageArgv {
	open?: string;
	session?: string;
	[k: string]: unknown;
}

/**
 * Run a command with a fresh, isolated page. Always creates a new tab.
 *
 * Why fresh? Several CDP features break on pre-existing pages:
 *
 * - **Screencast** (`Page.startScreencast`): The compositor only pipes frames
 *   to CDP sessions that created the page. If you `puppeteer.connect()` to a
 *   browser and call startScreencast on a page that was already open, you get
 *   0 frames. Creating the page via `newPage()` on the current connection
 *   fixes this.
 *
 * - **Device emulation for screenshots**: Applying emulation (viewport, device
 *   metrics, UA) to an existing page with its own layout state produces
 *   inconsistent results — the page may not re-layout fully, the info bar
 *   shifts the viewport, and fullPage screenshots ignore the emulated width.
 *   A fresh page with emulation applied before first navigation avoids this.
 *
 * - **Profiling** (CPU, memory): A fresh page gives a clean baseline without
 *   accumulated GC pressure, cached resources, or stale JS heap from prior
 *   navigation.
 *
 * How the URL/spec is resolved:
 *   --open <spec>  → parse context spec (URL, JSON, TOML). Apply device/viewport.
 *   -s <session>   → read URL from existing page, clone into fresh tab.
 *   (neither)      → read URL from active page, clone into fresh tab.
 */
export async function withFreshPage<T extends PageArgv>(
	argv: T,
	fn: (ctx: PageContext) => Promise<void>,
): Promise<void> {
	const browser = await new Browser().connect();
	try {
		// Resolve spec: either from --open or by cloning an existing page's URL
		let spec: ResolvedSpec;
		if (argv.open) {
			spec = resolveContextSpec(parseContextSpec(argv.open));
		} else {
			const existing = await browser.resolvePage(argv.session);
			spec = { url: existing.url(), dpr: 1, mobile: false, description: "cloned" };
		}

		// Create fresh tab
		const page = await browser.puppeteerBrowser.newPage();
		try {
			// Apply emulation before navigation if spec has dimensions
			if (spec.width && spec.height) {
				await applySpecEmulation(page, spec);
			}

			// Navigate
			if (spec.url) {
				await page.goto(spec.url, { waitUntil: "networkidle0" });
			}

			await fn({ page, browser });
		} finally {
			await page.close().catch(() => {});
		}
	} finally {
		await browser.disconnect();
	}
}

/**
 * Run a command on an existing page. No cloning, no fresh tab.
 *
 * When --open is given, creates a temporary page (like withOneShot today),
 * navigates, runs the handler, then tears down.
 *
 * When -s or default, resolves the existing page and uses it directly.
 */
export async function withPage<T extends PageArgv>(
	argv: T,
	fn: (ctx: PageContext) => Promise<void>,
): Promise<void> {
	const browser = await new Browser().connect();
	try {
		if (argv.open) {
			const spec = resolveContextSpec(parseContextSpec(argv.open));

			const page = await browser.puppeteerBrowser.newPage();
			try {
				if (spec.width && spec.height) {
					await applySpecEmulation(page, spec);
				}

				if (spec.url) {
					await page.goto(spec.url, { waitUntil: "networkidle0" });
				}

				await fn({ page, browser });
			} finally {
				await page.close().catch(() => {});
			}
		} else {
			const page = await browser.resolvePage(argv.session);
			await fn({ page, browser });
		}
	} finally {
		await browser.disconnect();
	}
}

/** Shared yargs options for --open and --session */
export { openOption } from "./oneshot.js";
export { sessionOption } from "./browser.js";
