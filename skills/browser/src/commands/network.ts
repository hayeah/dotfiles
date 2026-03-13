import type { CommandModule } from "yargs";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Browser, callerResolve, sessionOption } from "../browser.js";
import { openOption, withOneShot } from "../oneshot.js";

interface Args {
	open?: string;
	session?: string;
	duration?: number;
	filter?: string;
	type?: string;
	reload?: boolean;
	dump?: string;
}

// Shared state for one-shot pre-navigation CDP setup
let oneshotCDPClient: any = null;
let oneshotRequests: Map<string, RequestEntry> | null = null;

interface RequestEntry {
	requestId: string;
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

const MIME_EXTENSIONS: Record<string, string> = {
	"application/json": ".json",
	"text/html": ".html",
	"text/css": ".css",
	"text/plain": ".txt",
	"text/xml": ".xml",
	"text/javascript": ".js",
	"application/javascript": ".js",
	"application/x-javascript": ".js",
	"application/xml": ".xml",
	"application/pdf": ".pdf",
	"application/octet-stream": ".bin",
	"image/png": ".png",
	"image/jpeg": ".jpg",
	"image/gif": ".gif",
	"image/svg+xml": ".svg",
	"image/webp": ".webp",
	"image/x-icon": ".ico",
	"font/woff2": ".woff2",
	"font/woff": ".woff",
	"font/ttf": ".ttf",
};

function extForMime(mime: string | undefined): string {
	if (!mime) return ".bin";
	const base = mime.split(";")[0].trim();
	return MIME_EXTENSIONS[base] ?? `.${base.split("/")[1] ?? "bin"}`;
}

function slugifyURL(url: string): string {
	try {
		const u = new URL(url);
		let path = u.pathname.replace(/^\//, "").replace(/\//g, "-") || "index";
		// Strip file extension (will be re-added from mime type)
		path = path.replace(/\.[^.]+$/, "");
		// Trim to reasonable length
		return path.slice(0, 60).replace(/[^a-zA-Z0-9._-]/g, "_");
	} catch {
		return "unknown";
	}
}

export const networkCommand: CommandModule<{}, Args> = {
	command: "network",
	aliases: ["net"],
	describe: "Capture network requests on a session",
	builder: {
		...sessionOption,
		...openOption,
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
		dump: {
			type: "string",
			alias: "o",
			describe: "Directory to dump response bodies into",
		},
	},
	handler: withOneShot(async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			// In one-shot mode, CDP listeners were installed via beforeNavigate
			const client = oneshotCDPClient ?? await page.createCDPSession();
			const requests = oneshotRequests ?? new Map<string, RequestEntry>();

			if (!oneshotCDPClient) {
				// Normal mode — set up fresh
				await client.send("Network.enable" as any);

				client.on("Network.requestWillBeSent", (params: any) => {
					requests.set(params.requestId, {
						requestId: params.requestId,
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
			}

			// Clean up shared state
			oneshotCDPClient = null;
			oneshotRequests = null;

			const duration = (argv.duration ?? 10) * 1000;
			const typeFilter = (argv.type ?? "all").toLowerCase();
			const allowedTypes = resolveTypeFilter(typeFilter);

			console.error(`Listening for ${argv.duration}s… (Ctrl+C to stop early)`);

			await new Promise<void>((resolve) => {
				const timer = setTimeout(resolve, duration);
				const onSigint = () => {
					clearTimeout(timer);
					resolve();
				};
				process.once("SIGINT", onSigint);
			});

			// Filter and sort
			let entries = [...requests.values()].sort((a, b) => a.timestamp - b.timestamp);

			if (argv.filter) {
				const matcher = fzfMatcher(argv.filter);
				entries = entries.filter((e) => matcher(e.url));
			}

			if (allowedTypes) {
				entries = entries.filter((e) => allowedTypes.has(e.resourceType));
			}

			// Dump response bodies before disabling Network domain
			if (argv.dump && entries.length > 0) {
				const dumpDir = callerResolve(argv.dump);
				mkdirSync(dumpDir, { recursive: true });
				for (let i = 0; i < entries.length; i++) {
					const e = entries[i];
					const idx = String(i + 1).padStart(4, "0");
					const slug = slugifyURL(e.url);
					const ext = extForMime(e.mimeType);
					const filename = `${idx}-${e.method}-${slug}${ext}`;
					try {
						const { body, base64Encoded } = (await client.send(
							"Network.getResponseBody" as any,
							{ requestId: e.requestId },
						)) as { body: string; base64Encoded: boolean };
						const data = base64Encoded ? Buffer.from(body, "base64") : body;
						writeFileSync(join(dumpDir, filename), data);
					} catch {
						// Body unavailable (redirects, preflight, etc.)
					}
				}
				console.error(`Dumped to ${dumpDir}/`);
			}

			await client.send("Network.disable" as any);
			await client.detach();

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
	}, {
		beforeNavigate: async (page) => {
			const client = await page.createCDPSession();
			await client.send("Network.enable" as any);

			const requests = new Map<string, RequestEntry>();

			client.on("Network.requestWillBeSent", (params: any) => {
				requests.set(params.requestId, {
					requestId: params.requestId,
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

			oneshotCDPClient = client;
			oneshotRequests = requests;
		},
	}),
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
