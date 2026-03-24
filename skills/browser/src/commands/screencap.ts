import type { CommandModule } from "yargs";
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { Browser, sessionOption, callerResolve } from "../browser.js";
import { openOption, withOneShot } from "../oneshot.js";

interface Args {
	open?: string;
	session?: string;
	selector?: string;
	frames: number;
	interval: number;
	fps?: number;
	output: string;
	video: boolean;
	wait?: string;
	timeout?: number;
}

function findFfmpeg(): string {
	// Try common locations
	const candidates = [
		"ffmpeg",
		join(process.env.HOME ?? "", ".local/share/mise/installs/ffmpeg/8.1/bin/ffmpeg"),
	];
	for (const c of candidates) {
		try {
			execSync(`"${c}" -version`, { stdio: "pipe" });
			return c;
		} catch {}
	}
	throw new Error("ffmpeg not found. Install via: mise use ffmpeg");
}

export const screencapCommand: CommandModule<{}, Args> = {
	command: "screencap",
	describe: "Capture multiple frames from a page and optionally combine into video",
	builder: {
		...sessionOption,
		...openOption,
		frames: {
			type: "number",
			alias: "n",
			describe: "Number of frames to capture",
			default: 30,
		},
		interval: {
			type: "number",
			alias: "i",
			describe: "Milliseconds between captures (overridden by --fps)",
			default: 500,
		},
		fps: {
			type: "number",
			describe: "Capture at this frame rate (overrides --interval)",
		},
		output: {
			type: "string",
			alias: "o",
			describe: "Output directory for frames",
			default: "./frames",
		},
		video: {
			type: "boolean",
			describe: "Also generate an MP4 video from frames",
			default: false,
		},
		selector: {
			type: "string",
			alias: "S",
			describe: "CSS selector to capture a specific element instead of full viewport",
		},
		wait: {
			type: "string",
			alias: "w",
			describe: "JS expression to poll until truthy before starting capture",
		},
		timeout: {
			type: "number",
			describe: "Max wait time in ms for --wait",
			default: 10000,
		},
	},
	handler: withOneShot(async (argv) => {
		const interval = argv.fps ? Math.round(1000 / argv.fps) : argv.interval;
		const outDir = callerResolve(argv.output);
		mkdirSync(outDir, { recursive: true });

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			if (argv.wait) {
				await page.waitForFunction(argv.wait, { timeout: argv.timeout });
			}

			// If selector given, get its bounding box for clip-based capture
			let clip: { x: number; y: number; width: number; height: number } | undefined;
			if (argv.selector) {
				const el = await page.waitForSelector(argv.selector, { timeout: argv.timeout ?? 10000 });
				if (!el) throw new Error(`Element not found: ${argv.selector}`);
				const box = await el.boundingBox();
				if (!box) throw new Error(`Element has no bounding box: ${argv.selector}`);
				clip = { x: box.x, y: box.y, width: box.width, height: box.height };
			}

			for (let i = 0; i < argv.frames; i++) {
				const filename = `frame-${String(i).padStart(4, "0")}.png`;
				await page.screenshot({ path: join(outDir, filename), ...(clip ? { clip } : {}) });

				const elapsed = ((i + 1) * interval / 1000).toFixed(1);
				process.stderr.write(`\rCaptured ${i + 1}/${argv.frames} (t=${elapsed}s)`);

				if (i < argv.frames - 1) {
					await new Promise((r) => setTimeout(r, interval));
				}
			}
			process.stderr.write("\n");

			if (argv.video) {
				const ffmpeg = findFfmpeg();
				const fps = Math.max(1, Math.round(1000 / interval));
				const videoPath = join(outDir, "output.mp4");
				execSync(
					`"${ffmpeg}" -y -framerate ${fps} -i "${outDir}/frame-%04d.png" -c:v h264_videotoolbox -pix_fmt yuv420p "${videoPath}"`,
					{ stdio: "inherit" },
				);
				console.log(videoPath);
			} else {
				console.log(outDir);
			}
		} finally {
			await browser.disconnect();
		}
	}),
};
