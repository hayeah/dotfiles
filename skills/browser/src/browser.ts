import puppeteer, { type Browser as PuppeteerBrowser, type Page } from "puppeteer-core";
import { execSync, spawn } from "node:child_process";
import { homedir } from "node:os";

const CDP_URL = "http://localhost:9222";
const CONNECT_TIMEOUT = 5000;
const CACHE_DIR = `${homedir()}/.cache/browser-tools`;

export class Browser {
	private browser: PuppeteerBrowser | null = null;

	async connect(): Promise<this> {
		this.browser = await Promise.race([
			puppeteer.connect({ browserURL: CDP_URL, defaultViewport: null }),
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

	async activePage(): Promise<Page> {
		if (!this.browser) throw new Error("Not connected");
		const pages = await this.browser.pages();
		const page = pages.at(-1);
		if (!page) {
			console.error("✗ No active tab found");
			process.exit(1);
		}
		return page;
	}

	async disconnect(): Promise<void> {
		await this.browser?.disconnect();
		this.browser = null;
	}

	static async startChrome(opts: { profile?: boolean } = {}): Promise<void> {
		// Check if already running
		try {
			const b = await puppeteer.connect({ browserURL: CDP_URL, defaultViewport: null });
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
				const b = await puppeteer.connect({ browserURL: CDP_URL, defaultViewport: null });
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
