(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function csrfToken() {
    return getCookie('csrftoken');
  }

  function formatDate(iso) {
    if (!iso) return '';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    const day = String(date.getDate()).padStart(2, '0');
    const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
    const month = months[date.getMonth()] || '';
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return day + ' ' + month + ' ' + year + ', ' + hours + ':' + minutes;
  }

  function actionUrl(root, commentId) {
    const template = root.dataset.actionUrlTemplate || '';
    return template.replace(/\/0\/?$/, '/' + commentId + '/');
  }

  function profileUrl(root, profileId) {
    const template = root.dataset.profileUrlTemplate || '';
    return template.replace(/\/0\/?$/, '/' + profileId + '/');
  }

  async function requestJson(url, body) {
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
    let data = {};
    try {
      data = await response.json();
    } catch (err) {
      data = {};
    }
    if (!response.ok) {
      const error = new Error((data && data.error) || 'Ошибка запроса');
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function setError(root, message) {
    const el = root.querySelector('[data-comment-error]');
    if (!el) return;
    if (message) {
      el.textContent = message;
      el.classList.remove('hidden');
    } else {
      el.textContent = '';
      el.classList.add('hidden');
    }
  }

  function removeEmptyState(list) {
    const empty = list.querySelector('[data-comments-empty]');
    if (empty) empty.remove();
  }

  function ensureEmptyState(list) {
    if (list.querySelector('[data-comment-id]')) return;
    if (list.querySelector('[data-comments-empty]')) return;
    const p = document.createElement('p');
    p.className = 'text-sm text-ink-muted';
    p.dataset.commentsEmpty = '';
    p.textContent = 'Пока нет комментариев.';
    list.appendChild(p);
  }

  function fillCommentNode(root, node, comment) {
    node.dataset.commentId = String(comment.id);
    node.dataset.canEdit = comment.can_edit ? '1' : '0';
    node.dataset.canDelete = comment.can_delete ? '1' : '0';

    const avatar = node.querySelector('[data-comment-avatar]');
    const initial = node.querySelector('[data-comment-avatar-initial]');
    if (avatar) {
      avatar.href = profileUrl(root, comment.profile.id);
      const existingImg = avatar.querySelector('img');
      if (existingImg) existingImg.remove();
      if (comment.profile.photo_url) {
        const img = document.createElement('img');
        img.src = comment.profile.photo_url;
        img.alt = '';
        avatar.appendChild(img);
        if (initial) initial.hidden = true;
      } else if (initial) {
        initial.hidden = false;
        initial.textContent = comment.profile.initial || '?';
      }
    }

    const author = node.querySelector('[data-comment-author]');
    if (author) {
      author.href = profileUrl(root, comment.profile.id);
      author.textContent = comment.profile.display_name || '';
    }

    const time = node.querySelector('[data-comment-time]');
    if (time) {
      time.setAttribute('datetime', comment.created_at || '');
      let label = formatDate(comment.created_at);
      if (comment.updated_at && comment.updated_at !== comment.created_at) {
        label += ' · изменён';
      }
      time.textContent = label;
    }

    const textEl = node.querySelector('[data-comment-text]');
    if (textEl) textEl.textContent = comment.text || '';

    const editInput = node.querySelector('[data-comment-edit-input]');
    if (editInput) {
      editInput.maxLength = Number(root.dataset.maxLength || 2000);
      editInput.value = comment.text || '';
    }

    const editBtn = node.querySelector('[data-comment-edit]');
    const deleteBtn = node.querySelector('[data-comment-delete]');
    if (editBtn) editBtn.hidden = !comment.can_edit;
    if (deleteBtn) deleteBtn.hidden = !comment.can_delete;

    const actions = node.querySelector('[data-comment-actions]');
    if (actions) {
      actions.hidden = !(comment.can_edit || comment.can_delete);
    }

    const editForm = node.querySelector('[data-comment-edit-form]');
    if (editForm) editForm.classList.add('hidden');
    if (textEl) textEl.classList.remove('hidden');
    if (actions) actions.classList.remove('hidden');
  }

  function buildCommentNode(root, comment) {
    const template = document.getElementById('activity-comment-template');
    if (!template) return null;
    const node = template.content.firstElementChild.cloneNode(true);
    fillCommentNode(root, node, comment);
    return node;
  }

  function showEdit(node) {
    const textEl = node.querySelector('[data-comment-text]');
    const actions = node.querySelector('[data-comment-actions]');
    const editForm = node.querySelector('[data-comment-edit-form]');
    const editInput = node.querySelector('[data-comment-edit-input]');
    if (textEl) textEl.classList.add('hidden');
    if (actions) actions.classList.add('hidden');
    if (editForm) editForm.classList.remove('hidden');
    if (editInput) {
      editInput.value = textEl ? textEl.textContent : '';
      editInput.focus();
    }
  }

  function hideEdit(node) {
    const textEl = node.querySelector('[data-comment-text]');
    const actions = node.querySelector('[data-comment-actions]');
    const editForm = node.querySelector('[data-comment-edit-form]');
    if (editForm) editForm.classList.add('hidden');
    if (textEl) textEl.classList.remove('hidden');
    if (actions) actions.classList.remove('hidden');
  }

  function initComments(root) {
    const list = root.querySelector('[data-comments-list]');
    const form = root.querySelector('[data-comment-form]');
    const input = root.querySelector('[data-comment-input]');
    if (!list || !form || !input) return;

    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (root.dataset.busy === '1') return;
      const text = input.value.trim();
      if (!text) {
        setError(root, 'Введите текст комментария');
        return;
      }
      setError(root, '');
      root.dataset.busy = '1';
      try {
        const body = new URLSearchParams();
        body.set('text', text);
        const data = await requestJson(root.dataset.createUrl, body);
        removeEmptyState(list);
        const node = buildCommentNode(root, data.comment);
        if (node) list.appendChild(node);
        input.value = '';
      } catch (err) {
        setError(root, err.message || 'Не удалось отправить комментарий');
      } finally {
        root.dataset.busy = '0';
      }
    });

    list.addEventListener('click', async function (event) {
      const commentNode = event.target.closest('[data-comment-id]');
      if (!commentNode || !list.contains(commentNode)) return;

      if (event.target.closest('[data-comment-edit]')) {
        event.preventDefault();
        showEdit(commentNode);
        return;
      }

      if (event.target.closest('[data-comment-cancel]')) {
        event.preventDefault();
        hideEdit(commentNode);
        return;
      }

      if (event.target.closest('[data-comment-save]')) {
        event.preventDefault();
        if (root.dataset.busy === '1') return;
        const editInput = commentNode.querySelector('[data-comment-edit-input]');
        const text = editInput ? editInput.value.trim() : '';
        if (!text) {
          setError(root, 'Введите текст комментария');
          return;
        }
        setError(root, '');
        root.dataset.busy = '1';
        try {
          const body = new URLSearchParams();
          body.set('action', 'edit');
          body.set('text', text);
          const data = await requestJson(actionUrl(root, commentNode.dataset.commentId), body);
          fillCommentNode(root, commentNode, data.comment);
        } catch (err) {
          setError(root, err.message || 'Не удалось сохранить комментарий');
        } finally {
          root.dataset.busy = '0';
        }
        return;
      }

      if (event.target.closest('[data-comment-delete]')) {
        event.preventDefault();
        if (root.dataset.busy === '1') return;
        if (!window.confirm('Удалить комментарий?')) return;
        setError(root, '');
        root.dataset.busy = '1';
        try {
          const body = new URLSearchParams();
          body.set('action', 'delete');
          await requestJson(actionUrl(root, commentNode.dataset.commentId), body);
          commentNode.remove();
          ensureEmptyState(list);
        } catch (err) {
          setError(root, err.message || 'Не удалось удалить комментарий');
        } finally {
          root.dataset.busy = '0';
        }
      }
    });
  }

  document.querySelectorAll('.activity-comments').forEach(initComments);
})();
