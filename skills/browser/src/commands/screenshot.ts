import type { CommandModule } from "yargs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Browser, sessionOption } from "../browser.js";

interface Args {
	session?: string;
}

export const screenshotCommand: CommandModule<{}, Args> = {
	command: "screenshot",
	describe: "Capture current viewport to a temporary file",
	builder: {
		...sessionOption,
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
			const filepath = join(tmpdir(), `screenshot-${timestamp}.png`);
			await page.screenshot({ path: filepath });
			console.log(filepath);
		} finally {
			await browser.disconnect();
		}
	},
};
