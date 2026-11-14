import { html, raw, api, state, setAuth, clearAuth, refreshMe, openModal, closeModal, toast, actions, submits, formObj, $, confirmBox } from './core.js';

const adultCutoff = () => { const d = new Date(); d.setFullYear(d.getFullYear() - 18); return d.toISOString().slice(0, 10); };

export function openAuth(mode = 'login', heading) {
  if (mode === 'register') return openRegister(heading);
  if (mode === 'forgot') return openForgot();
  openModal(html`
    <span class="badge">18+ MEMBERS ONLY</span>
    <h2>${heading || 'Welcome back'}</h2>
    <form data-submit="login" class="stack">
      <label class="lbl" for="l-email">Email</label>
      <input class="field" id="l-email" name="email" type="email" autocomplete="email" required>
      <label class="lbl" for="l-pw">Password</label>
      <input class="field" id="l-pw" name="password" type="password" autocomplete="current-password" required>
      <button class="btn primary block" type="submit">Log in</button>
    </form>
    <div class="row between small"><button class="link" data-action="auth-forgot">Forgot password?</button><button class="link" data-action="auth-register">Create an account</button></div>
    ${state.meta && state.meta.demo_accounts ? raw(`<p class="notice">Demo accounts: <code>demo@gimble.local</code> (customer), <code>aanya@gimble.local</code> (partner) - password <code>DemoPass123!</code></p>`) : ''}`, { label: 'Log in' });
}

function openRegister(heading) {
  openModal(html`
    <span class="badge">18+ MEMBERS ONLY</span>
    <h2>${heading || 'Create your account'}</h2>
    <form data-submit="register" class="stack">
      <div class="seg" role="radiogroup" aria-label="Account type">
        <label><input type="radio" name="role" value="customer" checked><span>I want to book</span></label>
        <label><input type="radio" name="role" value="partner"><span>I want to be a partner</span></label>
      </div>
      <label class="lbl" for="r-name">Full name</label><input class="field" id="r-name" name="name" required minlength="2" maxlength="80" autocomplete="name">
      <label class="lbl" for="r-email">Email</label><input class="field" id="r-email" name="email" type="email" required autocomplete="email">
      <label class="lbl" for="r-pw">Password</label><input class="field" id="r-pw" name="password" type="password" required minlength="8" autocomplete="new-password" placeholder="8+ characters, letters and numbers">
      <div class="grid2">
        <div><label class="lbl" for="r-dob">Date of birth</label><input class="field" id="r-dob" name="dob" type="date" required max="${adultCutoff()}"></div>
        <div><label class="lbl" for="r-gender">Gender (optional)</label><select class="field" id="r-gender" name="gender"><option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="non-binary">Non-binary</option><option value="other">Other</option></select></div>
      </div>
      <label class="lbl" for="r-city">City</label><input class="field" id="r-city" name="city" required minlength="2" placeholder="e.g. Gurugram" autocomplete="address-level2">
      <label class="check"><input type="checkbox" name="accept_terms" required> <span>I am 18 or older and agree to the <a href="#/terms" data-action="close-modal">Terms</a>, <a href="#/privacy" data-action="close-modal">Privacy Policy</a> and <a href="#/standards" data-action="close-modal">Community Standards</a>. I understand Gimble is for non-sexual, public companionship only.</span></label>
      <button class="btn primary block" type="submit">Create account</button>
    </form>
    <p class="small center"><button class="link" data-action="auth-login">Already have an account? Log in</button></p>`, { label: 'Create account' });
}

function openForgot() {
  openModal(html`<h2>Reset your password</h2><p class="muted">Enter your email and we'll send a reset link.</p>
    <form data-submit="forgot" class="stack"><label class="lbl" for="f-email">Email</label><input class="field" id="f-email" name="email" type="email" required>
    <button class="btn primary block" type="submit">Send reset link</button></form><div id="forgot-out"></div>
    <p class="small center"><button class="link" data-action="auth-login">Back to log in</button></p>`, { label: 'Reset password' });
}

function afterLogin(data) {
  setAuth(data);
  closeModal();
  toast(`Welcome${data.user.name ? ', ' + data.user.name.split(' ')[0] : ''}!`, 'ok');
  const next = state.after; state.after = null;
  refreshMe().then(() => {
    if (next) next();
    else if (data.user.role === 'partner' && !data.__existing) location.hash = '#/dashboard';
    else if (data.user.role === 'admin') location.hash = '#/admin';
  });
}

actions['auth-login'] = () => openAuth('login');
actions['auth-register'] = () => openAuth('register');
actions['auth-forgot'] = () => openAuth('forgot');

submits.login = async f => {
  const data = await api('/auth/login', { method: 'POST', body: formObj(f) });
  data.__existing = true;
  afterLogin(data);
};
submits.register = async f => {
  const b = formObj(f); b.accept_terms = !!b.accept_terms;
  const data = await api('/auth/register', { method: 'POST', body: b });
  afterLogin(data);
  if (data.dev_verify_link) toast('Dev mode: email isn\'t configured - open the verification link from Account.', 'info');
  if (data.dev_verify_link) sessionStorage.setItem('dev_verify_link', data.dev_verify_link);
};
submits.forgot = async f => {
  const r = await api('/auth/forgot-password', { method: 'POST', body: formObj(f) });
  $('#forgot-out').innerHTML = html`<p class="notice ok">${r.message}</p>${r.dev_reset_link ? raw(`<p class="notice">Dev mode (no email server): <a href="${encodeURI(r.dev_reset_link)}" data-action="close-modal">open reset link</a></p>`) : ''}`.s;
};

actions.logout = async () => {
  clearAuth(); closeModal(); toast('Logged out'); location.hash = '#/';
};

// ---------- pages reached from email links ----------
export async function verifyPage(root, token) {
  root.innerHTML = '<div class="page narrow"><p class="muted">Verifying your email…</p></div>';
  try {
    await api('/auth/verify-email', { method: 'POST', body: { token } });
    root.innerHTML = html`<div class="page narrow center"><h1>Email verified ✓</h1><p class="muted">Thanks - your email is confirmed.</p><a class="btn primary" href="#/">Continue to Gimble</a></div>`.s;
    refreshMe();
  } catch (e) {
    root.innerHTML = html`<div class="page narrow center"><h1>Link problem</h1><p class="muted">${e.message}</p><a class="btn primary" href="#/">Back home</a></div>`.s;
  }
}

export function resetPage(root, token) {
  root.innerHTML = html`<div class="page narrow"><h1>Choose a new password</h1><form data-submit="reset" class="stack"><input type="hidden" name="token" value="${token}">
    <label class="lbl" for="np">New password</label><input class="field" id="np" name="password" type="password" minlength="8" required autocomplete="new-password" placeholder="8+ characters, letters and numbers">
    <button class="btn primary block" type="submit">Update password</button></form></div>`.s;
}
submits.reset = async f => {
  await api('/auth/reset-password', { method: 'POST', body: formObj(f) });
  toast('Password updated. Please log in.', 'ok');
  location.hash = '#/'; openAuth('login');
};
