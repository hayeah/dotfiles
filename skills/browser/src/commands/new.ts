import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";

interface Args {
	url: string;
}

export const newCommand: CommandModule<{}, Args> = {
	command: "new <url>",
	describe: "Open a new tab and navigate to URL",
	builder: {
		url: {
			type: "string",
			describe: "URL to open",
			demandOption: true,
		},
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const { info } = await browser.newPage(argv.url);
			console.log(`✓ Opened session ${info.index} (${info.targetId.slice(0, 8)}): ${info.url}`);
		} finally {
			await browser.disconnect();
		}
	},
};
