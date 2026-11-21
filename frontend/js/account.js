import { html, raw, avatar, emptyState, api, state, $, $$, openModal, closeModal, toast, actions, submits, formObj, inr, fmtDT, fmtD, ago, photo, isCustomer, askText, confirmBox, busy, clearAuth, refreshMe } from './core.js';
import { openAuth } from './auth.js';
import { openMembership, startBooking, card } from './discover.js';
import { openRazorpay } from './core.js';
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
    root.innerHTML = html`<div class="page"><div class="between"><div><h1>Saved</h1><p class="muted">${rows.length ? `${rows.length} ${rows.length === 1 ? 'profile' : 'profiles'} you liked` : ''}</p></div>${rows.length ? html`<a class="btn ghost sm" href="#/browse">Find more</a>` : ''}</div>
      ${rows.length ? html`<div class="grid">${rows.map(card)}</div>` : emptyState({ icon: '💜', title: 'Nothing saved yet', text: 'Swipe right or tap ♡ on a profile to keep it here for later.', cta: html`<a class="btn primary" href="#/browse">Start swiping</a>` })}</div>`.s;
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}

// ====================== NOTIFICATIONS ======================
export async function pollNotifications() {
  if (!state.me) return;
  try { const r = await api('/notifications'); state.unread = { n: r.unread, msgs: r.unread_messages }; state._notes = r.items; renderBadges(); } catch { /* ignore */ }
}
export function renderBadges() {
  const b = $('#bell-badge'); if (b) { b.hidden = !state.unread.n; b.textContent = state.unread.n > 9 ? '9+' : state.unread.n; }
  const m = $('#msg-badge'); if (m) { m.hidden = !state.unread.msgs; m.textContent = state.unread.msgs > 9 ? '9+' : state.unread.msgs; }
}
const N_ICON = { booking: '📅', payment: '💳', payout: '💰', kyc: '🪪', review: '⭐', report: '🛡️', profile: '✅', support: '💬', membership: '✨' };
actions.bell = async () => {
  if (!state.me) return openAuth('login');
  await pollNotifications();
  const items = state._notes || [], today = new Date().toDateString();
  const groups = [['Today', items.filter(n => new Date(n.created_at).toDateString() === today)], ['Earlier', items.filter(n => new Date(n.created_at).toDateString() !== today)]].filter(g => g[1].length);
  openModal(html`<h2>Notifications</h2>${items.length ? groups.map(([t, list]) => html`<p class="grp">${t}</p><div class="list">${list.map(n => html`<a class="notif ${n.read ? '' : 'unread'}" href="${n.link || '#/'}" data-action="close-modal"><span class="n-ico">${N_ICON[n.kind] || '🔔'}</span><span class="grow"><span>${n.text}</span><small class="muted">${ago(n.created_at)}</small></span>${n.read ? '' : html`<i class="n-dot"></i>`}</a>`)}</div>`)
    : emptyState({ icon: '🔔', title: "You're all caught up", text: 'Booking updates, payments and messages will show up here.' })}`, { label: 'Notifications' });
  if (state.unread.n) { api('/notifications/read', { method: 'POST' }).then(() => { state.unread.n = 0; renderBadges(); }); }
};

// ====================== PARTNER DASHBOARD ======================
let draft = null;
const ring = pct => html`<svg class="ring" viewBox="0 0 44 44" aria-label="${pct}% complete"><circle cx="22" cy="22" r="18" class="rb"></circle><circle cx="22" cy="22" r="18" class="rf" style="stroke-dasharray:${(113 * pct / 100).toFixed(1)} 113"></circle><text x="22" y="26" text-anchor="middle">${pct}%</text></svg>`;
function completeness(p) {
  const checks = [['Add your first photo', p.photos.length >= 1, 15], ['Add 3 or more photos', p.photos.length >= 3, 10], ['Write a catchy headline', p.headline.trim().length >= 5, 10],
    ['Write a longer bio (120+ characters)', p.bio.trim().length >= 120, 20], ['Offer 3 or more activities', p.activities.length >= 3, 15], ['List the languages you speak', p.languages.length >= 1, 5],
    ['Set your weekly hours', Object.keys(p.schedule || {}).length > 0, 10], ['Verify your ID for the ✓ badge', p.verified, 15]];
  return { pct: checks.reduce((s, c) => s + (c[1] ? c[2] : 0), 0), todo: checks.filter(c => !c[1]).slice(0, 3).map(c => c[0]) };
}
export async function dashboardPage(root) {
  if (!state.me) return needLogin(root);
  if (state.me.role !== 'partner') { root.innerHTML = html`<div class="page narrow">${emptyState({ icon: '🌟', title: 'Partner dashboard', text: 'This area is for partner accounts. Sign up as a partner to list your profile and start earning.', cta: html`<a class="btn primary" href="#/become-a-partner">Become a partner</a>` })}</div>`.s; return; }
  root.innerHTML = '<div class="page"><div class="skeleton tall"></div></div>';
  try {
    const [p, bookings] = await Promise.all([api('/partner/profile'), api('/bookings')]);
    const myReviews = await api(`/partners/${state.me.id}/reviews`).catch(() => []);
    draft = { ...p, photos: [...p.photos], activities: [...p.activities], rates: { ...p.rates } };
    const done = bookings.filter(b => b.status === 'completed'), pending = bookings.filter(b => b.status === 'requested'), upcoming = bookings.filter(b => b.status === 'accepted');
    const comp = completeness(p), first = state.me.name.split(' ')[0];
    const status = { draft: ['warn', 'Draft', 'Your profile isn\'t live yet. Complete it and submit for review.'], pending: ['info', 'Under review', 'We\'re reviewing your profile - usually within 24 hours.'],
      approved: ['ok', 'Live', 'Your profile is live and visible to customers.'], rejected: ['warn', 'Needs changes', p.reject_reason || 'Please review and resubmit.'] }[p.status];
    root.innerHTML = html`<div class="page wide-ish">
      <section class="dash-hero"><div class="dh-id">${avatar(state.me.name, p.photos[0], 'lg')}<div><p class="muted small">Welcome back</p><h1>Hi, ${first} 👋</h1><span class="status-chip ${status[0]}">● ${status[1]}</span></div></div>
        <div class="dh-actions">${p.status === 'approved' ? html`<a class="btn ghost sm" href="#/p/${p.id}">View public profile</a><button class="btn ghost sm" data-action="copy-link" data-id="${p.id}">🔗 Copy link</button>` : ''}
        <label class="switch"><input type="checkbox" id="avail" data-action="toggle-avail" ${p.available ? 'checked' : ''}><span></span> Accepting requests</label></div></section>
      <div class="notice ${status[0]}">${status[2]}</div>
      <div class="dash-grid">
        <div class="dcol">
          <div class="stats4"><div><i>📬</i><b>${pending.length}</b><span>New requests</span></div><div><i>🗓️</i><b>${upcoming.length}</b><span>Upcoming</span></div><div><i>✅</i><b>${done.length}</b><span>Completed</span></div><div><i>⭐</i><b>${p.review_count ? p.rating.toFixed(1) : '–'}</b><span>Rating</span></div></div>
          <h2 class="h2s">Inbox ${pending.length ? html`<span class="count-dot">${pending.length}</span>` : ''}</h2>
          ${pending.length ? html`<div class="list">${pending.map(b => html`<div class="req"><div class="req-top"><b>${b.activity}</b><span class="muted small">from ${b.customer_name}</span><span class="grow"></span><b>${inr(b.price)}</b></div><p class="muted small">🗓 ${fmtDT(b.scheduled_at)} · ${b.duration_minutes / 60}h · 📍 ${b.location}</p>${b.note ? html`<p class="small">“${b.note}”</p>` : ''}<div class="row"><button class="btn primary sm" data-action="dash-bk" data-id="${b.id}" data-s="accepted">Accept</button><button class="btn ghost sm" data-action="dash-bk" data-id="${b.id}" data-s="rejected">Decline</button></div></div>`)}</div>`
            : html`<div class="mini-empty">📭 No new requests right now. ${p.status !== 'approved' ? 'Get approved to start receiving them.' : 'Keep your profile fresh to get more.'}</div>`}
          ${myReviews.length ? html`<h2 class="h2s">Recent reviews</h2><div class="list">${myReviews.slice(0, 5).map(r => html`<div class="item"><div class="between"><b>${r.reviewer}</b><span class="stars">${'★'.repeat(r.rating)}</span></div><p>${r.comment || ''}</p>${r.partner_reply ? html`<p class="muted small">Your reply: ${r.partner_reply}</p>` : html`<button class="btn ghost sm" data-action="reply-review" data-id="${r.booking_id}">Reply</button>`}</div>`)}</div>` : ''}
        </div>
        <aside class="dcol">
          <div class="comp-card">${ring(comp.pct)}<div><b>Profile strength</b><p class="muted small">${comp.pct >= 100 ? 'Perfect - you\'re all set! 🎉' : 'Complete profiles get more bookings.'}</p></div></div>
          ${comp.todo.length ? html`<ul class="todo">${comp.todo.map(t => html`<li>${t}</li>`)}</ul>` : ''}
          <div class="tiles tiles-col"><a class="tile" href="#/earnings"><b>💰 Earnings &amp; payouts</b><span>Wallet, UPI payouts</span></a><a class="tile" href="#/verify-id"><b>${p.verified ? '✓ ID verified' : '🪪 Get ID verified'}</b><span>${p.verified ? 'Badge is active' : 'Needed for payouts'}</span></a><a class="tile" href="#/schedule"><b>🗓 Weekly hours</b><span>${Object.keys(p.schedule || {}).length ? Object.keys(p.schedule).length + ' days set' : 'Any time'}</span></a><a class="tile" href="#/messages"><b>💬 Messages</b><span>Customer inquiries &amp; chats</span></a><a class="tile" href="#/bookings"><b>📅 All bookings</b><span>Requests, upcoming, past</span></a></div>
        </aside></div>
      <h2 class="h2s">Edit your profile</h2>
      <form id="pform" data-submit="save-profile" class="stack ed">
        <div class="ed-card"><h3>Photos</h3><p class="muted small">Up to 6 · the first is your main photo · clear face photos only, no explicit images.</p><div class="photos" id="photos"></div></div>
        <div class="ed-card"><h3>About you</h3><label class="lbl" for="p-head">Headline</label><input class="field" id="p-head" name="headline" maxlength="120" value="${p.headline}" placeholder="e.g. Cafe hopper & movie buff">
          <label class="lbl" for="p-bio">Bio <small class="muted" id="bio-count"></small></label><textarea class="field" id="p-bio" name="bio" rows="5" maxlength="1500" placeholder="Tell customers about yourself (min 30 characters). No phone numbers, links or payment details.">${p.bio}</textarea>
          <label class="lbl" for="p-lang">Languages (comma separated)</label><input class="field" id="p-lang" name="languages" value="${p.languages.join(', ')}" placeholder="English, Hindi"></div>
        <div class="ed-card"><h3>Activities &amp; rates</h3><p class="muted small">Your price per session in ₹.</p><div id="acts"></div><div class="chips" id="sugg"></div><div class="row"><input class="field" id="new-act" placeholder="Add your own activity" maxlength="60"><button class="btn ghost" type="button" data-action="add-act">Add</button></div></div>
        <div class="notice">Only non-sexual, public-place activities are allowed. Profiles with sexual or adult-service wording are rejected automatically.</div>
        <div class="save-bar"><button class="btn ghost" type="submit" data-mode="save">Save changes</button><button class="btn primary" type="button" data-action="submit-profile">Save &amp; submit for review</button></div></form></div>`.s;
    drawPhotos(); drawActs(); bioCount();
    $('#p-bio').addEventListener('input', bioCount);
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}
actions['dash-bk'] = async el => {
  let reason = '';
  if (el.dataset.s === 'rejected') { reason = await askText({ title: 'Decline request', label: 'Optional note for the customer', confirm: 'Decline' }); if (reason === null) return; }
  await busy(el, async () => { await api(`/bookings/${el.dataset.id}`, { method: 'PATCH', body: { status: el.dataset.s, reason } }); toast(el.dataset.s === 'accepted' ? 'Accepted - the customer can now pay to confirm.' : 'Declined.', 'ok'); dashboardPage($('#view')); });
};
actions['copy-link'] = async el => { try { await navigator.clipboard.writeText(`${location.origin}/#/p/${el.dataset.id}`); toast('Profile link copied.', 'ok'); } catch { toast('Copy failed - long-press the link instead.', 'error'); } };
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
  const devLink = sessionStorage.getItem('gimble_dev_verify_link') || sessionStorage.getItem('dev_verify_link');
  const total = mem && mem.plan === 'annual' ? 365 : 30, left = mem && mem.active ? Math.max(0, Math.ceil((new Date(mem.expires_at) - Date.now()) / 864e5)) : 0;
  root.innerHTML = html`<div class="page narrow-lg">
    <section class="acc-hero">${avatar(me.name, '', 'xl')}<div class="grow"><h1>${me.name}</h1><p class="muted">${me.email}</p><div class="row wrap"><span class="pill ${me.role === 'admin' ? 'accepted' : 'requested'}">${me.role}</span><span class="pill ${me.email_verified ? 'completed' : 'requested'}">${me.email_verified ? '✓ email verified' : 'email not verified'}</span><span class="muted small">⌖ ${me.city}</span></div>
      ${me.email_verified ? '' : html`<button class="btn ghost sm" data-action="resend-verify">Resend verification email</button>${devLink ? html` <a class="small" href="${devLink}">dev: verify now</a>` : ''}`}</div></section>
    ${me.role === 'customer' ? (mem && mem.active ? html`<section class="mem-card"><div><span class="badge">GIMBLE MEMBER</span><h2>${mem.plan === 'annual' ? 'Annual' : 'Monthly'} plan</h2><p>Active until <b>${fmtD(mem.expires_at)}</b> · ${left} day${left === 1 ? '' : 's'} left</p><div class="bar"><i style="width:${Math.min(100, Math.round(left / total * 100))}%"></i></div></div><button class="btn ghost" data-action="open-membership">Extend</button></section>`
      : html`<section class="mem-card off"><div><span class="badge">UNLOCK BOOKINGS</span><h2>Become a member</h2><p>Browsing is free. A membership lets you send booking requests.</p></div><button class="btn primary" data-action="open-membership">See plans</button></section>`) : ''}
    <div class="qlinks">${me.role === 'customer' ? html`<a href="#/saved"><span>💜</span>Saved</a><a href="#/setup"><span>🖼️</span>My profile</a>` : ''}${me.role !== 'admin' ? html`<a href="#/account" data-action="switch-mode"><span>⇄</span>Switch Hire / Get hired</a>` : ''}<a href="#/messages"><span>💬</span>Messages</a>${me.role === 'partner' ? html`<a href="#/dashboard"><span>🌟</span>Dashboard</a><a href="#/earnings"><span>💰</span>Earnings</a>` : ''}${me.role === 'admin' ? html`<a href="#/admin"><span>🛠️</span>Admin</a>` : ''}<a href="#/bookings"><span>📅</span>Bookings</a><a href="#/support"><span>💬</span>Support</a><a href="#/safety"><span>🛡️</span>Safety</a></div>
    <h2 class="h2s">Security</h2><details class="faq"><summary>Change password</summary><form data-submit="chpw" class="stack pad"><input class="field" name="current_password" type="password" placeholder="Current password" autocomplete="current-password" required><input class="field" name="new_password" type="password" placeholder="New password (8+ chars, letters & numbers)" minlength="8" autocomplete="new-password" required><button class="btn primary" type="submit">Update password</button></form></details>
    <h2 class="h2s">Blocked users</h2>${blocks.length ? html`<div class="list">${blocks.map(b => html`<div class="item between"><span>${b.name}</span><button class="btn ghost sm" data-action="unblock" data-id="${b.user_id}">Unblock</button></div>`)}</div>` : html`<p class="muted small">You haven't blocked anyone.</p>`}
    <h2 class="h2s">Legal</h2><p class="small"><a href="#/terms">Terms</a> · <a href="#/privacy">Privacy</a> · <a href="#/standards">Community Standards</a> · <a href="#/refunds">Refunds</a> · <a href="#/faq">FAQ</a></p>
    <div class="row wrap acc-end"><button class="btn ghost" data-action="logout">Log out</button><button class="btn danger" data-action="delete-account">Delete my account</button></div></div>`.s;
}
actions['resend-verify'] = el => busy(el, async () => { const r = await api('/auth/resend-verification', { method: 'POST' }); if (r.dev_verify_link) sessionStorage.setItem('dev_verify_link', r.dev_verify_link); toast(r.message, 'ok'); accountPage($('#view')); });
actions.unblock = async el => { await api(`/blocks/${el.dataset.id}`, { method: 'DELETE' }); toast('Unblocked.', 'ok'); accountPage($('#view')); };
submits.chpw = async f => { await api('/auth/change-password', { method: 'POST', body: formObj(f) }); f.reset(); toast('Password changed.', 'ok'); };
actions['delete-account'] = () => {
  openModal(html`<h2>Delete your account?</h2><p class="muted">Enter your password to confirm. Accepted bookings must be cancelled or completed first.</p><form data-submit="del" class="stack"><input class="field" name="password" type="password" placeholder="Password" required autocomplete="current-password"><button class="btn danger block" type="submit">Permanently delete</button></form>`, { label: 'Delete account' });
};
submits.del = async f => { await api('/auth/delete-account', { method: 'POST', body: formObj(f) }); clearAuth(); closeModal(); toast('Your account was deleted.', 'ok'); location.hash = '#/'; };

actions['reply-review'] = async el => {
  const r = await askText({ title: 'Reply publicly', label: 'Keep it friendly - your reply is shown on your profile.', required: true, confirm: 'Post reply' }); if (r === null) return;
  await api(`/reviews/${el.dataset.id}/reply`, { method: 'POST', body: { reply: r } }); toast('Reply posted.', 'ok'); dashboardPage($('#view'));
};
