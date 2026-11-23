const button = document.querySelector('#google-auth');
const status = document.querySelector('#google-status');
let firebase;
async function loadFirebase() {
  const base = 'https://www.gstatic.com/firebasejs/11.10.0/';
  const [{initializeApp}, auth] = await Promise.all([import(base + 'firebase-app.js'), import(base + 'firebase-auth.js')]);
  const app = initializeApp(JSON.parse(document.querySelector('#firebase-config').textContent));
  const client = auth.getAuth(app);
  await auth.setPersistence(client, auth.inMemoryPersistence);
  return {auth, client};
}
firebase = loadFirebase().catch(() => null);
button.addEventListener('click', async () => {
  button.disabled = true;
  status.textContent = 'Membuka Google…';
  try {
    const sdk = await firebase;
    if (!sdk) throw Error('Google gagal dimuat. Periksa koneksi dan muat ulang halaman.');
    const result = await sdk.auth.signInWithPopup(sdk.client, new sdk.auth.GoogleAuthProvider());
    const params = new URLSearchParams(location.search);
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const response = await fetch(button.dataset.endpoint, {method:'POST', headers:{'X-CSRFToken':csrf},
      body:new URLSearchParams({token:await result.user.getIdToken(), challenge:document.querySelector('#desktop-code') ? params.get('challenge') || '' : '',
        link:button.dataset.link, next:button.dataset.link ? '/profile/' : params.get('next') || '/'})});
    const data = await response.json();
    if (!response.ok) throw Error(data.error);
    if (data.code) {
      const field = document.querySelector('#desktop-code');
      field.hidden = false;
      field.value = data.code;
      field.select();
      status.textContent = 'Salin kode ke Nongkee desktop dalam 3 menit.';
    } else location.assign(data.url);
  } catch (error) {
    status.textContent = error.code ? 'Login Google belum selesai. Silakan coba lagi.' : error.message;
  } finally { button.disabled = false; }
});
