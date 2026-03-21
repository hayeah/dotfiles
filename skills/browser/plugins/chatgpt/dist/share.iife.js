var __browserPlugin = (function() {
  "use strict";
  function setup() {
    function shareData() {
      var _a, _b, _c, _d, _e, _f, _g;
      const routeId = "routes/share.$shareId.($action)";
      const data = (_e = (_d = (_c = (_b = (_a = window.__reactRouterContext) == null ? void 0 : _a.state) == null ? void 0 : _b.loaderData) == null ? void 0 : _c[routeId]) == null ? void 0 : _d.serverResponse) == null ? void 0 : _e.data;
      if (!data) return null;
      const messages = (data.linear_conversation ?? []).map((node) => {
        var _a2, _b2, _c2, _d2, _e2, _f2, _g2, _h;
        const role = (_b2 = (_a2 = node.message) == null ? void 0 : _a2.author) == null ? void 0 : _b2.role;
        const parts = Array.isArray((_d2 = (_c2 = node.message) == null ? void 0 : _c2.content) == null ? void 0 : _d2.parts) ? node.message.content.parts : [];
        const text = parts.map((part) => {
          if (typeof part === "string") return part;
          if (part && typeof part === "object" && "text" in part) return part.text;
          return "";
        }).filter(Boolean).join("\n\n").trim();
        const hidden = Boolean(
          ((_f2 = (_e2 = node.message) == null ? void 0 : _e2.metadata) == null ? void 0 : _f2.is_visually_hidden_from_conversation) || ((_h = (_g2 = node.message) == null ? void 0 : _g2.metadata) == null ? void 0 : _h.is_user_system_message)
        );
        return { role, text, hidden };
      }).filter(
        (m) => (m.role === "assistant" || m.role === "user") && !m.hidden && m.text.length > 0
      );
      return {
        title: data.title ?? "",
        model: ((_f = data.model) == null ? void 0 : _f.title) ?? ((_g = data.model) == null ? void 0 : _g.slug) ?? "",
        messages
      };
    }
    return { shareData };
  }
  return setup;
})();
