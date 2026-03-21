import { build, type InlineConfig } from "vite";
import { resolve, join } from "node:path";
import { rmSync } from "node:fs";
import type { ResolvedPlugin } from "./types.js";

/** Build all browser modules for a plugin using Vite's JS API. */
export async function buildPlugin(plugin: ResolvedPlugin): Promise<void> {
	// Collect all unique browser module source paths from routes
	const browserEntries = new Set<string>();
	for (const route of plugin.manifest.routes) {
		if (route.browser) browserEntries.add(route.browser);
	}

	if (browserEntries.size === 0) {
		console.log(`${plugin.name}: no browser modules to build`);
		return;
	}

	const distDir = join(plugin.dir, "dist");

	// Clean dist
	try {
		rmSync(distDir, { recursive: true });
	} catch {}

	// Build each entry separately (IIFE doesn't support multiple entries)
	for (const entry of browserEntries) {
		const basename = entry.replace(/^.*\//, "").replace(/\.[^.]+$/, "");
		const entryPath = resolve(plugin.dir, entry);

		const config: InlineConfig = {
			root: plugin.dir,
			logLevel: "warn",
			build: {
				lib: {
					entry: entryPath,
					formats: ["iife"],
					name: "__browserPlugin",
					fileName: () => `${basename}.iife.js`,
				},
				outDir: distDir,
				minify: false,
				emptyOutDir: false,
			},
		};

		await build(config);
	}

	const entries = Array.from(browserEntries).map((e) =>
		e.replace(/^.*\//, "").replace(/\.[^.]+$/, ""),
	);
	console.log(`${plugin.name}: built ${entries.join(", ")}`);
}
