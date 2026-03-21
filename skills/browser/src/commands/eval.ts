import type { CommandModule } from "yargs";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import type { Page, Browser as PuppeteerBrowser } from "puppeteer-core";
import { Browser, sessionOption } from "../browser.js";
import { openOption, withOneShot } from "../oneshot.js";
import {
	scanPlugins,
	matchPlugins,
	forceMatchPlugin,
	browserDistPath,
} from "../plugins/loader.js";
import type { MatchedRoute } from "../plugins/types.js";

interface Args {
	code: string;
	open?: string;
	session?: string;
	node?: boolean;
	plugin?: string[];
	plugins?: boolean;
	expect?: string;
	timeout?: number;
	interval?: number;
}

function formatResult(result: unknown): void {
	if (Array.isArray(result)) {
		for (let i = 0; i < result.length; i++) {
			if (i > 0) console.log("");
			for (const [key, value] of Object.entries(result[i])) {
				console.log(`${key}: ${value}`);
			}
		}
	} else if (typeof result === "object" && result !== null) {
		for (const [key, value] of Object.entries(result)) {
			console.log(`${key}: ${value}`);
		}
	} else {
		console.log(result);
	}
}

// --- Browser eval: inject plugins as AsyncFunction parameters ---

async function evalBrowser(
	page: Page,
	code: string,
	matchedRoutes: MatchedRoute[],
): Promise<unknown> {
	const names: string[] = [];
	const iifeSources: string[] = [];

	for (const { plugin, route } of matchedRoutes) {
		if (!route.browser) continue;
		const distPath = browserDistPath(plugin.dir, route.browser);
		try {
			const source = readFileSync(distPath, "utf-8");
			names.push(plugin.name);
			iifeSources.push(source);
		} catch (e: any) {
			console.error(`Warning: could not load browser module for plugin "${plugin.name}": ${e.message}`);
		}
	}

	if (names.length === 0) {
		// No plugins — use original simple eval
		return page.evaluate((c: string) => {
			const AsyncFunction = (async () => {}).constructor as new (
				...args: string[]
			) => Function;
			return new AsyncFunction(`return (${c})`)();
		}, code);
	}

	return page.evaluate(
		(code: string, names: string[], sources: string[]) => {
			const pluginObjects = sources.map((src) => {
				const setup = new Function(`${src}; return __browserPlugin;`)();
				return typeof setup === "function" ? setup() : setup;
			});

			const AsyncFunction = (async () => {}).constructor as new (
				...args: string[]
			) => Function;
			const fn = new AsyncFunction(...names, `return (${code})`);
			return fn(...pluginObjects);
		},
		code,
		names,
		iifeSources,
	);
}

// --- Node eval: inject page, browser, and node plugin objects ---

async function evalNodeContext(
	page: Page,
	puppeteerBrowser: PuppeteerBrowser,
	code: string,
	matchedRoutes: MatchedRoute[],
): Promise<unknown> {
	const names = ["page", "browser"];
	const objects: unknown[] = [page, puppeteerBrowser];

	for (const { plugin, route } of matchedRoutes) {
		if (!route.node) continue;
		const modulePath = join(plugin.dir, route.node);
		try {
			const mod = await import(pathToFileURL(modulePath).href);
			const api = await mod.default({ page, browser: puppeteerBrowser });
			names.push(plugin.name);
			objects.push(api);
		} catch (e: any) {
			console.error(`Warning: could not load node module for plugin "${plugin.name}": ${e.message}`);
		}
	}

	const AsyncFunction = (async () => {}).constructor as new (...args: string[]) => Function;
	const fn = new AsyncFunction(...names, code);
	return fn(...objects);
}

// --- Expect polling loop ---

async function expectLoop(
	evalFn: () => Promise<unknown>,
	condition: string,
	timeout: number,
	interval: number,
): Promise<unknown> {
	const checkCondition = new Function("result", `return (${condition})`) as (
		result: unknown,
	) => unknown;
	const deadline = Date.now() + timeout * 1000;
	let lastResult: unknown;

	while (true) {
		lastResult = await evalFn();
		if (checkCondition(lastResult)) return lastResult;

		if (Date.now() >= deadline) {
			console.error(`Timeout: condition not met after ${timeout}s`);
			console.error("Last result:", JSON.stringify(lastResult, null, 2));
			process.exit(1);
		}

		await new Promise((r) => setTimeout(r, interval));
	}
}

// --- Resolve which plugins to load ---

function resolveMatchedRoutes(
	pageURL: string,
	explicitNames: string[] | undefined,
	noPlugins: boolean,
): MatchedRoute[] {
	if (noPlugins) return [];

	const allPlugins = scanPlugins();

	if (explicitNames && explicitNames.length > 0) {
		// Explicit --plugin flags: force-load named plugins
		const routes: MatchedRoute[] = [];
		for (const name of explicitNames) {
			const plugin = allPlugins.find((p) => p.name === name);
			if (!plugin) {
				console.error(`Warning: plugin "${name}" not found`);
				continue;
			}
			// Try URL match first, fall back to first route
			const urlMatches = matchPlugins([plugin], pageURL);
			if (urlMatches.length > 0) {
				routes.push(urlMatches[0]);
			} else {
				const forced = forceMatchPlugin(plugin);
				if (forced) routes.push(forced);
			}
		}
		return routes;
	}

	// Autoload: match all plugins against the URL
	return matchPlugins(allPlugins, pageURL);
}

// --- Command ---

export const evalCommand: CommandModule<{}, Args> = {
	command: "eval <code>",
	describe: "Execute JavaScript in a session (inline code or .js/.mjs/.ts file path)",
	builder: {
		code: {
			type: "string",
			describe: "JavaScript code or path to a .js/.mjs/.ts file",
			demandOption: true,
		},
		node: {
			type: "boolean",
			alias: "N",
			describe: "Evaluate in Node.js context (with page/browser access)",
			default: false,
		},
		plugin: {
			type: "string",
			array: true,
			alias: "p",
			describe: "Load specific plugin(s) by name",
		},
		plugins: {
			type: "boolean",
			describe: "Enable/disable plugin autoloading (use --no-plugins to skip)",
			default: true,
		},
		expect: {
			type: "string",
			alias: "E",
			describe: "Block until condition is truthy (JS expression; 'result' is the eval return value)",
		},
		timeout: {
			type: "number",
			describe: "Timeout for --expect in seconds",
			default: 30,
		},
		interval: {
			type: "number",
			describe: "Poll interval for --expect in ms",
			default: 500,
		},
		...sessionOption,
		...openOption,
	},
	handler: withOneShot(async (argv) => {
		const code = /\.(m?js|ts)$/.test(argv.code)
			? readFileSync(argv.code, "utf-8")
			: argv.code;

		const browserInstance = await new Browser().connect();
		try {
			const page = await browserInstance.resolvePage(argv.session);
			const pageURL = page.url();
			const matched = resolveMatchedRoutes(pageURL, argv.plugin, argv.plugins === false);

			const doEval = async () => {
				if (argv.node) {
					return evalNodeContext(page, browserInstance.puppeteerBrowser, code, matched);
				}
				return evalBrowser(page, code, matched);
			};

			let result: unknown;
			if (argv.expect) {
				result = await expectLoop(doEval, argv.expect, argv.timeout!, argv.interval!);
			} else {
				result = await doEval();
			}

			formatResult(result);
		} finally {
			await browserInstance.disconnect();
		}
	}),
};
