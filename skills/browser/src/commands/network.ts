import type { CommandModule } from "yargs";
import { Browser, sessionOption } from "../browser.js";

interface Args {
	session?: string;
	duration?: number;
	filter?: string;
	type?: string;
	reload?: boolean;
}

interface RequestEntry {
	method: string;
	url: string;
	resourceType: string;
	status?: number;
	mimeType?: string;
	contentLength?: number;
	timestamp: number;
}

function formatSize(bytes: number | undefined): string {
	if (bytes === undefined || bytes < 0) return "-";
	if (bytes < 1024) return `${bytes}B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export const networkCommand: CommandModule<{}, Args> = {
	command: "network",
	aliases: ["net"],
	describe: "Capture network requests on a session",
	builder: {
		...sessionOption,
		duration: {
			type: "number",
			alias: "d",
			describe: "Seconds to listen (default: 10)",
			default: 10,
		},
		filter: {
			type: "string",
			alias: "f",
			describe: "Only show URLs containing this substring",
		},
		type: {
			type: "string",
			alias: "t",
			describe: "Filter by resource type: xhr, doc, css, js, img, font, all (default: all)",
			default: "all",
		},
		reload: {
			type: "boolean",
			alias: "r",
			describe: "Reload the page after starting capture",
			default: false,
		},
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			const client = await page.createCDPSession();
			await client.send("Network.enable" as any);

			const requests = new Map<string, RequestEntry>();
			const duration = (argv.duration ?? 10) * 1000;

			const typeFilter = (argv.type ?? "all").toLowerCase();
			const allowedTypes = resolveTypeFilter(typeFilter);

			client.on("Network.requestWillBeSent", (params: any) => {
				requests.set(params.requestId, {
					method: params.request.method,
					url: params.request.url,
					resourceType: params.type,
					timestamp: params.timestamp,
				});
			});

			client.on("Network.responseReceived", (params: any) => {
				const entry = requests.get(params.requestId);
				if (entry) {
					entry.status = params.response.status;
					entry.mimeType = params.response.mimeType;
					entry.contentLength = params.response.headers?.["content-length"]
						? parseInt(params.response.headers["content-length"])
						: undefined;
				}
			});

			if (argv.reload) {
				console.error("Reloading…");
				page.reload({ waitUntil: "networkidle2" }).catch(() => {});
			}

			console.error(`Listening for ${argv.duration}s… (Ctrl+C to stop early)`);

			await new Promise<void>((resolve) => {
				const timer = setTimeout(resolve, duration);
				const onSigint = () => {
					clearTimeout(timer);
					resolve();
				};
				process.once("SIGINT", onSigint);
			});

			await client.send("Network.disable" as any);
			await client.detach();

			// Filter and sort
			let entries = [...requests.values()].sort((a, b) => a.timestamp - b.timestamp);

			if (argv.filter) {
				const matcher = fzfMatcher(argv.filter);
				entries = entries.filter((e) => matcher(e.url));
			}

			if (allowedTypes) {
				entries = entries.filter((e) => allowedTypes.has(e.resourceType));
			}

			if (entries.length === 0) {
				console.log("No matching requests captured.");
				return;
			}

			for (const e of entries) {
				const status = e.status ?? "---";
				const size = formatSize(e.contentLength);
				const mime = e.mimeType ?? "-";
				console.log(`${e.method.padEnd(6)} ${String(status).padEnd(4)} ${mime.padEnd(30)} ${size.padStart(8)}  ${e.url}`);
			}
			console.error(`\n${entries.length} request(s)`);
		} finally {
			await browser.disconnect();
		}
	},
};

function fzfMatcher(pattern: string): (s: string) => boolean {
	const tokens = pattern.split(/\s+/).filter(Boolean);
	const must: string[] = [];
	const mustNot: string[] = [];
	for (const t of tokens) {
		if (t.startsWith("!") || t.startsWith("\\!")) {
			const neg = t.replace(/^\\?!/, "");
			if (neg) mustNot.push(neg.toLowerCase());
		} else {
			must.push(t.toLowerCase());
		}
	}
	return (s: string) => {
		const lower = s.toLowerCase();
		return must.every((t) => lower.includes(t)) && mustNot.every((t) => !lower.includes(t));
	};
}

function resolveTypeFilter(type: string): Set<string> | null {
	switch (type) {
		case "all":
			return null;
		case "xhr":
			return new Set(["XHR", "Fetch"]);
		case "doc":
			return new Set(["Document"]);
		case "css":
			return new Set(["Stylesheet"]);
		case "js":
			return new Set(["Script"]);
		case "img":
			return new Set(["Image"]);
		case "font":
			return new Set(["Font"]);
		default:
			return new Set([type]);
	}
}
