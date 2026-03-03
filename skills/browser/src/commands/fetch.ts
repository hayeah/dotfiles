import type { CommandModule } from "yargs";
import { writeFileSync } from "node:fs";
import { Browser, sessionOption } from "../browser.js";

interface Args {
	url: string;
	method?: string;
	header?: string[];
	body?: string;
	output?: string;
	session?: string;
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
		};

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			const result = await page.evaluate(async (opts: typeof fetchOpts & { url: string }) => {
				const res = await fetch(opts.url, {
					method: opts.method,
					headers: opts.headers,
					body: opts.body,
				});
				const contentType = res.headers.get("content-type") ?? "";
				const text = await res.text();
				return { status: res.status, contentType, text };
			}, { ...fetchOpts, url: argv.url });

			if (argv.output) {
				writeFileSync(argv.output, result.text);
				console.error(`${result.status} ${result.contentType}`);
				console.error(`Written to ${argv.output}`);
			} else {
				console.error(`${result.status} ${result.contentType}`);
				console.log(result.text);
			}
		} finally {
			await browser.disconnect();
		}
	},
};
