var __browserPlugin = (function() {
  "use strict";
  function setup() {
    function isLoggedIn() {
      return document.querySelector('[data-testid="accounts-profile-button"]') !== null;
    }
    function currentModel() {
      var _a;
      const btn = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
      return ((_a = btn == null ? void 0 : btn.textContent) == null ? void 0 : _a.trim()) ?? null;
    }
    return { isLoggedIn, currentModel };
  }
  return setup;
})();
