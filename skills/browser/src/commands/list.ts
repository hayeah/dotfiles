import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";
import { listSessions } from "../session.js";

export const listCommand: CommandModule = {
	command: "list",
	aliases: ["ls"],
	describe: "List all open browser sessions",
	handler: async () => {
		const browser = await new Browser().connect();
		try {
			const pages = await browser.listPages();
			const sessions = listSessions();
			const sessionByTarget = new Map(sessions.map((s) => [s.targetId, s]));

			if (pages.length === 0 && sessions.length === 0) {
				console.log("No open tabs");
				return;
			}
			const lastIdx = pages.length - 1;
			for (const p of pages) {
				const marker = p.index === lastIdx ? "*" : " ";
				const id = p.targetId.slice(0, 8);
				const sess = sessionByTarget.get(p.targetId);
				const keyLabel = sess ? `[${sess.key}] ` : "";
				const title = p.title ? ` ${p.title}` : "";
				console.log(`${marker}${p.index}  ${keyLabel}${id}  ${p.url}${title}`);
			}
		} finally {
			await browser.disconnect();
		}
	},
};
