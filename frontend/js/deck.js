// Tinder/Bumble-style swipe deck: stacked cards, drag physics, fling velocity, tap-to-change-photo,
// swipe-up for details, undo. Framework-free; the page owns data and side effects through callbacks.
import { html, inr, hue, initials } from './core.js';
import { haptic, burst } from './fx.js';

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function cardHTML(p) {
  const photos = p.photos && p.photos.length ? p.photos : [];
  return html`<article class="dcard" data-id="${p.id}" aria-label="${p.name}, ${p.age}, ${p.city}">
    <div class="dc-photos">${photos.length ? photos.map((u, i) => html`<img class="${i === 0 ? 'on' : ''}" src="${u}" alt="${i === 0 ? p.name : ''}" draggable="false" ${i === 0 ? '' : 'loading="lazy"'}>`)
      : html`<div class="ph full" style="--h:${hue(p.name)}"><span>${initials(p.name)}</span></div>`}</div>
    ${photos.length > 1 ? html`<div class="dc-bars">${photos.map((_, i) => html`<i class="${i === 0 ? 'on' : ''}"></i>`)}</div>` : ''}
    <span class="stamp like">SAVE</span><span class="stamp nope">PASS</span>
    <div class="dc-info">
      <div class="dc-badges">${p.verified ? html`<span class="chip-badge ok">✓ ID verified</span>` : ''}<span class="chip-badge ${p.available ? 'live' : ''}">${p.available ? '● Available' : 'Unavailable'}</span></div>
      <h3>${p.name} <small>${p.age}</small></h3>
      <p class="dc-meta">⌖ ${p.city} · <b>★ ${p.review_count ? p.rating.toFixed(1) : 'New'}</b> · from <b>${inr(p.min_rate)}</b></p>
      ${p.headline ? html`<p class="dc-head">${p.headline}</p>` : ''}
      <div class="tags">${p.activities.slice(0, 3).map(t => html`<span>${t}</span>`)}</div>
    </div></article>`;
}

/**
 * opts: { items, getTotal(), loadMore():Promise, onSwipe(dir,p), onUndo(p,entry), onOpen(p), onIndex(i), onEmpty(), startIndex }
 * Returns { swipe(dir), undo(), open(), destroy(), index() }
 */
export function mountDeck(host, opts) {
  let idx = opts.startIndex || 0, busy = false, loading = false, drag = null;
  const history = [], nodes = [];
  host.innerHTML = '<div class="deck-stack" role="group" aria-label="Profiles to swipe"></div>';
  const stack = host.firstElementChild;

  const make = i => { const p = opts.items[i]; if (!p) return null; const w = document.createElement('div'); w.innerHTML = cardHTML(p).s; const c = w.firstElementChild; c._i = i; c._photo = 0; return c; };
  const place = (n, k, animate = true) => {
    n.style.transition = animate ? 'transform .34s cubic-bezier(.2,.8,.2,1), opacity .3s' : 'none';
    n.style.zIndex = String(10 - k); n.classList.toggle('top', k === 0);
    n.style.transform = k === 0 ? 'translate(0,0) rotate(0)' : `translateY(${k * 13}px) scale(${1 - k * 0.055})`;
    n.style.opacity = k > 2 ? '0' : '1';
  };
  const layout = () => nodes.forEach((n, k) => place(n, k));
  const preload = () => { for (let k = 1; k <= 3; k++) { const p = opts.items[idx + k]; if (p && p.photos) p.photos.slice(0, 2).forEach(u => { const im = new Image(); im.src = u; }); } };
  const empty = () => { stack.classList.toggle('is-empty', !nodes.length); if (!nodes.length && opts.onEmpty) opts.onEmpty(); };

  async function ensureMore() {
    if (loading || opts.items.length - idx > 4 || opts.items.length >= opts.getTotal()) return;
    loading = true; try { await opts.loadMore(); fill(); } finally { loading = false; }
  }
  function fill() {
    while (nodes.length < 3 && opts.items[idx + nodes.length]) {
      const n = make(idx + nodes.length); stack.append(n); nodes.push(n); place(n, nodes.length - 1, false);
    }
    layout(); preload(); opts.onIndex && opts.onIndex(idx); ensureMore(); empty();
  }

  function setPhoto(card, n) {
    const imgs = card.querySelectorAll('.dc-photos img'); if (imgs.length < 2) return false;
    const next = Math.max(0, Math.min(imgs.length - 1, n)); if (next === card._photo) { card.classList.add('bump'); setTimeout(() => card.classList.remove('bump'), 160); return true; }
    imgs[card._photo].classList.remove('on'); imgs[next].classList.add('on');
    const bars = card.querySelectorAll('.dc-bars i'); bars[card._photo].classList.remove('on'); bars[next].classList.add('on'); card._photo = next; return true;
  }
  const setStamps = (c, dx) => { const k = Math.min(1, Math.abs(dx) / 100); c.querySelector('.stamp.like').style.opacity = dx > 0 ? k : 0; c.querySelector('.stamp.nope').style.opacity = dx < 0 ? k : 0; };

  function swipe(dir, vx = 0) {
    if (busy || !nodes.length) return; busy = true;
    const card = nodes.shift(), p = opts.items[card._i], sign = dir === 'right' ? 1 : -1;
    history.push({ i: card._i, dir });
    setStamps(card, sign * 120);
    card.style.transition = 'transform .36s cubic-bezier(.25,.7,.3,1), opacity .36s ease-in';
    card.style.transform = `translate(${sign * (window.innerWidth + 200)}px, ${-30}px) rotate(${sign * 24}deg)`; card.style.opacity = '0';
    haptic(dir === 'right' ? 18 : 8);
    if (dir === 'right') { const r = card.getBoundingClientRect(); burst(r.left + r.width * 0.8, r.top + r.height * 0.3); }
    opts.onSwipe && opts.onSwipe(dir, p, card._i);
    idx++; layout();
    setTimeout(() => { card.remove(); busy = false; fill(); }, 300);
  }

  function undo() {
    if (busy || !history.length) return false; busy = true;
    const h = history.pop(); idx = h.i;
    const n = make(idx), sign = h.dir === 'right' ? 1 : -1;
    n.style.transition = 'none'; n.style.zIndex = '12'; n.style.transform = `translate(${sign * (window.innerWidth + 120)}px,-30px) rotate(${sign * 24}deg)`; n.style.opacity = '0';
    stack.append(n); nodes.unshift(n);
    void n.offsetWidth;
    nodes.forEach((x, k) => place(x, k));
    haptic(10);
    if (nodes.length > 3) { const gone = nodes.pop(); gone.remove(); }
    opts.onUndo && opts.onUndo(opts.items[idx], h); opts.onIndex && opts.onIndex(idx); empty();
    setTimeout(() => { busy = false; }, 320);
    return true;
  }
  const open = () => { if (nodes[0] && opts.onOpen) opts.onOpen(opts.items[nodes[0]._i]); };

  // ---- pointer gestures (mouse + touch + pen) ----
  const down = e => {
    if (busy || !nodes[0] || (e.button !== undefined && e.button > 0) || e.target.closest('button,a')) return;
    drag = { x: e.clientX, y: e.clientY, t: performance.now(), dx: 0, dy: 0, moved: false };
    try { stack.setPointerCapture(e.pointerId); } catch { /* ok */ }
    nodes[0].style.transition = 'none'; if (nodes[1]) nodes[1].style.transition = 'none';
  };
  const move = e => {
    if (!drag) return; const c = nodes[0]; if (!c) return;
    drag.dx = e.clientX - drag.x; drag.dy = e.clientY - drag.y;
    if (Math.abs(drag.dx) + Math.abs(drag.dy) > 9) drag.moved = true;
    c.style.transform = `translate(${drag.dx}px, ${drag.dy * 0.4}px) rotate(${drag.dx / 17}deg)`; setStamps(c, drag.dx);
    const k = Math.min(1, Math.abs(drag.dx) / 140);
    if (nodes[1]) nodes[1].style.transform = `translateY(${13 - 13 * k}px) scale(${0.945 + 0.055 * k})`;
  };
  const up = e => {
    if (!drag) return; const d = drag; drag = null; const c = nodes[0]; if (!c) return;
    const dt = Math.max(1, performance.now() - d.t), vx = d.dx / dt, w = c.getBoundingClientRect().width;
    if (d.moved && (Math.abs(d.dx) > w * 0.27 || (Math.abs(vx) > 0.5 && Math.abs(d.dx) > 40))) return swipe(d.dx > 0 ? 'right' : 'left', vx);
    c.style.transition = 'transform .38s cubic-bezier(.2,1.2,.3,1)'; c.style.transform = 'translate(0,0) rotate(0)'; setStamps(c, 0);
    if (nodes[1]) { nodes[1].style.transition = 'transform .3s'; nodes[1].style.transform = `translateY(13px) scale(.945)`; }
    if (d.moved && d.dy < -90 && Math.abs(d.dx) < 80) return open();           // swipe up = details
    if (!d.moved) {                                                              // tap: left/right edge = photo, middle = details
      const r = c.getBoundingClientRect(), fx = (e.clientX - r.left) / r.width;
      if (fx < 0.32) { if (!setPhoto(c, c._photo - 1)) open(); } else if (fx > 0.68) { if (!setPhoto(c, c._photo + 1)) open(); } else open();
    }
  };
  stack.addEventListener('pointerdown', down); stack.addEventListener('pointermove', move);
  stack.addEventListener('pointerup', up); stack.addEventListener('pointercancel', up);

  const key = e => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement && document.activeElement.tagName) || document.querySelector('#modal-root .modal')) return;
    if (e.key === 'ArrowLeft') swipe('left'); else if (e.key === 'ArrowRight') swipe('right'); else if (e.key === 'ArrowUp') open(); else if (e.key === 'Backspace' || e.key === 'z') undo();
  };
  document.addEventListener('keydown', key);

  fill();
  return { swipe, undo, open, index: () => idx, refill: fill, current: () => nodes[0] && opts.items[nodes[0]._i], destroy() { document.removeEventListener('keydown', key); stack.replaceChildren(); } };
}
