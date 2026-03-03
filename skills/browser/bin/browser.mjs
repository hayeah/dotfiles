#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const baseDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);

try {
	execFileSync("npx", ["tsx", join(baseDir, "src/main.ts"), ...args], {
		stdio: "inherit",
		cwd: baseDir,
		env: { ...process.env, BROWSER_CALLER_CWD: process.cwd() },
	});
} catch (e) {
	process.exit(e.status ?? 1);
}
