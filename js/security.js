import { ApiError, apiRequest } from './api.js';
import { dom } from './dom.js';
import { lockWorkspace } from './login.js';
import { stopMusicPlayback } from './music.js';
import { disableWorkspaceSync, flushWorkspaceSync } from './storage.js';

const ACTIVITY_PING_INTERVAL_MS = 60 * 1000;
const VALID_AUTO_LOCK_MINUTES = new Set([0, 5, 10, 15, 30, 60]);

let autoLockMinutes = 0;
let sessionActive = false;
let locking = false;
let autoLockTimer = 0;
let lastActivityPingAt = 0;
let activityPingInFlight = false;

function normalizedAutoLockMinutes(value) {
  const minutes = Number(value);
  return VALID_AUTO_LOCK_MINUTES.has(minutes) ? minutes : 0;
}

function setLockStatus(message = '', { error = false } = {}) {
  dom.securityLockStatus.textContent = message;
  dom.securityLockStatus.classList.toggle('is-error', error);
}

function setPasswordStatus(message = '', { error = false } = {}) {
  dom.securityPasswordStatus.textContent = message;
  dom.securityPasswordStatus.classList.toggle('is-error', error);
}

function autoLockDescription() {
  if (!autoLockMinutes) return 'Automatické zamknutie je vypnuté.';
  return `Pracovná plocha sa po ${autoLockMinutes} min. nečinnosti zamkne a relácia na serveri skončí.`;
}

function applySecurityPreferences(preferences = {}) {
  autoLockMinutes = normalizedAutoLockMinutes(preferences.autoLockMinutes);
  dom.securityAutoLockMinutes.value = String(autoLockMinutes);
  setLockStatus(autoLockDescription());
}

function clearAutoLockTimer() {
  window.clearTimeout(autoLockTimer);
  autoLockTimer = 0;
}

function scheduleAutoLock() {
  clearAutoLockTimer();
  if (!sessionActive || locking || !autoLockMinutes) return;
  autoLockTimer = window.setTimeout(() => {
    void lockCurrentWorkspace('Pracovná plocha bola automaticky zamknutá po nečinnosti.');
  }, autoLockMinutes * 60 * 1000);
}

async function pingActivity({ force = false } = {}) {
  if (!sessionActive || locking || activityPingInFlight) return;
  const now = Date.now();
  if (!force && now - lastActivityPingAt < ACTIVITY_PING_INTERVAL_MS) return;
  activityPingInFlight = true;
  try {
    await apiRequest('/auth/activity', { method: 'POST', body: {} });
    lastActivityPingAt = Date.now();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      void lockCurrentWorkspace('Relácia pracovnej plochy vypršala.');
    }
  } finally {
    activityPingInFlight = false;
  }
}

function registerActivity() {
  if (!sessionActive || locking) return;
  scheduleAutoLock();
  void pingActivity();
}

async function lockCurrentWorkspace(message) {
  if (locking || !sessionActive) return;
  locking = true;
  sessionActive = false;
  clearAutoLockTimer();
  try {
    await flushWorkspaceSync();
  } finally {
    disableWorkspaceSync();
    stopMusicPlayback();
    if (dom.settingsDialog.open) dom.settingsDialog.close();
    await lockWorkspace(message);
    locking = false;
  }
}

function setPasswordBusy(busy) {
  dom.securityCurrentPassword.disabled = busy;
  dom.securityNewPassword.disabled = busy;
  dom.securityNewPasswordConfirmation.disabled = busy;
  dom.securityPasswordForm.querySelector('button[type="submit"]').disabled = busy;
}

async function saveAutoLockPreference() {
  const requestedMinutes = normalizedAutoLockMinutes(dom.securityAutoLockMinutes.value);
  dom.securityAutoLockMinutes.disabled = true;
  setLockStatus('Ukladám nastavenie...');
  try {
    const preferences = await apiRequest('/auth/security', {
      method: 'POST',
      body: { autoLockMinutes: requestedMinutes }
    });
    applySecurityPreferences(preferences);
    lastActivityPingAt = 0;
    scheduleAutoLock();
    await pingActivity({ force: true });
  } catch (error) {
    setLockStatus(error.message || 'Nastavenie zamknutia sa nepodarilo uložiť.', { error: true });
  } finally {
    dom.securityAutoLockMinutes.disabled = false;
  }
}

async function submitPasswordChange(event) {
  event.preventDefault();
  const currentPassword = dom.securityCurrentPassword.value;
  const newPassword = dom.securityNewPassword.value;
  const newPasswordConfirmation = dom.securityNewPasswordConfirmation.value;
  if (newPassword !== newPasswordConfirmation) {
    setPasswordStatus('Nové heslá sa nezhodujú.', { error: true });
    dom.securityNewPasswordConfirmation.focus();
    return;
  }
  if (newPassword.length < 10) {
    setPasswordStatus('Nové heslo musí mať aspoň 10 znakov.', { error: true });
    dom.securityNewPassword.focus();
    return;
  }

  setPasswordBusy(true);
  setPasswordStatus('Mením heslo...');
  try {
    const result = await apiRequest('/auth/password', {
      method: 'POST',
      body: { currentPassword, newPassword, newPasswordConfirmation }
    });
    dom.securityPasswordForm.reset();
    dom.topbarUsername.textContent = result.user?.username || dom.topbarUsername.textContent;
    setPasswordStatus('Heslo je zmenené. Staršie prihlásenia boli zrušené.');
    lastActivityPingAt = 0;
    await pingActivity({ force: true });
  } catch (error) {
    setPasswordStatus(error.message || 'Heslo sa nepodarilo zmeniť.', { error: true });
    dom.securityCurrentPassword.select();
  } finally {
    setPasswordBusy(false);
  }
}

export async function loadSecuritySettings() {
  try {
    applySecurityPreferences(await apiRequest('/auth/security'));
  } catch (error) {
    applySecurityPreferences();
    setLockStatus(error.message || 'Nastavenie zamknutia sa nepodarilo načítať.', { error: true });
  }
}

export function startSecuritySession() {
  sessionActive = true;
  locking = false;
  lastActivityPingAt = 0;
  scheduleAutoLock();
  void pingActivity({ force: true });
}

export function stopSecuritySession() {
  sessionActive = false;
  clearAutoLockTimer();
  lastActivityPingAt = 0;
}

export function initializeSecurity() {
  dom.securityAutoLockMinutes.addEventListener('change', () => void saveAutoLockPreference());
  dom.securityLockButton.addEventListener('click', () => void lockCurrentWorkspace('Pracovná plocha je zamknutá.'));
  dom.securityPasswordForm.addEventListener('submit', (event) => void submitPasswordChange(event));
  ['pointerdown', 'keydown', 'wheel', 'touchstart', 'focusin'].forEach((eventName) => {
    document.addEventListener(eventName, registerActivity, { passive: eventName !== 'keydown' });
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) registerActivity();
  });
}
