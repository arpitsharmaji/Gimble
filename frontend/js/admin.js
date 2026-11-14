import { html, api, state, $, $$, toast, actions, submits, inr, fmtDT, ago, photo, askText, confirmBox, busy, openModal, closeModal, formObj } from './core.js';
import { CATEGORIES } from './safety.js';

let tab = 'overview';
const TABS = [['overview', 'Overview'], ['approvals', 'Approvals'], ['kyc', 'ID checks'], ['payouts', 'Payouts'], ['reports', 'Safety reports'], ['support', 'Support'], ['users', 'Users'], ['bookings', 'Bookings'], ['audit', 'Audit log']];

export async function adminPage(root) {
  if (!state.me || state.me.role !== 'admin') { root.innerHTML = '<div class="page narrow center"><h1>Admins only</h1><p class="muted">Log in with an administrator account.</p><button class="btn primary" data-action="auth-login">Log in</button></div>'; return; }
  root.innerHTML = html`<div class="page wide"><h1>Admin console</h1><div class="tabs" role="tablist">${TABS.map(([k, v]) => html`<button role="tab" class="${tab === k ? 'on' : ''}" data-action="admin-tab" data-tab="${k}">${v}<span class="tab-n" id="n-${k}"></span></button>`)}</div><div id="admin-body"><div class="skeleton"></div></div></div>`.s;
  await draw();
}
actions['admin-tab'] = el => { tab = el.dataset.tab; $$('.tabs button').forEach(b => b.classList.toggle('on', b === el)); draw(); };

async function draw() {
  const body = $('#admin-body'); if (!body) return;
  try {
    const s = await api('/admin/overview');
    const set = (k, n) => { const e = $('#n-' + k); if (e) e.textContent = n ? ` ${n}` : ''; };
    set('approvals', s.pending_partners); set('reports', s.open_reports); set('kyc', s.pending_kyc); set('payouts', s.pending_payouts); set('support', s.open_tickets);
    if (tab === 'overview') body.innerHTML = html`<div class="stats">${[['Users', s.users], ['Customers', s.customers], ['Live partners', s.live_partners], ['Pending approvals', s.pending_partners], ['Active memberships', s.active_memberships], ['Bookings', s.bookings], ['Completed', s.completed_bookings], ['Booked value', inr(s.gross_completed_inr)], ['Open reports', s.open_reports], ['Critical reports', s.critical_reports], ['Customer money held/paid (net)', inr(s.paid_in_inr)], ['Gimble fees (completed)', inr(s.platform_fees_inr)], ['Payouts waiting', `${s.pending_payouts} (${inr(s.pending_payout_inr)})`], ['ID checks waiting', s.pending_kyc], ['Open support tickets', s.open_tickets], ['Refunds to retry', s.refund_pending]].map(([l, v]) => html`<div class="${l === 'Critical reports' && v ? 'alert' : ''}"><b>${v}</b><span>${l}</span></div>`)}</div>`.s;
    if (tab === 'approvals') await approvals(body);
    if (tab === 'kyc') await kycTab(body);
    if (tab === 'payouts') await payoutsTab(body);
    if (tab === 'support') await supportTab(body);
    if (tab === 'reports') await reports(body);
    if (tab === 'users') await users(body);
    if (tab === 'bookings') await bookings(body);
    if (tab === 'audit') await auditTab(body);
  } catch (e) { body.innerHTML = html`<p class="err">${e.message}</p>`.s; }
}

async function approvals(body) {
  const rows = await api('/admin/partners?status=pending');
  body.innerHTML = rows.length ? rows.map(p => html`<div class="item review-card"><div class="rc-photo">${photo(p)}</div><div class="grow"><div class="between"><b>${p.name}, ${p.age} <small class="muted">${p.email}</small></b><span class="muted small">${p.submitted_at ? ago(p.submitted_at) : ''}</span></div>
    <p class="muted small">${p.city} · ${p.gender || 'gender not set'}</p><p class="headline">${p.headline}</p><p>${p.bio}</p>
    ${p.photos.length > 1 ? html`<div class="thumbs">${p.photos.map(u => html`<img src="${u}" alt="">`)}</div>` : ''}
    <div class="tags">${Object.entries(p.rates).map(([a, v]) => html`<span>${a} ${inr(v)}</span>`)}</div>
    <div class="row wrap"><button class="btn primary sm" data-action="ap-yes" data-id="${p.id}">Approve</button><button class="btn danger sm" data-action="ap-no" data-id="${p.id}">Reject…</button></div></div></div>`).join('') : '<div class="empty"><p>No profiles waiting for review 🎉</p></div>';
}
actions['ap-yes'] = el => busy(el, async () => { await api(`/admin/partners/${el.dataset.id}`, { method: 'PATCH', body: { approved: true } }); toast('Approved.', 'ok'); draw(); });
actions['ap-no'] = async el => { const r = await askText({ title: 'Reject profile', label: 'Reason (shown to the partner)', required: true, confirm: 'Reject', danger: true, placeholder: 'e.g. Please use a clear photo of your face' }); if (r === null) return; await api(`/admin/partners/${el.dataset.id}`, { method: 'PATCH', body: { approved: false, reason: r } }); toast('Rejected.', 'ok'); draw(); };

async function reports(body) {
  const rows = await api('/admin/reports?status=open');
  body.innerHTML = rows.length ? rows.map(r => html`<div class="item ${r.severity === 'critical' ? 'critical' : ''}"><div class="between"><b>${r.severity === 'critical' ? '🚨 ' : ''}${r.category === 'sos' ? 'SOS ALERT' : CATEGORIES[r.category] || r.category}</b><span class="muted small">${ago(r.created_at)}</span></div>
    <p class="small">From <b>${r.reporter ? r.reporter.name : '?'}</b>${r.target ? html` about <b>${r.target.name}</b>${r.target.active ? '' : ' (suspended)'}` : ''}${r.booking_id ? ` · booking #${r.booking_id}` : ''}</p>
    ${r.details ? html`<p>“${r.details}”</p>` : ''}
    <div class="row wrap"><button class="btn ghost sm" data-action="rp-res" data-id="${r.id}">Resolve</button>${r.target && r.target.active ? html`<button class="btn danger sm" data-action="rp-sus" data-id="${r.id}">Resolve &amp; suspend ${r.target.name}</button>` : ''}</div></div>`).join('') : '<div class="empty"><p>No open reports.</p></div>';
}
const resolve = async (el, suspend) => {
  const r = await askText({ title: suspend ? 'Resolve & suspend user' : 'Resolve report', label: 'Resolution note', confirm: 'Confirm', danger: suspend }); if (r === null) return;
  await api(`/admin/reports/${el.dataset.id}`, { method: 'PATCH', body: { resolution: r, suspend_target: suspend } }); toast('Report resolved.', 'ok'); draw();
};
actions['rp-res'] = el => resolve(el, false); actions['rp-sus'] = el => resolve(el, true);

let userQ = '';
async function users(body) {
  const rows = await api('/admin/users?q=' + encodeURIComponent(userQ));
  body.innerHTML = html`<form data-submit="user-search" class="row"><input class="field" name="q" value="${userQ}" placeholder="Search name or email"><button class="btn ghost" type="submit">Search</button></form>
    <div class="table-wrap"><table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>City</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(u => html`<tr><td>${u.id}</td><td>${u.name}</td><td>${u.email}${u.email_verified ? '' : ' ⚠'}</td><td>${u.role}</td><td>${u.city}</td><td>${u.active ? 'active' : html`<span class="warn" title="${u.suspended_reason}">suspended</span>`}</td><td>${u.role === 'admin' ? '' : u.active ? html`<button class="btn danger sm" data-action="u-sus" data-id="${u.id}">Suspend</button>` : html`<button class="btn ghost sm" data-action="u-un" data-id="${u.id}">Reinstate</button>`}</td></tr>`)}</tbody></table></div>`.s;
}
submits['user-search'] = async f => { userQ = formObj(f).q; draw(); };
actions['u-sus'] = async el => { const r = await askText({ title: 'Suspend user', label: 'Reason (required)', required: true, confirm: 'Suspend', danger: true }); if (r === null) return; await api(`/admin/users/${el.dataset.id}/suspend`, { method: 'PATCH', body: { suspended: true, reason: r } }); toast('User suspended.', 'ok'); draw(); };
actions['u-un'] = async el => { await api(`/admin/users/${el.dataset.id}/suspend`, { method: 'PATCH', body: { suspended: false } }); toast('User reinstated.', 'ok'); draw(); };

async function bookings(body) {
  const rows = await api('/admin/bookings');
  body.innerHTML = rows.length ? html`<div class="table-wrap"><table><thead><tr><th>#</th><th>Customer</th><th>Partner</th><th>Activity</th><th>When</th><th>Price</th><th>Status</th><th>Payment</th></tr></thead><tbody>${rows.map(b => html`<tr><td>${b.id}</td><td>${b.customer_name}</td><td>${b.partner_name}</td><td>${b.activity}</td><td>${fmtDT(b.scheduled_at)}</td><td>${inr(b.price)}</td><td><span class="pill ${b.status}">${b.status}</span></td><td>${b.payment_status}${b.payment_status === 'refund_pending' ? html` <button class="btn ghost sm" data-action="retry-refund" data-id="${b.id}">Retry refund</button>` : ''}</td></tr>`)}</tbody></table></div>`.s : '<div class="empty"><p>No bookings yet.</p></div>';
}
async function auditTab(body) {
  const rows = await api('/admin/audit');
  body.innerHTML = html`<div class="table-wrap"><table><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead><tbody>${rows.map(e => html`<tr><td>${ago(e.created_at)}</td><td>${e.actor_id ?? 'system'}</td><td>${e.action}</td><td>${e.target}</td><td>${e.detail}</td></tr>`)}</tbody></table></div>`.s;
}

actions['retry-refund'] = el => busy(el, async () => { const r = await api(`/admin/bookings/${el.dataset.id}/retry-refund`, { method: 'POST' }); toast('Refund status: ' + r.payment_status, 'ok'); draw(); });

// ---------- ID checks ----------
async function kycTab(body) {
  const rows = await api('/admin/kyc');
  body.innerHTML = rows.length ? rows.map(k => html`<div class="item"><div class="between"><b>${k.name} <small class="muted">${k.email}</small></b><span class="muted small">${ago(k.created_at)} · ${k.id_type}</span></div>
    <div class="row wrap"><button class="btn ghost sm" data-action="kyc-show" data-id="${k.id}" data-which="id">Show ID</button><button class="btn ghost sm" data-action="kyc-show" data-id="${k.id}" data-which="selfie">Show selfie</button></div>
    <div class="kyc-imgs" id="kyc-${k.id}"></div>
    <p class="muted small">Check: the photo matches the profile, ID is genuine and unexpired, name is consistent, age 18+. Files are deleted when you decide.</p>
    <div class="row wrap"><button class="btn primary sm" data-action="kyc-yes" data-id="${k.id}">Approve</button><button class="btn danger sm" data-action="kyc-no" data-id="${k.id}">Reject…</button></div></div>`).join('') : '<div class="empty"><p>No ID checks waiting.</p></div>';
}
actions['kyc-show'] = async el => {
  const res = await fetch(`/api/admin/kyc/${el.dataset.id}/file/${el.dataset.which}`, { headers: { Authorization: 'Bearer ' + state.token } });
  if (!res.ok) return toast('File not available.', 'error');
  const url = URL.createObjectURL(await res.blob());
  const box = $('#kyc-' + el.dataset.id); const img = document.createElement('img'); img.src = url; img.alt = el.dataset.which; box.append(img);
};
actions['kyc-yes'] = el => busy(el, async () => { await api(`/admin/kyc/${el.dataset.id}`, { method: 'PATCH', body: { approved: true } }); toast('Verified.', 'ok'); draw(); });
actions['kyc-no'] = async el => { const r = await askText({ title: 'Reject ID check', label: 'Reason (shown to the partner)', required: true, confirm: 'Reject', danger: true, placeholder: 'e.g. Selfie is blurry - please retake' }); if (r === null) return; await api(`/admin/kyc/${el.dataset.id}`, { method: 'PATCH', body: { approved: false, reason: r } }); toast('Rejected.', 'ok'); draw(); };

// ---------- payouts ----------
async function payoutsTab(body) {
  const rows = await api('/admin/payouts');
  body.innerHTML = (rows.length ? html`<p class="muted small">Send each payout by UPI from your business account, then record the transaction reference (UTR). Rejecting returns the money to the partner's wallet.</p>${rows.map(p => html`<div class="item"><div class="between"><b>${inr(p.amount)} → ${p.name}</b><span class="muted small">${ago(p.created_at)}</span></div><p>UPI: <code>${p.upi}</code> ${p.account_name ? ` (${p.account_name})` : ''}</p>
    <div class="row wrap"><button class="btn primary sm" data-action="po-paid" data-id="${p.id}">Mark paid…</button><button class="btn danger sm" data-action="po-no" data-id="${p.id}">Reject…</button></div></div>`)}` : html`<div class="empty"><p>No payouts waiting.</p></div>`).s;
}
actions['po-paid'] = async el => { const r = await askText({ title: 'Record payout', label: 'UPI / bank transaction reference (UTR)', required: true, confirm: 'Mark as paid' }); if (r === null) return; await api(`/admin/payouts/${el.dataset.id}`, { method: 'PATCH', body: { paid: true, reference: r } }); toast('Payout recorded.', 'ok'); draw(); };
actions['po-no'] = async el => { const r = await askText({ title: 'Reject payout', label: 'Reason (shown to the partner)', required: true, confirm: 'Reject', danger: true }); if (r === null) return; await api(`/admin/payouts/${el.dataset.id}`, { method: 'PATCH', body: { paid: false, reason: r } }); toast('Rejected; funds returned.', 'ok'); draw(); };

// ---------- support ----------
async function supportTab(body) {
  const rows = await api('/admin/support');
  body.innerHTML = rows.length ? rows.map(t => html`<div class="item"><div class="between"><b>#${t.id} · ${t.category.replace('_', ' ')}</b><span class="muted small">${ago(t.created_at)}</span></div><p class="small">${t.name} &lt;${t.email}&gt;${t.user_id ? ` · user ${t.user_id}` : ''}</p><p>${t.message}</p>
    <div class="row wrap"><button class="btn primary sm" data-action="tk-reply" data-id="${t.id}">Reply &amp; close</button><button class="btn ghost sm" data-action="tk-close" data-id="${t.id}">Close without reply</button></div></div>`).join('') : '<div class="empty"><p>No open tickets.</p></div>';
}
actions['tk-reply'] = async el => { const r = await askText({ title: 'Reply to customer', label: 'Your reply (emailed to them)', required: true, confirm: 'Send & close' }); if (r === null) return; await api(`/admin/support/${el.dataset.id}`, { method: 'PATCH', body: { reply: r, close: true } }); toast('Reply sent.', 'ok'); draw(); };
actions['tk-close'] = async el => { await api(`/admin/support/${el.dataset.id}`, { method: 'PATCH', body: { close: true } }); draw(); };
