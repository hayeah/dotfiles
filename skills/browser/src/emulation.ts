import { KnownDevices, type CDPSession, type Page } from "puppeteer-core";

/** All non-landscape device names from KnownDevices. */
export function listDevices(): string[] {
	return Object.keys(KnownDevices).filter((k) => !k.includes("landscape"));
}

/**
 * Resolve a device name from KnownDevices.
 * Tries exact match, then case-insensitive match, then case-insensitive prefix match.
 */
export function resolveDevice(name: string): { key: string; device: (typeof KnownDevices)[string] } | null {
	if (KnownDevices[name]) return { key: name, device: KnownDevices[name] };

	const lower = name.toLowerCase();
	const candidates = listDevices();

	for (const key of candidates) {
		if (key.toLowerCase() === lower) return { key, device: KnownDevices[key] };
	}

	const matches = candidates.filter((k) => k.toLowerCase().startsWith(lower));
	if (matches.length === 1) return { key: matches[0], device: KnownDevices[matches[0]] };
	if (matches.length > 1) {
		throw new Error(`Ambiguous device "${name}": ${matches.join(", ")}`);
	}

	return null;
}

/** Parse a viewport string like "390x844" or "390x844@3". */
export function parseViewport(spec: string): { width: number; height: number; deviceScaleFactor: number } | null {
	const match = spec.match(/^(\d+)x(\d+)(?:@(\d+(?:\.\d+)?))?$/);
	if (!match) return null;
	return {
		width: parseInt(match[1]),
		height: parseInt(match[2]),
		deviceScaleFactor: match[3] ? parseFloat(match[3]) : 1,
	};
}

export interface EmulationResult {
	description: string;
	/** The emulated CSS width in pixels. */
	width: number;
	/** Call to restore the original window size. */
	restore: () => Promise<void>;
}

/**
 * Apply device emulation by resizing the Chrome window.
 *
 * On headed Chrome, CSS layout is determined by the actual window size —
 * CDP Emulation.setDeviceMetricsOverride only changes what JS APIs report,
 * not the CSS layout viewport. So we resize the real window instead.
 *
 * Also sets DPR and user agent via CDP.
 * Returns a restore function to put the window back.
 */
export async function applyEmulation(
	page: Page,
	opts: { device?: string; viewport?: string; mobile?: boolean },
): Promise<EmulationResult> {
	let width: number;
	let height: number;
	let dpr: number;
	let mobile: boolean;
	let userAgent: string | undefined;
	let description: string;

	if (opts.device) {
		const result = resolveDevice(opts.device);
		if (!result) {
			throw new Error(`Unknown device "${opts.device}". Use 'browser devices' to list all.`);
		}
		const { viewport } = result.device;
		width = viewport.width;
		height = viewport.height;
		dpr = viewport.deviceScaleFactor ?? 1;
		mobile = viewport.isMobile ?? true;
		userAgent = result.device.userAgent;
		description = `${result.key} (${width}x${height}@${dpr})`;
	} else if (opts.viewport) {
		const vp = parseViewport(opts.viewport);
		if (!vp) throw new Error(`Invalid viewport "${opts.viewport}". Expected WxH or WxH@DPR (e.g. 390x844@3)`);
		width = vp.width;
		height = vp.height;
		dpr = vp.deviceScaleFactor;
		mobile = opts.mobile ?? false;
		description = `${width}x${height}@${dpr}${mobile ? " (mobile)" : ""}`;
	} else {
		throw new Error("Either --device or --viewport is required");
	}

	const cdp = await page.createCDPSession();

	// Save original window bounds
	const { windowId } = await cdp.send("Browser.getWindowForTarget");
	const { bounds: originalBounds } = await cdp.send("Browser.getWindowBounds", { windowId });

	// Chrome has a minimum window width (~500px on macOS). Account for browser
	// chrome (~85px for the tab bar / toolbar).
	const chromeHeight = 85;
	await cdp.send("Browser.setWindowBounds", {
		windowId,
		bounds: { width, height: height + chromeHeight, windowState: "normal" },
	});

	// Set DPR and mobile flag via emulation override.
	// Explicit width ensures DPR applies to screenshots on headed Chrome.
	// Height 0 = use window height (allows fullPage screenshots to expand).
	await cdp.send("Emulation.setDeviceMetricsOverride", {
		width,
		height: 0,
		deviceScaleFactor: dpr,
		mobile,
	});

	if (mobile) {
		await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true });
	}

	if (userAgent) {
		await cdp.send("Network.setUserAgentOverride", { userAgent });
	}

	// Small delay for window resize to take effect
	await new Promise((r) => setTimeout(r, 200));

	const restore = async () => {
		await cdp.send("Emulation.clearDeviceMetricsOverride");
		await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: false });
		await cdp.send("Network.setUserAgentOverride", { userAgent: "" });
		await cdp.send("Browser.setWindowBounds", { windowId, bounds: originalBounds });
	};

	return { description, width, restore };
}

/**
 * Apply emulation from a resolved context spec.
 * Returns the CDP session (caller must keep it alive to preserve emulation).
 */
export async function applySpecEmulation(
	page: Page,
	spec: { width?: number; height?: number; dpr: number; mobile: boolean; ua?: string; description: string },
): Promise<{ cdpSession: CDPSession; description: string; width: number; restore: () => Promise<void> }> {
	if (!spec.width || !spec.height) {
		throw new Error("Spec must have width and height for emulation");
	}

	const cdp = await page.createCDPSession();

	const { windowId } = await cdp.send("Browser.getWindowForTarget");
	const { bounds: originalBounds } = await cdp.send("Browser.getWindowBounds", { windowId });

	const chromeHeight = 85;
	await cdp.send("Browser.setWindowBounds", {
		windowId,
		bounds: { width: spec.width, height: spec.height + chromeHeight, windowState: "normal" },
	});

	await cdp.send("Emulation.setDeviceMetricsOverride", {
		width: spec.width,
		height: 0,
		deviceScaleFactor: spec.dpr,
		mobile: spec.mobile,
	});

	if (spec.mobile) {
		await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true });
	}

	if (spec.ua) {
		await cdp.send("Network.setUserAgentOverride", { userAgent: spec.ua });
	}

	await new Promise((r) => setTimeout(r, 200));

	const restore = async () => {
		await cdp.send("Emulation.clearDeviceMetricsOverride");
		await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: false });
		await cdp.send("Network.setUserAgentOverride", { userAgent: "" });
		await cdp.send("Browser.setWindowBounds", { windowId, bounds: originalBounds });
	};

	return { cdpSession: cdp, description: spec.description, width: spec.width, restore };
}

/** Clear emulation overrides via CDP. */
export async function clearEmulation(page: Page): Promise<void> {
	const cdp = await page.createCDPSession();
	await cdp.send("Emulation.clearDeviceMetricsOverride");
	await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: false });
	await cdp.send("Network.setUserAgentOverride", { userAgent: "" });
	await cdp.detach();
}

/** Yargs options for device/viewport flags, reusable across commands. */
export const emulationOptions = {
	device: {
		type: "string" as const,
		alias: "d" as const,
		describe: "Device name (e.g. 'iPhone 15 Pro', 'iPad')",
	},
	viewport: {
		type: "string" as const,
		alias: "v" as const,
		describe: "Custom viewport WxH[@DPR] (e.g. 390x844@3)",
	},
	mobile: {
		type: "boolean" as const,
		describe: "Enable mobile emulation (with --viewport)",
		default: false,
	},
} as const;
