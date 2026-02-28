import type { CommandModule } from "yargs";
import { Browser } from "../browser.js";

interface AXNode {
	nodeId: string;
	ignored: boolean;
	role?: { type: string; value: string };
	name?: { type: string; value: string };
	description?: { type: string; value: string };
	value?: { type: string; value: string };
	properties?: Array<{ name: string; value: { type: string; value: unknown } }>;
	childIds?: string[];
	parentId?: string;
}

interface Args {
	depth?: number;
	"include-ignored"?: boolean;
}

function formatTree(nodes: AXNode[], maxDepth: number, includeIgnored: boolean): string {
	const byId = new Map<string, AXNode>();
	for (const node of nodes) byId.set(node.nodeId, node);

	const lines: string[] = [];

	function walk(nodeId: string, depth: number) {
		if (maxDepth > 0 && depth > maxDepth) return;
		const node = byId.get(nodeId);
		if (!node) return;
		if (node.ignored && !includeIgnored) {
			for (const childId of node.childIds ?? []) walk(childId, depth);
			return;
		}

		const role = node.role?.value ?? "unknown";

		// InlineTextBox always duplicates its parent StaticText — skip
		if (role === "InlineTextBox") return;

		// StaticText: fold into parent when parent already shows the same name
		if (role === "StaticText") {
			const parent = node.parentId ? byId.get(node.parentId) : undefined;
			if (parent?.name?.value === node.name?.value) return;
		}

		const name = node.name?.value;
		const value = node.value?.value;
		const desc = node.description?.value;

		// Collect interesting properties
		const props: string[] = [];
		for (const p of node.properties ?? []) {
			const v = p.value.value;
			if (v === false || v === "" || v === undefined || v === null) continue;
			// Skip noisy defaults
			if (p.name === "focusable" || p.name === "readonly") continue;
			if (p.name === "level" || p.name === "checked" || p.name === "expanded" || p.name === "selected" || p.name === "required" || p.name === "disabled" || p.name === "invalid") {
				props.push(`${p.name}=${v}`);
			} else if (p.name === "url" || p.name === "autocomplete") {
				props.push(`${p.name}=${v}`);
			} else if (v === true) {
				props.push(p.name);
			}
		}

		const indent = "  ".repeat(depth);
		let line = `${indent}[${role}]`;
		if (name) line += ` "${name}"`;
		if (value) line += ` value="${value}"`;
		if (desc) line += ` desc="${desc}"`;
		if (props.length) line += ` ${props.join(" ")}`;

		lines.push(line);

		for (const childId of node.childIds ?? []) walk(childId, depth + 1);
	}

	// Find root (node with no parentId)
	const root = nodes.find((n) => !n.parentId);
	if (root) walk(root.nodeId, 0);

	return lines.join("\n");
}

export const accessibilityCommand: CommandModule<{}, Args> = {
	command: "accessibility",
	aliases: ["a11y"],
	describe: "Dump the accessibility tree of the active tab",
	builder: {
		depth: {
			type: "number",
			describe: "Maximum tree depth (0 = unlimited)",
			default: 0,
		},
		"include-ignored": {
			type: "boolean",
			describe: "Include ignored/hidden nodes",
			default: false,
		},
	},
	handler: async (argv) => {
		const browser = await new Browser().connect();
		try {
			const page = await browser.activePage();
			const client = await page.createCDPSession();
			const { nodes } = (await client.send("Accessibility.getFullAXTree" as any)) as {
				nodes: AXNode[];
			};
			await client.detach();

			const output = formatTree(nodes, argv.depth ?? 0, argv["include-ignored"] ?? false);
			console.log(output);
		} finally {
			await browser.disconnect();
		}
	},
};
