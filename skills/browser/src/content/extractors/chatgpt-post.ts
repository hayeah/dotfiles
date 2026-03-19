import type { ContentExtractor } from "../types.js";

interface PostMessage {
	role: "assistant" | "user";
	content: string;
}

const CHATGPT_POST_ROUTE_ID = "routes/s.$postId";

function roleLabel(role: PostMessage["role"]): string {
	return role === "assistant" ? "ChatGPT" : "User";
}

function formatPostMarkdown(messages: PostMessage[], modelTitle?: string): string {
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

export const chatGPTPostExtractor: ContentExtractor = {
	id: "extractor/chatgpt-post",
	matches: (url) => url.hostname === "chatgpt.com" && url.pathname.startsWith("/s/"),
	extract: async (page, url) => {
		try {
			await page.waitForFunction(
				(routeId) => {
					const post = (window as any).__reactRouterContext?.state?.loaderData?.[routeId]
						?.postWithProfile?.post;
					return (
						post &&
						Array.isArray(post.attachments) &&
						post.attachments.some(
							(a: any) => a.kind === "message_slice" && Array.isArray(a.messages) && a.messages.length > 0,
						)
					);
				},
				{ timeout: 10_000 },
				CHATGPT_POST_ROUTE_ID,
			);
		} catch {}

		const result = await page.evaluate((routeId) => {
			type PostMsg = {
				author?: { role?: string };
				content?: { content_type?: string; parts?: unknown[] };
				metadata?: {
					is_visually_hidden_from_conversation?: boolean;
					is_user_system_message?: boolean;
					resolved_model_slug?: string;
				};
			};
			type Attachment = {
				kind?: string;
				messages?: PostMsg[];
			};
			type Post = {
				text?: string;
				attachments?: Attachment[];
			};

			const post = (window as any).__reactRouterContext?.state?.loaderData?.[routeId]
				?.postWithProfile?.post as Post | undefined;
			if (!post || !Array.isArray(post.attachments)) return null;

			const allMessages: PostMsg[] = [];
			let modelSlug: string | undefined;
			for (const attachment of post.attachments) {
				if (attachment.kind === "message_slice" && Array.isArray(attachment.messages)) {
					for (const msg of attachment.messages) {
						allMessages.push(msg);
						if (!modelSlug && msg.metadata?.resolved_model_slug) {
							modelSlug = msg.metadata.resolved_model_slug;
						}
					}
				}
			}

			return {
				title: post.text,
				modelSlug,
				messages: allMessages.map((msg) => {
					const role = msg.author?.role;
					const parts = Array.isArray(msg.content?.parts) ? msg.content!.parts : [];
					const content = parts
						.map((part) => {
							if (typeof part === "string") return part;
							if (
								part &&
								typeof part === "object" &&
								"text" in part &&
								typeof (part as any).text === "string"
							) {
								return (part as any).text;
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
							msg.metadata?.is_visually_hidden_from_conversation ||
								msg.metadata?.is_user_system_message,
						),
					};
				}),
			};
		}, CHATGPT_POST_ROUTE_ID);

		if (!result) return null;

		const messages = result.messages.filter(
			(message): message is PostMessage & { hidden: boolean } =>
				(message.role === "assistant" || message.role === "user") &&
				!message.hidden &&
				message.content.length > 0,
		);
		if (messages.length === 0) return null;

		return {
			title:
				typeof result.title === "string" && result.title.trim().length > 0
					? result.title
					: url.pathname,
			content: formatPostMarkdown(messages, result.modelSlug),
		};
	},
};
