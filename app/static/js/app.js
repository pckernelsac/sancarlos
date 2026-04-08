/**
 * app.js — utilidades globales
 */

// Toast global
window.showToast = function (msg, ok = true) {
  const toast = document.getElementById('toast');
  const body  = document.getElementById('toast-body');
  if (!toast || !body) return;
  body.textContent = msg;
  body.className = `px-5 py-3 rounded-lg shadow-lg text-white text-sm font-medium ${ok ? 'bg-green-600' : 'bg-red-600'}`;
  toast.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.add('hidden'), 3000);
};

// Añade X-CSRFToken a todos los fetch automáticamente
const _originalFetch = window.fetch;
window.fetch = function (url, opts = {}) {
  const token = document.querySelector('meta[name="csrf-token"]')?.content
    || document.querySelector('input[name="csrf_token"]')?.value;
  if (token && opts.method && opts.method.toUpperCase() !== 'GET') {
    opts.headers = opts.headers || {};
    if (!opts.headers['X-CSRFToken']) {
      opts.headers['X-CSRFToken'] = token;
    }
  }
  return _originalFetch(url, opts);
};
