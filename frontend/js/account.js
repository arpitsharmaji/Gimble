import { html, raw, api, state, $, $$, openModal, closeModal, toast, actions, submits, formObj, inr, fmtDT, fmtD, ago, photo, isCustomer, askText, confirmBox, busy, clearAuth, refreshMe } from './core.js';
import { openAuth } from './auth.js';
import { openMembership, startBooking } from './discover.js';
import { reportModal, safetyModal, blockUser, CATEGORIES } from './safety.js';

export const timers = [];
export const stopTimers = () => { while (timers.length) clearInterval(timers.pop()); };
const needLogin = root => { root.innerHTML = html`<div class="page narrow center"><h1>Please log in</h1><p class="muted">Log in to see this page.</p><button class="btn primary" data-action="auth-login">Log in</button></div>`.s; };
const pill = s => html`<span class="pill ${s}">${s}</span>`;

// ====================== SAVED ======================
export async function savedPage(root) {
  if (!state.me) return needLogin(root);
  root.innerHTML = '<div class="page"><h1>Saved</h1><div class="skeleton"></div></div>';
  try {
    const rows = await api('/favorites');
    root.innerHTML = html`<div class="page"><h1>Saved profiles</h1>${rows.length ? html`<div class="grid">${rows.map(p => html`<article class="card" tabindex="0" data-action="open-profile" data-id="${p.id}"><div class="card-photo">${photo(p)}</div><div class="card-body"><div class="between"><h3>${p.name}, ${p.age}</h3><span class="rate">★ ${p.review_count ? p.rating.toFixed(1) : 'New'}</span></div><p class="muted small">⌖ ${p.city} · from <b>${inr(p.min_rate)}</b></p></div></article>`)}</div>` : html`<div class="empty"><p>Nothing saved yet.</p><p class="muted">Tap ♡ on a profile to keep it here.</p><a class="btn primary" href="#/">Discover people</a></div>`}</div>`.s;
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}

// ====================== BOOKINGS ======================
export async function bookingsPage(root) {
  if (!state.me) return needLogin(root);
  root.innerHTML = '<div class="page"><h1>Bookings</h1><div class="skeleton"></div></div>';
  let rows;
  try { rows = await api('/bookings'); } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; return; }
  const isP = state.me.role === 'partner';
  const now = Date.now();
  const groups = [
    [isP ? 'Needs your response' : 'Awaiting partner', b => b.status === 'requested'],
    ['Upcoming', b => b.status === 'accepted'],
    ['Past', b => ['completed', 'cancelled', 'rejected', 'expired'].includes(b.status)],
  ];
  root.innerHTML = html`<div class="page"><h1>Bookings</h1>
    ${!rows.length ? html`<div class="empty"><p>No bookings yet.</p>${isP ? html`<p class="muted">Requests from customers will appear here.</p>` : html`<a class="btn primary" href="#/">Find someone to meet</a>`}</div>` : ''}
    ${groups.map(([title, test]) => { const g = rows.filter(test); return g.length ? html`<h2>${title} <small class="muted">(${g.length})</small></h2><div class="list">${g.map(b => bookingCard(b, isP, now))}</div>` : ''; })}</div>`.s;
  root._rows = rows;
}
function bookingCard(b, isP, now) {
  const other = isP ? b.customer_name : b.partner_name, otherId = isP ? b.customer_id : b.partner_id;
  const started = new Date(b.scheduled_at) <= now;
  const soon = b.status === 'accepted' && now > new Date(b.scheduled_at) - 2 * 3600e3 && now < new Date(b.scheduled_at).getTime() + (b.duration_minutes + 360) * 60e3;
  return html`<div class="item"><div class="between"><div><b>${b.activity}</b> <span class="muted">with ${other}</span></div>${pill(b.status)}</div>
    <p class="muted small">📅 ${fmtDT(b.scheduled_at)} · ${b.duration_minutes / 60}h · ${inr(b.price)}</p>
    <p class="muted small">📍 ${b.location}</p>${b.note ? html`<p class="small">“${b.note}”</p>` : ''}${b.status_reason ? html`<p class="muted small">Reason: ${b.status_reason}</p>` : ''}
    <div class="row wrap">
    ${isP && b.status === 'requested' ? html`<button class="btn primary sm" data-action="bk" data-id="${b.id}" data-s="accepted">Accept</button><button class="btn ghost sm" data-action="bk" data-id="${b.id}" data-s="rejected">Decline</button>` : ''}
    ${!isP && b.status === 'requested' ? html`<button class="btn ghost sm" data-action="bk" data-id="${b.id}" data-s="cancelled">Cancel request</button>` : ''}
    ${b.status === 'accepted' ? html`<a class="btn ghost sm" href="#/messages/${otherId}">💬 Message</a>${started ? html`<button class="btn primary sm" data-action="bk" data-id="${b.id}" data-s="completed">Mark completed</button>` : html`<span class="muted small">Can be completed once it starts</span>`}<button class="btn ghost sm" data-action="bk" data-id="${b.id}" data-s="cancelled">Cancel</button>` : ''}
    ${soon ? html`<button class="btn danger sm" data-action="bk-safety" data-id="${b.id}">🛡 Safety</button>` : ''}
    ${!isP && b.status === 'completed' ? html`<button class="btn primary sm" data-action="bk-review" data-id="${b.id}">★ Leave a review</button>` : ''}
    ${['completed', 'accepted'].includes(b.status) ? html`<button class="link small" data-action="bk-report" data-id="${b.id}">Report</button>` : ''}
    </div></div>`;
}
const findBooking = el => $('#view')._rows.find(b => b.id === Number(el.dataset.id));
actions.bk = async el => {
  const b = findBooking(el), s = el.dataset.s; let reason = '';
  if (s === 'cancelled' && b.status === 'accepted') { reason = await askText({ title: 'Cancel this booking?', label: 'Reason (shared with the other person)', required: true, confirm: 'Cancel booking', danger: true }); if (reason === null) return; }
  else if (s === 'rejected') { reason = await askText({ title: 'Decline request', label: 'Optional note', confirm: 'Decline' }); if (reason === null) return; }
  else if (s === 'cancelled') { if (!await confirmBox({ title: 'Cancel request?', text: 'The partner will be notified.', confirm: 'Cancel request', danger: true })) return; }
  await busy(el, async () => { await api(`/bookings/${b.id}`, { method: 'PATCH', body: { status: s, reason } }); toast('Booking updated.', 'ok'); bookingsPage($('#view')); });
};
actions['bk-safety'] = el => safetyModal(findBooking(el));
actions['bk-report'] = el => { const b = findBooking(el); const isP = state.me.role === 'partner'; reportModal(isP ? b.customer_id : b.partner_id, isP ? b.customer_name : b.partner_name, b.id); };
actions['bk-review'] = el => {
  const b = findBooking(el);
  openModal(html`<h2>Rate your plan with ${b.partner_name}</h2><form data-submit="review" class="stack"><input type="hidden" name="id" value="${b.id}">
    <div class="starpick" role="radiogroup" aria-label="Rating">${[5, 4, 3, 2, 1].map(n => html`<input type="radio" id="st${n}" name="rating" value="${n}" ${n === 5 ? 'checked' : ''}><label for="st${n}" title="${n} stars">★</label>`)}</div>
    <textarea class="field" name="comment" rows="3" maxlength="1000" placeholder="How was it? (optional)"></textarea><button class="btn primary block" type="submit">Submit verified review</button></form>`, { label: 'Review' });
};
submits.review = async f => { const b = formObj(f); await api(`/bookings/${b.id}/reviews`, { method: 'POST', body: { rating: Number(b.rating), comment: b.comment } }); closeModal(); toast('Thanks for your review!', 'ok'); bookingsPage($('#view')); };

// ====================== MESSAGES ======================
let chatState = { other: null, last: 0 };
export async function messagesPage(root, otherId) {
  if (!state.me) return needLogin(root);
  let convs;
  try { convs = await api('/conversations'); } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; return; }
  const open = otherId ? Number(otherId) : null;
  root.innerHTML = html`<div class="page chat-page"><div class="chat ${open ? 'has-thread' : ''}">
    <aside class="convs"><h2>Messages</h2>${convs.length ? convs.map(c => html`<a class="conv ${open === c.user_id ? 'on' : ''}" href="#/messages/${c.user_id}"><span class="av">${c.name[0]}</span><span class="grow"><b>${c.name}</b><small class="muted">${c.last_message || 'Say hello 👋'}</small></span>${c.unread ? html`<span class="dot">${c.unread}</span>` : ''}</a>`) : html`<p class="muted small">Chat opens once a booking is accepted. Nothing here yet.</p>`}</aside>
    <section class="thread" id="thread">${open ? '' : html`<div class="empty"><p class="muted">Select a conversation</p></div>`}</section></div></div>`.s;
  if (open) await openThread(open);
}
async function openThread(id) {
  const box = $('#thread'); chatState = { other: id, last: 0 };
  try {
    const r = await api(`/messages/${id}`);
    box.innerHTML = html`<header class="thread-head"><a class="back mobile-only" href="#/messages">←</a><b>${r.other.name}</b><span class="grow"></span><button class="link small" data-action="chat-report" data-id="${id}" data-name="${r.other.name}">Report</button><button class="link small" data-action="chat-block" data-id="${id}" data-name="${r.other.name}">Block</button></header>
      <p class="notice small">🛡 Never send money, OTPs or card details in chat. Messages containing payment requests or sexual content are blocked.</p>
      <div class="msgs" id="msgs" aria-live="polite"></div>
      <form class="composer" data-submit="send-msg"><input type="hidden" name="to" value="${id}"><textarea name="body" rows="1" maxlength="2000" placeholder="Write a message" required aria-label="Message"></textarea><button class="btn primary" type="submit">Send</button></form>`.s;
    appendMsgs(r.messages);
    const ta = $('.composer textarea'); ta.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('.composer').requestSubmit(); } });
    stopTimers(); timers.push(setInterval(poll, 5000));
  } catch (e) { box.innerHTML = html`<div class="empty"><p class="err">${e.message}</p></div>`.s; }
}
function appendMsgs(list) {
  const m = $('#msgs'); if (!m) return;
  const stick = m.scrollTop + m.clientHeight >= m.scrollHeight - 60 || chatState.last === 0;
  for (const x of list) {
    if (x.id <= chatState.last) continue; chatState.last = x.id;
    const d = document.createElement('div'); d.className = 'msg ' + (x.sender_id === state.me.id ? 'me' : 'them');
    d.innerHTML = html`<p>${x.body}</p><small>${new Date(x.created_at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}${x.sender_id === state.me.id && x.read ? ' · Seen' : ''}</small>`.s;
    m.append(d);
  }
  if (stick) m.scrollTop = m.scrollHeight;
}
async function poll() {
  if (document.hidden || !chatState.other || !$('#msgs')) return;
  try { const r = await api(`/messages/${chatState.other}?after=${chatState.last}`); appendMsgs(r.messages); } catch { /* transient */ }
}
submits['send-msg'] = async f => {
  const b = formObj(f); const ta = $('textarea', f);
  const m = await api('/messages', { method: 'POST', body: { receiver_id: Number(b.to), body: b.body } });
  ta.value = ''; appendMsgs([m]);
};
actions['chat-report'] = el => reportModal(Number(el.dataset.id), el.dataset.name);
actions['chat-block'] = async el => { if (await blockUser(Number(el.dataset.id), el.dataset.name)) location.hash = '#/messages'; };

// ====================== NOTIFICATIONS ======================
export async function pollNotifications() {
  if (!state.me) return;
  try { const r = await api('/notifications'); state.unread = { n: r.unread, msgs: r.unread_messages }; state._notes = r.items; renderBadges(); } catch { /* ignore */ }
}
export function renderBadges() {
  const b = $('#bell-badge'); if (b) { b.hidden = !state.unread.n; b.textContent = state.unread.n > 9 ? '9+' : state.unread.n; }
  const m = $('#msg-badge'); if (m) { m.hidden = !state.unread.msgs; m.textContent = state.unread.msgs > 9 ? '9+' : state.unread.msgs; }
}
actions.bell = async () => {
  if (!state.me) return openAuth('login');
  await pollNotifications();
  const items = state._notes || [];
  openModal(html`<h2>Notifications</h2>${items.length ? html`<div class="list">${items.map(n => html`<a class="item ${n.read ? '' : 'unread'}" href="${n.link || '#/'}" data-action="close-modal"><p>${n.text}</p><small class="muted">${ago(n.created_at)}</small></a>`)}</div>` : html`<p class="muted">You're all caught up.</p>`}`, { label: 'Notifications' });
  if (state.unread.n) { api('/notifications/read', { method: 'POST' }).then(() => { state.unread.n = 0; renderBadges(); }); }
};

// ====================== PARTNER DASHBOARD ======================
let draft = null;
export async function dashboardPage(root) {
  if (!state.me) return needLogin(root);
  if (state.me.role !== 'partner') { root.innerHTML = html`<div class="page narrow center"><h1>Partner dashboard</h1><p class="muted">This area is for partner accounts. Sign up as a partner to list your profile.</p></div>`.s; return; }
  root.innerHTML = '<div class="page"><div class="skeleton tall"></div></div>';
  try {
    const [p, bookings] = await Promise.all([api('/partner/profile'), api('/bookings')]);
    draft = { ...p, photos: [...p.photos], activities: [...p.activities], rates: { ...p.rates } };
    const done = bookings.filter(b => b.status === 'completed'), pending = bookings.filter(b => b.status === 'requested');
    const banner = {
      draft: ['warn', 'Your profile isn\'t live yet. Complete it and submit for review.'],
      pending: ['info', 'Your profile is under review. We\'ll notify you when it\'s approved (usually within 24 hours).'],
      approved: ['ok', 'Your profile is live and visible to customers.'],
      rejected: ['warn', 'Your profile needs changes: ' + (p.reject_reason || 'please review and resubmit.')],
    }[p.status];
    root.innerHTML = html`<div class="page"><h1>Partner dashboard</h1>
      <div class="notice ${banner[0]}">${banner[1]}${p.status === 'approved' ? html` <a href="#/p/${p.id}">View public profile</a>` : ''}</div>
      <div class="stats"><div><b>${pending.length}</b><span>Pending requests</span></div><div><b>${done.length}</b><span>Completed</span></div><div><b>${p.review_count ? p.rating.toFixed(1) : '-'}</b><span>Rating</span></div><div><b>${inr(done.reduce((s, b) => s + b.price, 0))}</b><span>Booked value*</span></div></div>
      <p class="muted small">*Sum of completed booking prices. PairUp doesn't process booking payments or payouts in this build.</p>
      <label class="switch"><input type="checkbox" id="avail" data-action="toggle-avail" ${p.available ? 'checked' : ''}><span></span> Accepting booking requests</label>
      ${pending.length ? html`<h2>Pending requests</h2><div class="list">${pending.map(b => html`<div class="item"><b>${b.activity}</b> <span class="muted">from ${b.customer_name}</span><p class="muted small">${fmtDT(b.scheduled_at)} · ${inr(b.price)} · 📍 ${b.location}</p><a class="btn primary sm" href="#/bookings">Respond</a></div>`)}</div>` : ''}
      <h2>Your profile</h2><form id="pform" data-submit="save-profile" class="stack">
      <label class="lbl">Photos <small class="muted">(up to 6 · first is your main photo · clear face photos only, no explicit images)</small></label><div class="photos" id="photos"></div>
      <label class="lbl" for="p-head">Headline</label><input class="field" id="p-head" name="headline" maxlength="120" value="${p.headline}" placeholder="e.g. Cafe hopper & movie buff">
      <label class="lbl" for="p-bio">About you <small class="muted" id="bio-count"></small></label><textarea class="field" id="p-bio" name="bio" rows="5" maxlength="1500" placeholder="Tell customers about yourself (min 30 characters). No phone numbers, links or payment details.">${p.bio}</textarea>
      <label class="lbl" for="p-lang">Languages (comma separated)</label><input class="field" id="p-lang" name="languages" value="${p.languages.join(', ')}" placeholder="English, Hindi">
      <label class="lbl">Activities &amp; rates (₹ per session)</label><div id="acts"></div>
      <div class="chips" id="sugg"></div>
      <div class="row"><input class="field" id="new-act" placeholder="Add your own activity" maxlength="60"><button class="btn ghost" type="button" data-action="add-act">Add</button></div>
      <div class="notice">Only non-sexual, public-place activities are allowed. Profiles containing sexual or adult-service wording are rejected automatically.</div>
      <div class="row wrap"><button class="btn ghost" type="submit" data-mode="save">Save changes</button><button class="btn primary" type="button" data-action="submit-profile">Save &amp; submit for review</button></div></form></div>`.s;
    drawPhotos(); drawActs(); bioCount();
    $('#p-bio').addEventListener('input', bioCount);
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}
const bioCount = () => { const t = $('#p-bio'), c = $('#bio-count'); if (t && c) c.textContent = `${t.value.trim().length}/1500`; };
function drawPhotos() {
  const el = $('#photos'); if (!el) return;
  el.innerHTML = html`${draft.photos.map((u, i) => html`<div class="thumb"><img src="${u}" alt="Photo ${i + 1}">${i === 0 ? html`<span class="main-tag">Main</span>` : html`<button type="button" class="mk" data-action="photo-main" data-i="${i}">Make main</button>`}<button type="button" class="rm" data-action="photo-rm" data-i="${i}" aria-label="Remove photo">×</button></div>`)}
    ${draft.photos.length < 6 ? html`<label class="thumb add"><input type="file" id="photo-file" accept="image/jpeg,image/png,image/webp" hidden><span>＋<br><small>Add photo</small></span></label>` : ''}`.s;
  const fi = $('#photo-file'); if (fi) fi.onchange = async () => {
    const file = fi.files[0]; if (!file) return;
    if (file.size > 5 * 1024 * 1024) return toast('Photo must be under 5 MB.', 'error');
    const fd = new FormData(); fd.append('file', file);
    try { const r = await api('/uploads/photo', { method: 'POST', form: fd }); draft.photos.push(r.url); drawPhotos(); toast('Photo uploaded. Save to apply.', 'ok'); } catch (e) { toast(e.message, 'error'); }
  };
}
actions['photo-rm'] = el => { draft.photos.splice(Number(el.dataset.i), 1); drawPhotos(); };
actions['photo-main'] = el => { const [u] = draft.photos.splice(Number(el.dataset.i), 1); draft.photos.unshift(u); drawPhotos(); };
function drawActs() {
  const el = $('#acts'); if (!el) return;
  el.innerHTML = draft.activities.length ? draft.activities.map((a, i) => html`<div class="act-row"><span>${a}</span><label class="rate-in">₹<input type="number" min="${state.meta.min_rate}" max="${state.meta.max_rate}" step="10" value="${draft.rates[a] ?? ''}" data-act="${a}" aria-label="Rate for ${a}" required></label><button type="button" class="rm-btn" data-action="act-rm" data-i="${i}" aria-label="Remove ${a}">×</button></div>`).join('') : '<p class="muted small">No activities yet - add some below.</p>';
  $$('#acts input').forEach(i => i.addEventListener('input', () => { draft.rates[i.dataset.act] = Number(i.value); }));
  const have = new Set(draft.activities.map(a => a.toLowerCase()));
  $('#sugg').innerHTML = state.meta.activity_suggestions.filter(a => !have.has(a.toLowerCase())).map(a => html`<button type="button" class="chip" data-action="act-add" data-a="${a}">+ ${a}</button>`).join('');
}
function addAct(name) { name = name.trim(); if (!name) return; if (draft.activities.some(a => a.toLowerCase() === name.toLowerCase())) return toast('Already added.', 'error'); if (draft.activities.length >= 30) return toast('Max 30 activities.', 'error'); draft.activities.push(name); draftFromForm(); drawActs(); }
actions['act-add'] = el => addAct(el.dataset.a);
actions['add-act'] = () => { const i = $('#new-act'); addAct(i.value); i.value = ''; };
actions['act-rm'] = el => { const a = draft.activities.splice(Number(el.dataset.i), 1)[0]; delete draft.rates[a]; drawActs(); };
function draftFromForm() { draft.headline = $('#p-head').value; draft.bio = $('#p-bio').value; draft.languages = $('#p-lang').value.split(',').map(s => s.trim()).filter(Boolean); }
async function saveProfile() {
  draftFromForm();
  for (const a of draft.activities) if (!draft.rates[a]) throw new Error(`Add a rate for "${a}".`);
  const r = await api('/partner/profile', { method: 'PUT', body: { headline: draft.headline, bio: draft.bio, photos: draft.photos, activities: draft.activities, rates: draft.rates, languages: draft.languages } });
  return r;
}
submits['save-profile'] = async () => { const r = await saveProfile(); toast(r.message, 'ok'); dashboardPage($('#view')); };
actions['submit-profile'] = el => busy(el, async () => { await saveProfile(); const r = await api('/partner/profile/submit', { method: 'POST' }); toast(r.message, 'ok'); dashboardPage($('#view')); });
actions['toggle-avail'] = async el => { try { await api('/partner/availability', { method: 'PATCH', body: { available: el.checked } }); toast(el.checked ? 'You\'re accepting requests.' : 'Requests paused.', 'ok'); } catch (e) { el.checked = !el.checked; toast(e.message, 'error'); } };

// ====================== ACCOUNT ======================
export async function accountPage(root) {
  if (!state.me) return needLogin(root);
  await refreshMe(); const me = state.me;
  let mem = null, blocks = [];
  try { if (me.role === 'customer') mem = await api('/membership/status'); blocks = await api('/blocks'); } catch { /* shown empty */ }
  const devLink = sessionStorage.getItem('dev_verify_link');
  root.innerHTML = html`<div class="page narrow"><h1>Account</h1>
    <div class="item"><div class="between"><div><b>${me.name}</b><p class="muted small">${me.email} · ${me.city} · ${me.role}</p></div>${me.email_verified ? html`<span class="pill completed">email verified</span>` : html`<span class="pill requested">email not verified</span>`}</div>
    ${me.email_verified ? '' : html`<button class="btn ghost sm" data-action="resend-verify">Resend verification email</button>${devLink ? html` <a class="small" href="${devLink}">dev: verify now</a>` : ''}`}</div>
    ${me.role === 'customer' ? html`<h2>Membership</h2><div class="item">${mem && mem.active ? html`<p><b>${mem.plan}</b> plan active until ${fmtD(mem.expires_at)}</p><button class="btn ghost sm" data-action="open-membership">Extend</button>` : html`<p class="muted">No active membership. Required to send booking requests.</p><button class="btn primary sm" data-action="open-membership">Get membership</button>`}</div>` : ''}
    ${me.role === 'partner' ? html`<p><a class="btn primary" href="#/dashboard">Open partner dashboard</a></p>` : ''}
    ${me.role === 'admin' ? html`<p><a class="btn primary" href="#/admin">Open admin console</a></p>` : ''}
    <h2>Change password</h2><form data-submit="chpw" class="stack"><input class="field" name="current_password" type="password" placeholder="Current password" autocomplete="current-password" required><input class="field" name="new_password" type="password" placeholder="New password (8+ chars, letters & numbers)" minlength="8" autocomplete="new-password" required><button class="btn ghost" type="submit">Update password</button></form>
    <h2>Blocked users</h2>${blocks.length ? html`<div class="list">${blocks.map(b => html`<div class="item between"><span>${b.name}</span><button class="btn ghost sm" data-action="unblock" data-id="${b.user_id}">Unblock</button></div>`)}</div>` : html`<p class="muted small">You haven't blocked anyone.</p>`}
    <h2>Session</h2><button class="btn ghost" data-action="logout">Log out</button>
    <h2>Danger zone</h2><p class="muted small">Deleting your account deactivates it and removes your personal details. This can't be undone.</p><button class="btn danger" data-action="delete-account">Delete my account</button></div>`.s;
}
actions['resend-verify'] = el => busy(el, async () => { const r = await api('/auth/resend-verification', { method: 'POST' }); if (r.dev_verify_link) sessionStorage.setItem('dev_verify_link', r.dev_verify_link); toast(r.message, 'ok'); accountPage($('#view')); });
actions.unblock = async el => { await api(`/blocks/${el.dataset.id}`, { method: 'DELETE' }); toast('Unblocked.', 'ok'); accountPage($('#view')); };
submits.chpw = async f => { await api('/auth/change-password', { method: 'POST', body: formObj(f) }); f.reset(); toast('Password changed.', 'ok'); };
actions['delete-account'] = () => {
  openModal(html`<h2>Delete your account?</h2><p class="muted">Enter your password to confirm. Accepted bookings must be cancelled or completed first.</p><form data-submit="del" class="stack"><input class="field" name="password" type="password" placeholder="Password" required autocomplete="current-password"><button class="btn danger block" type="submit">Permanently delete</button></form>`, { label: 'Delete account' });
};
submits.del = async f => { await api('/auth/delete-account', { method: 'POST', body: formObj(f) }); clearAuth(); closeModal(); toast('Your account was deleted.', 'ok'); location.hash = '#/'; };
