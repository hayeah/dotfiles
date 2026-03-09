import type { CommandModule } from "yargs";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Browser, sessionOption, callerResolve } from "../browser.js";
import { applyEmulation, emulationOptions } from "../emulation.js";

interface Args {
	session?: string;
	device?: string;
	viewport?: string;
	mobile: boolean;
	output?: string;
	full?: boolean;
	wait?: string;
	timeout?: number;
	maxSize?: number;
	quality?: number;
}

/**
 * Constrain image so its longest side is at most maxPx, convert to JPEG.
 * Returns the final file path (.jpg).
 */
function constrainImage(filepath: string, maxPx: number, quality: number): string {
	const info = execSync(`sips -g pixelWidth -g pixelHeight "${filepath}"`, { encoding: "utf-8" });
	const w = parseInt(info.match(/pixelWidth:\s*(\d+)/)?.[1] ?? "0");
	const h = parseInt(info.match(/pixelHeight:\s*(\d+)/)?.[1] ?? "0");
	const longSide = Math.max(w, h);

	const outPath = filepath.replace(/\.png$/, ".jpg");

	if (longSide > maxPx) {
		if (w >= h) {
			execSync(`sips --resampleWidth ${maxPx} -s format jpeg -s formatOptions ${quality} "${filepath}" --out "${outPath}"`, { stdio: "pipe" });
		} else {
			execSync(`sips --resampleHeight ${maxPx} -s format jpeg -s formatOptions ${quality} "${filepath}" --out "${outPath}"`, { stdio: "pipe" });
		}
	} else {
		execSync(`sips -s format jpeg -s formatOptions ${quality} "${filepath}" --out "${outPath}"`, { stdio: "pipe" });
	}

	return outPath;
}

export const screenshotCommand: CommandModule<{}, Args> = {
	command: "screenshot",
	describe: "Capture current viewport to a temporary file",
	builder: {
		...sessionOption,
		...emulationOptions,
		output: {
			type: "string",
			alias: "o",
			describe: "Output file path (default: temp file)",
		},
		full: {
			type: "boolean",
			describe: "Capture full scrollable page",
			default: false,
		},
		wait: {
			type: "string",
			alias: "w",
			describe: "JS expression to poll until truthy before capturing",
		},
		timeout: {
			type: "number",
			describe: "Max wait time in ms for --wait",
			default: 10000,
		},
		maxSize: {
			type: "number",
			alias: "m",
			describe: "Constrain longest side to this many pixels and output as JPEG",
		},
		quality: {
			type: "number",
			describe: "JPEG quality 1-100 (with --max-size)",
			default: 85,
		},
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			const emulation = (argv.device || argv.viewport)
				? await applyEmulation(page, {
						device: argv.device,
						viewport: argv.viewport,
						mobile: argv.mobile,
					})
				: null;

			if (emulation) {
				// Reload so the page re-renders at new window size
				await page.reload({ waitUntil: "networkidle0" });
			}

			if (argv.wait) {
				await page.waitForFunction(argv.wait, { timeout: argv.timeout });
			}

			const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
			let filepath = argv.output ? callerResolve(argv.output) : join(tmpdir(), `screenshot-${timestamp}.png`);

			if (argv.full && emulation) {
				// fullPage: true ignores emulation width on headed Chrome.
				// Use clip instead to capture the full page at the emulated width.
				const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
				await page.screenshot({
					path: filepath,
					clip: { x: 0, y: 0, width: emulation.width, height: scrollHeight },
				});
			} else {
				await page.screenshot({ path: filepath, fullPage: argv.full });
			}

			if (argv.maxSize) {
				filepath = constrainImage(filepath, argv.maxSize, argv.quality ?? 85);
			}

			console.log(filepath);

			// Restore original window size after screenshot
			await emulation?.restore();
		} finally {
			await browser.disconnect();
		}
	},
};
