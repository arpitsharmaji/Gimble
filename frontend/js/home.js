import { html, raw, api, state, $, actions, inr, stars } from './core.js';
import { card } from './discover.js';
import { FAQ } from './pages.js';
import { openAuth } from './auth.js';

const STEPS = [
  ['1', 'Browse', 'Search verified profiles by city, activity, price and rating - it\'s free.'],
  ['2', 'Request', 'Pick an activity, time and a public meeting place. The partner confirms.'],
  ['3', 'Pay securely', 'Once accepted, pay through PairUp. We hold the money until your plan is done.'],
  ['4', 'Meet & review', 'Meet in public, enjoy, then leave a verified review.'],
];
const SAFETY = [
  ['🪪', 'ID-verified partners', 'Partners can verify with a government ID + selfie to earn a ✓ badge.'],
  ['📍', 'Public places only', 'Every booking needs a public venue. Private rooms and hotels are banned.'],
  ['🔒', 'Payments held in escrow', 'No advance payments to strangers. Money is released after the plan.'],
  ['🧹', 'Moderated by design', 'Sexual wording, scams and off-platform payment requests are blocked automatically.'],
  ['🛡', 'Report, block & SOS', 'One tap to report, block or alert our safety team during a booking.'],
  ['↩', 'Fair refunds', 'Clear cancellation policy - full refund if a partner cancels.'],
];

export async function homePage(root) {
  root.innerHTML = '<div class="land"><div class="skeleton tall"></div></div>';
  let d, plans = null;
  try { [d, plans] = await Promise.all([api('/home'), api('/membership/plans').catch(() => null)]); }
  catch { d = { stats: {}, featured: [], cities: [], activities: [], testimonials: [] }; }
  const acts = (state.meta && state.meta.activity_suggestions) || [];
  const s = d.stats;
  const nums = [[s.partners, 'verified-reviewed partners'], [s.cities, s.cities === 1 ? 'city' : 'cities'], [s.completed, 'plans completed'], [s.reviews, 'verified reviews']].filter(([n]) => n > 0);
  const fee = state.meta ? state.meta.platform_fee_percent : 15;
  root.innerHTML = html`<div class="land">
  <section class="land-hero"><div class="lh-text"><p class="eyebrow">PUBLIC · NON-SEXUAL · SAFETY-FIRST</p>
    <h1>Good company,<br>on <em>your</em> schedule.</h1>
    <p class="sub">Book friendly, admin-approved companions for coffee, films, workouts, city walks and events - always in public, always through PairUp.</p>
    <form class="search-card" data-submit="home-search" role="search"><input class="field" name="city" list="home-cities" placeholder="Your city" aria-label="City" value="${state.me ? state.me.city : ''}"><datalist id="home-cities">${d.cities.map(c => html`<option value="${c.city}">`)}</datalist>
      <select class="field" name="activity" aria-label="Activity"><option value="">Any activity</option>${acts.map(a => html`<option>${a}</option>`)}</select>
      <button class="btn primary" type="submit">Find companions</button></form>
    <ul class="trust"><li>✓ Reviewed profiles</li><li>✓ Pay only on PairUp</li><li>✓ 18+ only</li></ul></div>
    <div class="lh-art" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="floatcard c1"><b>☕ Coffee date</b><span>Starbucks · Sat 4 PM</span><i>✓ Confirmed</i></div><div class="floatcard c2"><b>★ 4.9</b><span>"So easy to talk to"</span></div><div class="floatcard c3"><b>🛡 ID verified</b></div></div></section>
  ${nums.length ? html`<section class="statbar">${nums.map(([n, l]) => html`<div><b>${n}</b><span>${l}</span></div>`)}</section>` : ''}
  <section class="section"><h2>How PairUp works</h2><ol class="steps">${STEPS.map(([n, t, x]) => html`<li><span class="num">${n}</span><b>${t}</b><p class="muted">${x}</p></li>`)}</ol></section>
  ${d.activities.length ? html`<section class="section"><h2>Popular plans</h2><div class="pillrow">${d.activities.map(a => html`<a class="pill-link" href="#/browse?activity=${encodeURIComponent(a.name)}">${a.name} <small>${a.count}</small></a>`)}</div></section>` : ''}
  ${d.featured.length ? html`<section class="section"><div class="between"><h2>Featured partners</h2><a href="#/browse">See everyone →</a></div><div class="grid">${d.featured.slice(0, 4).map(card)}</div></section>` : ''}
  ${d.cities.length ? html`<section class="section"><h2>Available in</h2><div class="pillrow">${d.cities.map(c => html`<a class="pill-link" href="#/browse?city=${encodeURIComponent(c.city)}">${c.city} <small>${c.count}</small></a>`)}</div></section>` : ''}
  <section class="section alt"><h2>Safety isn't an add-on. It's the product.</h2><div class="tiles3">${SAFETY.map(([i, t, x]) => html`<div class="feat"><span>${i}</span><b>${t}</b><p class="muted">${x}</p></div>`)}</div><p class="center"><a href="#/safety">Read our Safety centre →</a></p></section>
  ${d.testimonials.length ? html`<section class="section"><h2>What members say</h2><div class="testi">${d.testimonials.map(t => html`<blockquote><span class="stars">${stars(t.rating)}</span><p>“${t.comment}”</p><footer>${t.reviewer} · plan with ${t.partner}</footer></blockquote>`)}</div></section>` : ''}
  ${plans && plans.plans ? html`<section class="section"><h2>Simple membership</h2><p class="muted center">Browsing is free. A membership lets you send booking requests; each plan is paid separately to the partner's rate.</p><div class="plans wide">${plans.plans.map(p => html`<div class="plan-card"><b>${p.label}</b><strong>${inr(p.amount)}</strong><small>${p.days} days of booking requests</small></div>`)}</div></section>` : ''}
  <section class="section cta-band"><div><h2>Earn by being great company</h2><p class="muted">Set your own rates and hours. Keep ${100 - fee}% of every booking, paid out to UPI.</p></div><a class="btn primary big" href="#/become-a-partner">Become a partner</a></section>
  <section class="section"><h2>Questions</h2>${FAQ.slice(0, 5).map(([q, a]) => html`<details class="faq"><summary>${q}</summary><p>${a}</p></details>`)}<p><a href="#/faq">All questions →</a></p></section>
  <section class="section final"><h2>Ready to meet someone new?</h2><div class="row center-row"><a class="btn primary big" href="#/browse">Browse companions</a>${state.me ? '' : html`<button class="btn ghost big" data-action="auth-register">Create account</button>`}</div></section></div>`.s;
}
import { submits } from './core.js';
submits['home-search'] = async f => {
  const p = new URLSearchParams(); const fd = new FormData(f);
  for (const k of ['city', 'activity']) if (fd.get(k)) p.set(k, fd.get(k));
  location.hash = '#/browse' + (p.toString() ? '?' + p : '');
};
