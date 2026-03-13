import type { CommandModule } from "yargs";
import { Browser, sessionOption } from "../browser.js";
import { openOption, withOneShot } from "../oneshot.js";

interface Args {
	open?: string;
	session?: string;
}

export const cookiesCommand: CommandModule<{}, Args> = {
	command: "cookies",
	describe: "Display all cookies for a session",
	builder: {
		...sessionOption,
		...openOption,
	},
	handler: withOneShot(async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);
			const cookies = await page.cookies();
			for (const cookie of cookies) {
				console.log(`${cookie.name}: ${cookie.value}`);
				console.log(`  domain: ${cookie.domain}`);
				console.log(`  path: ${cookie.path}`);
				console.log(`  httpOnly: ${cookie.httpOnly}`);
				console.log(`  secure: ${cookie.secure}`);
				console.log("");
			}
		} finally {
			await browser.disconnect();
		}
	}),
};
