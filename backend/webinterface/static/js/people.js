(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function csrfToken() {
    return getCookie('csrftoken');
  }

  function setFollowButtonState(btn, isFollowing, requestPending) {
    const following = !!isFollowing;
    const pending = !following && !!requestPending;
    btn.dataset.following = following ? '1' : '0';
    btn.dataset.pending = pending ? '1' : '0';
    btn.setAttribute('aria-pressed', following ? 'true' : 'false');
    if (following) {
      btn.textContent = 'Отписаться';
    } else if (pending) {
      btn.textContent = 'Запрос отправлен';
    } else {
      btn.textContent = 'Подписаться';
    }
    btn.classList.toggle('btn-brand', !following && !pending);
    btn.classList.toggle('btn-ghost', following || pending);
  }

  async function toggleFollow(btn) {
    const url = btn.dataset.followUrl;
    if (!url || btn.disabled) return;

    btn.disabled = true;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken() || '',
        },
        credentials: 'same-origin',
      });
      if (!response.ok) return;
      const data = await response.json();
      setFollowButtonState(btn, !!data.is_following, !!data.request_pending);

      const countEl = document.querySelector('[data-followers-count]');
      if (countEl && typeof data.followers_count === 'number') {
        countEl.textContent = String(data.followers_count);
      }
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener('click', function (event) {
    const btn = event.target.closest('.follow-btn');
    if (!btn) return;
    event.preventDefault();
    toggleFollow(btn);
  });

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function avatarLetter(name) {
    const ch = (name || '?').trim().charAt(0);
    return ch ? ch.toUpperCase() : '?';
  }

  function renderResult(item) {
    const photo = item.photo_url
      ? `<img src="${escapeHtml(item.photo_url)}" alt="">`
      : escapeHtml(avatarLetter(item.display_name));
    const following = !!item.is_following;
    const pending = !following && !!item.request_pending;
    const btnClass = following || pending ? 'btn-ghost' : 'btn-brand';
    let btnLabel = 'Подписаться';
    if (following) btnLabel = 'Отписаться';
    else if (pending) btnLabel = 'Запрос отправлен';

    return `
      <article class="flex items-center gap-3 rounded bg-white px-4 py-3 shadow-card">
        <a href="${escapeHtml(item.profile_url)}" class="avatar h-10 w-10 text-sm">${photo}</a>
        <div class="min-w-0 flex-1">
          <a href="${escapeHtml(item.profile_url)}"
             class="block truncate text-sm font-semibold text-ink hover:text-brand">
            ${escapeHtml(item.display_name)}
          </a>
        </div>
        <button type="button"
                class="follow-btn ${btnClass} text-xs sm:text-sm"
                data-follow-url="${escapeHtml(item.follow_url)}"
                data-following="${following ? '1' : '0'}"
                data-pending="${pending ? '1' : '0'}"
                aria-pressed="${following ? 'true' : 'false'}">
          ${btnLabel}
        </button>
      </article>
    `;
  }

  function initPeopleSearch(root) {
    const input = root.querySelector('[data-people-search-input]');
    const results = root.querySelector('[data-people-search-results]');
    const searchUrl = root.dataset.searchUrl;
    if (!input || !results || !searchUrl) return;

    let timer = null;
    let controller = null;

    function showEmpty(message) {
      results.innerHTML = `<p class="px-1 py-8 text-center text-sm text-ink-muted">${escapeHtml(message)}</p>`;
    }

    async function runSearch(query) {
      if (controller) controller.abort();
      controller = new AbortController();

      if (!query) {
        showEmpty('Начните вводить имя или email');
        return;
      }

      try {
        const url = searchUrl + (searchUrl.includes('?') ? '&' : '?') + 'q=' + encodeURIComponent(query);
        const response = await fetch(url, {
          headers: { Accept: 'application/json' },
          credentials: 'same-origin',
          signal: controller.signal,
        });
        if (!response.ok) return;
        const data = await response.json();
        const items = data.results || [];
        if (!items.length) {
          showEmpty('Никого не нашли');
          return;
        }
        results.innerHTML = items.map(renderResult).join('');
      } catch (err) {
        if (err && err.name === 'AbortError') return;
      }
    }

    input.addEventListener('input', function () {
      const q = input.value.trim();
      clearTimeout(timer);
      timer = setTimeout(function () {
        runSearch(q);
      }, 300);
    });
  }

  document.querySelectorAll('[data-people-search]').forEach(initPeopleSearch);

  function applyYearStats(root, stats) {
    if (!stats) return;
    const distance = root.querySelector('[data-stat-distance]');
    const duration = root.querySelector('[data-stat-duration]');
    const elevation = root.querySelector('[data-stat-elevation]');
    const count = root.querySelector('[data-stat-count]');
    if (distance) distance.textContent = stats.distance;
    if (duration) duration.textContent = stats.duration_display;
    if (elevation) elevation.textContent = stats.elevation;
    if (count) count.textContent = stats.count_display;
  }

  function setYearPressed(switcher, year) {
    switcher.querySelectorAll('[data-year]').forEach(function (el) {
      const pressed = String(el.dataset.year) === String(year);
      el.setAttribute('aria-pressed', pressed ? 'true' : 'false');
      el.classList.toggle('!bg-gray-100', pressed);
      el.classList.toggle('font-bold', pressed);
    });
  }

  function initYearStats(root) {
    let byYear = {};
    try {
      byYear = JSON.parse(root.dataset.yearStatsJson || '{}');
    } catch (err) {
      return;
    }

    const switcher = root.querySelector('[data-year-switcher]');
    if (!switcher) return;

    setYearPressed(switcher, root.dataset.selectedYear);

    switcher.addEventListener('click', function (event) {
      const btn = event.target.closest('[data-year]');
      if (!btn || !switcher.contains(btn)) return;
      const year = btn.dataset.year;
      const stats = byYear[year];
      if (!stats) return;

      root.dataset.selectedYear = year;
      setYearPressed(switcher, year);
      applyYearStats(root, stats);
    });
  }

  document.querySelectorAll('[data-year-stats]').forEach(initYearStats);
})();
