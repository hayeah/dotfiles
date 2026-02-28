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

yargs(hideBin(process.argv))
	.scriptName("browser")
	.command(startCommand)
	.command(navCommand)
	.command(evalCommand)
	.command(screenshotCommand)
	.command(pickCommand)
	.command(cookiesCommand)
	.command(contentCommand)
	.command(accessibilityCommand)
	.demandCommand(1, "Please specify a command")
	.strict()
	.help()
	.parse();
