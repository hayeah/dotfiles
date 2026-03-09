import puppeteer, { type Browser as PuppeteerBrowser, type Page } from "puppeteer-core";
import { execSync, spawn } from "node:child_process";
import { homedir } from "node:os";
import { resolve } from "node:path";

const DEFAULT_PORT = 9222;
const CONNECT_TIMEOUT = 5000;
const CACHE_DIR = `${homedir()}/.cache/browser-tools`;

function cdpURL(): string {
	const port = process.env.BROWSER_CDP_PORT || DEFAULT_PORT;
	return `http://localhost:${port}`;
}

function getTargetId(page: Page): string {
	return (page.target() as any)._targetId as string;
}

export interface PageInfo {
	index: number;
	targetId: string;
	url: string;
	title: string;
}

/** Resolve a path against the caller's original cwd (before bin/browser.mjs changed it). */
export function callerResolve(p: string): string {
	const base = process.env.BROWSER_CALLER_CWD || process.cwd();
	return resolve(base, p);
}

export const sessionOption = {
	session: {
		type: "string" as const,
		alias: "s" as const,
		describe: "Target session (index or target ID prefix)",
	},
} as const;

export class Browser {
	private browser: PuppeteerBrowser | null = null;

	async connect(): Promise<this> {
		this.browser = await Promise.race([
			puppeteer.connect({ browserURL: cdpURL(), defaultViewport: null, protocolTimeout: 0 }),
			new Promise<never>((_, reject) =>
				setTimeout(() => reject(new Error("timeout connecting to Chrome")), CONNECT_TIMEOUT),
			),
		]).catch((e: Error) => {
			console.error(`✗ Could not connect to browser: ${e.message}`);
			console.error("  Run: browser start");
			process.exit(1);
		});
		return this;
	}

	async listPages(): Promise<PageInfo[]> {
		if (!this.browser) throw new Error("Not connected");
		const pages = await this.browser.pages();
		const result: PageInfo[] = [];
		for (let i = 0; i < pages.length; i++) {
			const page = pages[i];
			result.push({
				index: i,
				targetId: getTargetId(page),
				url: page.url(),
				title: await page.title(),
			});
		}
		return result;
	}

	async allPages(): Promise<Page[]> {
		if (!this.browser) throw new Error("Not connected");
		return this.browser.pages();
	}

	async resolvePage(session?: string): Promise<Page> {
		if (!this.browser) throw new Error("Not connected");
		const pages = await this.browser.pages();

		if (!session) {
			const page = pages.at(-1);
			if (!page) {
				console.error("✗ No active tab found");
				process.exit(1);
			}
			return page;
		}

		if (/^\d+$/.test(session)) {
			const idx = parseInt(session);
			if (idx < 0 || idx >= pages.length) {
				console.error(`✗ Session index ${idx} out of range (0-${pages.length - 1})`);
				process.exit(1);
			}
			return pages[idx];
		}

		// Target ID prefix match (case-insensitive)
		const prefix = session.toLowerCase();
		for (const page of pages) {
			if (getTargetId(page).toLowerCase().startsWith(prefix)) {
				return page;
			}
		}

		console.error(`✗ No session matching "${session}"`);
		process.exit(1);
	}

	async rawNewPage(): Promise<Page> {
		if (!this.browser) throw new Error("Not connected");
		return this.browser.newPage();
	}

	async pageInfo(page: Page): Promise<PageInfo> {
		if (!this.browser) throw new Error("Not connected");
		const pages = await this.browser.pages();
		return {
			index: pages.indexOf(page),
			targetId: getTargetId(page),
			url: page.url(),
			title: await page.title(),
		};
	}

	async newPage(url: string): Promise<{ page: Page; info: PageInfo }> {
		if (!this.browser) throw new Error("Not connected");
		const page = await this.browser.newPage();
		await page.goto(url, { waitUntil: "domcontentloaded" });
		const info = await this.pageInfo(page);
		return { page, info };
	}

	async disconnect(): Promise<void> {
		await this.browser?.disconnect();
		this.browser = null;
	}

	static async startChrome(opts: { profile?: boolean } = {}): Promise<void> {
		// Check if already running
		try {
			const b = await puppeteer.connect({ browserURL: cdpURL(), defaultViewport: null });
			await b.disconnect();
			console.log("✓ Chrome already running on :9222");
			return;
		} catch {}

		execSync(`mkdir -p "${CACHE_DIR}"`, { stdio: "ignore" });

		// Remove singleton locks to allow new instance
		try {
			execSync(
				`rm -f "${CACHE_DIR}/SingletonLock" "${CACHE_DIR}/SingletonSocket" "${CACHE_DIR}/SingletonCookie"`,
				{ stdio: "ignore" },
			);
		} catch {}

		if (opts.profile) {
			console.log("Syncing profile...");
			execSync(
				`rsync -a --delete \
					--exclude='SingletonLock' \
					--exclude='SingletonSocket' \
					--exclude='SingletonCookie' \
					--exclude='*/Sessions/*' \
					--exclude='*/Current Session' \
					--exclude='*/Current Tabs' \
					--exclude='*/Last Session' \
					--exclude='*/Last Tabs' \
					"${homedir()}/Library/Application Support/Google/Chrome/" "${CACHE_DIR}/"`,
				{ stdio: "pipe" },
			);
		}

		spawn(
			"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
			[
				"--remote-debugging-port=9222",
				`--user-data-dir=${CACHE_DIR}`,
				"--no-first-run",
				"--no-default-browser-check",
			],
			{ detached: true, stdio: "ignore" },
		).unref();

		// Wait for Chrome to be ready
		for (let i = 0; i < 30; i++) {
			try {
				const b = await puppeteer.connect({ browserURL: cdpURL(), defaultViewport: null });
				await b.disconnect();
				console.log(`✓ Chrome started on :9222${opts.profile ? " with your profile" : ""}`);
				return;
			} catch {
				await new Promise((r) => setTimeout(r, 500));
			}
		}

		console.error("✗ Failed to connect to Chrome");
		process.exit(1);
	}
}
