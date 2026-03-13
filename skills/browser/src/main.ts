import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { startCommand } from "./commands/start.js";
import { navCommand } from "./commands/nav.js";
import { evalCommand } from "./commands/eval.js";
import { screenshotCommand } from "./commands/screenshot.js";
import { pickCommand } from "./commands/pick.js";
import { cookiesCommand } from "./commands/cookies.js";
import { contentCommand } from "./commands/content.js";
import { accessibilityCommand } from "./commands/accessibility.js";
import { listCommand } from "./commands/list.js";
import { newCommand } from "./commands/new.js";
import { reloadCommand } from "./commands/reload.js";
import { closeCommand } from "./commands/close.js";
import { networkCommand } from "./commands/network.js";
import { fetchCommand } from "./commands/fetch.js";
import { openCommand } from "./commands/open.js";

yargs(hideBin(process.argv))
	.scriptName("browser")
	.command(startCommand)
	.command(openCommand)
	.command(listCommand)
	.command(newCommand)
	.command(navCommand)
	.command(reloadCommand)
	.command(closeCommand)
	.command(evalCommand)
	.command(screenshotCommand)
	.command(pickCommand)
	.command(cookiesCommand)
	.command(contentCommand)
	.command(accessibilityCommand)
	.command(networkCommand)
	.command(fetchCommand)
	.demandCommand(1, "Please specify a command")
	.strict()
	.help()
	.parse();
