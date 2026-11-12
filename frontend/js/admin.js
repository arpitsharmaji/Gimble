import { html, api, state, $, $$, toast, actions, submits, inr, fmtDT, ago, photo, askText, confirmBox, busy, openModal, closeModal, formObj } from './core.js';
import { CATEGORIES } from './safety.js';

let tab = 'overview';
const TABS = [['overview', 'Overview'], ['approvals', 'Approvals'], ['reports', 'Safety reports'], ['users', 'Users'], ['bookings', 'Bookings'], ['audit', 'Audit log']];

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
    set('approvals', s.pending_partners); set('reports', s.open_reports);
    if (tab === 'overview') body.innerHTML = html`<div class="stats">${[['Users', s.users], ['Customers', s.customers], ['Live partners', s.live_partners], ['Pending approvals', s.pending_partners], ['Active memberships', s.active_memberships], ['Bookings', s.bookings], ['Completed', s.completed_bookings], ['Booked value', inr(s.gross_completed_inr)], ['Open reports', s.open_reports], ['Critical reports', s.critical_reports]].map(([l, v]) => html`<div class="${l === 'Critical reports' && v ? 'alert' : ''}"><b>${v}</b><span>${l}</span></div>`)}</div>`.s;
    if (tab === 'approvals') await approvals(body);
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
  body.innerHTML = rows.length ? html`<div class="table-wrap"><table><thead><tr><th>#</th><th>Customer</th><th>Partner</th><th>Activity</th><th>When</th><th>Price</th><th>Status</th></tr></thead><tbody>${rows.map(b => html`<tr><td>${b.id}</td><td>${b.customer_name}</td><td>${b.partner_name}</td><td>${b.activity}</td><td>${fmtDT(b.scheduled_at)}</td><td>${inr(b.price)}</td><td><span class="pill ${b.status}">${b.status}</span></td></tr>`)}</tbody></table></div>`.s : '<div class="empty"><p>No bookings yet.</p></div>';
}
async function auditTab(body) {
  const rows = await api('/admin/audit');
  body.innerHTML = html`<div class="table-wrap"><table><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead><tbody>${rows.map(e => html`<tr><td>${ago(e.created_at)}</td><td>${e.actor_id ?? 'system'}</td><td>${e.action}</td><td>${e.target}</td><td>${e.detail}</td></tr>`)}</tbody></table></div>`.s;
}
