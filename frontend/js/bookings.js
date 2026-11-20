import { openManualPay } from './manualpay.js';
import { html, api, state, $, $$, openModal, closeModal, toast, actions, submits, formObj, inr, fmtDT, avatar, emptyState, askText, confirmBox, busy, timeUntil, downloadICS, mapsUrl, openRazorpay } from './core.js';
import { reportModal, safetyModal } from './safety.js';
import { confetti, haptic, reveal } from './fx.js';
import { startBooking } from './discover.js';

let tab = null, rows = [];
const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
const CLOSED = ['completed', 'cancelled', 'rejected', 'expired'];
const STEPS = ['Requested', 'Accepted', 'Paid', 'Done'];
const needLogin = root => { root.innerHTML = html`<div class="page narrow">${emptyState({ icon: '🔐', title: 'Please log in', text: 'Log in to see your bookings.', cta: html`<button class="btn primary" data-action="auth-login">Log in</button>` })}</div>`.s; };
const pill = s => html`<span class="pill ${s}">${s}</span>`;

function stepIndex(b) {
  if (b.status === 'completed') return 4;
  if (b.status === 'accepted') return b.payment_status === 'paid' ? 3 : b.payments_on ? 1 : 2;
  return 0;
}
const stepper = b => ['cancelled', 'rejected', 'expired'].includes(b.status)
  ? html`<div class="bk-dead">${b.status === 'cancelled' ? '✕ Cancelled' : b.status === 'rejected' ? '✕ Declined' : '⌛ Expired'}${b.status_reason ? html` · <span class="muted">${b.status_reason}</span>` : ''}</div>`
  : html`<ol class="stepper" aria-label="Booking progress">${STEPS.map((s, i) => html`<li class="${i < stepIndex(b) ? 'done' : i === stepIndex(b) ? 'now' : ''}"><i>${i < stepIndex(b) ? '✓' : i + 1}</i><span>${s}</span></li>`)}</ol>`;

let reviewing = new Set();   // booking ids whose UPI payment proof is waiting for admin approval
function payLine(b, isP) {
  if (b.payment_status === 'refunded') return html`<p class="bk-note ok">↩ Fully refunded (${inr(b.refund_amount)})</p>`;
  if (b.payment_status === 'partially_refunded') return html`<p class="bk-note warn">↩ Partly refunded (${inr(b.refund_amount)}) under the cancellation policy</p>`;
  if (b.payment_status === 'refund_pending') return html`<p class="bk-note warn">↩ Refund of ${inr(b.refund_amount)} is being processed</p>`;
  if (b.status === 'accepted' && b.payments_on) {
    if (b.payment_status === 'paid') return html`<p class="bk-note ok">🔒 Paid ${inr(b.paid_amount)} · held safely by Gimble until your plan is done${isP ? html` · you'll earn <b>${inr(b.partner_earning)}</b>` : ''}</p>`;
    if (reviewing.has(b.id)) return isP ? html`<p class="bk-note warn">⏳ Customer's payment is being verified</p>` : html`<p class="bk-note warn">⏳ Payment proof submitted - we're verifying it. You'll be notified once your plan is confirmed.</p>`;
    return isP ? html`<p class="bk-note warn">⏳ Waiting for the customer to pay (they must pay by ${fmtDT(b.pay_deadline)})</p>`
      : html`<div class="paybox"><span>Pay <b>${inr(b.price)}</b> by ${fmtDT(b.pay_deadline)} to confirm this plan.</span><button class="btn primary sm" data-action="pay-booking" data-id="${b.id}">Pay ${inr(b.price)}</button></div>`;
  }
  return '';
}

function card(b, isP) {
  const other = isP ? b.customer_name : b.partner_name, otherId = isP ? b.customer_id : b.partner_id;
  const d = new Date(b.scheduled_at), started = d <= Date.now();
  const soon = b.status === 'accepted' && Date.now() > d - 2 * 3600e3 && Date.now() < d.getTime() + (b.duration_minutes + 360) * 60e3;
  const until = b.status === 'accepted' && !started ? timeUntil(b.scheduled_at) : '';
  const canComplete = b.status === 'accepted' && started && !(b.payments_on && b.payment_status !== 'paid');
  return html`<article class="bk" data-id="${b.id}">
    <div class="bk-head">${avatar(other, isP ? '' : b.partner_photo, 'md')}<div class="grow"><b class="bk-title">${b.activity}</b><p class="muted small">with ${other}</p></div>${pill(b.status)}</div>
    <div class="bk-when"><div class="datechip"><small>${MON[d.getMonth()]}</small><b>${d.getDate()}</b></div>
      <div class="grow"><b>${d.toLocaleDateString('en-IN', { weekday: 'long' })}, ${d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}</b> <span class="muted">· ${b.duration_minutes / 60}h</span>
        <a class="bk-loc" href="${mapsUrl(b.location)}" target="_blank" rel="noopener noreferrer">📍 ${b.location} <span>↗</span></a></div>
      <div class="bk-price"><b>${inr(b.price)}</b>${until ? html`<em class="count">in ${until}</em>` : ''}</div></div>
    ${b.note ? html`<p class="bk-quote">“${b.note}”</p>` : ''}
    ${stepper(b)}${payLine(b, isP)}
    <div class="bk-actions">
      ${isP && b.status === 'requested' ? html`<button class="btn primary sm" data-action="bk" data-id="${b.id}" data-s="accepted">Accept</button><button class="btn ghost sm" data-action="bk" data-id="${b.id}" data-s="rejected">Decline</button>` : ''}
      ${!isP && b.status === 'requested' ? html`<button class="btn ghost sm" data-action="bk" data-id="${b.id}" data-s="cancelled">Cancel request</button>` : ''}
      ${b.status === 'accepted' ? html`<a class="btn ghost sm" href="#/messages/${otherId}">💬 Message</a><button class="btn ghost sm" data-action="bk-ics" data-id="${b.id}">📅 Add to calendar</button>${canComplete ? html`<button class="btn primary sm" data-action="bk" data-id="${b.id}" data-s="completed">Mark completed</button>` : ''}<button class="btn ghost sm" data-action="bk" data-id="${b.id}" data-s="cancelled">Cancel</button>` : ''}
      ${soon ? html`<button class="btn danger sm" data-action="bk-safety" data-id="${b.id}">🛡 Safety</button>` : ''}
      ${!isP && b.status === 'completed' ? html`<button class="btn primary sm" data-action="bk-review" data-id="${b.id}">★ Leave a review</button>` : ''}
      ${!isP && CLOSED.includes(b.status) ? html`<button class="btn ghost sm" data-action="bk-again" data-id="${b.partner_id}">↻ Book again</button>` : ''}
      ${['completed', 'accepted'].includes(b.status) ? html`<button class="link small" data-action="bk-report" data-id="${b.id}">Report</button>` : ''}
    </div></article>`;
}

export async function bookingsPage(root) {
  if (!state.me) return needLogin(root);
  root.innerHTML = '<div class="page"><h1>Bookings</h1><div class="skeleton"></div></div>';
  try { rows = await api('/bookings'); reviewing = await loadReviewing(); } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; return; }
  root._rows = rows; draw(root);
}
function draw(root = $('#view')) {
  const isP = state.me.role === 'partner';
  const T = isP ? [['requests', 'Requests', b => b.status === 'requested'], ['upcoming', 'Upcoming', b => b.status === 'accepted'], ['past', 'Past', b => CLOSED.includes(b.status)]]
    : [['upcoming', 'Upcoming', b => b.status === 'accepted'], ['pending', 'Pending', b => b.status === 'requested'], ['past', 'Past', b => CLOSED.includes(b.status)]];
  if (!tab || !T.some(t => t[0] === tab)) tab = (T.find(t => rows.some(t[2])) || T[0])[0];
  const cur = T.find(t => t[0] === tab), list = rows.filter(cur[2]);
  list.sort((a, b) => cur[0] === 'past' ? new Date(b.scheduled_at) - new Date(a.scheduled_at) : new Date(a.scheduled_at) - new Date(b.scheduled_at));
  const empties = { requests: ['📬', 'No new requests', 'When a customer asks to book you, it shows up here.'], upcoming: ['🗓️', 'Nothing coming up', isP ? 'Accepted bookings appear here.' : 'Find someone to meet and your plans will show up here.'], pending: ['⏳', 'No pending requests', 'Requests waiting for a partner to accept appear here.'], past: ['🧾', 'No past bookings yet', 'Completed and cancelled plans are kept here.'] };
  const [ic, tt, tx] = empties[tab];
  root.innerHTML = html`<div class="page narrow-lg"><div class="between"><h1>Bookings</h1>${!isP ? html`<a class="btn ghost sm" href="#/browse">+ New plan</a>` : ''}</div>
    <div class="tabs4" role="tablist">${T.map(([k, l, f]) => { const n = rows.filter(f).length; return html`<button role="tab" aria-selected="${String(k === tab)}" class="${k === tab ? 'on' : ''}" data-action="bk-tab" data-tab="${k}">${l}${n ? html`<i>${n}</i>` : ''}</button>`; })}</div>
    ${list.length ? html`<div class="bk-list">${list.map(b => card(b, isP))}</div>` : emptyState({ icon: ic, title: tt, text: tx, cta: !isP && tab !== 'past' ? html`<a class="btn primary" href="#/browse">Browse companions</a>` : '' })}</div>`.s;
  root._rows = rows;
}
actions['bk-tab'] = el => { tab = el.dataset.tab; haptic(5); draw(); };
const find = el => rows.find(b => b.id === Number(el.dataset.id));
const loadReviewing = async () => { try { return new Set((await api('/payments/manual/mine')).filter(m => m.kind === 'booking' && m.status === 'pending').map(m => m.booking_id)); } catch { return new Set(); } };
const reload = async () => { rows = await api('/bookings'); reviewing = await loadReviewing(); tab = null; draw(); };

actions['bk-ics'] = el => { const b = find(el), isP = state.me.role === 'partner'; downloadICS(b, isP ? b.customer_name : b.partner_name); toast('Calendar file downloaded.', 'ok'); };
actions['bk-again'] = async el => { try { const p = await api(`/partners/${el.dataset.id}`); startBooking(p, Object.keys(p.rates)[0]); } catch { toast('This partner isn\'t available right now.', 'error'); } };
actions['pay-booking'] = el => busy(el, async () => {
  const b = find(el);
  const co = await api(`/bookings/${b.id}/pay`, { method: 'POST' });
  const done = async () => { confetti(); haptic(30); toast('Payment confirmed - your plan is booked! 🎉', 'ok'); await reload(); };
  if (co.mode === 'manual') return openManualPay({ kind: 'booking', bookingId: b.id, amountInr: b.price, label: `${b.activity} with ${b.partner_name}`, onDone: reload });
  if (co.mode === 'demo') { await api(`/bookings/${b.id}/demo-pay`, { method: 'POST' }); return done(); }
  await openRazorpay(co, async resp => { if (resp) await api('/payments/verify', { method: 'POST', body: resp }); await done(); });
});
actions.bk = async el => {
  const b = find(el), s = el.dataset.s; let reason = '';
  if (s === 'cancelled' && b.status === 'accepted') { const refundNote = b.payment_status === 'paid' ? (state.me.id === b.customer_id ? ` If you cancel now you get ${b.refund_percent_now}% back.` : ' The customer will be fully refunded.') : ''; reason = await askText({ title: 'Cancel this booking?', label: 'Reason (shared with the other person).' + refundNote, required: true, confirm: 'Cancel booking', danger: true }); if (reason === null) return; }
  else if (s === 'rejected') { reason = await askText({ title: 'Decline request', label: 'Optional note', confirm: 'Decline' }); if (reason === null) return; }
  else if (s === 'cancelled') { if (!await confirmBox({ title: 'Cancel request?', text: 'The partner will be notified.', confirm: 'Cancel request', danger: true })) return; }
  await busy(el, async () => { await api(`/bookings/${b.id}`, { method: 'PATCH', body: { status: s, reason } }); if (s === 'accepted') confetti(); toast('Booking updated.', 'ok'); await reload(); });
};
actions['bk-safety'] = el => safetyModal(find(el));
actions['bk-report'] = el => { const b = find(el), isP = state.me.role === 'partner'; reportModal(isP ? b.customer_id : b.partner_id, isP ? b.customer_name : b.partner_name, b.id); };
actions['bk-review'] = el => {
  const b = find(el);
  openModal(html`<div class="center">${avatar(b.partner_name, b.partner_photo, 'lg')}<h2>How was your plan with ${b.partner_name}?</h2></div><form data-submit="review" class="stack"><input type="hidden" name="id" value="${b.id}">
    <div class="starpick" role="radiogroup" aria-label="Rating">${[5, 4, 3, 2, 1].map(n => html`<input type="radio" id="st${n}" name="rating" value="${n}" ${n === 5 ? 'checked' : ''}><label for="st${n}" title="${n} stars">★</label>`)}</div>
    <textarea class="field" name="comment" rows="3" maxlength="1000" placeholder="Tell others how it went (optional)"></textarea><button class="btn primary block" type="submit">Submit verified review</button></form>`, { label: 'Review' });
};
submits.review = async f => { const b = formObj(f); await api(`/bookings/${b.id}/reviews`, { method: 'POST', body: { rating: Number(b.rating), comment: b.comment } }); closeModal(); confetti(); toast('Thanks for your review!', 'ok'); await reload(); };
