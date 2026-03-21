var __browserPlugin = (function() {
  "use strict";
  function setup() {
    function messages() {
      const els = document.querySelectorAll("[data-message-id]");
      return Array.from(els).map((el) => {
        var _a;
        return {
          id: el.getAttribute("data-message-id") ?? "",
          role: el.getAttribute("data-message-author-role") ?? "unknown",
          text: ((_a = (el.querySelector(".markdown") ?? el).textContent) == null ? void 0 : _a.trim()) ?? ""
        };
      });
    }
    function lastResponse() {
      const msgs = messages();
      const last = msgs.filter((m) => m.role === "assistant").at(-1);
      return (last == null ? void 0 : last.text) ?? null;
    }
    function isResponseComplete() {
      return document.querySelector('[data-testid="stop-button"]') === null;
    }
    function send(text) {
      const textarea = document.querySelector("#prompt-textarea");
      if (!textarea) throw new Error("Prompt textarea not found");
      textarea.focus();
      textarea.textContent = text;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      requestAnimationFrame(() => {
        const sendBtn = document.querySelector(
          '[data-testid="send-button"]'
        );
        if (sendBtn) sendBtn.click();
      });
    }
    function title() {
      return document.title;
    }
    return { messages, lastResponse, isResponseComplete, send, title };
  }
  return setup;
})();
