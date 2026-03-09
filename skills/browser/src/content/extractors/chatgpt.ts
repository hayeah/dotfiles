import type { ContentExtractor } from "../types.js";

interface ChatGPTShareMessage {
	role: "assistant" | "user";
	content: string;
}

const CHATGPT_SHARE_ROUTE_ID = "routes/share.$shareId.($action)";

function roleLabel(role: ChatGPTShareMessage["role"]): string {
	return role === "assistant" ? "ChatGPT" : "User";
}

function formatConversationMarkdown(
	messages: ChatGPTShareMessage[],
	modelTitle?: string,
): string {
	const blocks = messages.map(
		(message) => `**${roleLabel(message.role)}**\n\n${message.content.trim()}`,
	);
	const parts: string[] = [];

	if (modelTitle) {
		parts.push(`- Model: ${modelTitle}`);
	}
	if (blocks.length > 0) {
		if (parts.length > 0) parts.push("", "---", "");
		parts.push(blocks.join("\n\n---\n\n"));
	}

	return parts.join("\n").trim();
}

export const chatGPTContentExtractor: ContentExtractor = {
	id: "extractor/chatgpt",
	matches: (url) => url.hostname === "chatgpt.com" && url.pathname.startsWith("/share/"),
	extract: async (page, url) => {
		try {
			await page.waitForFunction(
				(routeId) => {
					const data = (window as any).__reactRouterContext?.state?.loaderData?.[routeId]
						?.serverResponse?.data;
					return Array.isArray(data?.linear_conversation) && data.linear_conversation.length > 0;
				},
				{ timeout: 10_000 },
				CHATGPT_SHARE_ROUTE_ID,
			);
		} catch {}

		const share = await page.evaluate((routeId) => {
			type ShareNode = {
				message?: {
					author?: { role?: string };
					content?: { parts?: unknown[] };
					metadata?: {
						is_visually_hidden_from_conversation?: boolean;
						is_user_system_message?: boolean;
					};
				};
			};
			type ShareData = {
				title?: string;
				model?: { slug?: string; title?: string };
				linear_conversation?: ShareNode[];
			};

			const data = (window as any).__reactRouterContext?.state?.loaderData?.[routeId]
				?.serverResponse?.data as ShareData | undefined;
			if (!data || !Array.isArray(data.linear_conversation)) return null;

			return {
				title: data.title,
				modelTitle: data.model?.title ?? data.model?.slug,
				messages: data.linear_conversation.map((node) => {
					const role = node.message?.author?.role;
					const parts = Array.isArray(node.message?.content?.parts)
						? node.message?.content?.parts
						: [];
					const content = parts
						.map((part) => {
							if (typeof part === "string") return part;
							if (
								part &&
								typeof part === "object" &&
								"text" in part &&
								typeof part.text === "string"
							) {
								return part.text;
							}
							return "";
						})
						.filter(Boolean)
						.join("\n\n")
						.trim();

					return {
						role,
						content,
						hidden: Boolean(
							node.message?.metadata?.is_visually_hidden_from_conversation ||
								node.message?.metadata?.is_user_system_message,
						),
					};
				}),
			};
		}, CHATGPT_SHARE_ROUTE_ID);

		if (!share) return null;

		const messages = share.messages.filter(
			(message): message is ChatGPTShareMessage & { hidden: boolean } =>
				(message.role === "assistant" || message.role === "user") &&
				!message.hidden &&
				message.content.length > 0,
		);
		if (messages.length === 0) return null;

		return {
			title:
				typeof share.title === "string" && share.title.trim().length > 0
					? share.title
					: url.pathname,
			content: formatConversationMarkdown(messages, share.modelTitle),
		};
	},
};
