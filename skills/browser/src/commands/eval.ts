import type { CommandModule } from "yargs";
import { readFileSync } from "node:fs";
import { Browser, sessionOption } from "../browser.js";
import { openOption, withOneShot } from "../oneshot.js";

interface Args {
	code: string;
	open?: string;
	session?: string;
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

export const evalCommand: CommandModule<{}, Args> = {
	command: "eval <code>",
	describe: "Execute JavaScript in a session (inline code or .js/.mjs/.ts file path)",
	builder: {
		code: {
			type: "string",
			describe: "JavaScript code or path to a .js/.mjs/.ts file",
			demandOption: true,
		},
		...sessionOption,
		...openOption,
	},
	handler: withOneShot(async (argv) => {
		const code = /\.(m?js|ts)$/.test(argv.code)
			? readFileSync(argv.code, "utf-8")
			: argv.code;

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			const result = await page.evaluate((c: string) => {
				const AsyncFunction = (async () => {}).constructor as new (...args: string[]) => Function;
				return new AsyncFunction(`return (${c})`)();
			}, code);
			formatResult(result);
		} finally {
			await browser.disconnect();
		}
	}),
};
