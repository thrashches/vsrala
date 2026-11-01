(function () {
  function closeMenu(menu) {
    var toggle = menu.querySelector('[data-activity-menu-toggle]');
    var panel = menu.querySelector('[data-activity-menu-panel]');
    if (!toggle || !panel) return;
    panel.classList.add('hidden');
    toggle.setAttribute('aria-expanded', 'false');
  }

  function openMenu(menu) {
    var toggle = menu.querySelector('[data-activity-menu-toggle]');
    var panel = menu.querySelector('[data-activity-menu-panel]');
    if (!toggle || !panel) return;
    panel.classList.remove('hidden');
    toggle.setAttribute('aria-expanded', 'true');
  }

  function toggleMenu(menu) {
    var panel = menu.querySelector('[data-activity-menu-panel]');
    if (!panel) return;
    if (panel.classList.contains('hidden')) {
      openMenu(menu);
    } else {
      closeMenu(menu);
    }
  }

  document.addEventListener('click', function (event) {
    document.querySelectorAll('[data-activity-menu]').forEach(function (menu) {
      var toggle = menu.querySelector('[data-activity-menu-toggle]');
      if (toggle && toggle.contains(event.target)) {
        event.preventDefault();
        toggleMenu(menu);
        return;
      }
      if (!menu.contains(event.target)) {
        closeMenu(menu);
      }
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('[data-activity-menu]').forEach(closeMenu);
  });
})();
