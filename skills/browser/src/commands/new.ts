import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";
import { applyEmulation, emulationOptions } from "../emulation.js";

interface Args {
	url: string;
	device?: string;
	viewport?: string;
	mobile: boolean;
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
		...emulationOptions,
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			if (argv.device || argv.viewport) {
				const page = await browser.rawNewPage();
				// Resize window and apply emulation, then navigate
				const { description } = await applyEmulation(page, {
					device: argv.device,
					viewport: argv.viewport,
					mobile: argv.mobile,
				});
				await page.goto(argv.url, { waitUntil: "domcontentloaded" });
				const info = await browser.pageInfo(page);
				// Don't restore — leave the window at the emulated size for the user
				console.log(`✓ Opened session ${info.index} (${info.targetId.slice(0, 8)}): ${info.url} [${description}]`);
			} else {
				const { info } = await browser.newPage(argv.url);
				console.log(`✓ Opened session ${info.index} (${info.targetId.slice(0, 8)}): ${info.url}`);
			}
		} finally {
			await browser.disconnect();
		}
	},
};
