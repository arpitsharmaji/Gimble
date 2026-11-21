import { reveal } from './fx.js';
import { html, raw, $, $$, api, state, on, actions, closeModal, toast, refreshMe, modalOpen } from './core.js';
import { openAuth, verifyPage, resetPage, openModePicker } from './auth.js';
import { setupPage } from './setup.js';
import { discoverPage, profilePage, leaveBrowse } from './discover.js';
import { savedPage, dashboardPage, accountPage, stopTimers, timers, pollNotifications, renderBadges } from './account.js';
import { bookingsPage } from './bookings.js';
import { messagesPage } from './chat.js';
import { adminPage } from './admin.js';
import { homePage } from './home.js';
import { faqPage, partnerLandingPage, supportPage } from './pages.js';
import { earningsPage, schedulePage, kycPage } from './wallet.js';
import { legalPage } from './legal.js';

let view = $('#view');
/** Each navigation renders into a brand-new <main id="view">. A slow, stale render (e.g. the home page still loading when a
 *  login redirects to #/admin) then writes into a detached element and can never overwrite the page the user is on. */
function freshView() { const next = document.createElement('main'); next.id = 'view'; next.tabIndex = -1; next.className = 'enter'; view.replaceWith(next); view = next; return next; }

function renderHeader() {
  const me = state.me;
  const partnerMode = me && me.role === 'partner';
  const links = partnerMode ? [['browse', 'Discover'], ['messages', 'Messages'], ['bookings', 'Bookings'], ['dashboard', 'Dashboard'], ['earnings', 'Earnings']]
    : [['browse', 'Browse'], ['saved', 'Saved'], ['messages', 'Messages'], ['bookings', 'Bookings']];
  if (!me) links.push(['become-a-partner', 'Become a partner']);
  if (me && me.role === 'admin') links.push(['admin', 'Admin']);
  $('#topbar').innerHTML = html`<a class="brand" href="#/" aria-label="Gimble home"><img class="brand-logo" src="/logo-sm.png" alt="" width="40" height="33"><span>gimble</span></a>
    <nav class="top-nav" aria-label="Main">${links.map(([p, l]) => html`<a href="#/${p}" data-nav="${p}">${l}${p === 'messages' ? html`<span class="badge-n" id="msg-badge" hidden></span>` : ''}</a>`)}</nav>
    <div class="top-actions"><button class="icon-btn" data-action="bell" aria-label="Notifications">🔔<span class="badge-n" id="bell-badge" hidden></span></button>
    ${me && me.role !== 'admin' ? html`<button class="mode-pill" data-action="switch-mode" title="Switch between Hire and Get hired">${partnerMode ? '🌟 Getting hired' : '🔍 Hiring'} ⇄</button>` : ''}
    ${me ? html`<a class="avatar" href="#/account" aria-label="Account">${(me.name || 'A')[0].toUpperCase()}</a>` : html`<button class="btn primary sm" data-action="auth-login">Log in</button><button class="btn ghost sm hide-sm" data-action="auth-register">Sign up</button>`}</div>`.s;
  $('#bottomnav').innerHTML = html`${[['', '⌂', 'Home'], ['browse', '⌕', me && me.role === 'partner' ? 'Discover' : 'Browse'], ['messages', '▤', 'Chats'], ['bookings', '▣', 'Bookings'], [me ? 'account' : 'login', '○', me ? 'Account' : 'Log in']].map(([p, i, l]) => html`<a href="#/${p === 'login' ? '' : p}" data-nav="${p}" ${p === 'login' ? raw('data-action="auth-login"') : ''}><span>${i}</span>${l}</a>`)}`.s;
  markNav(); renderBadges();
}
const markNav = () => { const p = location.hash.replace(/^#\/?/, '').split('/')[0]; $$('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === p)); };

async function route() {
  stopTimers(); leaveBrowse(); if (modalOpen()) closeModal();
  const [pathPart, query = ''] = location.hash.replace(/^#\/?/, '').split('?'); const [path, ...rest] = pathPart.split('/'); const arg = rest.join('/');
  markNav(); window.scrollTo(0, 0); document.body.dataset.route = path;
  const host = freshView();
  // Customers must finish their profile (photos + bio) before using the app.
  const FREE = ['setup', 'terms', 'privacy', 'standards', 'refunds', 'safety', 'faq', 'support', 'verify', 'reset', 'account'];
  if (state.me && state.me.role === 'customer' && state.me.modes && !state.me.modes.hire.complete && !FREE.includes(path)) { location.hash = '#/setup'; return; }
  try {
    switch (path) {
      case '': await homePage(host); break;
      case 'browse': case 'discover': await discoverPage(host, new URLSearchParams(query)); break;
      case 'faq': faqPage(host); break;
      case 'support': await supportPage(host); break;
      case 'become-a-partner': partnerLandingPage(host); break;
      case 'earnings': await earningsPage(host); break;
      case 'schedule': await schedulePage(host); break;
      case 'verify-id': await kycPage(host); break;
      case 'p':
        if (state.me && state.me.role === 'partner' && String(state.me.id) !== arg) { host.innerHTML = html`<div class="page narrow center"><h1>Partners can't browse partners</h1><p class="muted">Switch to Hire mode to find a companion.</p><button class="btn primary" data-action="switch-mode">Switch mode</button></div>`.s; break; }
        await profilePage(host, arg); break;
      case 'setup': await setupPage(host); break;
      case 'saved': await savedPage(host); break;
      case 'messages': await messagesPage(host, arg); break;
      case 'bookings': await bookingsPage(host); break;
      case 'dashboard': await dashboardPage(host); break;
      case 'account': await accountPage(host); break;
      case 'admin': await adminPage(host); break;
      case 'verify': await verifyPage(host, arg); break;
      case 'reset': resetPage(host, arg); break;
      case 'safety': case 'terms': case 'privacy': case 'standards': case 'refunds': legalPage(host, path); break;
      default: host.innerHTML = html`<div class="page narrow center"><h1>Page not found</h1><a class="btn primary" href="#/">Go home</a></div>`.s;
    }
  } catch (e) { console.error(e); host.innerHTML = html`<div class="page narrow center"><h1>Something went wrong</h1><p class="muted">${e.message}</p><button class="btn primary" data-action="reload">Reload</button></div>`.s; }
  if (host !== view) return;   // a newer navigation took over
  reveal(host);
  document.title = ({ '': 'Gimble - Meet your kind of company', browse: 'Browse companions · Gimble', faq: 'FAQ · Gimble', refunds: 'Refund policy · Gimble', safety: 'Safety · Gimble', terms: 'Terms · Gimble', privacy: 'Privacy · Gimble' })[path] || 'Gimble';
}
actions.reload = () => location.reload();
actions['skip-main'] = () => view.focus();
actions['install-app'] = async () => { if (window._installEvt) { window._installEvt.prompt(); window._installEvt = null; $('#install-btn').hidden = true; } };

// Re-render header on any auth refresh; re-run the page only on real login/logout.
on('auth', renderHeader);
on('authchange', () => { startPolling(); route(); });
window.addEventListener('hashchange', route);
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); window._installEvt = e; $('#install-btn').hidden = false; });

let notifTimer = null;
function startPolling() {
  clearInterval(notifTimer);
  if (!state.me) return;
  pollNotifications(); notifTimer = setInterval(() => { if (!document.hidden) pollNotifications(); }, 30000);
}

// First-visit onboarding (also the 18+ confirmation; the real age check is the date of birth at sign-up)
const SLIDES = [
  ['logo', 'Plans are better with good company', 'Book friendly, admin-approved companions for coffee, films, workouts and city walks.'],
  ['🛡️', 'Safe by design', 'Public places only. You pay through Gimble after they accept - never upfront to a stranger.'],
  ['⇆', 'Swipe to find your kind of company', 'Browse verified profiles like you would on your favourite app. Gimble is for adults 18+ and strictly non-sexual.'],
];
function onboarding() {
  if (localStorage.getItem('gimble_18') === '1') return;
  const g = $('#gate'); g.hidden = false; document.body.classList.add('no-scroll');
  g.innerHTML = html`<div class="ob"><div class="ob-bg" aria-hidden="true"><i class="orb o1"></i><i class="orb o2"></i></div>
    <button class="ob-skip link" id="ob-skip">Skip</button>
    <div class="ob-track" id="ob-track">${SLIDES.map(([i, t, x]) => html`<section class="ob-slide"><div class="ob-art ${i === 'logo' ? 'logo' : ''}">${i === 'logo' ? html`<img src="/logo-lg.png" alt="Gimble">` : html`<span>${i}</span>`}</div><h2>${t}</h2><p>${x}</p></section>`)}</div>
    <div class="ob-dots" id="ob-dots">${SLIDES.map((_, i) => html`<i class="${i === 0 ? 'on' : ''}"></i>`)}</div>
    <div class="ob-actions"><button class="btn primary big block" id="ob-next">Next</button><button class="btn ghost block" id="ob-leave" hidden>Leave</button></div></div>`.s;
  const track = $('#ob-track'), dots = $$('#ob-dots i'), next = $('#ob-next'), leave = $('#ob-leave');
  const cur = () => Math.round(track.scrollLeft / track.clientWidth);
  const sync = () => { const i = cur(); dots.forEach((d, k) => d.classList.toggle('on', k === i)); const last = i === SLIDES.length - 1; next.textContent = last ? "I'm 18 or older - let's go" : 'Next'; leave.hidden = !last; $('#ob-skip').style.visibility = last ? 'hidden' : 'visible'; };
  const go = i => track.scrollTo ? track.scrollTo({ left: i * track.clientWidth, behavior: 'smooth' }) : (track.scrollLeft = i * track.clientWidth);
  track.addEventListener('scroll', sync, { passive: true });
  next.onclick = () => { if (cur() >= SLIDES.length - 1) { localStorage.setItem('gimble_18', '1'); g.hidden = true; g.innerHTML = ''; document.body.classList.remove('no-scroll'); } else go(cur() + 1); };
  $('#ob-skip').onclick = () => go(SLIDES.length - 1);
  leave.onclick = () => { location.href = 'https://www.google.com'; };
  sync();
}
window.addEventListener('scroll', () => document.body.classList.toggle('scrolled', window.scrollY > 24), { passive: true });

(async () => {
  onboarding(); renderHeader();
  try { state.meta = await api('/meta'); } catch { state.meta = { activity_suggestions: [], min_rate: 50, max_rate: 50000 }; toast('Couldn\'t reach the server. Some features may not work.', 'error'); }
  await refreshMe();
  startPolling();
  await route();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
})();
