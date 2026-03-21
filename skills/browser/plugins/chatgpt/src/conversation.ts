export default function setup() {
	interface Message {
		id: string;
		role: string;
		text: string;
	}

	function messages(): Message[] {
		const els = document.querySelectorAll("[data-message-id]");
		return Array.from(els).map((el) => ({
			id: el.getAttribute("data-message-id") ?? "",
			role: el.getAttribute("data-message-author-role") ?? "unknown",
			text: (el.querySelector(".markdown") ?? el).textContent?.trim() ?? "",
		}));
	}

	function lastResponse(): string | null {
		const msgs = messages();
		const last = msgs.filter((m) => m.role === "assistant").at(-1);
		return last?.text ?? null;
	}

	function isResponseComplete(): boolean {
		// The stop button appears while streaming
		return document.querySelector('[data-testid="stop-button"]') === null;
	}

	function send(text: string): void {
		const textarea = document.querySelector("#prompt-textarea") as HTMLElement | null;
		if (!textarea) throw new Error("Prompt textarea not found");

		// It's a contenteditable div, not a <textarea>
		textarea.focus();
		textarea.textContent = text;
		textarea.dispatchEvent(new Event("input", { bubbles: true }));

		// Find the send button — it appears after typing
		requestAnimationFrame(() => {
			const sendBtn = document.querySelector(
				'[data-testid="send-button"]',
			) as HTMLElement | null;
			if (sendBtn) sendBtn.click();
		});
	}

	function title(): string {
		return document.title;
	}

	return { messages, lastResponse, isResponseComplete, send, title };
}
