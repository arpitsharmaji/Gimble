import { html, api, state, openModal, closeModal, toast, actions, submits, formObj, confirmBox, $ } from './core.js';

export const CATEGORIES = {
  sexual_solicitation: 'Sexual or adult-service solicitation',
  harassment: 'Harassment or disrespect',
  scam_or_payment: 'Scam / asked for money outside Gimble',
  fake_profile: 'Fake or misleading profile',
  no_show: 'No-show',
  unsafe: 'I felt unsafe',
  underage: 'Appears to be under 18',
  other: 'Something else',
};

export function reportModal(targetId, targetName, bookingId = null) {
  openModal(html`<h2>Report ${targetName}</h2><p class="muted">Reports are reviewed by our safety team. If you are in immediate danger, call <b>112</b>.</p>
    <form data-submit="report" class="stack"><input type="hidden" name="target_id" value="${targetId}"><input type="hidden" name="booking_id" value="${bookingId || ''}">
    <label class="lbl" for="rp-cat">What happened?</label>
    <select class="field" id="rp-cat" name="category" required>${Object.entries(CATEGORIES).map(([k, v]) => html`<option value="${k}">${v}</option>`)}</select>
    <label class="lbl" for="rp-det">Details (optional)</label><textarea class="field" id="rp-det" name="details" rows="4" maxlength="2000" placeholder="Tell us what happened"></textarea>
    <button class="btn danger block" type="submit">Submit report</button></form>`, { label: 'Report user' });
}
submits.report = async f => {
  const b = formObj(f);
  await api('/reports', { method: 'POST', body: { target_id: Number(b.target_id), booking_id: b.booking_id ? Number(b.booking_id) : null, category: b.category, details: b.details } });
  closeModal(); toast('Report sent. Thank you for helping keep Gimble safe.', 'ok');
};

export async function blockUser(id, name) {
  if (!await confirmBox({ title: `Block ${name}?`, text: 'You won\'t see each other, can\'t message, and any pending or accepted bookings between you will be cancelled.', confirm: 'Block', danger: true })) return false;
  try { await api(`/blocks/${id}`, { method: 'PUT' }); toast(`${name} blocked.`, 'ok'); return true; }
  catch (e) { toast(e.message, 'error'); return false; }
}

export function safetyModal(booking = null) {
  const other = booking ? (state.me.id === booking.customer_id ? booking.partner_name : booking.customer_name) : '';
  openModal(html`<h2>Safety centre</h2>
    <div class="sos"><p><b>In danger? Call 112 now.</b></p><a class="btn danger block" href="tel:112">📞 Call 112 (emergency)</a></div>
    <ul class="plain small"><li>Women's helpline: <a href="tel:1091">1091</a></li><li>Cyber-crime helpline: <a href="tel:1930">1930</a></li></ul>
    <hr>
    <p class="muted small">Alert the Gimble safety team${booking ? html` about your plan with <b>${other}</b>` : ''}. This does not replace calling emergency services.</p>
    <form data-submit="sos" class="stack"><input type="hidden" name="booking_id" value="${booking ? booking.id : ''}">
    <textarea class="field" name="note" rows="2" maxlength="500" placeholder="What's happening? (optional)"></textarea>
    <button class="btn ghost block" type="submit">Send alert to Gimble team</button></form>
    <p class="small center"><a href="#/safety" data-action="close-modal">Read safety tips</a></p>`, { label: 'Safety centre' });
}
submits.sos = async f => {
  const b = formObj(f);
  const r = await api('/safety/sos', { method: 'POST', body: { booking_id: b.booking_id ? Number(b.booking_id) : null, note: b.note } });
  toast(r.message, 'ok');
};
actions['open-safety'] = () => safetyModal();
