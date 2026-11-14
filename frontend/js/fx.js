// Small, dependency-free effects: scroll reveal, count-up, haptics, heart/confetti bursts.
export const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
export const isMobile = () => window.matchMedia ? window.matchMedia('(max-width: 820px)').matches : false;
export const haptic = (ms = 12) => { try { if (navigator.vibrate) navigator.vibrate(ms); } catch { /* unsupported */ } };

let io = null;
/** Fade/slide elements with class .rv into view as they scroll on screen. */
export function reveal(root = document) {
  const els = [...root.querySelectorAll('.rv:not(.in)')];
  if (!els.length) return;
  if (!('IntersectionObserver' in window) || reduceMotion()) { els.forEach(e => e.classList.add('in')); return; }
  io ||= new IntersectionObserver(entries => entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); en.target.dispatchEvent(new CustomEvent('revealed')); } }), { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
  els.forEach(e => io.observe(e));
}

/** Animate a number up to `to` once its element is revealed. */
export function countUp(el, to, dur = 1100) {
  const run = () => {
    if (reduceMotion()) { el.textContent = to.toLocaleString('en-IN'); return; }
    const t0 = performance.now();
    const tick = t => { const k = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))).toLocaleString('en-IN'); if (k < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  };
  const host = el.closest('.rv');
  if (host && !host.classList.contains('in')) host.addEventListener('revealed', run, { once: true }); else run();
}

/** Emoji particles bursting from a point (e.g. when a profile is saved). */
export function burst(x, y, glyph = '♥', n = 12) {
  if (reduceMotion()) return;
  for (let i = 0; i < n; i++) {
    const s = document.createElement('span');
    s.className = 'burst'; s.textContent = glyph; s.style.left = x + 'px'; s.style.top = y + 'px';
    s.style.fontSize = (14 + Math.random() * 16) + 'px';
    document.body.append(s);
    const ang = (Math.PI * 2 * i) / n + Math.random() * 0.6, dist = 60 + Math.random() * 70;
    if (s.animate) {
      s.animate([{ transform: 'translate(-50%,-50%) scale(.4)', opacity: 1 }, { transform: `translate(calc(-50% + ${Math.cos(ang) * dist}px), calc(-50% + ${Math.sin(ang) * dist - 30}px)) scale(1.1)`, opacity: 0 }], { duration: 650 + Math.random() * 250, easing: 'cubic-bezier(.2,.7,.3,1)' }).onfinish = () => s.remove();
    } else setTimeout(() => s.remove(), 700);
  }
}

export function confetti() {
  if (reduceMotion()) return;
  const colors = ['#6a3dff', '#e060f8', '#ffd27a', '#7be0ad', '#8ab4ff'];
  for (let i = 0; i < 46; i++) {
    const c = document.createElement('i');
    c.className = 'confetti'; c.style.background = colors[i % colors.length]; c.style.left = Math.random() * 100 + 'vw';
    document.body.append(c);
    if (c.animate) c.animate([{ transform: 'translateY(-10vh) rotate(0)', opacity: 1 }, { transform: `translateY(105vh) translateX(${(Math.random() - .5) * 200}px) rotate(${Math.random() * 720}deg)`, opacity: .9 }], { duration: 1600 + Math.random() * 1400, delay: Math.random() * 300, easing: 'cubic-bezier(.3,.6,.4,1)' }).onfinish = () => c.remove();
    else setTimeout(() => c.remove(), 1500);
  }
}
