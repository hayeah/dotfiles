import { defineConfig } from "vite";
import { resolve } from "node:path";

// Vite IIFE format doesn't support multiple entries in one build.
// Use BROWSER_PLUGIN_ENTRY env var to select which entry to build.
// The build script runs vite build once per entry.

const entry = process.env.BROWSER_PLUGIN_ENTRY ?? "src/conversation.ts";
const name = entry.replace(/^.*\//, "").replace(/\.[^.]+$/, "");

export default defineConfig({
	build: {
		lib: {
			entry: resolve(__dirname, entry),
			formats: ["iife"],
			name: "__browserPlugin",
			fileName: () => `${name}.iife.js`,
		},
		outDir: "dist",
		minify: false,
		emptyOutDir: false,
	},
});
