import type { CommandModule } from "yargs";
import { execSync, spawn, type ChildProcess } from "node:child_process";
import { join } from "node:path";
import type { Page, CDPSession } from "puppeteer-core";
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
	screenshots: boolean;
	trigger?: string;
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

function buildFfmpegArgs(fps: number, outPath: string, inputCodec: string, crop?: CropRect): string[] {
	const args = [
		"-loglevel", "error",
		"-f", "image2pipe",
		"-vcodec", inputCodec,
		"-framerate", String(fps),
		"-i", "pipe:0",
		"-an",
	];

	if (crop) {
		const cw = crop.w % 2 === 0 ? crop.w : crop.w - 1;
		const ch = crop.h % 2 === 0 ? crop.h : crop.h - 1;
		args.push("-vf", `crop=${cw}:${ch}:${crop.x}:${crop.y}`);
	}

	return args;
}

function addEncoder(ffmpegBin: string, args: string[], outPath: string): void {
	try {
		execSync(`"${ffmpegBin}" -hide_banner -encoders 2>&1 | grep h264_videotoolbox`, { stdio: "pipe" });
		args.push("-c:v", "h264_videotoolbox");
	} catch {
		args.push("-c:v", "libx264", "-preset", "ultrafast", "-crf", "23");
	}
	args.push("-pix_fmt", "yuv420p", "-y", outPath);
}

interface CropRect {
	x: number;
	y: number;
	w: number;
	h: number;
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

async function getElementCrop(page: Page, selector: string, timeout: number): Promise<{ clip: { x: number; y: number; width: number; height: number }; crop: CropRect }> {
	const el = await page.waitForSelector(selector, { timeout });
	if (!el) throw new Error(`Element not found: ${selector}`);
	const box = await el.boundingBox();
	if (!box) throw new Error(`Element has no bounding box: ${selector}`);
	const dpr = await page.evaluate(() => window.devicePixelRatio);
	return {
		clip: { x: box.x, y: box.y, width: box.width, height: box.height },
		crop: {
			x: Math.round(box.x * dpr),
			y: Math.round(box.y * dpr),
			w: Math.round(box.width * dpr),
			h: Math.round(box.height * dpr),
		},
	};
}

/** CDP screencast: high fps, pipes frames directly from compositor to ffmpeg */
async function recordScreencast(
	page: Page,
	ffmpegBin: string,
	outPath: string,
	opts: { duration: number; fps: number; quality: number; crop?: CropRect },
): Promise<void> {
	const args = buildFfmpegArgs(opts.fps, outPath, "mjpeg", opts.crop);
	addEncoder(ffmpegBin, args, outPath);
	const ffmpeg = spawn(ffmpegBin, args, { stdio: ["pipe", "inherit", "inherit"] });

	const client = await page.createCDPSession();
	await client.send("Page.enable");

	let frameCount = 0;
	let previousTimestamp: number | null = null;

	client.on("Page.screencastFrame", (event: any) => {
		const { data, metadata, sessionId } = event;
		client.send("Page.screencastFrameAck", { sessionId }).catch(() => {});

		const buf = Buffer.from(data, "base64");

		// Duplicate frames to fill gaps and maintain target fps
		if (previousTimestamp !== null) {
			const dt = Math.max(metadata.timestamp - previousTimestamp, 0);
			const count = Math.max(Math.round(opts.fps * dt), 1);
			for (let i = 0; i < count; i++) {
				ffmpeg.stdin!.write(buf);
				frameCount++;
			}
		} else {
			ffmpeg.stdin!.write(buf);
			frameCount++;
		}
		previousTimestamp = metadata.timestamp;

		process.stderr.write(`\rFrames: ${frameCount}`);
	});

	const viewport = page.viewport();
	await client.send("Page.startScreencast", {
		format: "jpeg",
		quality: opts.quality,
		maxWidth: viewport?.width ?? 1280,
		maxHeight: viewport?.height ?? 720,
		everyNthFrame: 1,
	});

	await new Promise((r) => setTimeout(r, opts.duration * 1000));

	await client.send("Page.stopScreencast");
	await client.detach();
	process.stderr.write(`\rFrames: ${frameCount}\n`);

	if (frameCount === 0) {
		ffmpeg.stdin!.end();
		ffmpeg.kill();
		throw new Error(
			"Screencast captured 0 frames. The page may not be actively rendering.\n" +
			"Try: browser screencap --screenshots ...",
		);
	}

	ffmpeg.stdin!.end();
	await waitForFfmpeg(ffmpeg);
}

/** Screenshot loop: slower but works in all cases */
async function recordScreenshots(
	page: Page,
	ffmpegBin: string,
	outPath: string,
	opts: { duration: number; fps: number; quality: number; clip?: { x: number; y: number; width: number; height: number } },
): Promise<void> {
	const args = buildFfmpegArgs(opts.fps, outPath, "mjpeg");
	addEncoder(ffmpegBin, args, outPath);
	const ffmpeg = spawn(ffmpegBin, args, { stdio: ["pipe", "inherit", "inherit"] });

	const interval = Math.round(1000 / opts.fps);
	const totalFrames = Math.ceil(opts.duration * opts.fps);

	for (let i = 0; i < totalFrames; i++) {
		const start = Date.now();

		const buf = await page.screenshot({
			type: "jpeg",
			quality: opts.quality,
			...(opts.clip ? { clip: opts.clip } : {}),
		}) as Buffer;
		ffmpeg.stdin!.write(buf);

		const elapsed = (i + 1) / opts.fps;
		process.stderr.write(`\r${elapsed.toFixed(1)}s / ${opts.duration}s (${i + 1}/${totalFrames} frames)`);

		const took = Date.now() - start;
		const sleep = Math.max(0, interval - took);
		if (sleep > 0 && i < totalFrames - 1) {
			await new Promise((r) => setTimeout(r, sleep));
		}
	}

	process.stderr.write("\n");
	ffmpeg.stdin!.end();
	await waitForFfmpeg(ffmpeg);
}

export const screencapCommand: CommandModule<{}, Args> = {
	command: "screencap",
	describe: "Record video from a browser page",
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
			describe: "Target frame rate",
			default: 15,
		},
		output: {
			type: "string",
			alias: "o",
			describe: "Output video file path",
			default: "./recording.mp4",
		},
		quality: {
			type: "number",
			describe: "JPEG quality 1-100",
			default: 80,
		},
		screenshots: {
			type: "boolean",
			describe: "Use screenshot loop instead of CDP screencast (slower but more reliable)",
			default: false,
		},
		trigger: {
			type: "string",
			alias: "t",
			describe: "JS expression to evaluate right before recording starts (e.g. \"__epub.anim.start()\")",
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

		const browser = await new Browser().connect();
		try {
			const page = await browser.resolvePage(argv.session);

			if (argv.wait) {
				await page.waitForFunction(argv.wait, { timeout: argv.timeout });
			}

			let clip: { x: number; y: number; width: number; height: number } | undefined;
			let crop: CropRect | undefined;
			if (argv.selector) {
				const result = await getElementCrop(page, argv.selector, argv.timeout ?? 10000);
				clip = result.clip;
				crop = result.crop;
			}

			if (argv.trigger) {
				await page.evaluate(argv.trigger);
			}

			process.stderr.write(
				`Recording ${argv.duration}s at ${argv.fps}fps${argv.screenshots ? " (screenshots)" : " (screencast)"} → ${outPath}\n`,
			);

			if (argv.screenshots) {
				await recordScreenshots(page, ffmpegBin, outPath, {
					duration: argv.duration,
					fps: argv.fps,
					quality: argv.quality,
					clip,
				});
			} else {
				await recordScreencast(page, ffmpegBin, outPath, {
					duration: argv.duration,
					fps: argv.fps,
					quality: argv.quality,
					crop,
				});
			}

			console.log(outPath);
		} finally {
			await browser.disconnect();
		}
	}),
};
