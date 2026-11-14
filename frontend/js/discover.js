import { html, raw, api, state, $, $$, openModal, closeModal, toast, actions, submits, formObj, inr, fmtD, photo, stars, isCustomer, requireLogin, busy, ago, openRazorpay } from './core.js';
import { openAuth } from './auth.js';
import { reportModal, blockUser } from './safety.js';
import { mountDeck } from './deck.js';
import { isMobile, burst, haptic, reveal } from './fx.js';

const login = fn => requireLogin(fn, openAuth);
const DEFAULT_F = { q: '', city: '', activity: '', max_price: '', min_rating: '', gender: '', sort: 'relevance', available: false };
const F = { ...DEFAULT_F };
const EMOJI = { 'Video call': '📹', 'Coffee date': '☕', 'Movie companion': '🎬', 'Dinner': '🍽️', 'Shopping': '🛍️', 'Gym partner': '🏋️', 'City exploration': '🌆', 'Event / concert plus-one': '🎤', 'Cafe study partner': '📚', 'Language practice': '🗣️', 'Sports partner': '⚽', 'Museum / gallery visit': '🖼️', 'Board games': '🎲' };
export const emojiFor = a => EMOJI[a] || '✨';
let view = localStorage.getItem('pairup_view') || (isMobile() ? 'deck' : 'grid');
let items = [], total = 0, loading = false, deckCtl = null, deckIdx = 0, rootEl = null, sentinelIO = null;

const activeFilterCount = () => ['city', 'max_price', 'min_rating', 'gender'].filter(k => F[k]).length + (F.available ? 1 : 0);

function cleanup() {
  if (deckCtl) { deckCtl.destroy(); deckCtl = null; }
  if (sentinelIO) { sentinelIO.disconnect(); sentinelIO = null; }
  document.body.classList.remove('deck-mode');
}
export { cleanup as leaveBrowse };

// ====================== BROWSE ======================
export async function discoverPage(root, params) {
  cleanup(); rootEl = root;
  if (params && [...params.keys()].length) { Object.assign(F, DEFAULT_F); for (const k of ['q', 'city', 'activity', 'max_price', 'min_rating', 'gender', 'sort']) if (params.get(k)) F[k] = params.get(k); deckIdx = 0; }
  const acts = (state.meta && state.meta.activity_suggestions) || [];
  root.innerHTML = html`<div class="browse v-${view}">
    <div class="b-top">
      <div class="b-row"><div class="searchbox"><span aria-hidden="true">⌕</span><input id="f-q" type="search" placeholder="Search" value="${F.q}" aria-label="Search"></div>
        <button class="btn ghost filt" data-action="open-filters" aria-label="Filters">⚙<span class="hide-xs"> Filters</span>${activeFilterCount() ? html`<b class="count-dot">${activeFilterCount()}</b>` : ''}</button>
        <div class="seg small" role="group" aria-label="View"><button class="${view === 'deck' ? 'on' : ''}" data-action="set-view" data-view="deck" aria-label="Swipe view">⇆<span class="hide-xs"> Swipe</span></button><button class="${view === 'grid' ? 'on' : ''}" data-action="set-view" data-view="grid" aria-label="Grid view">▦<span class="hide-xs"> Grid</span></button></div></div>
      <div class="chips-row" role="group" aria-label="Activity"><button class="cat ${F.activity ? '' : 'on'}" data-action="cat" data-a=""><span>✨</span>All</button>${acts.map(a => html`<button class="cat ${F.activity === a ? 'on' : ''}" data-action="cat" data-a="${a}"><span>${emojiFor(a)}</span>${a.replace(' / concert plus-one', '').replace(' / gallery visit', '')}</button>`)}</div>
    </div>
    <section id="results" aria-live="polite"></section></div>`.s;
  let t; $('#f-q').addEventListener('input', e => { F.q = e.target.value.trim(); clearTimeout(t); t = setTimeout(() => load(true), 300); });
  await load(true);
}

actions.cat = el => { F.activity = el.dataset.a; $$('.cat').forEach(c => c.classList.toggle('on', c === el)); if (el.scrollIntoView) el.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' }); haptic(6); load(true); };
actions['set-view'] = el => { view = el.dataset.view; localStorage.setItem('pairup_view', view); deckIdx = 0; discoverPage(rootEl); };
actions['reset-filters'] = () => { Object.assign(F, DEFAULT_F); deckIdx = 0; closeModal(); discoverPage(rootEl); };
actions['retry-load'] = () => load(true);

actions['open-filters'] = async () => {
  let cities = []; try { cities = await api('/cities'); } catch { /* optional */ }
  openModal(html`<h2>Filters</h2><form data-submit="apply-filters" class="stack">
    <label class="lbl" for="x-city">City</label><input class="field" id="x-city" name="city" list="x-cities" value="${F.city}" placeholder="Anywhere"><datalist id="x-cities">${cities.map(c => html`<option value="${c}">`)}</datalist>
    <div class="grid2"><div><label class="lbl" for="x-price">Starting price</label><select class="field" id="x-price" name="max_price"><option value="">Any</option>${[300, 500, 800, 1200].map(v => html`<option value="${v}" ${String(F.max_price) === String(v) ? 'selected' : ''}>Up to ${inr(v)}</option>`)}</select></div>
    <div><label class="lbl" for="x-rating">Rating</label><select class="field" id="x-rating" name="min_rating"><option value="">Any</option>${[4, 4.5].map(v => html`<option value="${v}" ${String(F.min_rating) === String(v) ? 'selected' : ''}>${v}★ &amp; up</option>`)}</select></div></div>
    <div class="grid2"><div><label class="lbl" for="x-gender">Gender</label><select class="field" id="x-gender" name="gender"><option value="">Anyone</option>${['female', 'male', 'non-binary'].map(v => html`<option value="${v}" ${F.gender === v ? 'selected' : ''}>${v[0].toUpperCase() + v.slice(1)}</option>`)}</select></div>
    <div><label class="lbl" for="x-sort">Sort by</label><select class="field" id="x-sort" name="sort"><option value="relevance">Best match</option><option value="rating" ${F.sort === 'rating' ? 'selected' : ''}>Top rated</option><option value="price_low" ${F.sort === 'price_low' ? 'selected' : ''}>Price: low to high</option><option value="price_high" ${F.sort === 'price_high' ? 'selected' : ''}>Price: high to low</option><option value="newest" ${F.sort === 'newest' ? 'selected' : ''}>Newest</option></select></div></div>
    <label class="check pill"><input type="checkbox" name="available" ${F.available ? 'checked' : ''}> Only people available now</label>
    <div class="row"><button class="btn ghost grow" type="button" data-action="reset-filters">Reset</button><button class="btn primary grow" type="submit">Show results</button></div></form>`, { label: 'Filters' });
};
submits['apply-filters'] = async f => { const b = formObj(f); Object.assign(F, { city: b.city.trim(), max_price: b.max_price, min_rating: b.min_rating, gender: b.gender, sort: b.sort, available: !!b.available }); closeModal(); deckIdx = 0; discoverPage(rootEl); };

async function load(reset) {
  if (loading) return; loading = true;
  const out = $('#results');
  if (reset) { if (deckCtl) { deckCtl.destroy(); deckCtl = null; } items = []; if (reset !== 'keep') deckIdx = deckIdx || 0; if (out) out.innerHTML = view === 'deck' ? '<div class="swipe-screen"><div class="deck-host"><div class="skeleton deck-sk"></div></div></div>' : '<div class="grid">' + '<div class="skeleton card-sk"></div>'.repeat(6) + '</div>'; }
  try { const r = await fetchPage(reset ? 0 : items.length); items = reset ? r.items : items.concat(r.items); total = r.total; if (reset && deckIdx >= items.length) deckIdx = 0; draw(); }
  catch (e) { if (out) out.innerHTML = html`<div class="empty"><h3>Couldn't load profiles</h3><p class="muted">${e.message}</p><button class="btn primary" data-action="retry-load">Try again</button></div>`.s; }
  finally { loading = false; }
}
async function fetchPage(offset) {
  const qs = new URLSearchParams({ sort: F.sort, limit: 24, offset });
  for (const k of ['q', 'city', 'activity', 'max_price', 'min_rating', 'gender']) if (F[k]) qs.set(k, F[k]);
  if (F.available) qs.set('available', 'true');
  return api('/partners?' + qs);
}

function draw() {
  const out = $('#results'); if (!out) return;
  cleanup();
  if (!items.length) { out.innerHTML = html`<div class="empty"><div class="empty-art">🔍</div><h3>No matches right now</h3><p class="muted">Try another activity or clear your filters - new partners join every day.</p><button class="btn primary" data-action="reset-filters">Clear filters</button></div>`.s; return; }
  if (view === 'deck') return drawDeck(out);
  out.innerHTML = html`<p class="muted small count">${total} ${total === 1 ? 'person' : 'people'} found</p><div class="grid">${items.map(card)}</div><div id="sentinel" class="center muted small">${items.length < total ? 'Loading more…' : 'You\'ve seen everyone 🎉'}</div>`.s;
  reveal(out);
  if (items.length < total && 'IntersectionObserver' in window) {
    sentinelIO = new IntersectionObserver(async en => { if (en[0].isIntersecting && !loading) { sentinelIO.disconnect(); await load(false); } }, { rootMargin: '400px' });
    sentinelIO.observe($('#sentinel'));
  }
}

export const card = p => html`<article class="card" tabindex="0" data-action="open-profile" data-id="${p.id}" aria-label="${p.name}, ${p.age}, ${p.city}">
  <div class="card-photo">${photo(p)}${p.verified ? html`<span class="verified">✓ ID verified</span>` : ''}${heart(p.id)}</div>
  <div class="card-body"><div class="between"><h3>${p.name}, ${p.age}</h3><span class="rate">★ ${p.review_count ? p.rating.toFixed(1) : 'New'}</span></div>
  <p class="meta"><span class="dotstat ${p.available ? 'on' : ''}"></span>${p.city} · from <b>${inr(p.min_rate)}</b></p>
  <div class="tags">${p.activities.slice(0, 2).map(t => html`<span>${t}</span>`)}${p.activities.length > 2 ? html`<span>+${p.activities.length - 2}</span>` : ''}</div></div></article>`;

export const heart = id => html`<button class="heart ${state.favs.has(id) ? 'on' : ''}" data-action="toggle-fav" data-id="${id}" aria-label="${state.favs.has(id) ? 'Remove from saved' : 'Save profile'}" aria-pressed="${String(state.favs.has(id))}">${state.favs.has(id) ? '♥' : '♡'}</button>`;

actions['open-profile'] = el => { location.hash = '#/p/' + el.dataset.id; };
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches && e.target.matches('.card[data-action]')) e.target.click(); });

async function setFav(id, want) {
  await api(`/favorites/${id}`, { method: want ? 'PUT' : 'DELETE' });
  want ? state.favs.add(id) : state.favs.delete(id);
  $$(`.heart[data-id="${id}"]`).forEach(h => { h.classList.toggle('on', want); h.textContent = want ? '♥' : '♡'; h.setAttribute('aria-pressed', String(want)); });
}
actions['toggle-fav'] = (el, ev) => login(async () => {
  if (!isCustomer()) { toast('Log in with a customer account to save profiles.', 'error'); return; }
  const id = Number(el.dataset.id), was = state.favs.has(id);
  try { await setFav(id, !was); if (!was) { const r = el.getBoundingClientRect(); burst(r.left + r.width / 2, r.top + r.height / 2); haptic(15); } toast(was ? 'Removed from saved.' : 'Saved ♥', 'ok'); } catch (e) { toast(e.message, 'error'); }
});

// ====================== SWIPE SCREEN ======================
function drawDeck(out) {
  document.body.classList.add('deck-mode');
  out.innerHTML = html`<div class="swipe-screen">
    <div class="deck-host" id="deckHost"></div>
    <div class="deck-empty" id="deckEmpty" hidden><div class="empty-art">🎉</div><h3>You're all caught up</h3><p class="muted">That's everyone for these filters. Try another activity, or come back later.</p><div class="row center-row"><button class="btn primary" data-action="open-filters">Adjust filters</button><button class="btn ghost" data-action="deck-restart">Start over</button></div></div>
    <div class="deck-actions" id="deckActions">
      <button class="ab sm" data-action="deck-undo" aria-label="Undo last swipe" title="Undo">↺</button>
      <button class="ab big pass" data-action="deck-pass" aria-label="Pass" title="Pass (←)">✕</button>
      <button class="ab sm info" data-action="deck-info" aria-label="View details" title="Details (↑)">ⓘ</button>
      <button class="ab big save" data-action="deck-save" aria-label="Save" title="Save (→)">♥</button>
      <button class="ab sm book" data-action="deck-book" aria-label="Request booking" title="Book">📅</button>
    </div>
    <p class="deck-hint"><span id="deckCount"></span><span class="hide-sm"> · ← pass · → save · ↑ details · tap photo edges to flip</span></p></div>`.s;
  deckCtl = mountDeck($('#deckHost'), {
    items, startIndex: Math.min(deckIdx, items.length - 1), getTotal: () => total,
    loadMore: async () => { const r = await fetchPage(items.length); items.push(...r.items); total = r.total; },
    onIndex: i => { deckIdx = i; const c = $('#deckCount'); if (c) c.textContent = `${Math.min(i + 1, total)} of ${total}`; },
    onSwipe: (dir, p) => { if (dir === 'right') swipeSave(p); },
    onUndo: (p, h) => { if (h.dir === 'right' && swipedSaves.has(p.id)) { swipedSaves.delete(p.id); setFav(p.id, false).catch(() => {}); toast('Removed from saved.', 'info'); } },
    onOpen: p => partnerSheet(p),
    onEmpty: () => { const e = $('#deckEmpty'), a = $('#deckActions'); if (e) { e.hidden = false; a && a.classList.add('dim'); } },
  });
}
const swipedSaves = new Set();
function swipeSave(p) {
  if (!state.me) { toast('Log in to save profiles - swipe right again after.', 'info'); return; }
  if (!isCustomer()) return;
  if (state.favs.has(p.id)) return;
  swipedSaves.add(p.id);
  setFav(p.id, true).then(() => toast(`Saved ${p.name} ♥`, 'ok')).catch(e => toast(e.message, 'error'));
}
actions['deck-pass'] = () => deckCtl && deckCtl.swipe('left');
actions['deck-save'] = () => deckCtl && deckCtl.swipe('right');
actions['deck-undo'] = () => { if (deckCtl && !deckCtl.undo()) toast('Nothing to undo yet.', 'info'); };
actions['deck-info'] = () => deckCtl && deckCtl.open();
actions['deck-book'] = () => { const p = deckCtl && deckCtl.current(); if (p) startBooking(p, Object.keys(p.rates)[0]); };
actions['deck-restart'] = () => { deckIdx = 0; discoverPage(rootEl); };

/** Bottom-sheet preview shown from the deck: tap the card centre, swipe up, or press ⓘ. */
export function partnerSheet(p) {
  openModal(html`<div class="sheet-photos">${p.photos.length ? p.photos.map(u => html`<img src="${u}" alt="${p.name}" loading="lazy">`) : html`<div class="sheet-ph">${photo(p)}</div>`}</div>
    <div class="between"><h2 class="nomt">${p.name}, ${p.age}</h2><span class="rate">★ ${p.review_count ? p.rating.toFixed(1) : 'New'}${p.review_count ? html` <small class="muted">(${p.review_count})</small>` : ''}</span></div>
    <p class="muted small">⌖ ${p.city}${p.verified ? ' · ✓ ID verified' : ''} · ${p.available ? '● Available' : 'Not taking requests'}</p>
    ${p.headline ? html`<p class="headline">${p.headline}</p>` : ''}<p>${p.bio}</p>
    <div class="rate-list">${Object.entries(p.rates).map(([a, v]) => html`<div class="rate-row"><span>${emojiFor(a)} ${a}</span><strong>${inr(v)}</strong></div>`)}</div>
    <div class="row"><a class="btn ghost grow" href="#/p/${p.id}" data-action="close-modal">Full profile</a><button class="btn primary grow" data-action="sheet-book" data-id="${p.id}">Request booking</button></div>`, { label: p.name });
  $('#modal-root')._p = p;
}
actions['sheet-book'] = () => { const p = $('#modal-root')._p; closeModal(); if (p) startBooking(p, Object.keys(p.rates)[0]); };

// ====================== PROFILE PAGE ======================
let selAct = '';
export async function profilePage(root, id) {
  cleanup();
  root.innerHTML = '<div class="page"><div class="skeleton tall"></div></div>';
  let p, reviews;
  try { [p, reviews] = await Promise.all([api(`/partners/${id}`), api(`/partners/${id}/reviews`)]); }
  catch (e) { root.innerHTML = html`<div class="page narrow center"><h1>Profile unavailable</h1><p class="muted">${e.status === 404 ? 'This profile isn\'t available.' : e.message}</p><a class="btn primary" href="#/browse">Back to browse</a></div>`.s; return; }
  const rates = Object.entries(p.rates); selAct = selAct && p.rates[selAct] ? selAct : rates[0] ? rates[0][0] : '';
  const own = state.me && state.me.id === p.id;
  root.innerHTML = html`<div class="page profile pf"><div class="pf-grid">
    <div class="pf-gallery"><div class="pf-track" id="pfTrack">${p.photos.length ? p.photos.map((u, i) => html`<img src="${u}" alt="${i === 0 ? p.name : ''}" ${i ? 'loading="lazy"' : ''}>`) : html`<div class="pf-ph">${photo(p)}</div>`}</div>
      ${p.photos.length > 1 ? html`<div class="pf-dots" id="pfDots">${p.photos.map((_, i) => html`<i class="${i === 0 ? 'on' : ''}"></i>`)}</div>` : ''}
      <a class="pf-btn back" href="#/browse" aria-label="Back">←</a><div class="pf-tools">${heart(p.id)}<button class="pf-btn" data-action="share-profile" data-name="${p.name}" aria-label="Share">⤴</button></div>
      ${p.verified ? html`<span class="verified pf-ver">✓ ID verified</span>` : ''}</div>
    <div class="pf-body">
      <h1>${p.name}, ${p.age}</h1>
      <p class="muted">⌖ ${p.city} · Member since ${p.member_since} · <span class="${p.available ? 'ok' : 'warn'}">${p.available ? '● Available' : '● Not taking requests'}</span></p>
      <p class="stars">${p.review_count ? html`<b>${p.rating.toFixed(1)}</b> <span>${stars(p.rating)}</span> <span class="muted">(${p.review_count} verified ${p.review_count === 1 ? 'review' : 'reviews'})</span>` : html`<span class="muted">New on PairUp - no reviews yet</span>`}</p>
      ${p.headline ? html`<p class="headline big">${p.headline}</p>` : ''}
      <div class="pf-card"><h3>About</h3><p class="bio">${p.bio}</p>${p.languages.length ? html`<p class="small"><b>Speaks:</b> ${p.languages.join(', ')}</p>` : ''}
      ${Object.keys(p.schedule || {}).length ? html`<p class="small"><b>Usually available:</b> ${Object.entries(p.schedule).map(([k, w]) => `${k[0].toUpperCase() + k.slice(1)} ${w[0]}-${w[1]}`).join(' · ')} <span class="muted">(IST)</span></p>` : ''}</div>
      <div class="pf-card"><h3>Activities &amp; rates</h3><div class="rate-list" role="radiogroup" aria-label="Choose an activity">${rates.map(([a, v]) => html`<label class="rate-row ${a === selAct ? 'sel' : ''}"><span><input type="radio" name="rate" value="${a}" ${a === selAct ? 'checked' : ''} data-action="pick-rate"> ${emojiFor(a)} ${a}</span><strong>${inr(v)}</strong></label>`)}</div>
      <p class="muted small">Per session. You pay <b>after the partner accepts</b>; PairUp holds the money until your plan is done. <a href="#/refunds">Cancellation &amp; refunds</a></p></div>
      <div class="notice">🛡 Meet in public places · never pay outside PairUp · no sexual services. <a href="#/safety">Safety tips</a></div>
      ${!own ? html`<div class="row small"><button class="link" data-action="report-user" data-id="${p.id}" data-name="${p.name}">Report</button><button class="link" data-action="block-user" data-id="${p.id}" data-name="${p.name}">Block</button></div>` : ''}
      <h2>Reviews</h2>${reviews.length ? html`<div class="reviews">${reviews.map(r => html`<div class="review"><div class="between"><b>${r.reviewer}</b><span class="stars">${stars(r.rating)}</span></div><p>${r.comment || html`<span class="muted">No written comment.</span>`}</p><p class="muted small">${fmtD(r.created_at)} · verified booking</p>${r.partner_reply ? html`<div class="reply"><b>${p.name} replied:</b> ${r.partner_reply}</div>` : ''}</div>`)}</div>` : html`<p class="muted">No reviews yet. Only customers with a completed booking can review.</p>`}
    </div></div>
    <div class="pf-bar"><div><small class="muted">from</small><b>${inr(p.min_rate)}</b></div><button class="btn primary big grow" data-action="book" data-id="${p.id}" ${own ? 'disabled' : ''}>${own ? 'This is your profile' : 'Request booking'}</button></div></div>`.s;
  root._partner = p;
  const track = $('#pfTrack'), dots = $$('#pfDots i');
  if (track && dots.length) track.addEventListener('scroll', () => { const i = Math.round(track.scrollLeft / track.clientWidth); dots.forEach((d, k) => d.classList.toggle('on', k === i)); }, { passive: true });
}
actions['pick-rate'] = el => { selAct = el.value; $$('.rate-row').forEach(r => r.classList.toggle('sel', r.contains(el))); };
actions['share-profile'] = async el => {
  const url = location.href;
  try { if (navigator.share) await navigator.share({ title: `${el.dataset.name} on PairUp`, url }); else { await navigator.clipboard.writeText(url); toast('Link copied.', 'ok'); } } catch { /* cancelled */ }
};
actions['report-user'] = el => login(() => reportModal(Number(el.dataset.id), el.dataset.name));
actions['block-user'] = el => login(async () => { if (await blockUser(Number(el.dataset.id), el.dataset.name)) location.hash = '#/browse'; });
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
  const min = new Date(Date.now() + 135 * 60000); min.setMinutes(Math.ceil(min.getMinutes() / 15) * 15, 0, 0);
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
    <p class="muted small center">Nothing is charged now. If the partner accepts, you'll pay securely through PairUp to confirm the plan. <a href="#/refunds" data-action="close-modal">Refund policy</a></p></form>`, { label: 'Booking request' });
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
  await openRazorpay(co, async resp => { await api('/payments/verify', { method: 'POST', body: resp }); finish(); });
};
actions['open-membership'] = () => login(() => { if (!isCustomer()) toast('Memberships are for customer accounts.', 'error'); else openMembership(); });
