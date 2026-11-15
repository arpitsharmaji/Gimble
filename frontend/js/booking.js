// Booking wizard: pick activity -> day -> time slot -> duration -> public place, with a live summary.
// All times are India Standard Time (the platform is India-only); the API receives a UTC instant.
import { html, api, state, $, $$, openModal, closeModal, toast, actions, submits, inr, avatar } from './core.js';
import { haptic, confetti } from './fx.js';

const IST_MS = 5.5 * 3600e3, LEAD_MS = 125 * 60e3;
const DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DURATIONS = [60, 120, 180, 240, 360];
const VENUES = ['Starbucks', 'Café Coffee Day', 'Mall food court', 'Popular café near a metro'];
const EMOJI = { 'Video call': '📹', 'Coffee date': '☕', 'Movie companion': '🎬', 'Dinner': '🍽️', 'Shopping': '🛍️', 'Gym partner': '🏋️', 'City exploration': '🌆', 'Event / concert plus-one': '🎤', 'Cafe study partner': '📚', 'Language practice': '🗣️', 'Sports partner': '⚽', 'Museum / gallery visit': '🖼️', 'Board games': '🎲' };

let W = null;
const days = () => { const b = new Date(Date.now() + IST_MS); b.setUTCHours(0, 0, 0, 0); return [...Array(14)].map((_, i) => new Date(b.getTime() + i * 86400e3)); };
const windowFor = (p, d) => { const s = p.schedule || {}; if (!Object.keys(s).length) return [8 * 60, 22 * 60]; const w = s[DAYS[d.getUTCDay()]]; return w ? w.map(t => Number(t.slice(0, 2)) * 60 + Number(t.slice(3))) : null; };
const toUtcMs = (d, minutes) => d.getTime() + minutes * 60000 - IST_MS;
function slotsFor(p, d, dur) {
  const w = windowFor(p, d); if (!w) return [];
  const out = []; for (let t = w[0]; t + dur <= w[1]; t += 30) if (toUtcMs(d, t) >= Date.now() + LEAD_MS) out.push(t);
  return out;
}
const hhmm = m => { const h = Math.floor(m / 60), mm = m % 60, ap = h >= 12 ? 'PM' : 'AM'; return `${((h + 11) % 12) + 1}:${String(mm).padStart(2, '0')} ${ap}`; };
const dayName = (d, i) => i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : `${WD[d.getUTCDay()]}, ${d.getUTCDate()} ${MON[d.getUTCMonth()]}`;

export function bookingWizard(p, activity) {
  const acts = Object.keys(p.rates); const ds = days();
  W = { p, activity: acts.includes(activity) ? activity : acts[0], dur: 60, ds, dayIdx: -1, slot: null };
  // preselect the first day that has a free slot
  W.dayIdx = ds.findIndex(d => slotsFor(p, d, W.dur).length);
  openModal(html`<div class="w-head">${avatar(p.name, p.photo_url, 'sm')}<div><span class="badge">BOOKING REQUEST</span><h2>Plan with ${p.name}</h2></div></div>
    <div class="w-sec"><label class="lbl">What would you like to do?</label><div class="w-chips" id="w-acts"></div></div>
    <div class="w-sec"><label class="lbl">Day</label><div class="day-row" id="w-days"></div></div>
    <div class="w-sec"><label class="lbl">Start time <span class="muted">(India time)</span></label><div class="slot-grid" id="w-slots"></div></div>
    <div class="w-sec"><label class="lbl">How long?</label><div class="w-chips" id="w-durs"></div></div>
    <div class="w-sec"><label class="lbl" for="w-loc">Public meeting place</label><input class="field" id="w-loc" maxlength="200" placeholder="e.g. Starbucks, CyberHub, Gurugram" autocomplete="off">
      <div class="w-chips tight">${VENUES.map(v => html`<button type="button" class="chip" data-action="w-venue" data-v="${v}">${v}</button>`)}</div></div>
    <details class="w-note"><summary>Add a note for ${p.name} (optional)</summary><textarea class="field" id="w-note" rows="2" maxlength="1000" placeholder="Anything helpful - e.g. what you'd like to see or talk about"></textarea></details>
    <div class="w-sum" id="w-sum"></div>
    <label class="check"><input type="checkbox" id="w-ack"> <span>I'll meet in a public place, respect boundaries and keep payments on Gimble. I understand sexual services aren't allowed.</span></label>
    <button class="btn primary big block" id="w-send" disabled>Send request</button>
    <p class="muted small center">Nothing is charged now. If ${p.name} accepts, you pay securely through Gimble to confirm. <a href="#/refunds" data-action="close-modal">Refund policy</a></p>`, { label: 'Booking request', wide: false });
  $('#w-loc').addEventListener('input', refresh); $('#w-ack').addEventListener('change', refresh);
  draw();
}

function draw() {
  const { p, ds } = W;
  $('#w-acts').innerHTML = Object.entries(p.rates).map(([a, v]) => `<button type="button" class="wchip ${a === W.activity ? 'on' : ''}" data-action="w-act" data-a="${a.replace(/"/g, '&quot;')}"><span>${EMOJI[a] || '✨'}</span>${a.replace(/</g, '&lt;')} <b>${inr(v)}</b></button>`).join('');
  $('#w-durs').innerHTML = DURATIONS.map(m => `<button type="button" class="wchip ${m === W.dur ? 'on' : ''}" data-action="w-dur" data-m="${m}">${m / 60} hour${m > 60 ? 's' : ''}</button>`).join('');
  $('#w-days').innerHTML = ds.map((d, i) => { const n = slotsFor(p, d, W.dur).length; return `<button type="button" class="day ${i === W.dayIdx ? 'on' : ''}" data-action="w-day" data-i="${i}" ${n ? '' : 'disabled'} aria-label="${dayName(d, i)}"><small>${i === 0 ? 'Today' : WD[d.getUTCDay()]}</small><b>${d.getUTCDate()}</b><em>${MON[d.getUTCMonth()]}</em></button>`; }).join('');
  const slots = W.dayIdx >= 0 ? slotsFor(p, ds[W.dayIdx], W.dur) : [];
  if (W.slot !== null && !slots.includes(W.slot)) W.slot = null;
  $('#w-slots').innerHTML = slots.length ? slots.map(t => `<button type="button" class="slot ${t === W.slot ? 'on' : ''}" data-action="w-slot" data-t="${t}">${hhmm(t)}</button>`).join('')
    : `<p class="muted small">${W.dayIdx < 0 ? `${p.name} has no free times in the next two weeks for this length.` : 'No times left that day - try another day.'}</p>`;
  refresh();
}

function refresh() {
  if (!W) return;
  const { p } = W, price = p.rates[W.activity], ok = W.slot !== null && W.dayIdx >= 0 && $('#w-loc').value.trim().length >= 3 && $('#w-ack').checked;
  const when = W.slot !== null ? `${dayName(W.ds[W.dayIdx], W.dayIdx)} · ${hhmm(W.slot)} – ${hhmm(W.slot + W.dur)}` : 'Choose a day and time';
  $('#w-sum').innerHTML = `<div><span>Plan</span><b>${W.activity.replace(/</g, '&lt;')}</b></div><div><span>When</span><b>${when}</b></div><div class="tot"><span>Price</span><b>${inr(price)}</b><small>pay after acceptance</small></div>`;
  const btn = $('#w-send'); btn.disabled = !ok; btn.textContent = ok ? `Send request · ${inr(price)}` : 'Send request';
}

actions['w-act'] = el => { W.activity = el.dataset.a; haptic(6); draw(); };
actions['w-dur'] = el => { W.dur = Number(el.dataset.m); haptic(6); const f = slotsFor(W.p, W.ds[Math.max(W.dayIdx, 0)], W.dur).length; if (!f) W.dayIdx = W.ds.findIndex(d => slotsFor(W.p, d, W.dur).length); draw(); };
actions['w-day'] = el => { W.dayIdx = Number(el.dataset.i); W.slot = null; haptic(6); draw(); };
actions['w-slot'] = el => { W.slot = Number(el.dataset.t); haptic(8); draw(); };
actions['w-venue'] = el => { $('#w-loc').value = el.dataset.v + ', '; $('#w-loc').focus(); refresh(); };
document.addEventListener('click', async e => {
  const btn = e.target.closest('#w-send'); if (!btn || !W || btn.disabled) return;
  btn.disabled = true; btn.textContent = 'Sending…';
  try {
    await api('/bookings', { method: 'POST', body: { partner_id: W.p.id, activity: W.activity, scheduled_at: new Date(toUtcMs(W.ds[W.dayIdx], W.slot)).toISOString(), duration_minutes: W.dur, location: $('#w-loc').value.trim(), note: ($('#w-note').value || '').trim(), safety_ack: true } });
    closeModal(); confetti(); haptic(25); toast(`Request sent to ${W.p.name}! You'll be notified when they respond.`, 'ok'); location.hash = '#/bookings';
  } catch (err) {
    btn.disabled = false; refresh();
    if (err.status === 402) { const { openMembership } = await import('./discover.js'); const p = W.p, a = W.activity; return openMembership(() => bookingWizard(p, a)); }
    toast(err.message, 'error');
  }
});
