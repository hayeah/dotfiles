import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { matchesURL } from "./match.js";
import type { PluginManifest, ResolvedPlugin, MatchedRoute, PluginRoute } from "./types.js";

/** Directories to scan for plugins, in order. Later entries override earlier ones by name. */
function pluginDirs(): string[] {
	const dirs: string[] = [];

	// Built-in plugins (inside the browser skill)
	const builtIn = join(dirname(new URL(import.meta.url).pathname), "../../plugins");
	if (existsSync(builtIn)) dirs.push(builtIn);

	// User plugins
	const user = join(homedir(), ".config/browser-plugins");
	if (existsSync(user)) dirs.push(user);

	return dirs;
}

function loadPlugin(dir: string): ResolvedPlugin | null {
	const manifestPath = join(dir, "plugin.json");
	if (!existsSync(manifestPath)) return null;

	const manifest: PluginManifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
	if (!manifest.name || !manifest.routes) return null;

	let skillMd: string | undefined;
	const skillPath = join(dir, "SKILL.md");
	if (existsSync(skillPath)) {
		skillMd = readFileSync(skillPath, "utf-8");
	}

	return {
		name: manifest.name,
		description: manifest.description || "",
		dir,
		manifest,
		skillMd,
	};
}

export function scanPlugins(): ResolvedPlugin[] {
	const byName = new Map<string, ResolvedPlugin>();

	for (const parentDir of pluginDirs()) {
		let entries: string[];
		try {
			entries = readdirSync(parentDir, { withFileTypes: true })
				.filter((d) => d.isDirectory())
				.map((d) => d.name);
		} catch {
			continue;
		}

		for (const entry of entries) {
			const plugin = loadPlugin(join(parentDir, entry));
			if (plugin) {
				byName.set(plugin.name, plugin); // later dirs override
			}
		}
	}

	return Array.from(byName.values());
}

/** For each plugin, find the first matching route (waterfall). Returns one MatchedRoute per plugin that has a match. */
export function matchPlugins(plugins: ResolvedPlugin[], pageURL: string): MatchedRoute[] {
	let url: URL;
	try {
		url = new URL(pageURL);
	} catch {
		return [];
	}

	const results: MatchedRoute[] = [];
	for (const plugin of plugins) {
		for (const route of plugin.manifest.routes) {
			if (route.match.length === 0) continue;
			if (matchesURL(route.match, route.exclude, url)) {
				results.push({ plugin, route });
				break; // first match wins per plugin
			}
		}
	}

	return results;
}

/** Force-resolve a plugin by name, using its first route regardless of URL. */
export function forceMatchPlugin(plugin: ResolvedPlugin): MatchedRoute | null {
	if (plugin.manifest.routes.length === 0) return null;
	return { plugin, route: plugin.manifest.routes[0] };
}

/** Resolve a browser module source path to its built IIFE dist path. */
export function browserDistPath(pluginDir: string, sourcePath: string): string {
	// src/conversation.ts → dist/conversation.iife.js
	const basename = sourcePath.replace(/^.*\//, "").replace(/\.(m?[jt]s)$/, "");
	return join(pluginDir, "dist", `${basename}.iife.js`);
}
