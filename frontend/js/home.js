import { html, raw, api, state, $, $$, actions, submits, inr, stars, hue, initials } from './core.js';
import { card, emojiFor } from './discover.js';
import { FAQ } from './pages.js';
import { reveal, countUp } from './fx.js';
import { timers } from './account.js';

const STEPS = [
  ['🔍', 'Browse or swipe', 'Filter by city, activity and price - or just swipe through profiles like you would on your favourite app.'],
  ['📅', 'Request a plan', 'Pick an activity, time and a public meeting spot. Your partner confirms.'],
  ['🔒', 'Pay once accepted', 'You pay through PairUp. We hold the money until your plan is done - never upfront to a stranger.'],
  ['☕', 'Meet & review', 'Meet in public, have a great time, then leave a verified review.'],
];
const BENTO = [
  ['🪪', 'ID-verified partners', 'Government ID + selfie check earns a ✓ badge.'],
  ['🔒', 'Pay after they accept', 'Money is held by PairUp and released after the plan - zero advance-payment scams.'],
  ['🧹', 'Moderated by design', 'Sexual wording, scams and off-platform payment requests are blocked automatically.'],
  ['↩', 'Fair refunds', 'Full refund if a partner cancels. Clear policy for the rest.'],
  ['⭐', 'Reviews you can trust', 'Only customers with a completed booking can review.'],
];
const TILE_BG = ['linear-gradient(135deg,#ff4f81,#ff8a5b)', 'linear-gradient(135deg,#7c5cff,#c05cff)', 'linear-gradient(135deg,#00b3a4,#5be7a9)', 'linear-gradient(135deg,#ff9d3d,#ffd27a)', 'linear-gradient(135deg,#3d7bff,#7be0ff)', 'linear-gradient(135deg,#ff5c8a,#ffb199)', 'linear-gradient(135deg,#8a5cff,#ff6fae)', 'linear-gradient(135deg,#17b890,#8ae26b)'];

const avatar = p => p.photo_url ? html`<img src="${p.photo_url}" alt="" loading="lazy">` : html`<span class="ph-mini" style="--h:${hue(p.name)}">${initials(p.name)}</span>`;

function mockCard(p, i) {
  return html`<div class="pm-card" data-pos="${i}">${p.photo_url ? html`<img src="${p.photo_url}" alt="">` : html`<div class="ph full" style="--h:${hue(p.name)}"><span>${initials(p.name)}</span></div>`}
    <span class="stamp like">SAVE</span><span class="stamp nope">PASS</span>
    <div class="pm-info"><b>${p.name}, ${p.age}</b><span>⌖ ${p.city} · ★ ${p.review_count ? p.rating.toFixed(1) : 'New'}</span><em>${p.activities.slice(0, 2).join(' · ')}</em></div></div>`;
}

export async function homePage(root) {
  root.innerHTML = '<div class="land"><div class="skeleton tall"></div></div>';
  let d, plans = null;
  try { [d, plans] = await Promise.all([api('/home'), api('/membership/plans').catch(() => null)]); }
  catch { d = { stats: {}, featured: [], cities: [], activities: [], testimonials: [] }; }
  const acts = (state.meta && state.meta.activity_suggestions) || [];
  const s = d.stats, fee = state.meta ? state.meta.platform_fee_percent : 15;
  const nums = [[s.partners, 'reviewed partners'], [s.cities, s.cities === 1 ? 'city' : 'cities'], [s.completed, 'plans completed'], [s.reviews, 'verified reviews']].filter(([n]) => n > 0);
  const withRev = d.featured.filter(p => p.review_count > 0), revN = withRev.reduce((a, p) => a + p.review_count, 0);
  const avg = revN ? withRev.reduce((a, p) => a + p.rating * p.review_count, 0) / revN : 0;
  const mock = d.featured.slice(0, 4);
  const tiles = (d.activities.length ? d.activities.map(a => a.name) : acts).slice(0, 8);
  const marquee = (acts.length ? acts : tiles).map(a => html`<span>${emojiFor(a)} ${a}</span>`);

  root.innerHTML = html`<div class="land">
  <section class="hero4"><div class="hero-bg" aria-hidden="true"><i class="orb o1"></i><i class="orb o2"></i><i class="orb o3"></i></div>
    <div class="h4-text">
      <p class="pill-eyebrow"><span class="live-dot"></span> 18+ · Public meet-ups only · Safety first</p>
      <h1>Plans are better with <em>good company.</em></h1>
      <p class="sub">Book friendly, admin-approved companions for coffee, films, workouts and city walks - always in public, always paid safely through PairUp.</p>
      <div class="cta-row"><a class="btn primary big glow" href="#/browse" data-action="start-swiping">Start swiping →</a><button class="btn ghost big" data-action="scroll-how">How it works</button></div>
      <form class="search-pill" data-submit="home-search" role="search"><label><span>Where</span><input name="city" list="home-cities" placeholder="Your city" value="${state.me ? state.me.city : ''}" autocomplete="off"></label><datalist id="home-cities">${d.cities.map(c => html`<option value="${c.city}">`)}</datalist>
        <label><span>What</span><select name="activity"><option value="">Any activity</option>${acts.map(a => html`<option>${a}</option>`)}</select></label><button class="btn primary" type="submit" aria-label="Search">Search</button></form>
      <div class="proof">${mock.length ? html`<div class="avatars">${mock.map(avatar)}</div>` : ''}<p>${avg ? html`<b>★ ${avg.toFixed(1)}</b> average from <b>${revN}</b> verified ${revN === 1 ? 'review' : 'reviews'}` : html`<b>New &amp; growing</b> - be among the first members`}</p></div>
    </div>
    <div class="h4-art" aria-hidden="true">
      <div class="phone"><i class="notch"></i><div class="phone-screen"><div class="pm-top"><b>✦ pairup</b><span>🔔</span></div>
        <div class="pm-stack" id="pmStack">${mock.length ? mock.map(mockCard) : html`<div class="pm-card" data-pos="0"><div class="ph full" style="--h:330"><span>✦</span></div></div>`}</div>
        <div class="pm-actions"><i>✕</i><i class="s">♥</i><i>📅</i></div></div></div>
      <div class="fbadge fb1"><b>✓ ID verified</b><span>Reviewed by our team</span></div><div class="fbadge fb2"><b>☕ Coffee date</b><span>Sat · 4:00 PM · CyberHub</span></div><div class="fbadge fb3"><b>🔒 Paid safely</b><span>Held until it's done</span></div></div>
  </section>
  <div class="marquee" aria-hidden="true"><div class="mq-track">${marquee}${marquee}</div></div>
  ${nums.length ? html`<section class="statbar rv">${nums.map(([n, l]) => html`<div><b data-count="${n}">0</b><span>${l}</span></div>`)}</section>` : ''}
  <section class="section rv" id="how"><p class="kicker">HOW IT WORKS</p><h2>From “maybe” to meeting in four steps</h2><ol class="steps4">${STEPS.map(([i, t, x], n) => html`<li><span class="step-ico">${i}</span><span class="step-n">0${n + 1}</span><b>${t}</b><p class="muted">${x}</p></li>`)}</ol></section>
  ${d.featured.length ? html`<section class="section rv"><div class="between"><div><p class="kicker">FEATURED</p><h2>People you might click with</h2></div><a class="more" href="#/browse">See everyone →</a></div><div class="hscroll">${d.featured.map(card)}</div></section>` : ''}
  <section class="section rv"><p class="kicker">SAFETY, BUILT IN</p><h2>Safety isn't an add-on. It's the product.</h2>
    <div class="bento"><div class="bt big"><span class="bt-ico">🛡️</span><h3>Public places. Always.</h3><p>Every booking requires a public venue. Private rooms and hotels are banned, and our moderation blocks anything that crosses the line.</p><ul><li>One-tap report &amp; block</li><li>SOS alert to our safety team during a booking</li><li>Instant links to 112 &amp; helplines</li></ul><a class="btn ghost" href="#/safety">Visit the Safety centre</a></div>
      ${BENTO.map(([i, t, x]) => html`<div class="bt"><span class="bt-ico">${i}</span><h3>${t}</h3><p>${x}</p></div>`)}</div></section>
  <section class="section rv"><p class="kicker">POPULAR PLANS</p><h2>What do you feel like doing?</h2><div class="acts">${tiles.map((a, i) => html`<a class="act-tile" style="background:${TILE_BG[i % TILE_BG.length]}" href="#/browse?activity=${encodeURIComponent(a)}"><span>${emojiFor(a)}</span><b>${a}</b></a>`)}</div>
    ${d.cities.length ? html`<p class="small muted cities">Available in ${d.cities.map(c => html`<a href="#/browse?city=${encodeURIComponent(c.city)}">${c.city}</a>`).reduce((a, b) => [a, ' · ', b])}</p>` : ''}</section>
  ${d.testimonials.length ? html`<section class="section rv"><p class="kicker">LOVED BY MEMBERS</p><h2>Real reviews, real plans</h2><div class="testi">${d.testimonials.map(t => html`<blockquote><span class="stars">${stars(t.rating)}</span><p>“${t.comment}”</p><footer>${t.reviewer} · plan with ${t.partner}</footer></blockquote>`)}</div></section>` : ''}
  <section class="section earn rv"><div class="earn-text"><p class="kicker">FOR PARTNERS</p><h2>Turn your good company into income</h2><p class="muted">Set your own rates and hours. Keep ${100 - fee}% of every completed booking, paid out to UPI. See what a few plans a week could add up to:</p>
    <div class="calc"><label>Plans per week <b id="cs-v">4</b><input type="range" id="calc-s" min="1" max="15" value="4"></label><label>Average rate <b id="cr-v">₹500</b><input type="range" id="calc-r" min="200" max="1500" step="50" value="500"></label>
      <div class="calc-out"><span>Estimated monthly earnings</span><strong id="calc-total">₹0</strong><small>After PairUp's ${fee}% fee. Illustrative only - not a guarantee. Taxes are your responsibility.</small></div></div>
    <a class="btn primary big" href="#/become-a-partner">Become a partner</a></div>
    <div class="earn-art" aria-hidden="true"><div class="ecard e1"><b>+ ${inr(399 - Math.round(399 * fee / 100))}</b><span>Coffee date · Sat</span></div><div class="ecard e2"><b>+ ${inr(499 - Math.round(499 * fee / 100))}</b><span>Movie companion</span></div><div class="ecard e3"><b>✓ Payout sent</b><span>to your UPI</span></div></div></section>
  ${plans && plans.plans ? html`<section class="section rv"><p class="kicker">SIMPLE PRICING</p><h2>Browsing is free</h2><p class="muted center">A membership lets you send booking requests. Each plan is then paid at the partner's own rate.</p><div class="plans wide">${plans.plans.map((p, i) => html`<div class="plan-card ${i ? '' : 'hot'}">${i ? '' : html`<i>Popular</i>`}<b>${p.label}</b><strong>${inr(p.amount)}</strong><small>${p.days} days of booking requests</small></div>`)}</div></section>` : ''}
  <section class="section rv"><p class="kicker">QUESTIONS</p><h2>Good to know</h2>${FAQ.slice(0, 5).map(([q, a]) => html`<details class="faq"><summary>${q}</summary><p>${a}</p></details>`)}<p><a href="#/faq">All questions →</a></p></section>
  <section class="final-cta rv"><h2>Ready to meet someone new?</h2><p>Swipe through verified profiles in your city - it's free to look.</p><div class="row center-row"><a class="btn primary big glow" href="#/browse">Start swiping →</a>${state.me ? '' : html`<button class="btn ghost big" data-action="auth-register">Create account</button>`}</div></section></div>`.s;

  reveal(root);
  $$('[data-count]', root).forEach(el => countUp(el, Number(el.dataset.count)));
  startMock(); startCalc(fee);
}

function startMock() {
  const stack = $('#pmStack'); if (!stack) return;
  const cards = $$('.pm-card', stack); if (cards.length < 2) return;
  let shift = 0, n = cards.length, flip = false;
  const assign = () => cards.forEach((c, i) => { c.dataset.pos = String((i - shift % n + n) % n); });
  assign();
  timers.push(setInterval(() => {
    const top = cards.find(c => c.dataset.pos === '0'); if (!top) return;
    flip = !flip; top.classList.add(flip ? 'fly-r' : 'fly-l');
    setTimeout(() => { top.classList.add('notrans'); top.classList.remove('fly-r', 'fly-l'); shift++; assign(); void top.offsetWidth; top.classList.remove('notrans'); }, 520);
  }, 2600));
}
function startCalc(fee) {
  const s = $('#calc-s'), r = $('#calc-r'); if (!s || !r) return;
  const upd = () => { $('#cs-v').textContent = s.value; $('#cr-v').textContent = inr(r.value); $('#calc-total').textContent = inr(Math.round(Number(s.value) * 4.33 * Number(r.value) * (1 - fee / 100))); };
  s.addEventListener('input', upd); r.addEventListener('input', upd); upd();
}
submits['home-search'] = async f => {
  const p = new URLSearchParams(); const fd = new FormData(f);
  for (const k of ['city', 'activity']) if (fd.get(k)) p.set(k, fd.get(k));
  location.hash = '#/browse' + (p.toString() ? '?' + p : '');
};
actions['start-swiping'] = () => { localStorage.setItem('pairup_view', 'deck'); };
actions['scroll-how'] = () => { const el = document.getElementById('how'); if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
