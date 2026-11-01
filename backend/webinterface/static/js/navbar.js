(function () {
  function closeMenu(menu) {
    const toggle = menu.querySelector('[data-user-menu-toggle]');
    const panel = menu.querySelector('[data-user-menu-panel]');
    const chevron = menu.querySelector('[data-user-menu-chevron]');
    if (!toggle || !panel) return;
    panel.classList.add('hidden');
    toggle.setAttribute('aria-expanded', 'false');
    if (chevron) chevron.classList.remove('rotate-180');
  }

  function openMenu(menu) {
    const toggle = menu.querySelector('[data-user-menu-toggle]');
    const panel = menu.querySelector('[data-user-menu-panel]');
    const chevron = menu.querySelector('[data-user-menu-chevron]');
    if (!toggle || !panel) return;
    panel.classList.remove('hidden');
    toggle.setAttribute('aria-expanded', 'true');
    if (chevron) chevron.classList.add('rotate-180');
  }

  function toggleMenu(menu) {
    const panel = menu.querySelector('[data-user-menu-panel]');
    if (!panel) return;
    if (panel.classList.contains('hidden')) {
      openMenu(menu);
    } else {
      closeMenu(menu);
    }
  }

  document.addEventListener('click', function (event) {
    const menus = document.querySelectorAll('[data-user-menu]');
    menus.forEach(function (menu) {
      const toggle = menu.querySelector('[data-user-menu-toggle]');
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
    document.querySelectorAll('[data-user-menu]').forEach(closeMenu);
  });
})();
