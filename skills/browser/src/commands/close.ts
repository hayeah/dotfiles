import type { CommandModule } from "yargs";
import { Browser, sessionOption } from "../browser.js";

interface Args {
	session?: string;
}

export const closeCommand: CommandModule<{}, Args> = {
	command: "close",
	describe: "Close a session",
	builder: {
		...sessionOption,
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			const url = page.url();
			await page.close();
			console.log("✓ Closed:", url);
		} finally {
			await browser.disconnect();
		}
	},
};
