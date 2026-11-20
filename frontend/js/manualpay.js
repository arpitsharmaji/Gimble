// Manual UPI QR payment: show the QR, the customer pays any amount they type themselves, then submits UTR + screenshot
// for an admin to approve. Used for both memberships and companion bookings.
import { html, api, $, openModal, closeModal, toast, submits, actions, inr } from './core.js';

const MAX = 5 * 1024 * 1024;

/** opts: { kind: 'membership'|'booking', amountInr, plan?, bookingId?, label?, onDone? } */
export async function openManualPay(opts) {
  let info;
  try { info = await api('/payments/manual/info'); } catch (e) { toast(e.message, 'error'); return; }
  const isMem = opts.kind === 'membership';
  const root = openModal(html`<span class="badge">${isMem ? 'MEMBERSHIP' : 'COMPANION BOOKING'}</span>
    <h2>Pay ${inr(opts.amountInr)} by UPI</h2>
    ${opts.label ? html`<p class="muted">${opts.label}</p>` : ''}
    <div class="upi-box">
      <img class="upi-qr" src="${info.qr_url}" alt="UPI QR code to pay ${info.payee_name}" width="220" height="220">
      <div class="upi-meta">
        <div class="muted small">Pay to</div><b>${info.payee_name}</b>
        <div class="upi-id"><code>${info.upi_id}</code><button type="button" class="btn ghost sm" data-action="copy-upi" data-v="${info.upi_id}">Copy</button></div>
      </div>
    </div>
    <ol class="mini-steps">
      <li>Open any UPI app (GPay, PhonePe, Paytm, BHIM) and scan the QR, or pay to the UPI ID.</li>
      <li><b>Type the amount yourself: ${inr(opts.amountInr)}.</b> The QR doesn't fill it in. Pay the exact amount.</li>
      <li>After paying, enter the <b>UTR / transaction ID</b> and upload a <b>screenshot</b> of the success screen below.</li>
    </ol>
    <form data-submit="manual-pay" class="stack">
      <label class="lbl" for="mp-utr">UTR / transaction ID</label>
      <input class="field" id="mp-utr" name="utr" required minlength="8" maxlength="40" autocomplete="off" placeholder="e.g. 412345678901">
      <label class="lbl" for="mp-proof">Payment screenshot</label>
      <input class="field" id="mp-proof" name="proof" type="file" accept="image/*" required>
      <button class="btn primary block" type="submit">Submit payment proof</button>
    </form>
    <p class="muted small">${isMem ? 'Your membership' : 'Your booking'} is confirmed once we verify the payment (usually within a few hours). Wrong amount or fake proof will be rejected.</p>`,
    { label: 'Pay by UPI' });
  root._mp = opts;
}

actions['copy-upi'] = async el => {
  try { await navigator.clipboard.writeText(el.dataset.v); toast('UPI ID copied.', 'ok'); }
  catch { toast('Copy failed - select the UPI ID and copy it manually.', 'error'); }
};

submits['manual-pay'] = async f => {
  const o = $('#modal-root')._mp;
  const file = f.elements.proof.files[0];
  if (!file) throw new Error('Choose the payment screenshot.');
  if (file.size > MAX) throw new Error('The screenshot must be under 5 MB.');
  const fd = new FormData(f);
  fd.append('kind', o.kind);
  if (o.plan) fd.append('plan', o.plan);
  if (o.bookingId) fd.append('booking_id', o.bookingId);
  const r = await api('/payments/manual', { method: 'POST', form: fd });
  closeModal();
  toast(r.message, 'ok');
  if (o.onDone) o.onDone();
};
