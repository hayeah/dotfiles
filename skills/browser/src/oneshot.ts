import type { Page } from "puppeteer-core";
import { Browser, getTargetId } from "./browser.js";
import { parseContextSpec, resolveContextSpec } from "./context-spec.js";
import { applySpecEmulation } from "./emulation.js";

export const openOption = {
	open: {
		type: "string" as const,
		alias: "O" as const,
		describe: "One-shot mode: context spec (TOML file, JSON, or URL)",
	},
} as const;

interface OneShotArgv {
	open?: string;
	session?: string;
}

/**
 * Wrap a command handler with one-shot mode support.
 * When --open is given, creates a new window, applies the spec, runs the handler, then tears down.
 *
 * opts.beforeNavigate is called after emulation but before navigation — useful for
 * installing CDP listeners (e.g. network capture) that need to see the initial load.
 */
export function withOneShot<T extends OneShotArgv>(
	handler: (argv: T) => Promise<void>,
	opts?: { beforeNavigate?: (page: Page) => Promise<void> },
): (argv: T) => Promise<void> {
	return async (argv) => {
		if (!argv.open) {
			return handler(argv);
		}

		const spec = parseContextSpec(argv.open);
		const resolved = resolveContextSpec(spec);

		const browser = new Browser();
		await browser.connect();
		const { page } = await browser.newWindow();
		const targetId = getTargetId(page);

		try {
			if (resolved.width && resolved.height) {
				await applySpecEmulation(page, resolved);
			}

			if (opts?.beforeNavigate) {
				await opts.beforeNavigate(page);
			}

			if (resolved.url) {
				await page.goto(resolved.url, { waitUntil: "networkidle0" });
			}

			// Inject the targetId as session so resolvePage finds it
			argv.session = targetId;

			await handler(argv);
		} finally {
			try { await browser.closeTarget(targetId); } catch {}
			await browser.disconnect();
		}
	};
}
