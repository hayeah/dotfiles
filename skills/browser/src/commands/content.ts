import type { CommandModule } from "yargs";
import { Browser, sessionOption } from "../browser.js";
import { extractContent } from "../content/index.js";

interface Args {
	url: string;
	session?: string;
}

export const contentCommand: CommandModule<{}, Args> = {
	command: "content <url>",
	describe: "Extract readable page content as markdown",
	builder: {
		url: {
			type: "string",
			describe: "URL to extract content from",
			demandOption: true,
		},
		...sessionOption,
	},
	handler: async (argv) => {
		const TIMEOUT = 30_000;
		const timeoutId = setTimeout(() => {
			console.error("✗ Timeout after 30s");
			process.exit(1);
		}, TIMEOUT).unref();

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			await Promise.race([
				page.goto(argv.url, { waitUntil: "networkidle2" }),
				new Promise((r) => setTimeout(r, 10_000)),
			]).catch(() => {});

			const finalURL = page.url();
			const extracted = await extractContent(page, finalURL);
			const title = extracted?.title;
			const content = extracted?.content ?? "(Could not extract content)";

			console.log(`URL: ${finalURL}`);
			if (title) console.log(`Title: ${title}`);
			console.log("");
			console.log(content);

			clearTimeout(timeoutId);
		} finally {
			await browser.disconnect();
		}
	},
};
