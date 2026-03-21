var __browserPlugin = (function() {
	//#region plugins/chatgpt/share.ts
	function setup() {
		function shareData() {
			const data = window.__reactRouterContext?.state?.loaderData?.["routes/share.$shareId.($action)"]?.serverResponse?.data;
			if (!data) return null;
			const messages = (data.linear_conversation ?? []).map((node) => {
				return {
					role: node.message?.author?.role,
					text: (Array.isArray(node.message?.content?.parts) ? node.message.content.parts : []).map((part) => {
						if (typeof part === "string") return part;
						if (part && typeof part === "object" && "text" in part) return part.text;
						return "";
					}).filter(Boolean).join("\n\n").trim(),
					hidden: Boolean(node.message?.metadata?.is_visually_hidden_from_conversation || node.message?.metadata?.is_user_system_message)
				};
			}).filter((m) => (m.role === "assistant" || m.role === "user") && !m.hidden && m.text.length > 0);
			return {
				title: data.title ?? "",
				model: data.model?.title ?? data.model?.slug ?? "",
				messages
			};
		}
		return { shareData };
	}
	//#endregion
	return setup;
})();
