(function () {
  var root = document.documentElement;

  // ── theme ──
  function applyTheme(t) {
    root.setAttribute('data-theme', t);
    document.querySelectorAll('[data-theme-toggle] i').forEach(function (i) {
      i.className = 'bi ' + (t === 'dark' ? 'bi-sun' : 'bi-moon-stars');
    });
  }
  applyTheme(root.getAttribute('data-theme') || 'dark');
  document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('beamer-theme', t); } catch (e) {}
      applyTheme(t);
    });
  });

  // ── toast ──
  window.toast = function (msg, type) {
    var zone = document.getElementById('toast-zone');
    if (!zone) return;
    var el = document.createElement('div');
    el.className = 'toast ' + (type || 'info');
    el.innerHTML = '<span class="dot"></span><span></span>';
    el.lastChild.textContent = msg;
    zone.appendChild(el);
    setTimeout(function () {
      el.style.transition = 'opacity .3s'; el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 300);
    }, 2600);
  };
  document.querySelectorAll('#toast-zone .toast').forEach(function (el) {
    setTimeout(function () { el.style.transition = 'opacity .3s'; el.style.opacity = '0'; setTimeout(function () { el.remove(); }, 300); }, 3800);
  });

  // ── copy ──
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) {}
    ta.remove(); return ok;
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var text = btn.getAttribute('data-copy');
    var done = function (ok) {
      if (!ok) return window.toast('Could not copy', 'danger');
      var icon = btn.querySelector('i'), old = icon.className;
      icon.className = 'bi bi-check2'; btn.classList.add('copied');
      window.toast('Link copied', 'success');
      setTimeout(function () { icon.className = old; btn.classList.remove('copied'); }, 1500);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); });
    } else { done(fallbackCopy(text)); }
  });

  // ── favourite ──
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.fav-btn');
    if (!btn) return;
    var meta = document.querySelector('meta[name="csrf-token"]');
    fetch('/fav/' + btn.dataset.id, { method: 'POST', headers: { 'X-CSRF-Token': meta ? meta.content : '' } })
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (d) {
        btn.classList.toggle('on', d.fav);
        btn.querySelector('i').className = 'bi ' + (d.fav ? 'bi-star-fill' : 'bi-star');
        btn.title = d.fav ? 'Remove favourite' : 'Add to favourites';
        if (!d.fav && btn.closest('[data-favs-only]')) {
          var c = btn.closest('.lcard'); if (c) c.remove();
        }
      })
      .catch(function () { window.toast('Could not update favourite', 'danger'); });
  });

  // ── mobile drawer ──
  var menu = document.getElementById('menu-btn');
  if (menu) {
    menu.addEventListener('click', function () { document.body.classList.toggle('nav-open'); });
    document.querySelectorAll('.scrim').forEach(function (s) {
      s.addEventListener('click', function () { document.body.classList.remove('nav-open'); });
    });
  }

  // ── confirm dialogs ──
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-confirm]');
    if (!b) return;
    var dlg = document.getElementById('confirm-dialog');
    dlg.querySelector('h3').textContent = b.dataset.confirmTitle || 'Are you sure?';
    dlg.querySelector('p').textContent = b.dataset.confirm;
    dlg.querySelector('form').action = b.dataset.action;
    dlg.showModal();
  });
  document.querySelectorAll('[data-close]').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('dialog').close(); });
  });

  // ── reset password dialog ──
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-reset]');
    if (!b) return;
    var dlg = document.getElementById('reset-dialog');
    dlg.querySelector('[data-name]').textContent = b.dataset.name;
    dlg.querySelector('form').action = b.dataset.action;
    dlg.showModal();
  });

  // ── show/hide password ──
  document.querySelectorAll('[data-pw-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var inp = b.parentElement.querySelector('input');
      var show = inp.type === 'password';
      inp.type = show ? 'text' : 'password';
      b.querySelector('i').className = 'bi ' + (show ? 'bi-eye-slash' : 'bi-eye');
    });
  });

  // ── debounced search ──
  var si = document.getElementById('search-input');
  if (si) {
    var t;
    si.addEventListener('input', function () {
      clearTimeout(t);
      t = setTimeout(function () { si.form.submit(); }, 400);
    });
  }

  // ── edit member dialog ──
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-edit]');
    if (!b) return;
    var dlg = document.getElementById('edit-dialog');
    dlg.querySelector('#e-name').value = b.dataset.name;
    dlg.querySelector('#e-emp').value = b.dataset.emp;
    dlg.querySelector('form').action = b.dataset.action;
    dlg.showModal();
  });

  // ── auto-submit filters ──
  document.querySelectorAll('[data-autosubmit]').forEach(function (el) {
    el.addEventListener('change', function () { el.form.submit(); });
  });

  // ── prevent double submit ──
  document.querySelectorAll('form[data-once]').forEach(function (f) {
    f.addEventListener('submit', function () {
      var b = f.querySelector('button[type=submit]');
      if (b) setTimeout(function () { b.disabled = true; }, 0);
    });
  });
})();
