var __browserPlugin = (function() {
	//#region plugins/chatgpt/common.ts
	function setup() {
		function isLoggedIn() {
			return document.querySelector("[data-testid=\"accounts-profile-button\"]") !== null;
		}
		function currentModel() {
			return document.querySelector("[data-testid=\"model-switcher-dropdown-button\"]")?.textContent?.trim() ?? null;
		}
		return {
			isLoggedIn,
			currentModel
		};
	}
	//#endregion
	return setup;
})();
