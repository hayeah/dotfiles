import type { CommandModule } from "yargs";
import { createWriteStream, type WriteStream } from "node:fs";
import { Browser, callerResolve, sessionOption } from "../browser.js";

interface Args {
	url: string;
	method?: string;
	header?: string[];
	body?: string;
	output?: string;
	timeout?: number;
	session?: string;
}

function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes}B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/** Bind a function into the browser page, replacing any stale binding from a previous run. */
async function expose(page: import("puppeteer-core").Page, name: string, fn: (...args: any[]) => any) {
	try {
		await page.removeExposedFunction(name);
	} catch {}
	await page.exposeFunction(name, fn);
}

export const fetchCommand: CommandModule<{}, Args> = {
	command: "fetch <url>",
	describe: "Fetch a URL using the session's context (cookies, auth)",
	builder: {
		url: {
			type: "string",
			describe: "URL to fetch",
			demandOption: true,
		},
		method: {
			type: "string",
			alias: "X",
			describe: "HTTP method (default: GET)",
			default: "GET",
		},
		header: {
			type: "string",
			alias: "H",
			describe: "Request header (repeatable): 'Content-Type: application/json'",
			array: true,
		},
		body: {
			type: "string",
			alias: "d",
			describe: "Request body",
		},
		output: {
			type: "string",
			alias: "o",
			describe: "Write response body to file instead of stdout",
		},
		timeout: {
			type: "number",
			alias: "t",
			describe: "Request timeout in seconds (default: no timeout)",
		},
		...sessionOption,
	},
	handler: async (argv) => {
		const headers: Record<string, string> = {};
		for (const h of argv.header ?? []) {
			const idx = h.indexOf(":");
			if (idx > 0) {
				headers[h.slice(0, idx).trim()] = h.slice(idx + 1).trim();
			}
		}

		const fetchOpts = {
			method: (argv.method ?? "GET").toUpperCase(),
			headers,
			body: argv.body ?? null,
			timeoutMs: argv.timeout ? argv.timeout * 1000 : 0,
		};

		const outPath = argv.output ? callerResolve(argv.output) : null;
		let writeStream: WriteStream | null = null;
		let totalBytes = 0;
		let totalSize: number | null = null;
		let lastProgressAt = 0;
		const PROGRESS_INTERVAL = 5000;

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			await expose(page, "__fetchMeta", (status: number, contentType: string, size: number | null) => {
				totalSize = size;
				process.stderr.write(`${status} ${contentType}\n`);
				if (outPath) {
					writeStream = createWriteStream(outPath);
				}
			});

			await expose(page, "__fetchChunk", (base64: string) => {
				const buf = Buffer.from(base64, "base64");
				totalBytes += buf.length;
				if (writeStream) {
					writeStream.write(buf);
				} else if (!outPath) {
					process.stdout.write(buf);
				}
				const now = Date.now();
				if (now - lastProgressAt >= PROGRESS_INTERVAL) {
					lastProgressAt = now;
					if (totalSize) {
						const pct = ((totalBytes / totalSize) * 100).toFixed(1);
						process.stderr.write(`  ${formatBytes(totalBytes)} / ${formatBytes(totalSize)} (${pct}%)\n`);
					} else {
						process.stderr.write(`  ${formatBytes(totalBytes)}\n`);
					}
				}
			});

			await page.evaluate(async (opts: typeof fetchOpts & { url: string }) => {
				const init: RequestInit = {
					method: opts.method,
					headers: opts.headers,
					body: opts.body,
				};
				if (opts.timeoutMs > 0) {
					init.signal = AbortSignal.timeout(opts.timeoutMs);
				}
				const res = await fetch(opts.url, init);
				const contentType = res.headers.get("content-type") ?? "";
				const cl = res.headers.get("content-length");
				const size = cl ? parseInt(cl) : null;

				await (window as any).__fetchMeta(res.status, contentType, size);

				const reader = res.body!.getReader();
				for (;;) {
					const { done, value } = await reader.read();
					if (done) break;
					const bytes = value as Uint8Array;
					let binary = "";
					for (let i = 0; i < bytes.length; i++) {
						binary += String.fromCharCode(bytes[i]);
					}
					await (window as any).__fetchChunk(btoa(binary));
				}
			}, { ...fetchOpts, url: argv.url });

			if (writeStream) {
				await new Promise<void>((resolve) => writeStream!.end(resolve));
				process.stderr.write(`  ${formatBytes(totalBytes)} written to ${outPath}\n`);
			} else if (outPath) {
				// output was specified but no data received
				process.stderr.write(`  0B written to ${outPath}\n`);
			} else {
				process.stderr.write(`  ${formatBytes(totalBytes)} total\n`);
			}
		} finally {
			await browser.disconnect();
		}
	},
};
