// Customer ("Hire") profile: photos + bio, no rates. Required before using the app as a customer.
import { html, api, state, toast, actions, submits, $, refreshMe } from './core.js';

let photos = [];
const MAX_PHOTOS = 6, MAX_BYTES = 5 * 1024 * 1024;

function drawPhotos() {
  const g = $('#ph-grid'); if (!g) return;
  g.innerHTML = html`${photos.map((u, i) => html`<div class="ph-item"><img src="${u}" alt="Your photo ${i + 1}"><button type="button" class="ph-del" data-action="ph-del" data-i="${i}" aria-label="Remove photo ${i + 1}">×</button></div>`)}
    ${photos.length < MAX_PHOTOS ? html`<label class="ph-add"><input type="file" id="ph-file" accept="image/*" multiple hidden><span>＋ Add photo</span></label>` : ''}`.s;
}

export async function setupPage(root) {
  if (!state.me) { root.innerHTML = html`<div class="page narrow center"><h1>Log in to continue</h1><button class="btn primary" data-action="auth-login">Log in</button></div>`.s; return; }
  if (state.me.role === 'partner') { location.hash = '#/dashboard'; return; }
  const c = await api('/me/customer-profile');
  photos = [...c.photos];
  root.innerHTML = html`<div class="page narrow"><h1>Set up your profile</h1>
    <p class="muted">Add photos and a short bio so partners know who you are. No rates needed. Our team reviews your profile before partners can see it, and you can hire companions straight away.</p>
    ${c.status === 'rejected' ? html`<p class="notice err">Your profile needs changes: ${c.reject_reason}</p>` : ''}
    ${c.status === 'pending' ? html`<p class="notice info">Your profile is under review.</p>` : ''}
    <form data-submit="save-cprofile" class="stack">
      <label class="lbl">Photos (1 to ${MAX_PHOTOS}). Clear, recent photos of you.</label>
      <div class="ph-grid" id="ph-grid"></div>
      <label class="lbl" for="c-bio">About you</label>
      <textarea class="field" id="c-bio" name="bio" rows="5" minlength="${c.bio_min}" maxlength="500" required placeholder="What do you enjoy? What kind of company are you looking for?">${c.bio}</textarea>
      <small class="muted"><span id="bio-n">${c.bio.length}</span>/500 · at least ${c.bio_min} characters. No contact details or sexual wording.</small>
      <label class="check"><input type="checkbox" name="discoverable" ${c.discoverable ? 'checked' : ''}> <span>Let approved partners see my first name, age, city, photos and bio, and send me a friendly intro message. I can turn this off any time.</span></label>
      <button class="btn primary block" type="submit">Save profile</button>
    </form></div>`.s;
  drawPhotos();
}

document.addEventListener('change', async e => {
  if (e.target.id !== 'ph-file') return;
  for (const f of [...e.target.files]) {
    if (photos.length >= MAX_PHOTOS) { toast(`You can add up to ${MAX_PHOTOS} photos.`, 'info'); break; }
    if (f.size > MAX_BYTES) { toast(`${f.name} is over 5 MB.`, 'error'); continue; }
    const fd = new FormData(); fd.append('file', f);
    try { const r = await api('/uploads/photo', { method: 'POST', form: fd }); photos.push(r.url); drawPhotos(); }
    catch (err) { toast(err.message, 'error'); }
  }
});
document.addEventListener('input', e => { if (e.target.id === 'c-bio') { const n = $('#bio-n'); if (n) n.textContent = e.target.value.length; } });
actions['ph-del'] = el => { photos.splice(Number(el.dataset.i), 1); drawPhotos(); };

submits['save-cprofile'] = async f => {
  const body = { bio: f.elements.bio.value, photos, discoverable: f.elements.discoverable.checked };
  const r = await api('/me/customer-profile', { method: 'PUT', body });
  toast(r.message, 'ok');
  await refreshMe();
  if (r.complete) location.hash = '#/browse';
};
