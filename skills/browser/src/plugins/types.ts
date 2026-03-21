export interface PluginRoute {
	match: string[];
	exclude?: string[];
	browser?: string; // source path relative to plugin dir
	node?: string; // source path relative to plugin dir
}

export interface PluginManifest {
	name: string;
	description: string;
	routes: PluginRoute[];
}

export interface ResolvedPlugin {
	name: string;
	description: string;
	dir: string; // absolute path to plugin directory
	manifest: PluginManifest;
	skillMd?: string; // contents of SKILL.md if present
}

export interface MatchedRoute {
	plugin: ResolvedPlugin;
	route: PluginRoute;
}
