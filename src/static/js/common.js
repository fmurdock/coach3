/* Coach3 Shared Frontend Utilities (CSP-Compliant, XSS-Safe, Non-HTTPS LAN Safe) */
(function (global) {
  'use strict';

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Safe markdown renderer: escapes ALL raw HTML first, then applies minimal
   * block/inline markdown formatting so injected tags/scripts can never execute.
   */
  function formatMarkdown(text) {
    if (!text) return '';
    const escaped = escapeHtml(text);
    const lines = escaped.split(/\r?\n/);
    const out = [];
    let inList = false;

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      const bulletMatch = line.match(/^\s*[-*]\s+(.+)$/);
      if (bulletMatch) {
        if (!inList) {
          out.push('<ul>');
          inList = true;
        }
        out.push('<li>' + applyInlineMarkdown(bulletMatch[1]) + '</li>');
        continue;
      }
      if (inList) {
        out.push('</ul>');
        inList = false;
      }
      if (/^###\s+(.+)$/.test(line)) {
        out.push('<h3>' + applyInlineMarkdown(line.replace(/^###\s+/, '')) + '</h3>');
      } else if (/^##\s+(.+)$/.test(line)) {
        out.push('<h2>' + applyInlineMarkdown(line.replace(/^##\s+/, '')) + '</h2>');
      } else if (/^#\s+(.+)$/.test(line)) {
        out.push('<h1>' + applyInlineMarkdown(line.replace(/^#\s+/, '')) + '</h1>');
      } else if (line.trim() === '') {
        out.push('<br />');
      } else {
        out.push('<p>' + applyInlineMarkdown(line) + '</p>');
      }
    }
    if (inList) out.push('</ul>');
    return out.join('\n');
  }

  function applyInlineMarkdown(safeStr) {
    return safeStr
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  /**
   * Generates a UUID v4 that works in both HTTPS secure contexts and plain HTTP LAN contexts.
   */
  function safeUUID() {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /**
   * Copies text to clipboard with fallback for non-HTTPS LAN origins where navigator.clipboard is undefined.
   */
  async function safeCopy(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } finally {
      document.body.removeChild(ta);
    }
    return ok;
  }

  function ensureToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(message, type) {
    const container = ensureToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type || 'info'}`;
    toast.textContent = String(message || '');
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4200);
  }

  async function authFetch(url, options) {
    const res = await fetch(url, options);
    if (res.status === 401 && window.location.pathname !== '/login') {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?next=${next}`;
    }
    return res;
  }

  async function initSignOutButton() {
    const btn = document.getElementById('btn-signout');
    if (!btn) return;
    try {
      const res = await fetch('/api/v1/auth/status');
      if (res.ok) {
        const st = await res.json();
        if (st.auth_required && st.authenticated && !st.localhost_bypass_active) {
          btn.style.display = 'inline-flex';
        }
      }
    } catch (_) {
      // Ignore network errors on status check
    }
    btn.addEventListener('click', async () => {
      await fetch('/api/v1/auth/logout', { method: 'POST' });
      window.location.href = '/login';
    });
  }

  document.addEventListener('DOMContentLoaded', initSignOutButton);

  global.Coach3 = {
    escapeHtml,
    formatMarkdown,
    safeUUID,
    safeCopy,
    showToast,
    authFetch,
  };
})(window);

