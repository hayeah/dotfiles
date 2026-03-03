import type { CommandModule } from "yargs";
import { Browser, sessionOption } from "../browser.js";

interface Args {
	session?: string;
}

export const reloadCommand: CommandModule<{}, Args> = {
	command: "reload",
	describe: "Reload a session",
	builder: {
		...sessionOption,
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			await page.reload({ waitUntil: "domcontentloaded" });
			console.log("✓ Reloaded:", page.url());
		} finally {
			await browser.disconnect();
		}
	},
};
