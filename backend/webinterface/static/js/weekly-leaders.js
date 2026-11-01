(function () {
  const root = document.getElementById('weekly-leaders');
  if (!root) return;

  const apiUrl = root.dataset.apiUrl;
  const profileUrlTemplate = root.dataset.profileUrlTemplate || '';
  const labelEl = root.querySelector('[data-week-label]');
  const listEl = root.querySelector('[data-leaders-list]');

  const state = {
    week: 'current',
    metric: 'distance',
    sport: '',
  };

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function profileUrl(profileId) {
    return profileUrlTemplate.replace(/0\/?$/, String(profileId) + '/');
  }

  function setPressed(groupAttr, value) {
    root.querySelectorAll('[' + groupAttr + ']').forEach(function (btn) {
      const pressed = String(btn.getAttribute(groupAttr)) === String(value);
      btn.setAttribute('aria-pressed', pressed ? 'true' : 'false');
      btn.classList.toggle('!bg-gray-100', pressed);
      btn.classList.toggle('font-bold', pressed);
    });
  }

  function syncPressed() {
    setPressed('data-week', state.week);
    setPressed('data-metric', state.metric);
    setPressed('data-sport', state.sport);
  }

  function renderLeaders(leaders) {
    if (!leaders.length) {
      listEl.innerHTML =
        '<li data-empty class="py-4 text-center text-sm text-ink-muted">Нет тренировок за эту неделю</li>';
      return;
    }

    listEl.innerHTML = leaders
      .map(function (row) {
        const url = escapeHtml(profileUrl(row.profile_id));
        const name = escapeHtml(row.display_name);
        const total = escapeHtml(row.total_display);
        const avatar = row.photo_url
          ? '<img src="' + escapeHtml(row.photo_url) + '" alt="">'
          : escapeHtml(row.initial || '?');
        return (
          '<li class="flex items-center gap-2">' +
          '<span class="w-5 shrink-0 text-center text-xs font-bold text-ink-muted">' +
          escapeHtml(row.rank) +
          '</span>' +
          '<a href="' +
          url +
          '" class="avatar h-8 w-8 shrink-0 text-xs">' +
          avatar +
          '</a>' +
          '<a href="' +
          url +
          '" class="min-w-0 flex-1 truncate text-sm font-medium hover:text-brand">' +
          name +
          '</a>' +
          '<span class="shrink-0 text-sm font-semibold tabular-nums">' +
          total +
          '</span>' +
          '</li>'
        );
      })
      .join('');
  }

  let requestId = 0;

  async function load() {
    if (!apiUrl) return;
    const id = ++requestId;
    const params = new URLSearchParams({
      week: state.week,
      metric: state.metric,
    });
    if (state.sport) params.set('sport', state.sport);

    try {
      const response = await fetch(apiUrl + '?' + params.toString(), {
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok || id !== requestId) return;
      const data = await response.json();
      if (id !== requestId) return;
      if (labelEl && data.week_label) labelEl.textContent = data.week_label;
      renderLeaders(data.leaders || []);
    } catch (e) {
      /* ignore network errors */
    }
  }

  root.addEventListener('click', function (event) {
    const btn = event.target.closest('button[data-week], button[data-metric], button[data-sport]');
    if (!btn || !root.contains(btn)) return;

    if (btn.hasAttribute('data-week')) {
      state.week = btn.getAttribute('data-week');
    } else if (btn.hasAttribute('data-metric')) {
      state.metric = btn.getAttribute('data-metric');
    } else if (btn.hasAttribute('data-sport')) {
      state.sport = btn.getAttribute('data-sport') || '';
    }

    syncPressed();
    load();
  });

  syncPressed();
})();
