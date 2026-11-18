import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

// Run the real login controller with an isolated DOM/API instead of a browser.
const source = readFileSync(new URL('../js/login.js', import.meta.url), 'utf8')
  .replace(/^import \{ dom \} from '\.\/dom\.js';\n/m, '')
  .replace(/^import \{ apiRequest \} from '\.\/api\.js';\n/m, '')
  .replace(/^export (?=(?:async )?function )/gm, '');
const controller = new vm.Script(`'use strict';\n${source}`, { filename: 'js/login.js' });
const username = 'Fixture user';
const password = 'fixture-password-only';

async function fixture({ existing = false, authenticated = false, onAuthenticated, logoutError } = {}) {
  let hasAccount = existing;
  let session = authenticated;
  let submitHandler;
  const calls = [];
  const user = { id: 'fixture-user', username };
  const element = () => ({
    value: '', textContent: '', disabled: false, hidden: false, focused: false, selected: false,
    attributes: {}, classes: new Set(),
    focus() { this.focused = true; },
    select() { this.selected = true; },
    setAttribute(name, value) { this.attributes[name] = value; },
    get classList() { return { toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name) }; },
  });
  const dom = {
    loginScreen: element(), loginMessage: element(), loginUsername: element(), loginPassword: element(),
    loginSubmit: element(), appShell: element(), topbarUsername: element(),
    loginForm: {
      addEventListener(name, callback) { assert.equal(name, 'submit'); submitHandler = callback; },
      reset() { dom.loginUsername.value = ''; dom.loginPassword.value = ''; },
    },
  };
  const apiRequest = async (path, options = {}) => {
    calls.push({ path, method: options.method || 'GET' });
    if (path === '/auth/status') return { needsSetup: !hasAccount, authenticated: session, user: session ? user : null };
    if (path === '/auth/setup') {
      if (hasAccount) throw new Error('Pracovná plocha už má vytvorený účet.');
      if (options.body.password.length < 10) throw new Error('Heslo musí mať aspoň 10 znakov.');
      hasAccount = true;
      session = true;
    } else if (path === '/auth/login') {
      if (!hasAccount || options.body.username !== username || options.body.password !== password) {
        throw new Error('Nesprávne meno používateľa alebo heslo.');
      }
      session = true;
    } else if (path === '/auth/logout') {
      if (logoutError) throw new Error(logoutError);
      session = false;
      return { authenticated: false };
    } else {
      throw new Error(`Unexpected request: ${path}`);
    }
    return { needsSetup: false, authenticated: true, user };
  };
  const context = vm.createContext({ dom, apiRequest, document: { body: { dataset: {} } }, requestAnimationFrame: callback => callback() });
  controller.runInContext(context);
  context.initializeLogin({ onAuthenticated });
  await new Promise(resolve => setImmediate(resolve));
  return {
    dom, context, calls,
    async submit(value = password) {
      dom.loginUsername.value = username;
      dom.loginPassword.value = value;
      await submitHandler({ preventDefault() {} });
    },
  };
}

test('first account can log out and log in without refreshing the page', async () => {
  const app = await fixture();
  assert.equal(app.dom.loginSubmit.textContent, 'Vytvoriť pracovnú plochu');
  assert.equal(app.dom.loginPassword.minLength, 10);

  await app.submit();
  assert.equal(app.context.isAuthenticated(), true);
  assert.equal(app.dom.loginPassword.value, '');
  await app.context.logout();
  assert.equal(app.context.isAuthenticated(), false);
  assert.equal(app.dom.loginScreen.hidden, false);
  assert.equal(app.dom.appShell.hidden, true);
  assert.equal(app.dom.loginSubmit.textContent, 'Prihlásiť');
  assert.equal(app.dom.loginPassword.minLength, 1);
  assert.equal(app.dom.loginPassword.title, '');

  await app.submit();
  assert.equal(app.context.isAuthenticated(), true);
  assert.equal(app.dom.loginMessage.textContent, '');
  assert.equal(app.dom.loginSubmit.disabled, false);
  assert.deepEqual(app.calls.map(call => call.path), ['/auth/status', '/auth/setup', '/auth/logout', '/auth/login']);
});

test('first account unlocks through login rather than setup and keeps its username', async () => {
  const app = await fixture();
  await app.submit();
  await app.context.lockWorkspace('Pracovná plocha je zamknutá.');
  assert.equal(app.context.isAuthenticated(), false);
  assert.equal(app.dom.loginUsername.value, username);
  assert.equal(app.dom.loginPassword.value, '');
  assert.equal(app.dom.loginPassword.focused, true);
  assert.equal(app.dom.loginMessage.textContent, 'Pracovná plocha je zamknutá.');
  assert.equal(app.dom.loginSubmit.textContent, 'Prihlásiť');
  await app.submit();
  assert.equal(app.context.isAuthenticated(), true);
  assert.equal(app.calls.at(-1).path, '/auth/login');
});

test('failed setup stays in setup mode until an account is actually created', async () => {
  const app = await fixture();
  await app.submit('short');
  assert.equal(app.context.isAuthenticated(), false);
  assert.equal(app.dom.loginSubmit.textContent, 'Vytvoriť pracovnú plochu');
  assert.equal(app.dom.loginPassword.minLength, 10);
  assert.equal(app.dom.loginMessage.textContent, 'Heslo musí mať aspoň 10 znakov.');
  assert.equal(app.dom.loginSubmit.disabled, false);
  await app.submit();
  await app.context.logout();
  await app.submit();
  assert.equal(app.context.isAuthenticated(), true);
  assert.deepEqual(app.calls.map(call => call.path), ['/auth/status', '/auth/setup', '/auth/setup', '/auth/logout', '/auth/login']);
});

test('wrong password after first logout remains a login error and permits retry', async () => {
  const app = await fixture();
  await app.submit();
  await app.context.logout();
  await app.submit('wrong-password');
  assert.equal(app.context.isAuthenticated(), false);
  assert.equal(app.calls.at(-1).path, '/auth/login');
  assert.equal(app.dom.loginMessage.textContent, 'Nesprávne meno používateľa alebo heslo.');
  assert.equal(app.dom.loginPassword.selected, true);
  assert.equal(app.dom.loginSubmit.disabled, false);
  await app.submit();
  assert.equal(app.context.isAuthenticated(), true);
});

test('an existing account continues to use login across repeated logouts', async () => {
  const app = await fixture({ existing: true });
  assert.equal(app.dom.loginSubmit.textContent, 'Prihlásiť');
  await app.submit();
  await app.context.logout();
  await app.submit();
  assert.equal(app.context.isAuthenticated(), true);
  assert.equal(app.calls.some(call => call.path === '/auth/setup'), false);
});

test('an authenticated session retains login mode when subsequently logged out', async () => {
  let activations = 0;
  const app = await fixture({ existing: true, authenticated: true, onAuthenticated() { activations += 1; } });
  assert.equal(app.context.isAuthenticated(), true);
  assert.equal(activations, 1);
  await app.context.logout();
  assert.equal(app.dom.loginSubmit.textContent, 'Prihlásiť');
  await app.submit();
  assert.equal(activations, 2);
  assert.equal(app.calls.at(-1).path, '/auth/login');
});

test('a workspace loading error after successful setup cannot revert to account creation', async () => {
  const app = await fixture({ onAuthenticated() { throw new Error('Fixture workspace loading failure'); } });
  await app.submit();
  await app.context.logout();
  assert.equal(app.dom.loginSubmit.textContent, 'Prihlásiť');
  await app.submit();
  assert.equal(app.calls.at(-1).path, '/auth/login');
  assert.equal(app.calls.filter(call => call.path === '/auth/setup').length, 1);
});

test('local logout after an API failure preserves the existing-account login mode', async () => {
  const app = await fixture({ logoutError: 'Fixture network error' });
  await app.submit();
  await assert.rejects(app.context.logout(), /Fixture network error/);
  assert.equal(app.context.isAuthenticated(), false);
  assert.equal(app.dom.loginScreen.hidden, false);
  assert.equal(app.dom.loginSubmit.textContent, 'Prihlásiť');
  await app.submit();
  assert.equal(app.calls.at(-1).path, '/auth/login');
});
