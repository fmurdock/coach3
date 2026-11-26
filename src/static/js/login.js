(function () {
  'use strict';

  const form = document.getElementById('login-form');
  const input = document.getElementById('passphrase');
  const submitBtn = document.getElementById('login-submit');
  const errBox = document.getElementById('login-error');

  function showError(msg) {
    errBox.textContent = msg;
    errBox.style.display = 'block';
  }

  function safeNextUrl() {
    const params = new URLSearchParams(window.location.search);
    const next = params.get('next');
    if (next && next.startsWith('/') && !next.startsWith('//')) {
      return next;
    }
    return '/dashboard';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.style.display = 'none';
    const passphrase = input.value;
    if (!passphrase) return;

    submitBtn.disabled = true;
    submitBtn.textContent = 'Signing in...';
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passphrase }),
      });
      if (res.ok) {
        window.location.href = safeNextUrl();
        return;
      }
      const data = await res.json().catch(() => ({}));
      showError(data.detail || 'Authentication failed.');
    } catch (_) {
      showError('Unable to reach server. Check your network connection.');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Sign In';
    }
  });
})();

