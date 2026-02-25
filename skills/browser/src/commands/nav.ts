import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";

interface Args {
	url: string;
	new?: boolean;
	reload?: boolean;
}

export const navCommand: CommandModule<{}, Args> = {
	command: "nav <url>",
	describe: "Navigate to a URL",
	builder: {
		url: {
			type: "string",
			describe: "URL to navigate to",
			demandOption: true,
		},
		new: {
			type: "boolean",
			describe: "Open in a new tab",
			default: false,
		},
		reload: {
			type: "boolean",
			describe: "Force reload after navigating",
			default: false,
		},
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			if (argv.new) {
				const page = await browser.activePage();
				const b = (page as any).browser();
				const p = await b.newPage();
				await p.goto(argv.url, { waitUntil: "domcontentloaded" });
				console.log("✓ Opened:", argv.url);
			} else {
				const page = await browser.activePage();
				await page.goto(argv.url, { waitUntil: "domcontentloaded" });
				if (argv.reload) {
					await page.reload({ waitUntil: "domcontentloaded" });
				}
				console.log("✓ Navigated to:", argv.url);
			}
		} finally {
			await browser.disconnect();
		}
	},
};
