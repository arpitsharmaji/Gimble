import { html, api, state, $, $$, toast, actions, submits, formObj, inr, fmtDT, fmtD, ago, busy } from './core.js';

const needPartner = root => { root.innerHTML = html`<div class="page narrow center"><h1>Partner area</h1><p class="muted">Log in with a partner account to see this page.</p><button class="btn primary" data-action="auth-login">Log in</button></div>`.s; };
const isPartner = () => state.me && state.me.role === 'partner';
const KIND = { earning: 'Booking earning', cancel_compensation: 'Late-cancellation compensation', payout: 'Payout requested', payout_reversal: 'Payout returned', adjustment: 'Adjustment by Gimble' };

// ====================== EARNINGS ======================
export async function earningsPage(root) {
  if (!isPartner()) return needPartner(root);
  root.innerHTML = '<div class="page"><div class="skeleton tall"></div></div>';
  try {
    const w = await api('/wallet'), d = w.payout_details;
    root.innerHTML = html`<div class="page"><a class="back" href="#/dashboard">← Dashboard</a><h1>Earnings &amp; payouts</h1>
      <div class="stats"><div><b>${inr(w.available)}</b><span>Available to withdraw</span></div><div><b>${inr(w.pending)}</b><span>On ${w.hold_hours}h hold</span></div><div><b>${inr(w.balance)}</b><span>Wallet balance</span></div></div>
      <p class="muted small">You keep ${100 - w.fee_percent}% of every completed booking (Gimble fee ${w.fee_percent}%). Earnings are released ${w.hold_hours} hours after completion so any issue can be reported first. Minimum payout ${inr(w.min_payout)}, sent to your UPI ID within 2 working days.</p>
      ${!w.verified ? html`<div class="notice warn">Verify your ID to unlock withdrawals. <a href="#/verify-id">Start verification →</a></div>` : ''}
      <h2>Payout details</h2><form data-submit="payout-details" class="stack"><label class="lbl" for="upi">UPI ID</label><input class="field" id="upi" name="upi" value="${d.upi}" placeholder="yourname@okaxis" required autocomplete="off">
        <label class="lbl" for="acn">Name on the UPI account</label><input class="field" id="acn" name="name" value="${d.name}" maxlength="80"><button class="btn ghost" type="submit">Save payout details</button></form>
      <h2>Withdraw</h2><form data-submit="payout" class="row wrap"><input class="field" style="max-width:180px" name="amount" type="number" min="${w.min_payout}" max="${w.available}" step="1" placeholder="Amount (₹)" required ${w.verified && d.upi && w.available >= w.min_payout ? '' : 'disabled'}>
        <button class="btn primary" type="submit" ${w.verified && d.upi && w.available >= w.min_payout ? '' : 'disabled'}>Request payout</button></form>
      ${w.available < w.min_payout ? html`<p class="muted small">You need at least ${inr(w.min_payout)} available to withdraw.</p>` : ''}
      ${w.payouts.length ? html`<h2>Payout history</h2><div class="list">${w.payouts.map(p => html`<div class="item between"><div><b>${inr(p.amount)}</b> <span class="muted small">to ${p.upi} · ${fmtD(p.created_at)}</span>${p.reference ? html`<p class="muted small">Ref: ${p.reference}</p>` : ''}${p.reason ? html`<p class="muted small">${p.reason}</p>` : ''}</div><span class="pill ${p.status === 'paid' ? 'completed' : p.status === 'rejected' ? 'rejected' : 'requested'}">${p.status}</span></div>`)}</div>` : ''}
      <h2>Wallet activity</h2>${w.ledger.length ? html`<div class="table-wrap"><table><thead><tr><th>When</th><th>What</th><th>Note</th><th>Amount</th></tr></thead><tbody>${w.ledger.map(e => html`<tr><td>${ago(e.created_at)}</td><td>${KIND[e.kind] || e.kind}</td><td class="muted">${e.note}${e.amount > 0 && new Date(e.available_at) > Date.now() ? ` · available ${fmtDT(e.available_at)}` : ''}</td><td class="${e.amount < 0 ? 'warn' : 'ok'}"><b>${e.amount < 0 ? '-' : '+'}${inr(Math.abs(e.amount))}</b></td></tr>`)}</tbody></table></div>` : html`<div class="empty"><p>No earnings yet.</p><p class="muted">Completed, paid bookings appear here.</p></div>`}</div>`.s;
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}
submits['payout-details'] = async f => { const r = await api('/wallet/payout-details', { method: 'PUT', body: formObj(f) }); toast(r.message, 'ok'); earningsPage($('#view')); };
submits.payout = async f => { const r = await api('/wallet/payouts', { method: 'POST', body: { amount: Number(formObj(f).amount) } }); toast(r.message, 'ok'); earningsPage($('#view')); };

// ====================== WEEKLY HOURS ======================
const DAYS = [['mon', 'Monday'], ['tue', 'Tuesday'], ['wed', 'Wednesday'], ['thu', 'Thursday'], ['fri', 'Friday'], ['sat', 'Saturday'], ['sun', 'Sunday']];
export async function schedulePage(root) {
  if (!isPartner()) return needPartner(root);
  try {
    const p = await api('/partner/profile'); const s = p.schedule || {}; const any = !Object.keys(s).length;
    root.innerHTML = html`<div class="page narrow"><a class="back" href="#/dashboard">← Dashboard</a><h1>Weekly hours</h1>
      <p class="muted">Customers can only request times inside these hours (India time, IST). Leave everything off to accept requests at any time.</p>
      <form data-submit="schedule" class="stack">${DAYS.map(([k, l]) => html`<div class="act-row"><label class="check"><input type="checkbox" name="on_${k}" ${s[k] ? 'checked' : ''}> <span>${l}</span></label><span class="grow"></span><input type="time" class="field time" name="from_${k}" value="${s[k] ? s[k][0] : '10:00'}" aria-label="${l} from"> <span class="muted">to</span> <input type="time" class="field time" name="to_${k}" value="${s[k] ? s[k][1] : '20:00'}" aria-label="${l} to"></div>`)}
      <p class="muted small" id="sched-note">${any ? 'Currently: any time.' : ''}</p><button class="btn primary" type="submit">Save hours</button></form></div>`.s;
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}
submits.schedule = async f => {
  const b = formObj(f), days = {};
  for (const [k] of DAYS) if (b['on_' + k]) days[k] = [b['from_' + k], b['to_' + k]];
  await api('/partner/schedule', { method: 'PUT', body: { days } }); toast(Object.keys(days).length ? 'Weekly hours saved.' : 'Cleared - you accept requests at any time.', 'ok');
};

// ====================== ID VERIFICATION ======================
export async function kycPage(root) {
  if (!isPartner()) return needPartner(root);
  try {
    const k = await api('/partner/kyc'), l = k.latest;
    root.innerHTML = html`<div class="page narrow"><a class="back" href="#/dashboard">← Dashboard</a><h1>ID verification</h1>
      ${k.verified ? html`<div class="notice ok"><b>✓ You're ID verified.</b> The badge shows on your profile and you can withdraw earnings.</div>` : ''}
      ${!k.verified && l && l.status === 'pending' ? html`<div class="notice info">Your documents are under review (submitted ${ago(l.created_at)}). We usually finish within 1-2 working days.</div>` : ''}
      ${!k.verified && l && l.status === 'rejected' ? html`<div class="notice warn"><b>Not approved:</b> ${l.reason}. Please resubmit below.</div>` : ''}
      ${!k.verified && !(l && l.status === 'pending') ? html`
      <p class="muted">Verified partners get a ✓ badge, more bookings and can withdraw earnings. We check that your ID and a selfie match.</p>
      <form data-submit="kyc" class="stack"><label class="lbl" for="k-type">Government ID type</label><select class="field" id="k-type" name="id_type" required>${k.id_types.map(t => html`<option value="${t}">${t.replace('_', ' ').replace(/^./, c => c.toUpperCase())}</option>`)}</select>
      <label class="lbl" for="k-id">Photo of your ID (all four corners visible)</label><input class="field" id="k-id" name="id_file" type="file" accept="image/jpeg,image/png,image/webp" required>
      <label class="lbl" for="k-self">Selfie holding the same ID</label><input class="field" id="k-self" name="selfie_file" type="file" accept="image/jpeg,image/png,image/webp" required capture="user">
      <div class="notice">🔒 <b>Privacy:</b> files are stored privately, only Gimble admins can open them, and they are <b>deleted as soon as we decide</b> - we keep only the result. For Aadhaar, cover the first 8 digits before photographing.</div>
      <button class="btn primary block" type="submit">Submit for verification</button></form>` : ''}</div>`.s;
  } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; }
}
submits.kyc = async f => {
  const fd = new FormData(f);
  for (const k of ['id_file', 'selfie_file']) if (fd.get(k).size > 5 * 1024 * 1024) throw new Error('Each file must be under 5 MB.');
  const r = await api('/partner/kyc', { method: 'POST', form: fd }); toast(r.message, 'ok'); kycPage($('#view'));
};
