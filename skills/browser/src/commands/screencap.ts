import type { CommandModule } from "yargs";
import { execSync, spawn, type ChildProcess } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { Browser, sessionOption, callerResolve } from "../browser.js";
import { openOption, withOneShot } from "../oneshot.js";

interface Args {
	open?: string;
	session?: string;
	selector?: string;
	duration: number;
	fps: number;
	output: string;
	quality: number;
	wait?: string;
	timeout?: number;
}

function findFfmpeg(): string {
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

function spawnFfmpeg(ffmpegBin: string, fps: number, outPath: string, crop?: { x: number; y: number; w: number; h: number }): ChildProcess {
	const args = [
		"-loglevel", "error",
		"-f", "image2pipe",
		"-vcodec", "mjpeg",
		"-framerate", String(fps),
		"-i", "pipe:0",
		"-an",
	];

	if (crop) {
		const cw = crop.w % 2 === 0 ? crop.w : crop.w - 1;
		const ch = crop.h % 2 === 0 ? crop.h : crop.h - 1;
		args.push("-vf", `crop=${cw}:${ch}:${crop.x}:${crop.y}`);
	}

	// Try hardware encoder, fall back to software
	try {
		execSync(`"${ffmpegBin}" -hide_banner -encoders 2>&1 | grep h264_videotoolbox`, { stdio: "pipe" });
		args.push("-c:v", "h264_videotoolbox");
	} catch {
		args.push("-c:v", "libx264", "-preset", "ultrafast", "-crf", "23");
	}

	args.push("-pix_fmt", "yuv420p", "-y", outPath);

	return spawn(ffmpegBin, args, { stdio: ["pipe", "inherit", "inherit"] });
}

async function waitForFfmpeg(ffmpeg: ChildProcess): Promise<void> {
	return new Promise((resolve, reject) => {
		ffmpeg.on("close", (code) => {
			if (code === 0) resolve();
			else reject(new Error(`ffmpeg exited with code ${code}`));
		});
		ffmpeg.on("error", reject);
	});
}

export const screencapCommand: CommandModule<{}, Args> = {
	command: "screencap",
	describe: "Record video from a browser page by taking rapid screenshots and piping to ffmpeg",
	builder: {
		...sessionOption,
		...openOption,
		duration: {
			type: "number",
			alias: "d",
			describe: "Recording duration in seconds",
			default: 5,
		},
		fps: {
			type: "number",
			describe: "Target frame rate (practical ceiling ~15 for screenshot-based capture)",
			default: 10,
		},
		output: {
			type: "string",
			alias: "o",
			describe: "Output video file path",
			default: "./recording.mp4",
		},
		quality: {
			type: "number",
			describe: "JPEG quality 1-100 for frames",
			default: 80,
		},
		selector: {
			type: "string",
			alias: "S",
			describe: "CSS selector to crop to a specific element",
		},
		wait: {
			type: "string",
			alias: "w",
			describe: "JS expression to poll until truthy before recording",
		},
		timeout: {
			type: "number",
			describe: "Max wait time in ms for --wait",
			default: 10000,
		},
	},
	handler: withOneShot(async (argv) => {
		const outPath = callerResolve(argv.output);
		const ffmpegBin = findFfmpeg();
		const interval = Math.round(1000 / argv.fps);
		const totalFrames = Math.ceil(argv.duration * argv.fps);

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			if (argv.wait) {
				await page.waitForFunction(argv.wait, { timeout: argv.timeout });
			}

			// Get element crop region if selector specified
			let crop: { x: number; y: number; w: number; h: number } | null = null;
			let clip: { x: number; y: number; width: number; height: number } | undefined;
			if (argv.selector) {
				const el = await page.waitForSelector(argv.selector, { timeout: argv.timeout ?? 10000 });
				if (!el) throw new Error(`Element not found: ${argv.selector}`);
				const box = await el.boundingBox();
				if (!box) throw new Error(`Element has no bounding box: ${argv.selector}`);
				clip = { x: box.x, y: box.y, width: box.width, height: box.height };
			}

			// Spawn ffmpeg, pipe JPEG frames to stdin
			const ffmpeg = spawnFfmpeg(ffmpegBin, argv.fps, outPath, crop);

			process.stderr.write(`Recording ${argv.duration}s at ${argv.fps}fps → ${outPath}\n`);

			for (let i = 0; i < totalFrames; i++) {
				const start = Date.now();

				const buf = await page.screenshot({
					type: "jpeg",
					quality: argv.quality,
					...(clip ? { clip } : {}),
				}) as Buffer;
				ffmpeg.stdin!.write(buf);

				const elapsed = (i + 1) / argv.fps;
				process.stderr.write(`\r${elapsed.toFixed(1)}s / ${argv.duration}s (${i + 1}/${totalFrames} frames)`);

				// Sleep remaining interval time (accounting for screenshot duration)
				const took = Date.now() - start;
				const sleep = Math.max(0, interval - took);
				if (sleep > 0 && i < totalFrames - 1) {
					await new Promise((r) => setTimeout(r, sleep));
				}
			}

			process.stderr.write("\n");

			// Finalize video
			ffmpeg.stdin!.end();
			await waitForFfmpeg(ffmpeg);

			console.log(outPath);
		} finally {
			await browser.disconnect();
		}
	}),
};
