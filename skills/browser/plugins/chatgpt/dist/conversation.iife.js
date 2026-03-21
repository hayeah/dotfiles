var __browserPlugin = (function() {
	//#region plugins/chatgpt/src/conversation.ts
	function setup() {
		function messages() {
			const els = document.querySelectorAll("[data-message-id]");
			return Array.from(els).map((el) => ({
				id: el.getAttribute("data-message-id") ?? "",
				role: el.getAttribute("data-message-author-role") ?? "unknown",
				text: (el.querySelector(".markdown") ?? el).textContent?.trim() ?? ""
			}));
		}
		function lastResponse() {
			return messages().filter((m) => m.role === "assistant").at(-1)?.text ?? null;
		}
		function isResponseComplete() {
			return document.querySelector("[data-testid=\"stop-button\"]") === null;
		}
		function send(text) {
			const textarea = document.querySelector("#prompt-textarea");
			if (!textarea) throw new Error("Prompt textarea not found");
			textarea.focus();
			textarea.textContent = text;
			textarea.dispatchEvent(new Event("input", { bubbles: true }));
			requestAnimationFrame(() => {
				const sendBtn = document.querySelector("[data-testid=\"send-button\"]");
				if (sendBtn) sendBtn.click();
			});
		}
		function title() {
			return document.title;
		}
		return {
			messages,
			lastResponse,
			isResponseComplete,
			send,
			title
		};
	}
	//#endregion
	return setup;
})();
