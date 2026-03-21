/**
 * Chrome @match pattern URL matching.
 * Format: <scheme>://<host>/<path>
 *
 * Scheme: http, https, or * (both)
 * Host: exact domain, *.example.com (subdomains), or * (all)
 * Path: literal with * as wildcard
 */

function globToRegex(pattern: string): RegExp {
	const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
	const withWildcards = escaped.replace(/\*/g, ".*");
	return new RegExp(`^${withWildcards}$`);
}

export function matchesPattern(pattern: string, url: URL): boolean {
	// Parse pattern: scheme://host/path
	const match = pattern.match(/^(\*|https?):\/\/([^/]+)(\/.*)?$/);
	if (!match) return false;

	const [, schemePattern, hostPattern, pathPattern = "/*"] = match;

	// Check scheme
	if (schemePattern !== "*" && schemePattern !== url.protocol.replace(":", "")) {
		return false;
	}

	// Check host
	if (hostPattern === "*") {
		// matches any host
	} else if (hostPattern.startsWith("*.")) {
		const suffix = hostPattern.slice(2);
		if (url.hostname !== suffix && !url.hostname.endsWith(`.${suffix}`)) {
			return false;
		}
	} else {
		if (url.hostname !== hostPattern) return false;
	}

	// Check path
	const pathRegex = globToRegex(pathPattern);
	if (!pathRegex.test(url.pathname)) return false;

	return true;
}

export function matchesURL(
	patterns: string[],
	excludePatterns: string[] | undefined,
	url: URL,
): boolean {
	// Exclude wins
	if (excludePatterns) {
		for (const pattern of excludePatterns) {
			if (matchesPattern(pattern, url)) return false;
		}
	}

	// At least one pattern must match
	for (const pattern of patterns) {
		if (matchesPattern(pattern, url)) return true;
	}

	return false;
}
