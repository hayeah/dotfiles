import type { CommandModule } from "yargs";
import { scanPlugins, matchPlugins } from "../plugins/loader.js";

interface Args {
	name?: string;
	url?: string;
}

export const pluginsCommand: CommandModule<{}, Args> = {
	command: "plugins [name]",
	describe: "List available plugins or show plugin details",
	builder: {
		name: {
			type: "string",
			describe: "Plugin name to show details for",
		},
		url: {
			type: "string",
			describe: "Filter plugins that match this URL",
		},
	},
	handler: async (argv) => {
		const plugins = scanPlugins();

		if (argv.name) {
			// Show details for a specific plugin
			const plugin = plugins.find((p) => p.name === argv.name);
			if (!plugin) {
				console.error(`Plugin "${argv.name}" not found`);
				process.exit(1);
			}

			console.log(`Name: ${plugin.name}`);
			console.log(`Description: ${plugin.description}`);
			console.log(`Path: ${plugin.dir}`);
			console.log("");
			console.log("Routes:");
			for (const route of plugin.manifest.routes) {
				const modules: string[] = [];
				if (route.browser) modules.push("browser");
				if (route.node) modules.push("node");
				const patterns = route.match.join(", ");
				console.log(`  ${patterns} → ${modules.join(" + ")}`);
			}

			if (plugin.skillMd) {
				console.log("");
				console.log("--- SKILL.md ---");
				console.log(plugin.skillMd);
			}
			return;
		}

		if (argv.url) {
			// Show plugins matching a URL
			const matched = matchPlugins(plugins, argv.url);
			if (matched.length === 0) {
				console.log("No plugins match this URL.");
				return;
			}

			const nameWidth = Math.max(6, ...matched.map((m) => m.plugin.name.length));
			const routeWidth = Math.max(5, ...matched.map((m) => m.route.match.join(", ").length));
			console.log(
				`${"PLUGIN".padEnd(nameWidth)}  ${"ROUTE".padEnd(routeWidth)}  MODULES`,
			);
			for (const { plugin, route } of matched) {
				const modules: string[] = [];
				if (route.browser) modules.push("browser");
				if (route.node) modules.push("node");
				const patterns = route.match.join(", ");
				console.log(
					`${plugin.name.padEnd(nameWidth)}  ${patterns.padEnd(routeWidth)}  ${modules.join(" + ")}`,
				);
			}
			return;
		}

		// List all plugins
		if (plugins.length === 0) {
			console.log("No plugins found.");
			return;
		}

		const nameWidth = Math.max(4, ...plugins.map((p) => p.name.length));
		console.log(`${"NAME".padEnd(nameWidth)}  ROUTES  DESCRIPTION`);
		for (const plugin of plugins) {
			const routeCount = plugin.manifest.routes.length.toString();
			console.log(
				`${plugin.name.padEnd(nameWidth)}  ${routeCount.padEnd(6)}  ${plugin.description}`,
			);
		}
	},
};
