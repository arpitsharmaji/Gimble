import { html, raw, api, state, $, $$, openModal, closeModal, toast, actions, submits, formObj, inr, fmtD, photo, stars, isCustomer, requireLogin, busy, ago } from './core.js';
import { openAuth } from './auth.js';
import { reportModal, blockUser } from './safety.js';

const login = fn => requireLogin(fn, openAuth);
const F = { q: '', city: '', activity: '', max_price: '', min_rating: '', gender: '', sort: 'relevance', available: false };
let view = localStorage.getItem('pairup_view') || 'grid';
let items = [], total = 0, deckIdx = 0, loading = false, rootEl = null;
let cleanupDeck = null;

// ====================== DISCOVER ======================
export async function discoverPage(root) {
  rootEl = root; cleanupDeck = null;
  const acts = (state.meta && state.meta.activity_suggestions) || [];
  root.innerHTML = html`
  <section class="hero">
    <div><p class="eyebrow">YOUR CITY, YOUR PEOPLE</p><h1>Find your kind<br>of <em>company.</em></h1>
    <p class="sub">Coffee, a film, a gym session or a city walk - book verified, friendly companions for public, non-sexual plans.</p>
    <ul class="trust"><li>✓ Admin-approved profiles</li><li>✓ Public meet-ups only</li><li>✓ Report &amp; block tools</li><li>✓ Pay only through PairUp</li></ul></div>
  </section>
  <section class="filters" aria-label="Filters">
    <input class="field" id="f-q" type="search" placeholder="Search name or interest" value="${F.q}" aria-label="Search">
    <input class="field" id="f-city" list="city-list" placeholder="City" value="${F.city}" aria-label="City"><datalist id="city-list"></datalist>
    <select class="field" id="f-activity" aria-label="Activity"><option value="">Any activity</option>${acts.map(a => html`<option ${F.activity === a ? 'selected' : ''}>${a}</option>`)}</select>
    <select class="field" id="f-price" aria-label="Max starting price"><option value="">Any price</option>${[300, 500, 800, 1200].map(v => html`<option value="${v}" ${String(F.max_price) === String(v) ? 'selected' : ''}>Up to ${inr(v)}</option>`)}</select>
    <select class="field" id="f-rating" aria-label="Minimum rating"><option value="">Any rating</option>${[4, 4.5].map(v => html`<option value="${v}" ${String(F.min_rating) === String(v) ? 'selected' : ''}>${v}★ &amp; up</option>`)}</select>
    <select class="field" id="f-gender" aria-label="Gender"><option value="">Any gender</option>${['female', 'male', 'non-binary'].map(v => html`<option value="${v}" ${F.gender === v ? 'selected' : ''}>${v[0].toUpperCase() + v.slice(1)}</option>`)}</select>
    <select class="field" id="f-sort" aria-label="Sort"><option value="relevance">Best match</option><option value="rating" ${F.sort === 'rating' ? 'selected' : ''}>Top rated</option><option value="price_low" ${F.sort === 'price_low' ? 'selected' : ''}>Price: low to high</option><option value="price_high" ${F.sort === 'price_high' ? 'selected' : ''}>Price: high to low</option><option value="newest" ${F.sort === 'newest' ? 'selected' : ''}>Newest</option></select>
    <label class="check pill"><input type="checkbox" id="f-avail" ${F.available ? 'checked' : ''}> Available now</label>
    <button class="btn ghost" data-action="reset-filters">Reset</button>
    <div class="seg small" role="group" aria-label="View"><button class="${view === 'grid' ? 'on' : ''}" data-action="set-view" data-view="grid">▦ Grid</button><button class="${view === 'deck' ? 'on' : ''}" data-action="set-view" data-view="deck">⇆ Swipe</button></div>
  </section>
  <section id="results" aria-live="polite"></section>`.s;
  api('/cities').then(c => { const dl = $('#city-list'); if (dl) dl.innerHTML = c.map(x => `<option value="${x.replace(/"/g, '&quot;')}">`).join(''); }).catch(() => {});
  bindFilters();
  await load(true);
}

function bindFilters() {
  let t;
  const read = () => {
    F.q = $('#f-q').value.trim(); F.city = $('#f-city').value.trim(); F.activity = $('#f-activity').value;
    F.max_price = $('#f-price').value; F.min_rating = $('#f-rating').value; F.gender = $('#f-gender').value;
    F.sort = $('#f-sort').value; F.available = $('#f-avail').checked;
    clearTimeout(t); t = setTimeout(() => load(true), 300);
  };
  $$('.filters input,.filters select').forEach(el => el.addEventListener('input', read));
}
actions['reset-filters'] = () => { Object.assign(F, { q: '', city: '', activity: '', max_price: '', min_rating: '', gender: '', sort: 'relevance', available: false }); discoverPage(rootEl); };
actions['set-view'] = el => { view = el.dataset.view; localStorage.setItem('pairup_view', view); $$('.seg.small button').forEach(b => b.classList.toggle('on', b === el)); draw(); };

async function load(reset) {
  if (loading) return; loading = true;
  const out = $('#results');
  if (reset) { items = []; deckIdx = 0; if (out) out.innerHTML = '<div class="grid">' + '<div class="skeleton"></div>'.repeat(6) + '</div>'; }
  const qs = new URLSearchParams({ sort: F.sort, limit: 24, offset: items.length });
  for (const k of ['q', 'city', 'activity', 'max_price', 'min_rating', 'gender']) if (F[k]) qs.set(k, F[k]);
  if (F.available) qs.set('available', 'true');
  try { const r = await api('/partners?' + qs); items = reset ? r.items : items.concat(r.items); total = r.total; draw(); }
  catch (e) { if (out) out.innerHTML = html`<div class="empty"><p>Couldn't load profiles.</p><p class="muted">${e.message}</p><button class="btn primary" data-action="retry-load">Try again</button></div>`.s; }
  finally { loading = false; }
}
actions['retry-load'] = () => load(true);
actions['load-more'] = () => load(false);

function draw() {
  const out = $('#results'); if (!out) return;
  if (cleanupDeck) { cleanupDeck(); cleanupDeck = null; }
  if (!items.length) { out.innerHTML = html`<div class="empty"><h3>No matches yet</h3><p class="muted">Try removing a filter, or check back soon - new partners are approved every day.</p><button class="btn ghost" data-action="reset-filters">Clear filters</button></div>`.s; return; }
  if (view === 'deck') return drawDeck(out);
  out.innerHTML = html`<p class="muted small count">${total} ${total === 1 ? 'person' : 'people'} found</p><div class="grid">${items.map(card)}</div>${items.length < total ? html`<div class="center"><button class="btn ghost" data-action="load-more">Load more</button></div>` : ''}`.s;
}

const card = p => html`<article class="card" tabindex="0" data-action="open-profile" data-id="${p.id}" aria-label="${p.name}, ${p.age}, ${p.city}">
  <div class="card-photo">${photo(p)}${p.verified ? html`<span class="verified">✓ ID verified</span>` : ''}${heart(p.id)}
  <span class="avail ${p.available ? 'on' : ''}">${p.available ? 'Available' : 'Unavailable'}</span></div>
  <div class="card-body"><div class="between"><h3>${p.name}, ${p.age}</h3><span class="rate">★ ${p.review_count ? p.rating.toFixed(1) : 'New'}</span></div>
  <p class="muted small">⌖ ${p.city} · from <b>${inr(p.min_rate)}</b></p>
  ${p.headline ? html`<p class="headline">${p.headline}</p>` : ''}
  <div class="tags">${p.activities.slice(0, 3).map(t => html`<span>${t}</span>`)}${p.activities.length > 3 ? html`<span>+${p.activities.length - 3}</span>` : ''}</div></div></article>`;

const heart = id => html`<button class="heart ${state.favs.has(id) ? 'on' : ''}" data-action="toggle-fav" data-id="${id}" aria-label="${state.favs.has(id) ? 'Remove from saved' : 'Save profile'}" aria-pressed="${String(state.favs.has(id))}">${state.favs.has(id) ? '♥' : '♡'}</button>`;

actions['open-profile'] = el => { location.hash = '#/p/' + el.dataset.id; };
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches && e.target.matches('.card[data-action]')) e.target.click(); });

actions['toggle-fav'] = el => login(async () => {
  if (!isCustomer()) { toast('Log in with a customer account to save profiles.', 'error'); return; }
  const id = Number(el.dataset.id), was = state.favs.has(id);
  try {
    await api(`/favorites/${id}`, { method: was ? 'DELETE' : 'PUT' });
    was ? state.favs.delete(id) : state.favs.add(id);
    $$(`.heart[data-id="${id}"]`).forEach(h => { h.classList.toggle('on', !was); h.textContent = was ? '♡' : '♥'; h.setAttribute('aria-pressed', String(!was)); });
    toast(was ? 'Removed from saved.' : 'Saved to your likes.', 'ok');
  } catch (e) { toast(e.message, 'error'); }
});

// ====================== SWIPE DECK ======================
function drawDeck(out) {
  if (deckIdx >= items.length) {
    out.innerHTML = html`<div class="empty"><h3>You've seen everyone for now</h3><p class="muted">Adjust filters or look again later.</p>${items.length < total ? html`<button class="btn primary" data-action="load-more">Load more</button>` : html`<button class="btn ghost" data-action="deck-restart">Start over</button>`}</div>`.s; return;
  }
  const p = items[deckIdx];
  out.innerHTML = html`<div class="deck"><div class="deck-card" id="deckCard" tabindex="0" aria-label="${p.name}, ${p.age}">
    <div class="card-photo tall">${photo(p)}${p.verified ? html`<span class="verified">✓ ID verified</span>` : ''}<span class="avail ${p.available ? 'on' : ''}">${p.available ? 'Available' : 'Unavailable'}</span>
    <span class="stamp save">SAVE</span><span class="stamp pass">PASS</span></div>
    <div class="card-body"><div class="between"><h3>${p.name}, ${p.age}</h3><span class="rate">★ ${p.review_count ? p.rating.toFixed(1) : 'New'} <small>(${p.review_count})</small></span></div>
    <p class="muted small">⌖ ${p.city} · from <b>${inr(p.min_rate)}</b></p><p class="bio clamp">${p.bio}</p>
    <div class="tags">${p.activities.slice(0, 4).map(t => html`<span>${t}</span>`)}</div>
    <button class="btn primary block" data-action="open-profile" data-id="${p.id}">View rates &amp; book →</button></div></div>
    <div class="controls"><button class="round pass" data-action="deck-pass" aria-label="Pass">×</button><button class="round info" data-action="open-profile" data-id="${p.id}" aria-label="View profile">i</button><button class="round like" data-action="deck-save" aria-label="Save">♥</button></div>
    <p class="muted small center">Swipe or use ← → keys · ${deckIdx + 1} of ${total}</p></div>`.s;
  const c = $('#deckCard'); let sx = 0, dx = 0, drag = false;
  const down = e => { if (e.target.closest('button')) return; drag = true; sx = e.clientX; c.setPointerCapture(e.pointerId); c.style.transition = 'none'; };
  const move = e => { if (!drag) return; dx = e.clientX - sx; c.style.transform = `translateX(${dx}px) rotate(${dx / 25}deg)`; c.classList.toggle('s-save', dx > 40); c.classList.toggle('s-pass', dx < -40); };
  const up = () => { if (!drag) return; drag = false; c.style.transition = ''; if (dx > 110) deckAct('save'); else if (dx < -110) deckAct('pass'); else { c.style.transform = ''; c.classList.remove('s-save', 's-pass'); } dx = 0; };
  c.addEventListener('pointerdown', down); c.addEventListener('pointermove', move); c.addEventListener('pointerup', up); c.addEventListener('pointercancel', up);
  const key = e => { if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return; if (e.key === 'ArrowLeft') deckAct('pass'); if (e.key === 'ArrowRight') deckAct('save'); };
  document.addEventListener('keydown', key); cleanupDeck = () => document.removeEventListener('keydown', key);
}
function deckAct(kind) {
  const p = items[deckIdx]; if (!p) return;
  const c = $('#deckCard'); if (c) { c.style.transform = `translateX(${kind === 'save' ? 600 : -600}px) rotate(${kind === 'save' ? 20 : -20}deg)`; c.style.opacity = '0'; }
  if (kind === 'save') {
    if (state.me && isCustomer() && !state.favs.has(p.id)) api(`/favorites/${p.id}`, { method: 'PUT' }).then(() => { state.favs.add(p.id); toast(`Saved ${p.name}.`, 'ok'); }).catch(e => toast(e.message, 'error'));
    else if (!state.me) toast('Log in to save profiles.', 'info');
  }
  setTimeout(() => { deckIdx++; draw(); }, 180);
}
actions['deck-pass'] = () => deckAct('pass'); actions['deck-save'] = () => deckAct('save');
actions['deck-restart'] = () => { deckIdx = 0; draw(); };

// ====================== PROFILE PAGE ======================
let selAct = '';
export async function profilePage(root, id) {
  root.innerHTML = '<div class="page"><div class="skeleton tall"></div></div>';
  let p, reviews;
  try { [p, reviews] = await Promise.all([api(`/partners/${id}`), api(`/partners/${id}/reviews`)]); }
  catch (e) { root.innerHTML = html`<div class="page narrow center"><h1>Profile unavailable</h1><p class="muted">${e.status === 404 ? 'This profile isn\'t available.' : e.message}</p><a class="btn primary" href="#/">Back to discover</a></div>`.s; return; }
  const rates = Object.entries(p.rates); selAct = selAct && p.rates[selAct] ? selAct : rates[0] ? rates[0][0] : '';
  const own = state.me && state.me.id === p.id;
  root.innerHTML = html`<div class="page profile"><a class="back" href="#/">← Back</a>
  <div class="profile-grid">
    <div class="gallery"><div class="main-photo">${photo(p)}${p.verified ? html`<span class="verified">✓ ID verified</span>` : ''}</div>
      ${p.photos.length > 1 ? html`<div class="thumbs">${p.photos.map((u, i) => html`<button data-action="gallery-pick" data-src="${u}" aria-label="Photo ${i + 1}"><img src="${u}" alt="" loading="lazy"></button>`)}</div>` : ''}</div>
    <div class="info">
      <div class="between"><h1>${p.name}, ${p.age}</h1>${heart(p.id)}</div>
      <p class="muted">⌖ ${p.city} · Member since ${p.member_since} · <span class="${p.available ? 'ok' : 'warn'}">${p.available ? '● Available' : '● Not taking requests'}</span></p>
      <p class="stars" aria-label="Rating ${p.rating} of 5">${p.review_count ? html`<b>${p.rating.toFixed(1)}</b> <span>${stars(p.rating)}</span> <span class="muted">(${p.review_count} verified ${p.review_count === 1 ? 'review' : 'reviews'})</span>` : html`<span class="muted">New on PairUp - no reviews yet</span>`}</p>
      ${p.headline ? html`<p class="headline big">${p.headline}</p>` : ''}
      <p class="bio">${p.bio}</p>
      ${p.languages.length ? html`<p class="small"><b>Speaks:</b> ${p.languages.join(', ')}</p>` : ''}
      <h3>Activities &amp; rates</h3>
      <div class="rate-list" role="radiogroup" aria-label="Choose an activity">${rates.map(([a, v]) => html`<label class="rate-row ${a === selAct ? 'sel' : ''}"><span><input type="radio" name="rate" value="${a}" ${a === selAct ? 'checked' : ''} data-action="pick-rate"> ${a}</span><strong>${inr(v)}</strong></label>`)}</div>
      <p class="muted small">Per session, in INR. The price is fixed by the partner and locked when you send a request. Browsing is free; a membership is needed to send requests.</p>
      <div class="cta-bar"><button class="btn primary big" data-action="book" data-id="${p.id}" ${own ? 'disabled' : ''}>${own ? 'This is your profile' : 'Request booking →'}</button>
        <button class="btn ghost" data-action="share-profile" data-name="${p.name}">Share</button></div>
      <div class="notice">🛡 Meet in public places · never pay outside PairUp · no sexual services. <a href="#/safety">Safety tips</a></div>
      ${!own ? html`<div class="row small"><button class="link" data-action="report-user" data-id="${p.id}" data-name="${p.name}">Report</button><button class="link" data-action="block-user" data-id="${p.id}" data-name="${p.name}">Block</button></div>` : ''}
    </div></div>
  <h2>Reviews</h2>${reviews.length ? html`<div class="reviews">${reviews.map(r => html`<div class="review"><div class="between"><b>${r.reviewer}</b><span class="stars">${stars(r.rating)}</span></div><p>${r.comment || html`<span class="muted">No written comment.</span>`}</p><p class="muted small">${fmtD(r.created_at)} · verified booking</p></div>`)}</div>` : html`<p class="muted">No reviews yet. Reviews can only be written by customers after a completed booking.</p>`}
  </div>`.s;
  root._partner = p;
}
actions['gallery-pick'] = el => { const img = $('.main-photo img'); if (img) img.src = el.dataset.src; };
actions['pick-rate'] = el => { selAct = el.value; $$('.rate-row').forEach(r => r.classList.toggle('sel', r.contains(el))); };
actions['share-profile'] = async el => {
  const url = location.href.split('#')[0] + location.hash;
  try { if (navigator.share) await navigator.share({ title: `${el.dataset.name} on PairUp`, url }); else { await navigator.clipboard.writeText(url); toast('Link copied.', 'ok'); } } catch { /* cancelled */ }
};
actions['report-user'] = el => login(() => reportModal(Number(el.dataset.id), el.dataset.name));
actions['block-user'] = el => login(async () => { if (await blockUser(Number(el.dataset.id), el.dataset.name)) location.hash = '#/'; });
actions.book = el => { const p = $('#view')._partner; if (p) startBooking(p, selAct); };

// ====================== BOOKING FLOW ======================
export function startBooking(p, activity) {
  login(async () => {
    if (!isCustomer()) { toast('Only customer accounts can send booking requests.', 'error'); return; }
    try { const m = await api('/membership/status'); if (!m.active) return openMembership(() => bookingForm(p, activity)); bookingForm(p, activity); }
    catch (e) { toast(e.message, 'error'); }
  });
}

function bookingForm(p, activity) {
  const min = new Date(Date.now() + 45 * 60000); min.setMinutes(Math.ceil(min.getMinutes() / 15) * 15, 0, 0);
  const local = new Date(min.getTime() - min.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const max = new Date(Date.now() + 89 * 86400000); const maxLocal = new Date(max.getTime() - max.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  openModal(html`<span class="badge">BOOKING REQUEST</span><h2>Plan with ${p.name}</h2>
    <form data-submit="booking" class="stack"><input type="hidden" name="partner_id" value="${p.id}">
    <label class="lbl" for="b-act">Activity</label>
    <select class="field" id="b-act" name="activity">${Object.entries(p.rates).map(([a, v]) => html`<option value="${a}" ${a === activity ? 'selected' : ''}>${a} - ${inr(v)}</option>`)}</select>
    <div class="grid2"><div><label class="lbl" for="b-when">Date &amp; time</label><input class="field" id="b-when" name="when" type="datetime-local" min="${local}" max="${maxLocal}" value="${local}" required></div>
    <div><label class="lbl" for="b-dur">Duration</label><select class="field" id="b-dur" name="duration_minutes">${[1, 2, 3, 4, 6, 8].map(h => html`<option value="${h * 60}">${h} hour${h > 1 ? 's' : ''}</option>`)}</select></div></div>
    <label class="lbl" for="b-loc">Public meeting place</label><input class="field" id="b-loc" name="location" required minlength="3" maxlength="200" placeholder="e.g. Starbucks, CyberHub, Gurugram">
    <label class="lbl" for="b-note">Note (optional)</label><textarea class="field" id="b-note" name="note" rows="2" maxlength="1000" placeholder="Anything helpful for the partner"></textarea>
    <label class="check"><input type="checkbox" name="safety_ack" required> <span>I'll meet in a public place, respect boundaries, keep payments on PairUp, and understand sexual services are not allowed.</span></label>
    <button class="btn primary block" type="submit">Send booking request</button>
    <p class="muted small center">You're not charged per booking by PairUp. The partner confirms before anything is final.</p></form>`, { label: 'Booking request' });
}
submits.booking = async f => {
  const b = formObj(f);
  try {
    await api('/bookings', { method: 'POST', body: { partner_id: Number(b.partner_id), activity: b.activity, scheduled_at: new Date(b.when).toISOString(), duration_minutes: Number(b.duration_minutes), location: b.location, note: b.note, safety_ack: !!b.safety_ack } });
  } catch (e) {
    if (e.status === 402) { const p = $('#view')._partner; return openMembership(() => p && bookingForm(p, b.activity)); }
    throw e;
  }
  closeModal(); toast('Request sent! You\'ll be notified when the partner responds.', 'ok'); location.hash = '#/bookings';
};

// ====================== MEMBERSHIP ======================
let _loaded = {};
const loadScript = src => _loaded[src] ||= new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('Could not load the payment window.')); document.head.append(s); });

export async function openMembership(onDone) {
  let info;
  try { info = await api('/membership/plans'); } catch (e) { toast(e.message, 'error'); return; }
  openModal(html`<span class="badge">UNLOCK BOOKINGS</span><h2>Make your next plan happen.</h2>
    <p class="muted">Browsing profiles and prices is always free. A membership lets you send booking requests.</p>
    <form data-submit="checkout" class="stack"><div class="plans">${info.plans.map((pl, i) => html`<label class="plan-opt"><input type="radio" name="plan" value="${pl.id}" ${i === 0 ? 'checked' : ''}><span><b>${pl.label}</b><strong>${inr(pl.amount)}</strong><small>${pl.days} days</small></span></label>`)}</div>
    ${info.mode === 'unavailable' ? html`<p class="notice warn">Payments aren't switched on yet. Please check back soon.</p>` : html`<button class="btn primary block" type="submit">${info.mode === 'demo' ? 'Activate demo membership (no payment)' : 'Pay securely with Razorpay'}</button>`}
    </form>
    ${info.mode === 'demo' ? html`<p class="notice warn">Demo mode: no money is charged. Real checkout needs Razorpay keys (see README).</p>` : html`<p class="muted small">Payments are processed by Razorpay (UPI, cards, netbanking). Prices shown are proposed launch prices.</p>`}`, { label: 'Membership' });
  $('#modal-root')._mem = { mode: info.mode, onDone };
}
submits.checkout = async f => {
  const { mode, onDone } = $('#modal-root')._mem; const plan = formObj(f).plan;
  const finish = () => { closeModal(); toast('Membership active - you can now send requests.', 'ok'); if (onDone) onDone(); };
  if (mode === 'demo') { await api('/membership/demo-activate', { method: 'POST', body: { plan } }); return finish(); }
  const co = await api('/membership/checkout', { method: 'POST', body: { plan } });
  await loadScript('https://checkout.razorpay.com/v1/checkout.js');
  const rzp = new window.Razorpay({ key: co.key_id, amount: co.amount, currency: co.currency, name: co.name, description: co.description, order_id: co.order_id, prefill: co.prefill, theme: { color: '#ff648d' },
    handler: async resp => { try { await api('/membership/verify', { method: 'POST', body: resp }); finish(); } catch (e) { toast(e.message + ' If you were charged, your membership will activate automatically within a few minutes.', 'error'); } } });
  rzp.on('payment.failed', () => toast('Payment failed. Please try again.', 'error'));
  rzp.open();
};
actions['open-membership'] = () => login(() => { if (!isCustomer()) toast('Memberships are for customer accounts.', 'error'); else openMembership(); });
