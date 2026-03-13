import type { CommandModule } from "yargs";
import { Browser, sessionOption } from "../browser.js";
import { readSession, deleteSession } from "../session.js";

interface Args {
	session?: string;
	all?: boolean;
}

export const closeCommand: CommandModule<{}, Args> = {
	command: "close",
	describe: "Close a session (or all sessions with --all)",
	builder: {
		...sessionOption,
		all: {
			type: "boolean" as const,
			default: false,
			describe: "Close all sessions",
		},
	},
	handler: async (argv) => {
		// If closing a persistent session by key, kill the holding process
		if (argv.session) {
			const sess = readSession(argv.session);
			if (sess) {
				try { process.kill(sess.pid, "SIGTERM"); } catch {}
				// Give the open process time to clean up its window
				await new Promise((r) => setTimeout(r, 500));
				deleteSession(sess.key);
				console.log(`✓ Closed session ${sess.key}`);
				return;
			}
		}

		const browser = await new Browser().connect();
		try {
			if (argv.all) {
				const pages = await browser.allPages();
				for (const page of pages) {
					const url = page.url();
					await page.close();
					console.log("✓ Closed:", url);
				}
				console.log(`Closed ${pages.length} session(s)`);
			} else {
				const page = await browser.resolvePage(argv.session);
				const url = page.url();
				await page.close();
				console.log("✓ Closed:", url);
			}
		} finally {
			await browser.disconnect();
		}
	},
};
