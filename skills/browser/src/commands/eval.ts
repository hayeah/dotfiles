import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";

interface Args {
	code: string;
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
	describe: "Execute JavaScript in the active tab",
	builder: {
		code: {
			type: "string",
			describe: "JavaScript code to evaluate",
			demandOption: true,
		},
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.activePage();
			const result = await page.evaluate((c: string) => {
				const AsyncFunction = (async () => {}).constructor as new (...args: string[]) => Function;
				return new AsyncFunction(`return (${c})`)();
			}, argv.code);
			formatResult(result);
		} finally {
			await browser.disconnect();
		}
	},
};
