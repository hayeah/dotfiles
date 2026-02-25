import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";

interface Args {
	profile?: boolean;
}

export const startCommand: CommandModule<{}, Args> = {
	command: "start",
	describe: "Launch Chrome with remote debugging on :9222",
	builder: {
		profile: {
			type: "boolean",
			describe: "Copy your default Chrome profile (cookies, logins)",
			default: false,
		},
	},
	handler: async (argv) => {
		await Browser.startChrome({ profile: argv.profile });
	},
};
