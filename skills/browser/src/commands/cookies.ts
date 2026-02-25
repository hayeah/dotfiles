import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";

export const cookiesCommand: CommandModule = {
	command: "cookies",
	describe: "Display all cookies for the current tab",
	handler: async () => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.activePage();
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
	},
};
