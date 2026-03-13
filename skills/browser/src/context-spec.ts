import { readFileSync } from "node:fs";
import { parse as parseTOML } from "smol-toml";
import { resolveDevice, parseViewport } from "./emulation.js";
import { callerResolve } from "./browser.js";

export interface ContextSpec {
	url?: string;
	device?: string;
	width?: number;
	height?: number;
	dpr?: number;
	mobile?: boolean;
	ua?: string;
	viewport?: string;
}

export interface ResolvedSpec {
	url?: string;
	width?: number;
	height?: number;
	dpr: number;
	mobile: boolean;
	ua?: string;
	description: string;
}

export function parseContextSpec(input: string): ContextSpec {
	// TOML file
	if (input.endsWith(".toml")) {
		const path = callerResolve(input);
		const text = readFileSync(path, "utf-8");
		return parseTOML(text) as unknown as ContextSpec;
	}

	// JSON literal
	if (input.startsWith("{")) {
		return JSON.parse(input) as ContextSpec;
	}

	// Bare URL
	if (/^https?:\/\//.test(input) || (input.includes(".") && !/\s/.test(input))) {
		return { url: input };
	}

	throw new Error(
		`Cannot parse context spec: "${input}"\nExpected: TOML file path, JSON literal, or URL`,
	);
}

export function resolveContextSpec(spec: ContextSpec): ResolvedSpec {
	let width: number | undefined;
	let height: number | undefined;
	let dpr = 1;
	let mobile = false;
	let ua: string | undefined;
	let description = "desktop";

	// Resolve device first as base
	if (spec.device) {
		const result = resolveDevice(spec.device);
		if (!result) {
			throw new Error(`Unknown device "${spec.device}". Use 'browser devices' to list all.`);
		}
		const { viewport } = result.device;
		width = viewport.width;
		height = viewport.height;
		dpr = viewport.deviceScaleFactor ?? 1;
		mobile = viewport.isMobile ?? true;
		ua = result.device.userAgent;
		description = `${result.key} (${width}x${height}@${dpr})`;
	}

	// Resolve viewport string if given
	if (spec.viewport) {
		const vp = parseViewport(spec.viewport);
		if (!vp) throw new Error(`Invalid viewport "${spec.viewport}". Expected WxH or WxH@DPR`);
		width = vp.width;
		height = vp.height;
		dpr = vp.deviceScaleFactor;
		description = `${width}x${height}@${dpr}`;
	}

	// Explicit overrides take precedence
	if (spec.width !== undefined) width = spec.width;
	if (spec.height !== undefined) height = spec.height;
	if (spec.dpr !== undefined) dpr = spec.dpr;
	if (spec.mobile !== undefined) mobile = spec.mobile;
	if (spec.ua !== undefined) ua = spec.ua;

	if (width && height && !spec.device && !spec.viewport) {
		description = `${width}x${height}@${dpr}${mobile ? " (mobile)" : ""}`;
	}

	return { url: spec.url, width, height, dpr, mobile, ua, description };
}
