import type { CommandModule } from "yargs";
import { writeFileSync } from "node:fs";
import { callerResolve, sessionOption } from "../browser.js";
import { openOption } from "../oneshot.js";
import { withFreshPage } from "../with-page.js";

interface Args {
	open?: string;
	session?: string;
	duration: number;
	mem: boolean;
	output: string;
	trigger?: string;
	wait?: string;
	timeout?: number;
}

export const profileCommand: CommandModule<{}, Args> = {
	command: "profile",
	describe: "Capture CPU profile (and optionally heap snapshot) from a page",
	builder: {
		...sessionOption,
		...openOption,
		duration: {
			type: "number",
			alias: "d",
			describe: "Profiling duration in seconds",
			default: 5,
		},
		mem: {
			type: "boolean",
			describe: "Also capture a heap snapshot",
			default: false,
		},
		output: {
			type: "string",
			alias: "o",
			describe: "Output file path (without extension — .cpuprofile and .heapsnapshot added automatically)",
			default: "./profile",
		},
		trigger: {
			type: "string",
			alias: "t",
			describe: "JS expression to evaluate before profiling starts (e.g. start an animation)",
		},
		wait: {
			type: "string",
			alias: "w",
			describe: "JS expression to poll until truthy before profiling",
		},
		timeout: {
			type: "number",
			describe: "Max wait time in ms for --wait",
			default: 10000,
		},
	},
	handler: async (argv) => {
		await withFreshPage(argv, async ({ page }) => {
			if (argv.wait) {
				await page.waitForFunction(argv.wait, { timeout: argv.timeout });
			}

			if (argv.trigger) {
				await page.evaluate(argv.trigger);
			}

			const client = await page.createCDPSession();
			const basePath = callerResolve(argv.output);

			// CPU profile
			process.stderr.write(`Profiling CPU for ${argv.duration}s...\n`);
			await client.send("Profiler.enable");
			await client.send("Profiler.start");

			await new Promise((r) => setTimeout(r, argv.duration * 1000));

			const { profile } = await client.send("Profiler.stop");
			const cpuPath = `${basePath}.cpuprofile`;
			writeFileSync(cpuPath, JSON.stringify(profile));
			console.log(cpuPath);

			// Heap snapshot
			if (argv.mem) {
				process.stderr.write("Capturing heap snapshot...\n");
				await client.send("HeapProfiler.enable");

				const chunks: string[] = [];
				client.on("HeapProfiler.addHeapSnapshotChunk", (event: any) => {
					chunks.push(event.chunk);
				});

				await client.send("HeapProfiler.takeHeapSnapshot", { reportProgress: false });

				const heapPath = `${basePath}.heapsnapshot`;
				writeFileSync(heapPath, chunks.join(""));
				console.log(heapPath);
			}

			await client.detach();
		});
	},
};
