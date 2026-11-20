// Core: state, API client, safe templating, modal, toast, helpers.
export const state = {
  token: localStorage.getItem('gimble_token') || '',
  me: JSON.parse(localStorage.getItem('gimble_user') || 'null'),
  favs: new Set(),
  meta: null,
  unread: { n: 0, msgs: 0 },
  after: null, // function to run after a successful login
};

// ---------- safe HTML templating: every interpolated value is escaped unless wrapped in raw() ----------
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = s => new Raw(s);
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = s => String(s).replace(/[&<>"']/g, c => ESC[c]);
const part = v => v instanceof Raw ? v.s : Array.isArray(v) ? v.map(part).join('') : (v == null || v === false) ? '' : esc(v);
export function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += part(v) + strings[i + 1]; });
  return new Raw(out);
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ---------- tiny event bus ----------
const handlers = {};
export const on = (ev, fn) => (handlers[ev] ||= []).push(fn);
export const emit = (ev, data) => (handlers[ev] || []).forEach(fn => fn(data));

// ---------- API ----------
export class ApiError extends Error { constructor(msg, status) { super(msg); this.status = status; } }
export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  if (state.token) headers.Authorization = 'Bearer ' + state.token;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res;
  try { res = await fetch('/api' + path, { method, headers, body: payload }); }
  catch { throw new ApiError('Network error - please check your connection.', 0); }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map(e => (e.msg || '').replace(/^Value error, /, '')).join('; ');
    if (res.status === 401 && state.token) { clearAuth(); toast('Your session expired. Please log in again.', 'error'); }
    throw new ApiError(msg || `Request failed (${res.status})`, res.status);
  }
  return data;
}

export function setAuth(data) {
  state.token = data.access_token; state.me = data.user;
  localStorage.setItem('gimble_token', state.token);
  localStorage.setItem('gimble_user', JSON.stringify(state.me));
  emit('auth'); emit('authchange');
}
export function clearAuth() {
  state.token = ''; state.me = null; state.favs = new Set(); state.unread = { n: 0, msgs: 0 };
  localStorage.removeItem('gimble_token'); localStorage.removeItem('gimble_user');
  emit('auth'); emit('authchange');
}
export async function refreshMe() {
  if (!state.token) return;
  try {
    state.me = await api('/auth/me');
    localStorage.setItem('gimble_user', JSON.stringify(state.me));
    if (state.me.role === 'customer') state.favs = new Set(await api('/favorites/ids'));
  } catch { /* api() already handled 401 */ }
  emit('auth');
}

// ---------- toast ----------
export function toast(msg, type = 'info') {
  const box = $('#toasts');
  const el = document.createElement('div');
  el.className = 'toast ' + type; el.setAttribute('role', type === 'error' ? 'alert' : 'status');
  const ico = document.createElement('span'); ico.className = 't-ico'; ico.textContent = type === 'ok' ? '✓' : type === 'error' ? '!' : 'i';
  const txt = document.createElement('span'); txt.textContent = msg;
  el.append(ico, txt); box.append(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 250); }, type === 'error' ? 5200 : 3000);
}

// ---------- modal ----------
let lastFocus = null;
export function openModal(content, { label = 'Dialog', wide = false } = {}) {
  lastFocus = document.activeElement;
  const root = $('#modal-root');
  root.innerHTML = html`<div class="backdrop" data-action="modal-backdrop"><div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-label="${label}"><button class="modal-x" data-action="close-modal" aria-label="Close">×</button><div class="modal-body">${content}</div></div></div>`.s;
  document.body.classList.add('no-scroll');
  const first = $('input:not([type=hidden]),textarea,select,.btn.primary', root);
  if (first) setTimeout(() => first.focus(), 30);
  return root;
}
export function closeModal() {
  $('#modal-root').innerHTML = ''; document.body.classList.remove('no-scroll');
  if (lastFocus && lastFocus.focus) lastFocus.focus();
}
export const modalOpen = () => !!$('#modal-root .modal');

/** Ask for a short text (e.g. a cancellation reason). Resolves with the string or null if dismissed. */
export function askText({ title, label, required = false, placeholder = '', confirm = 'Confirm', danger = false }) {
  return new Promise(resolve => {
    openModal(html`<h2>${title}</h2><label class="lbl" for="ask-input">${label}</label><textarea class="field" id="ask-input" rows="3" maxlength="300" placeholder="${placeholder}"></textarea><p class="err" id="ask-err" hidden></p><div class="row end"><button class="btn ghost" id="ask-no">Back</button><button class="btn ${danger ? 'danger' : 'primary'}" id="ask-yes">${confirm}</button></div>`, { label: title });
    const done = v => { closeModal(); resolve(v); };
    $('#ask-no').onclick = () => done(null);
    $('#ask-yes').onclick = () => {
      const v = $('#ask-input').value.trim();
      if (required && !v) { const e = $('#ask-err'); e.textContent = 'Please enter a short reason.'; e.hidden = false; return; }
      done(v);
    };
  });
}
export function confirmBox({ title, text, confirm = 'Confirm', danger = false }) {
  return new Promise(resolve => {
    openModal(html`<h2>${title}</h2><p class="muted">${text}</p><div class="row end"><button class="btn ghost" id="c-no">Cancel</button><button class="btn ${danger ? 'danger' : 'primary'}" id="c-yes">${confirm}</button></div>`, { label: title });
    $('#c-no').onclick = () => { closeModal(); resolve(false); };
    $('#c-yes').onclick = () => { closeModal(); resolve(true); };
  });
}

// ---------- delegated actions / forms ----------
export const actions = {};
export const submits = {};
document.addEventListener('click', e => {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const name = el.dataset.action;
  if (name === 'modal-backdrop') { if (e.target === el) closeModal(); return; }
  if (name === 'close-modal') { closeModal(); return; }
  if (actions[name]) { if (el.tagName === 'A' && !el.getAttribute('href')) e.preventDefault(); actions[name](el, e); }
});
document.addEventListener('submit', e => {
  const f = e.target.closest('form[data-submit]');
  if (!f) return;
  e.preventDefault();
  const fn = submits[f.dataset.submit];
  if (fn) busy(f.querySelector('button[type=submit]'), () => fn(f));
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && modalOpen()) closeModal(); });

/** Disable a button while an async job runs (prevents double submits). */
export async function busy(btn, fn) {
  if (btn) { if (btn.disabled) return; btn.disabled = true; btn.dataset.label = btn.textContent; btn.textContent = 'Please wait…'; }
  try { return await fn(); }
  catch (e) { toast(e.message || 'Something went wrong', 'error'); }
  finally { if (btn && btn.isConnected) { btn.disabled = false; btn.textContent = btn.dataset.label; } }
}
export const formObj = f => Object.fromEntries(new FormData(f).entries());

// ---------- formatting ----------
export const inr = n => '₹' + Number(n).toLocaleString('en-IN');
export const fmtDT = iso => new Date(iso).toLocaleString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
export const fmtD = iso => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
export function ago(iso) {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}
export const hue = name => ([...String(name)].reduce((a, c) => a + c.charCodeAt(0), 0) * 37) % 360;
export const initials = name => String(name).trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();
export const stars = r => '★'.repeat(Math.round(r)) + '☆'.repeat(5 - Math.round(r));
export function photo(p, cls = '') {
  return p.photo_url
    ? html`<img class="${cls}" src="${p.photo_url}" alt="${p.name}" loading="lazy">`
    : html`<div class="ph ${cls}" style="--h:${hue(p.name)}" aria-label="${p.name}"><span>${initials(p.name)}</span></div>`;
}
export const isCustomer = () => state.me && state.me.role === 'customer';

/** Run `fn` now if logged in, otherwise open login and run it after success. */
export function requireLogin(fn, openAuth) {
  if (state.me) return fn();
  state.after = fn;
  openAuth('login');
}

// ---------- Razorpay checkout (shared by membership and booking payments) ----------
const _scripts = {};
export const loadScript = src => _scripts[src] ||= new Promise((res, rej) => {
  const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('Could not load the payment window.')); document.head.append(s);
});
/** Poll our server until the order is paid (UPI: the customer may pay inside GPay/PhonePe/Paytm and come back
 *  to a suspended tab, in which case Razorpay's JS callback never fires). Resolves true if paid. */
async function waitForPayment(orderId, { tries = 40, every = 3000 } = {}) {
  for (let i = 0; i < tries; i++) {
    try { if ((await api(`/payments/orders/${encodeURIComponent(orderId)}`)).status === 'paid') return true; } catch { /* keep trying */ }
    await new Promise(r => setTimeout(r, every));
  }
  return false;
}

export async function openRazorpay(co, onSuccess) {
  await loadScript('https://checkout.razorpay.com/v1/checkout.js');
  let settled = false;
  const finish = async resp => {
    if (settled) return; settled = true;
    try { await onSuccess(resp); } catch (e) { toast(e.message + ' If you were charged, this will be confirmed automatically within a few minutes.', 'error'); }
  };
  const rzp = new window.Razorpay({ key: co.key_id, amount: co.amount, currency: co.currency, name: co.name, description: co.description,
    order_id: co.order_id, prefill: co.prefill, theme: { color: '#6a3dff' }, retry: { enabled: true, max_count: 3 },
    // UPI first (on phones Checkout opens the installed UPI app via intent); cards / netbanking / wallets stay available.
    config: { display: { blocks: { upi: { name: 'Pay with UPI', instruments: [{ method: 'upi' }] } }, sequence: ['block.upi'], preferences: { show_default_blocks: true } } },
    handler: finish,
    modal: { confirm_close: true, ondismiss: async () => {
      if (settled) return;
      // Closed without a callback: the payment may still have gone through in the UPI app. Check before giving up.
      toast('Checking your payment status…', 'info');
      if (await waitForPayment(co.order_id, { tries: 10 })) await finish(null);
    } } });
  rzp.on('payment.failed', r => toast((r?.error?.description || 'Payment failed') + '. You have not been charged. Please try again.', 'error'));
  rzp.open();
  // Mobile UPI intent backgrounds this tab; if the callback never arrives, notice the payment via the server.
  document.addEventListener('visibilitychange', async function onVis() {
    if (settled) return document.removeEventListener('visibilitychange', onVis);
    if (document.visibilityState === 'visible' && await waitForPayment(co.order_id, { tries: 5, every: 2000 })) { document.removeEventListener('visibilitychange', onVis); await finish(null); }
  });
}

// ---------- shared UI building blocks ----------
export function avatar(name, photoUrl, cls = '') {
  return photoUrl ? html`<img class="av-img ${cls}" src="${photoUrl}" alt="" loading="lazy">` : html`<span class="av-ph ${cls}" style="--h:${hue(name)}">${initials(name)}</span>`;
}
export const emptyState = ({ icon = '✨', title, text = '', cta = '' }) => html`<div class="empty4"><div class="e-art">${icon}</div><h3>${title}</h3><p class="muted">${text}</p>${cta}</div>`;

/** "2d 4h", "3h 20m", "25m" until an ISO time (empty string if in the past). */
export function timeUntil(iso) {
  const ms = new Date(iso) - Date.now(); if (ms <= 0) return '';
  const m = Math.floor(ms / 60000), d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m % 60}m` : `${m}m`;
}
export const mapsUrl = q => 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(q);

/** Download an .ics calendar file for a booking (works in Google/Apple/Outlook calendars). */
export function downloadICS(b, withName) {
  const z = d => new Date(d).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
  const start = new Date(b.scheduled_at), end = new Date(start.getTime() + b.duration_minutes * 60000);
  const esc = s => String(s).replace(/([,;\\])/g, '\\$1').replace(/\n/g, '\\n');
  const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Gimble//EN', 'BEGIN:VEVENT', `UID:gimble-${b.id}@gimble`, `DTSTAMP:${z(Date.now())}`, `DTSTART:${z(start)}`, `DTEND:${z(end)}`,
    `SUMMARY:${esc(b.activity + ' with ' + withName)}`, `LOCATION:${esc(b.location)}`, `DESCRIPTION:${esc('Booked on Gimble. Meet in a public place and keep payments on Gimble.')}`, 'BEGIN:VALARM', 'TRIGGER:-PT1H', 'ACTION:DISPLAY', 'DESCRIPTION:Your plan starts in 1 hour', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([ics], { type: 'text/calendar' })); a.download = `gimble-plan-${b.id}.ics`;
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
