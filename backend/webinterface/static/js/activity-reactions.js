(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function csrfToken() {
    return getCookie('csrftoken');
  }

  function closeAllPickers(except) {
    document.querySelectorAll('[data-reaction-picker]').forEach(function (picker) {
      if (except && picker === except) return;
      picker.hidden = true;
      const wrap = picker.closest('.activity-reactions');
      const toggle = wrap && wrap.querySelector('[data-reaction-toggle]');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    });
  }

  function updatePickerVisibility(root, mine) {
    const wrap = root.querySelector('[data-reaction-picker-wrap]');
    if (!wrap) return;
    const hasMine = !!mine;
    wrap.hidden = hasMine;
    wrap.classList.toggle('is-hidden', hasMine);
    if (hasMine) {
      const picker = wrap.querySelector('[data-reaction-picker]');
      const toggle = wrap.querySelector('[data-reaction-toggle]');
      if (picker) picker.hidden = true;
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    }
  }

  function renderChips(root, counts, mine) {
    const chipsEl = root.querySelector('[data-reaction-chips]');
    if (!chipsEl) return;

    chipsEl.innerHTML = '';
    (counts || []).forEach(function (item) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'reaction-chip' + (mine === item.emoji ? ' is-mine' : '');
      btn.dataset.emoji = item.emoji;
      btn.setAttribute('aria-pressed', mine === item.emoji ? 'true' : 'false');
      btn.innerHTML =
        '<span class="reaction-chip__emoji"></span>' +
        '<span class="reaction-chip__count"></span>';
      btn.querySelector('.reaction-chip__emoji').textContent = item.emoji;
      btn.querySelector('.reaction-chip__count').textContent = String(item.count);
      chipsEl.appendChild(btn);
    });

    root.querySelectorAll('.reaction-picker__btn').forEach(function (btn) {
      const isMine = mine === btn.dataset.emoji;
      btn.classList.toggle('is-mine', isMine);
    });

    updatePickerVisibility(root, mine);
  }

  async function sendReaction(root, emoji) {
    const url = root.dataset.reactUrl;
    if (!url || root.dataset.busy === '1') return;

    root.dataset.busy = '1';
    try {
      const body = new URLSearchParams();
      body.set('emoji', emoji);
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken() || '',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        },
        credentials: 'same-origin',
        body: body.toString(),
      });
      if (!response.ok) return;
      const data = await response.json();
      root.dataset.mine = data.mine || '';
      renderChips(root, data.counts || [], data.mine || null);
    } finally {
      root.dataset.busy = '0';
      closeAllPickers();
    }
  }

  document.addEventListener('click', function (event) {
    const toggle = event.target.closest('[data-reaction-toggle]');
    if (toggle) {
      event.preventDefault();
      const root = toggle.closest('.activity-reactions');
      const picker = root && root.querySelector('[data-reaction-picker]');
      if (!picker) return;
      const willOpen = picker.hidden;
      closeAllPickers(willOpen ? picker : null);
      picker.hidden = !willOpen;
      toggle.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
      return;
    }

    const emojiBtn = event.target.closest('[data-emoji]');
    if (emojiBtn && emojiBtn.closest('.activity-reactions')) {
      event.preventDefault();
      const root = emojiBtn.closest('.activity-reactions');
      const emoji = emojiBtn.dataset.emoji;
      if (emoji) sendReaction(root, emoji);
      return;
    }

    if (!event.target.closest('.activity-reactions__picker-wrap')) {
      closeAllPickers();
    }
  });
})();
