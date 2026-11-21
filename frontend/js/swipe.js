// Partner side: swipe through customer profiles. Left = pass. Right = a free intro message is sent.
import { html, api, state, $, openModal, closeModal, toast, actions, hue, initials } from './core.js';
import { mountDeck } from './deck.js';

let ctl = null, items = [], last = null, suppressUndo = false, pending = Promise.resolve();
export function leaveCustomerDeck() { if (ctl) { ctl.destroy(); ctl = null; } document.body.classList.remove('deck-mode'); }

const card = c => html`<article class="dcard" data-id="${c.id}" aria-label="${c.name}, ${c.age}, ${c.city}">
  <div class="dc-photos">${c.photos.length ? c.photos.map((u, i) => html`<img class="${i === 0 ? 'on' : ''}" src="${u}" alt="${i === 0 ? c.name : ''}" draggable="false" loading="lazy">`)
    : html`<div class="ph full" style="--h:${hue(c.name)}"><span>${initials(c.name)}</span></div>`}</div>
  ${c.photos.length > 1 ? html`<div class="dc-bars">${c.photos.map((_, i) => html`<i class="${i === 0 ? 'on' : ''}"></i>`)}</div>` : ''}
  <span class="stamp like">SAY HI</span><span class="stamp nope">PASS</span>
  <div class="dc-info"><h3>${c.name} <small>${c.age}</small></h3><p class="dc-meta">⌖ ${c.city}</p>
  <p class="dc-head">${c.bio.length > 150 ? c.bio.slice(0, 150) + '…' : c.bio}</p></div></article>`;

const setLeft = n => { const e = $('#intro-left'); if (e) e.textContent = `${n} intro${n === 1 ? '' : 's'} left today`; };

async function load() {
  const r = await api('/discover/customers?limit=20');
  items = r.items; setLeft(r.intros_left);
  const hint = $('#intro-preview'); if (hint) hint.textContent = r.intro_preview;
  return r;
}

function mount() {
  if (ctl) { ctl.destroy(); ctl = null; }
  const empty = $('#deckEmpty'), acts = $('#deckActions');
  if (empty) empty.hidden = items.length > 0; if (acts) acts.classList.toggle('dim', !items.length);
  if (!items.length) return;
  ctl = mountDeck($('#deckHost'), {
    items, card, getTotal: () => items.length, loadMore: async () => {},
    onSwipe: (dir, c) => { pending = send(dir, c); },
    onUndo: c => { if (!suppressUndo) api(`/discover/swipes/${c.id}`, { method: 'DELETE' }).catch(() => {}); },
    onOpen: c => sheet(c),
    onEmpty: async () => { await pending; try { await load(); if (items.length) mount(); else { const e = $('#deckEmpty'), a = $('#deckActions'); if (e) e.hidden = false; if (a) a.classList.add('dim'); } } catch { /* keep empty state */ } },
  });
}

async function send(dir, c) {
      try {
        const r = await api('/discover/swipe', { method: 'POST', body: { customer_id: c.id, direction: dir } });
        last = { id: c.id, dir }; setLeft(r.intros_left);
        if (r.sent) toast(`Intro sent to ${c.name} 👋`, 'ok');
      } catch (e) {
        toast(e.message, 'error');                      // e.g. daily limit / availability off: put the card back
        setTimeout(() => { suppressUndo = true; if (ctl) ctl.undo(); suppressUndo = false; }, 400);   // after the swipe animation ends
      }
}

function sheet(c) {
  openModal(html`<div class="sheet-photos">${c.photos.map(u => html`<img src="${u}" alt="${c.name}" loading="lazy">`)}</div>
    <h2 class="nomt">${c.name}, ${c.age}</h2><p class="muted small">⌖ ${c.city}</p><p>${c.bio}</p>
    <div class="row"><button class="btn ghost grow" data-action="cd-pass-sheet">Pass</button><button class="btn primary grow" data-action="cd-hi-sheet">Say hi 👋</button></div>`, { label: c.name });
}

export async function customerDeckPage(root) {
  document.body.classList.add('deck-mode');
  root.innerHTML = html`<div class="page deck-page"><div class="between deck-top"><h1 class="nomt">Discover customers</h1><span class="chip" id="intro-left"></span></div>
    <div class="swipe-screen"><div class="deck-host" id="deckHost"></div>
    <div class="deck-empty" id="deckEmpty" hidden><div class="empty-art">🎉</div><h3>You're all caught up</h3><p class="muted">No more customers to show right now. Check back later.</p></div>
    <div class="deck-actions" id="deckActions">
      <button class="ab sm" data-action="cd-undo" aria-label="Undo last pass" title="Undo pass">↺</button>
      <button class="ab big pass" data-action="cd-pass" aria-label="Pass" title="Pass (←)">✕</button>
      <button class="ab sm info" data-action="cd-info" aria-label="View details" title="Details (↑)">ⓘ</button>
      <button class="ab big save" data-action="cd-hi" aria-label="Say hi" title="Say hi (→)">👋</button></div>
    <p class="deck-hint">Swipe right to send a free intro: “<span id="intro-preview"></span>” · Left to pass.</p></div></div>`.s;
  try { await load(); }
  catch (e) {
    document.body.classList.remove('deck-mode');
    root.innerHTML = html`<div class="page narrow center"><h1>Discover customers</h1><p class="muted">${e.message}</p><a class="btn primary" href="#/dashboard">Go to my dashboard</a></div>`.s;
    return;
  }
  mount();
}

actions['cd-pass'] = () => ctl && ctl.swipe('left');
actions['cd-hi'] = () => ctl && ctl.swipe('right');
actions['cd-info'] = () => ctl && ctl.open();
actions['cd-undo'] = () => {
  if (last && last.dir === 'right') { toast('A sent intro can’t be undone.', 'info'); return; }
  if (!ctl || !ctl.undo()) toast('Nothing to undo yet.', 'info');
};
actions['cd-pass-sheet'] = () => { closeModal(); ctl && ctl.swipe('left'); };
actions['cd-hi-sheet'] = () => { closeModal(); ctl && ctl.swipe('right'); };
