(function () {
  function activateTab(root, tabId) {
    root.querySelectorAll('[data-tab]').forEach(function (btn) {
      var active = btn.getAttribute('data-tab') === tabId;
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
      btn.classList.toggle('border-brand', active);
      btn.classList.toggle('text-brand', active);
      btn.classList.toggle('border-transparent', !active);
      btn.classList.toggle('text-ink-muted', !active);
    });
    root.querySelectorAll('[data-tab-panel]').forEach(function (panel) {
      var match = panel.getAttribute('data-tab-panel') === tabId;
      panel.classList.toggle('hidden', !match);
    });
  }

  document.querySelectorAll('[data-activity-tabs]').forEach(function (root) {
    root.addEventListener('click', function (event) {
      var btn = event.target.closest('[data-tab]');
      if (!btn || !root.contains(btn)) return;
      event.preventDefault();
      activateTab(root, btn.getAttribute('data-tab'));
    });
  });
})();
