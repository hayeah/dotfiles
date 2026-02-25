import type { CommandModule } from "yargs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Browser } from "../browser.js";

export const screenshotCommand: CommandModule = {
	command: "screenshot",
	describe: "Capture current viewport to a temporary file",
	handler: async () => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.activePage();
			const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
			const filepath = join(tmpdir(), `screenshot-${timestamp}.png`);
			await page.screenshot({ path: filepath });
			console.log(filepath);
		} finally {
			await browser.disconnect();
		}
	},
};
