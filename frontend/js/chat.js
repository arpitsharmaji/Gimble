import { html, api, state, $, $$, openModal, toast, actions, submits, formObj, ago, avatar, emptyState, fmtDT } from './core.js';
import { reportModal, blockUser } from './safety.js';
import { timers, stopTimers } from './account.js';
import { openMembership, startBooking } from './discover.js';
import { haptic } from './fx.js';

const EMOJI = { 'Video call': '📹', 'Coffee date': '☕', 'Movie companion': '🎬', 'Dinner': '🍽️', 'Shopping': '🛍️', 'Gym partner': '🏋️', 'City exploration': '🌆', 'Event / concert plus-one': '🎤', 'Cafe study partner': '📚', 'Language practice': '🗣️', 'Sports partner': '⚽', 'Museum / gallery visit': '🖼️', 'Board games': '🎲' };
const QUICK = ['On my way 🚶', 'Running 5 min late ⏰', "I'm here! 👋", 'Thank you! 😊'];
let S = { other: null, last: 0, lastSender: null, lastTime: 0, lastDay: '' };

const dayLabel = d => { const t = new Date(); const y = new Date(Date.now() - 864e5); const same = (a, b) => a.toDateString() === b.toDateString(); return same(d, t) ? 'Today' : same(d, y) ? 'Yesterday' : d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }); };
const clock = iso => new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
const ctxChip = b => b ? html`<span class="ctx-chip">${EMOJI[b.activity] || '📅'} ${b.activity} · ${fmtDT(b.scheduled_at)}</span>` : '';

export async function messagesPage(root, otherId) {
  if (!state.me) { root.innerHTML = html`<div class="page narrow">${emptyState({ icon: '🔐', title: 'Please log in', text: 'Log in to see your messages.', cta: html`<button class="btn primary" data-action="auth-login">Log in</button>` })}</div>`.s; return; }
  let convs;
  try { convs = await api('/conversations'); } catch (e) { root.innerHTML = html`<div class="page"><p class="err">${e.message}</p></div>`.s; return; }
  const open = otherId ? Number(otherId) : null;
  root.innerHTML = html`<div class="page chat-page"><div class="chat4 ${open ? 'has-thread' : ''}">
    <aside class="convs4"><div class="convs-head"><h2>Messages</h2></div>${convs.length ? convs.map(c => html`<a class="conv4 ${open === c.user_id ? 'on' : ''}" href="#/messages/${c.user_id}">${avatar(c.name, c.photo_url, 'md')}<span class="grow"><span class="between"><b>${c.name}</b>${c.last_at ? html`<small class="muted">${ago(c.last_at)}</small>` : ''}</span><small class="muted line">${c.last_message || 'Say hello 👋'}</small>${c.booking ? html`<small class="ctx-mini">${EMOJI[c.booking.activity] || '📅'} ${c.booking.activity}</small>` : html`<small class="ctx-mini">💬 Inquiry</small>`}</span>${c.unread ? html`<span class="dot">${c.unread}</span>` : ''}</a>`)
      : html`<div class="convs-empty">${emptyState({ icon: '💬', title: 'No chats yet', text: state.me.role === 'partner' ? 'Customers can message you from your profile. Replies and booking chats show up here.' : 'Message a partner from their profile, or chat once a booking is accepted.', cta: html`<a class="btn ghost sm" href="#/browse">Browse companions</a>` })}</div>`}</aside>
    <section class="thread4" id="thread">${open ? '' : html`<div class="thread-empty">${emptyState({ icon: '💬', title: 'Select a conversation', text: 'Your messages with partners and customers appear here.' })}</div>`}</section></div></div>`.s;
  if (open) await openThread(open);
}

const STARTERS = ['Hi! Are you free this weekend? 👋', 'What time works for a coffee?', 'Do you offer video calls too?'];
const lockedBox = st => st.needs_membership
  ? html`<div class="locked"><p>🔒 ${st.reason}</p><button class="btn primary" data-action="open-membership">Get membership</button></div>`
  : html`<div class="locked"><p>⏳ ${st.reason}</p></div>`;
const composerBox = (id, st, inquiry) => html`${inquiry ? html`<p class="inq-hint" id="inqHint">${st.remaining === 1 ? '1 message left' : `${st.remaining} messages left`} until they reply · no phone numbers or links yet</p>` : ''}
  <div class="quick" id="quick">${(inquiry ? STARTERS : QUICK).map(q => html`<button type="button" data-action="quick" data-q="${q}">${q}</button>`)}</div>
  <form class="composer" data-submit="send-msg"><input type="hidden" name="to" value="${id}"><textarea name="body" rows="1" maxlength="2000" placeholder="Write a message…" required aria-label="Message"></textarea><button class="send-btn" type="submit" aria-label="Send">➤</button></form>`;

async function openThread(id) {
  const box = $('#thread'); S = { other: id, last: 0, lastSender: null, lastTime: 0, lastDay: '', locked: false, remaining: null };
  try {
    const r = await api(`/messages/${id}`);
    const st = r.state || { can_send: true, remaining: null }, inquiry = st.remaining !== null && st.remaining !== undefined && st.can_send;
    const tip = localStorage.getItem('gimble_chat_tip') !== '1', first = r.other.name.split(' ')[0];
    S.locked = !st.can_send; S.remaining = st.remaining;
    box.innerHTML = html`<header class="th-head"><a class="back mobile-only" href="#/messages" aria-label="Back">←</a>${avatar(r.other.name, r.other.photo_url, 'md')}<div class="grow"><b>${r.other.name}</b><div>${r.other.booking ? ctxChip(r.other.booking) : html`<span class="ctx-chip soft">💬 Inquiry</span>`}</div></div>
      ${!r.other.booking && state.me.role === 'customer' ? html`<button class="btn primary sm" data-action="chat-book" data-id="${id}">Book ${first}</button>` : ''}
      <button class="icon-btn dots" data-action="chat-menu" data-id="${id}" data-name="${r.other.name}" aria-label="More options">⋯</button></header>
      ${tip ? html`<div class="tip-banner" id="chatTip">🛡 ${r.other.booking ? 'Never send money, OTPs or card details here.' : 'Keep it on Gimble: phone numbers, links and payment requests aren\'t allowed until a booking is accepted.'} Sexual content is blocked.<button class="tip-x" data-action="chat-tip-x" aria-label="Dismiss">×</button></div>` : ''}
      <div class="msgs4" id="msgs" aria-live="polite"></div>
      <div id="composerBox">${st.can_send ? composerBox(id, st, inquiry) : lockedBox(st)}</div>`.s;
    appendMsgs(r.messages);
    if (!r.messages.length) $('#msgs').innerHTML = `<div class="say-hi"><span>👋</span><p>${st.can_send ? `Say hi to ${first.replace(/</g, '&lt;')} to start the conversation` : 'No messages yet'}</p></div>`;
    wireComposer();
    stopTimers(); timers.push(setInterval(poll, 5000));
  } catch (e) { box.innerHTML = html`<div class="thread-empty">${emptyState({ icon: '🚫', title: 'Chat unavailable', text: e.message })}</div>`.s; }
}
function wireComposer() {
  const ta = $('.composer textarea'); if (!ta) return;
  ta.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('.composer').requestSubmit(); } });
  ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'; });
}
function lockNow(reason) { S.locked = true; const b = $('#composerBox'); if (b) b.innerHTML = lockedBox({ needs_membership: false, reason }).s; }

function appendMsgs(list) {
  const m = $('#msgs'); if (!m || !list.length) return;
  const stick = m.scrollTop + m.clientHeight >= m.scrollHeight - 80 || S.last === 0;
  const hi = m.querySelector('.say-hi'); if (hi) hi.remove();
  m.querySelectorAll('.seen').forEach(e => e.remove());
  for (const x of list) {
    if (x.id <= S.last) continue; S.last = x.id;
    const d = new Date(x.created_at), day = d.toDateString();
    if (day !== S.lastDay) { const sep = document.createElement('div'); sep.className = 'day-sep'; sep.innerHTML = `<span>${dayLabel(d)}</span>`; m.append(sep); S.lastDay = day; S.lastSender = null; }
    const mine = x.sender_id === state.me.id, cont = S.lastSender === x.sender_id && d - S.lastTime < 5 * 60e3;
    const prev = m.querySelector('.msg:last-of-type'); if (cont && prev) prev.classList.add('no-time');
    const el = document.createElement('div'); el.className = `msg ${mine ? 'me' : 'them'}${cont ? ' cont' : ''}`;
    el.innerHTML = html`<p>${x.body}</p><small>${clock(x.created_at)}</small>`.s;
    m.append(el); S.lastSender = x.sender_id; S.lastTime = d.getTime();
    if (mine && x.read) S.lastSeen = el;
  }
  const own = [...m.querySelectorAll('.msg.me')].pop();
  if (own && list.some(x => x.sender_id === state.me.id && x.read)) { const s = document.createElement('span'); s.className = 'seen'; s.textContent = '✓✓ Seen'; own.append(s); }
  if (stick) m.scrollTop = m.scrollHeight;
}
async function poll() {
  if (document.hidden || !S.other || !$('#msgs')) return;
  try { const r = await api(`/messages/${S.other}?after=${S.last}`); if (S.locked && r.state && r.state.can_send) return openThread(S.other); const hadNew = r.messages.length; appendMsgs(r.messages); if (hadNew && r.messages.some(x => x.sender_id !== state.me.id)) haptic(8); } catch { /* transient */ }
}
async function sendText(to, body) {
  const m = await api('/messages', { method: 'POST', body: { receiver_id: Number(to), body } });
  appendMsgs([m]); haptic(6);
  if (m.remaining !== undefined && m.remaining !== null) {
    S.remaining = m.remaining; const h = $('#inqHint');
    if (m.remaining === 0) lockNow("You've used your messages. Please wait for them to reply - you'll be notified.");
    else if (h) h.textContent = `${m.remaining === 1 ? '1 message left' : `${m.remaining} messages left`} until they reply · no phone numbers or links yet`;
  }
}
submits['send-msg'] = async f => { const b = formObj(f); const ta = $('textarea', f); try { await sendText(b.to, b.body); ta.value = ''; ta.style.height = 'auto'; } catch (e) { if (e.status === 402) openMembership(); else throw e; } };
actions.quick = async el => { try { await sendText(S.other, el.dataset.q); } catch (e) { toast(e.message, 'error'); } };
actions['chat-book'] = async el => { try { const p = await api(`/partners/${el.dataset.id}`); startBooking(p, Object.keys(p.rates)[0]); } catch { toast('This person isn\'t available for booking.', 'error'); } };
actions['chat-tip-x'] = () => { localStorage.setItem('gimble_chat_tip', '1'); const t = $('#chatTip'); if (t) t.remove(); };
actions['chat-report'] = el => reportModal(Number(el.dataset.id), el.dataset.name);
actions['chat-block'] = async el => { if (await blockUser(Number(el.dataset.id), el.dataset.name)) location.hash = '#/messages'; };
actions['chat-menu'] = el => openModal(html`<h2>${el.dataset.name}</h2><div class="stack"><button class="btn ghost block" data-action="chat-report" data-id="${el.dataset.id}" data-name="${el.dataset.name}">🚩 Report ${el.dataset.name}</button><button class="btn danger block" data-action="chat-block" data-id="${el.dataset.id}" data-name="${el.dataset.name}">⛔ Block ${el.dataset.name}</button></div><p class="muted small">Blocking cancels any pending bookings between you and hides your profiles from each other.</p>`, { label: 'Chat options' });
