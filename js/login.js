import { dom } from './dom.js';

let authenticated = false;

export function isAuthenticated() {
  return authenticated;
}

export function initializeLogin({ onAuthenticated } = {}) {
  dom.loginForm.addEventListener('submit', (event) => {
    event.preventDefault();

    const username = dom.loginUsername.value.trim();
    const password = dom.loginPassword.value;
    if (!username || !password) return;

    authenticated = true;
    dom.brandSubtitle.textContent = username;
    dom.loginPassword.value = '';
    dom.loginScreen.hidden = true;
    dom.appShell.hidden = false;
    dom.appShell.setAttribute('aria-hidden', 'false');
    document.body.dataset.authenticated = 'true';
    onAuthenticated?.();
  });

  requestAnimationFrame(() => dom.loginUsername.focus());
}
