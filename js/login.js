import { dom } from './dom.js';
import { apiRequest } from './api.js';

let authenticated = false;
let needsSetup = false;

export function isAuthenticated() {
  return authenticated;
}

function setMessage(message = '', { error = false } = {}) {
  dom.loginMessage.textContent = message;
  dom.loginMessage.classList.toggle('is-error', error);
}

function updateLoginMode() {
  dom.loginSubmit.textContent = needsSetup ? 'Vytvoriť pracovnú plochu' : 'Prihlásiť';
  dom.loginPassword.minLength = needsSetup ? 10 : 1;
  dom.loginPassword.title = needsSetup ? 'Heslo musí mať aspoň 10 znakov.' : '';
  setMessage(needsSetup ? 'Vytvor prvé konto pre túto pracovnú plochu.' : '');
}

async function activate(user, onAuthenticated) {
  authenticated = true;
  dom.brandSubtitle.textContent = user.username;
  dom.loginPassword.value = '';
  dom.loginScreen.hidden = true;
  dom.appShell.hidden = false;
  dom.appShell.setAttribute('aria-hidden', 'false');
  document.body.dataset.authenticated = 'true';
  await onAuthenticated?.(user);
}

export async function logout() {
  try {
    await apiRequest('/auth/logout', { method: 'POST', body: {} });
  } finally {
    authenticated = false;
    delete document.body.dataset.authenticated;
    dom.appShell.hidden = true;
    dom.appShell.setAttribute('aria-hidden', 'true');
    dom.loginForm.reset();
    dom.loginScreen.hidden = false;
    setMessage('');
    requestAnimationFrame(() => dom.loginUsername.focus());
  }
}

export function initializeLogin({ onAuthenticated } = {}) {
  dom.loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const username = dom.loginUsername.value.trim();
    const password = dom.loginPassword.value;
    if (!username || !password) return;

    dom.loginSubmit.disabled = true;
    setMessage('Overujem údaje...');
    try {
      const result = await apiRequest(needsSetup ? '/auth/setup' : '/auth/login', {
        method: 'POST',
        body: { username, password }
      });
      await activate(result.user, onAuthenticated);
    } catch (error) {
      setMessage(error.message || 'Prihlásenie sa nepodarilo.', { error: true });
      dom.loginPassword.select();
    } finally {
      dom.loginSubmit.disabled = false;
    }
  });

  void apiRequest('/auth/status')
    .then(async (status) => {
      needsSetup = status.needsSetup;
      updateLoginMode();
      if (status.authenticated && status.user) await activate(status.user, onAuthenticated);
      else requestAnimationFrame(() => dom.loginUsername.focus());
    })
    .catch(() => {
      needsSetup = false;
      updateLoginMode();
      setMessage('Server nie je dostupný. Spusť Poznámkovník cez server.py.', { error: true });
    });
}
