export default function setup() {
	function isLoggedIn(): boolean {
		return document.querySelector('[data-testid="accounts-profile-button"]') !== null;
	}

	function currentModel(): string | null {
		const btn = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
		return btn?.textContent?.trim() ?? null;
	}

	return { isLoggedIn, currentModel };
}
