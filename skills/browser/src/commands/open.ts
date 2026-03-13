import type { CommandModule } from "yargs";
import { Browser, getTargetId } from "../browser.js";
import { parseContextSpec, resolveContextSpec } from "../context-spec.js";
import { applySpecEmulation } from "../emulation.js";
import { generateSessionKey, writeSession, deleteSession } from "../session.js";

interface Args {
	spec: string;
}

export const openCommand: CommandModule<{}, Args> = {
	command: "open <spec>",
	describe: "Open a persistent browser session (run in background, prints session key)",
	builder: {
		spec: {
			type: "string",
			describe: "Context spec: TOML file path, JSON literal, or URL",
			demandOption: true,
		},
	},
	handler: async (argv) => {
		const spec = parseContextSpec(argv.spec);
		const resolved = resolveContextSpec(spec);

		const browser = new Browser();
		await browser.connect();
		const { page, windowId } = await browser.newWindow();
		const targetId = getTargetId(page);

		if (resolved.width && resolved.height) {
			// applySpecEmulation returns a CDP session — we hold the reference
			// to keep emulation alive for the lifetime of this process
			await applySpecEmulation(page, resolved);
		}

		if (resolved.url) {
			await page.goto(resolved.url, { waitUntil: "domcontentloaded" });
		}

		const key = generateSessionKey();
		writeSession({
			key,
			pid: process.pid,
			targetId,
			windowId,
			spec,
			createdAt: new Date().toISOString(),
		});

		// Print session key as first line — agent captures this
		console.log(key);
		if (resolved.description !== "desktop") {
			console.error(`Session ${key}: ${resolved.description}`);
		}
		if (resolved.url) {
			console.error(`URL: ${resolved.url}`);
		}

		let cleaning = false;
		const cleanup = async () => {
			if (cleaning) return;
			cleaning = true;
			try { await browser.closeTarget(targetId); } catch {}
			deleteSession(key);
			try { await browser.disconnect(); } catch {}
			process.exit(0);
		};

		process.on("SIGINT", cleanup);
		process.on("SIGTERM", cleanup);
		process.on("SIGHUP", cleanup);

		// Block forever — process lifetime IS session lifetime
		await new Promise(() => {});
	},
};
