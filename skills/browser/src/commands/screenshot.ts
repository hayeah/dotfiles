import type { CommandModule } from "yargs";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parse as parseYAML } from "yaml";
import { Browser, sessionOption, callerResolve } from "../browser.js";
import { applyEmulation, emulationOptions } from "../emulation.js";
import { openOption, withOneShot } from "../oneshot.js";

interface Step {
	eval?: string;
	wait?: string;
}

interface Args {
	open?: string;
	session?: string;
	device?: string;
	viewport?: string;
	mobile: boolean;
	output?: string;
	full?: boolean;
	eval?: string;
	wait?: string;
	timeout?: number;
	maxSize?: number;
	quality?: number;
	steps?: string;
}

/**
 * Insert an index before the file extension.
 * "foo.png" + 1 → "foo.1.png"
 */
function indexedPath(filepath: string, index: number): string {
	const dotIdx = filepath.lastIndexOf(".");
	if (dotIdx === -1) return `${filepath}.${index}`;
	return `${filepath.slice(0, dotIdx)}.${index}${filepath.slice(dotIdx)}`;
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
		...openOption,
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
		eval: {
			type: "string",
			alias: "e",
			describe: "JS to evaluate on the page before capturing (runs after --wait if both given)",
		},
		wait: {
			type: "string",
			alias: "w",
			describe: "JS expression to poll until truthy, or plain number for sleep in ms",
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
		steps: {
			type: "string",
			describe: "YAML list of steps, each with optional eval/wait. Captures a screenshot per step.",
		},
	},
	handler: withOneShot(async (argv) => {
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

			// Build step list: either from --steps YAML or from inline --eval/--wait
			let steps: Step[];
			if (argv.steps) {
				steps = parseYAML(argv.steps);
				if (!Array.isArray(steps)) {
					throw new Error("--steps must be a YAML list");
				}
			} else {
				steps = [{ eval: argv.eval, wait: argv.wait }];
			}

			const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
			const basePath = argv.output ? callerResolve(argv.output) : join(tmpdir(), `screenshot-${timestamp}.png`);
			const multiStep = steps.length > 1;

			for (let i = 0; i < steps.length; i++) {
				const step = steps[i];

				if (step.wait) {
					const waitMs = Number(step.wait);
					if (!isNaN(waitMs) && String(waitMs) === step.wait) {
						await new Promise((r) => setTimeout(r, waitMs));
					} else {
						await page.waitForFunction(step.wait, { timeout: argv.timeout });
					}
				}

				if (step.eval) {
					await page.evaluate(step.eval);
					await new Promise((r) => setTimeout(r, 2000));
				}

				let filepath = multiStep ? indexedPath(basePath, i + 1) : basePath;

				if (argv.full && emulation) {
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
			}

			// Restore original window size after screenshot
			await emulation?.restore();
		} finally {
			await browser.disconnect();
		}
	}),
};
