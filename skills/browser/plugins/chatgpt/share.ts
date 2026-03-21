export default function setup() {
	function shareData() {
		const routeId = "routes/share.$shareId.($action)";
		const data = (window as any).__reactRouterContext?.state?.loaderData?.[routeId]
			?.serverResponse?.data;
		if (!data) return null;

		const messages = (data.linear_conversation ?? [])
			.map((node: any) => {
				const role = node.message?.author?.role;
				const parts = Array.isArray(node.message?.content?.parts)
					? node.message.content.parts
					: [];
				const text = parts
					.map((part: any) => {
						if (typeof part === "string") return part;
						if (part && typeof part === "object" && "text" in part) return part.text;
						return "";
					})
					.filter(Boolean)
					.join("\n\n")
					.trim();
				const hidden = Boolean(
					node.message?.metadata?.is_visually_hidden_from_conversation ||
						node.message?.metadata?.is_user_system_message,
				);
				return { role, text, hidden };
			})
			.filter(
				(m: any) =>
					(m.role === "assistant" || m.role === "user") && !m.hidden && m.text.length > 0,
			);

		return {
			title: data.title ?? "",
			model: data.model?.title ?? data.model?.slug ?? "",
			messages,
		};
	}

	return { shareData };
}
