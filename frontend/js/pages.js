import { html, raw, api, state, $, toast, actions, submits, formObj, inr, ago, fmtD } from './core.js';
import { openAuth } from './auth.js';

export const FAQ = [
  ['What is PairUp?', 'PairUp lets adults (18+) book friendly, time-limited company for public, non-sexual plans - a coffee, a film, a gym session, a city walk, a plus-one for an event, or a video chat.'],
  ['Is this an escort or dating service?', 'No. Sexual services, solicitation and adult content are strictly banned and filtered. Profiles and chats are screened, and anyone who breaks the rule is permanently removed. Meetings must be in public places.'],
  ['How do I book someone?', 'Browse profiles for free, pick an activity and time, and send a request (a membership is needed to send requests). When the partner accepts, you pay through PairUp to confirm the plan, and chat opens.'],
  ['Why do I pay PairUp instead of the partner?', 'Paying on-platform protects both sides. PairUp holds your money until the plan is completed, which prevents advance-payment scams. Anyone asking you to pay by UPI or wallet outside PairUp should be reported.'],
  ['What if I need to cancel?', 'Cancel 24+ hours before the start for a full refund, 2-24 hours before for a 50% refund, and under 2 hours before for no refund. If a partner cancels, you always get a full refund. See the Refund policy.'],
  ['How are partners verified?', 'Every profile is reviewed by our team before going live. Partners can also complete ID verification (government ID + selfie) to earn a ✓ badge. Only completed bookings can be reviewed, so reviews are genuine.'],
  ['How do partners get paid?', 'After a booking is completed and the 24-hour dispute window passes, the partner\'s share is released to their wallet and can be withdrawn to UPI once their ID is verified.'],
  ['What should I do if I feel unsafe?', 'Use the 🛡 Safety button on any active booking to alert our team, call 112 for emergencies, and use Report or Block on any profile or chat. See the Safety centre for tips.'],
  ['Can I delete my account?', 'Yes - Account → Delete my account. Your personal details are removed; closed bookings are kept in anonymised form for dispute and legal records.'],
];

export function faqPage(root) {
  root.innerHTML = html`<div class="page narrow"><h1>Frequently asked questions</h1>${FAQ.map(([q, a]) => html`<details class="faq"><summary>${q}</summary><p>${a}</p></details>`)}
    <div class="notice">Can't find your answer? <a href="#/support">Contact support</a>.</div></div>`.s;
}

export function partnerLandingPage(root) {
  const fee = state.meta ? state.meta.platform_fee_percent : 15, min = state.meta ? state.meta.min_payout_inr : 500;
  root.innerHTML = html`<div class="page narrow"><p class="eyebrow">FOR PARTNERS</p><h1>Get paid to be great company.</h1>
    <p class="sub">Set your own rates and hours, meet people in public places, and keep ${100 - fee}% of every completed booking.</p>
    <div class="tiles"><div class="tile"><b>💸 You set the price</b><span>Every activity has your own rate</span></div><div class="tile"><b>🗓 You set the hours</b><span>Weekly schedule, pause any time</span></div><div class="tile"><b>🛡 Safety built in</b><span>Public venues, block, report, SOS</span></div></div>
    <h2>How it works</h2><ol class="steps vertical"><li><b>Create your profile</b> - photos, a short bio, the activities you offer and your rates.</li><li><b>Get approved</b> - our team reviews every profile (usually within 24 hours).</li><li><b>Accept requests</b> - customers pay through PairUp once you accept, so you're never chasing money.</li><li><b>Get paid</b> - earnings release 24 hours after completion; withdraw to UPI (min ${inr(min)}) after ID verification.</li></ol>
    <h2>Requirements</h2><ul><li>18 or older, with your own clear photos</li><li>Government ID verification to withdraw earnings</li><li>Public, non-sexual plans only - zero tolerance for sexual services or off-platform payments</li></ul>
    <p class="notice">PairUp's fee is ${fee}% of each completed booking. Taxes on your earnings are your responsibility - consult a tax adviser.</p>
    <div class="center"><button class="btn primary big" data-action="become-partner">Create a partner profile</button></div></div>`.s;
}
actions['become-partner'] = () => { openAuth('register', 'Become a partner'); const r = $('input[name=role][value=partner]'); if (r) r.checked = true; };

// ====================== SUPPORT ======================
export async function supportPage(root) {
  const me = state.me; let mine = [];
  if (me) { try { mine = await api('/support/mine'); } catch { /* ignore */ } }
  root.innerHTML = html`<div class="page narrow"><h1>Help &amp; support</h1><p class="muted">Check the <a href="#/faq">FAQ</a> first. Otherwise tell us what's up and we'll reply by email within 1-2 working days. <b>In danger? Call 112.</b></p>
    <form data-submit="support" class="stack"><div class="grid2"><div><label class="lbl" for="s-name">Your name</label><input class="field" id="s-name" name="name" required minlength="2" value="${me ? me.name : ''}"></div><div><label class="lbl" for="s-email">Email</label><input class="field" id="s-email" name="email" type="email" required value="${me ? me.email : ''}"></div></div>
    <label class="lbl" for="s-cat">Topic</label><select class="field" id="s-cat" name="category"><option value="booking">A booking</option><option value="payment_refund">Payment or refund</option><option value="account">My account</option><option value="safety">Safety concern</option><option value="partner_application">Partner application</option><option value="other">Something else</option></select>
    <label class="lbl" for="s-msg">Message</label><textarea class="field" id="s-msg" name="message" rows="5" required minlength="10" maxlength="3000" placeholder="Include booking numbers or names if relevant"></textarea>
    <button class="btn primary" type="submit">Send message</button></form>
    ${mine.length ? html`<h2>Your tickets</h2><div class="list">${mine.map(t => html`<div class="item"><div class="between"><b>#${t.id} · ${t.category.replace('_', ' ')}</b><span class="pill ${t.status === 'open' ? 'requested' : 'completed'}">${t.status}</span></div><p class="small">${t.message}</p>${t.admin_reply ? html`<div class="reply"><b>PairUp:</b> ${t.admin_reply}</div>` : html`<p class="muted small">Sent ${ago(t.created_at)}</p>`}</div>`)}</div>` : ''}</div>`.s;
}
submits.support = async f => { const r = await api('/support', { method: 'POST', body: formObj(f) }); toast(r.message, 'ok'); supportPage($('#view')); };
