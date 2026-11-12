import { html, raw, $, $$, api, state, on, actions, closeModal, toast, refreshMe, modalOpen } from './core.js';
import { openAuth, verifyPage, resetPage } from './auth.js';
import { discoverPage, profilePage } from './discover.js';
import { savedPage, bookingsPage, messagesPage, dashboardPage, accountPage, stopTimers, timers, pollNotifications, renderBadges } from './account.js';
import { adminPage } from './admin.js';
import { homePage } from './home.js';
import { faqPage, partnerLandingPage, supportPage } from './pages.js';
import { earningsPage, schedulePage, kycPage } from './wallet.js';
import { legalPage } from './legal.js';

const view = $('#view');

function renderHeader() {
  const me = state.me;
  const links = [['browse', 'Browse'], ['saved', 'Saved'], ['messages', 'Messages'], ['bookings', 'Bookings']];
  if (me && me.role === 'partner') links.push(['dashboard', 'Dashboard'], ['earnings', 'Earnings']);
  if (!me || me.role !== 'partner') links.push(['become-a-partner', 'Become a partner']);
  if (me && me.role === 'admin') links.push(['admin', 'Admin']);
  $('#topbar').innerHTML = html`<a class="brand" href="#/"><span class="brand-mark">✦</span> pairup</a>
    <nav class="top-nav" aria-label="Main">${links.map(([p, l]) => html`<a href="#/${p}" data-nav="${p}">${l}${p === 'messages' ? html`<span class="badge-n" id="msg-badge" hidden></span>` : ''}</a>`)}</nav>
    <div class="top-actions"><button class="icon-btn" data-action="bell" aria-label="Notifications">🔔<span class="badge-n" id="bell-badge" hidden></span></button>
    ${me ? html`<a class="avatar" href="#/account" aria-label="Account">${(me.name || 'A')[0].toUpperCase()}</a>` : html`<button class="btn primary sm" data-action="auth-login">Log in</button><button class="btn ghost sm hide-sm" data-action="auth-register">Sign up</button>`}</div>`.s;
  $('#bottomnav').innerHTML = html`${[['', '⌂', 'Home'], ['browse', '⌕', 'Browse'], ['messages', '▤', 'Chats'], ['bookings', '▣', 'Bookings'], [me ? 'account' : 'login', '○', me ? 'Account' : 'Log in']].map(([p, i, l]) => html`<a href="#/${p === 'login' ? '' : p}" data-nav="${p}" ${p === 'login' ? raw('data-action="auth-login"') : ''}><span>${i}</span>${l}</a>`)}`.s;
  markNav(); renderBadges();
}
const markNav = () => { const p = location.hash.replace(/^#\/?/, '').split('/')[0]; $$('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === p)); };

async function route() {
  stopTimers(); if (modalOpen()) closeModal();
  const [pathPart, query = ''] = location.hash.replace(/^#\/?/, '').split('?'); const [path, ...rest] = pathPart.split('/'); const arg = rest.join('/');
  markNav(); window.scrollTo(0, 0);
  try {
    switch (path) {
      case '': await homePage(view); break;
      case 'browse': case 'discover': await discoverPage(view, new URLSearchParams(query)); break;
      case 'faq': faqPage(view); break;
      case 'support': await supportPage(view); break;
      case 'become-a-partner': partnerLandingPage(view); break;
      case 'earnings': await earningsPage(view); break;
      case 'schedule': await schedulePage(view); break;
      case 'verify-id': await kycPage(view); break;
      case 'p': await profilePage(view, arg); break;
      case 'saved': await savedPage(view); break;
      case 'messages': await messagesPage(view, arg); break;
      case 'bookings': await bookingsPage(view); break;
      case 'dashboard': await dashboardPage(view); break;
      case 'account': await accountPage(view); break;
      case 'admin': await adminPage(view); break;
      case 'verify': await verifyPage(view, arg); break;
      case 'reset': resetPage(view, arg); break;
      case 'safety': case 'terms': case 'privacy': case 'standards': case 'refunds': legalPage(view, path); break;
      default: view.innerHTML = html`<div class="page narrow center"><h1>Page not found</h1><a class="btn primary" href="#/">Go home</a></div>`.s;
    }
  } catch (e) { console.error(e); view.innerHTML = html`<div class="page narrow center"><h1>Something went wrong</h1><p class="muted">${e.message}</p><button class="btn primary" data-action="reload">Reload</button></div>`.s; }
  document.title = ({ '': 'PairUp - Meet your kind of company', browse: 'Browse companions · PairUp', faq: 'FAQ · PairUp', refunds: 'Refund policy · PairUp', safety: 'Safety · PairUp', terms: 'Terms · PairUp', privacy: 'Privacy · PairUp' })[path] || 'PairUp';
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

// 18+ gate (the real age check is the date of birth at sign-up)
function gate() {
  if (localStorage.getItem('pairup_18') === '1') return;
  const g = $('#gate'); g.hidden = false; document.body.classList.add('no-scroll');
  $('#gate-yes').onclick = () => { localStorage.setItem('pairup_18', '1'); g.hidden = true; document.body.classList.remove('no-scroll'); };
  $('#gate-no').onclick = () => { location.href = 'https://www.google.com'; };
}

(async () => {
  gate(); renderHeader();
  try { state.meta = await api('/meta'); } catch { state.meta = { activity_suggestions: [], min_rate: 50, max_rate: 50000 }; toast('Couldn\'t reach the server. Some features may not work.', 'error'); }
  await refreshMe();
  startPolling();
  await route();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
})();
