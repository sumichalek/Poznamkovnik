import { apiRequest } from './api.js';
import { dom } from './dom.js';

const MAX_BACKGROUND_BYTES = 12 * 1024 * 1024;
const supportedTypes = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);

function setStatus(message = '', { error = false } = {}) {
  dom.backgroundStatus.textContent = message;
  dom.backgroundStatus.classList.toggle('is-error', error);
}

function setBusy(busy) {
  dom.backgroundUploadButton.disabled = busy;
  dom.backgroundRemoveButton.disabled = busy || !document.body.classList.contains('has-custom-background');
}

export function applyBackgroundPreference(background) {
  const hasBackground = Boolean(background?.hasBackground && background?.version);
  document.body.classList.toggle('has-custom-background', hasBackground);
  if (hasBackground) {
    const version = encodeURIComponent(background.version);
    document.body.style.setProperty('--custom-background-image', `url("/api/preferences/background?v=${version}")`);
    setStatus('Vlastná fotografia je aktívna.');
  } else {
    document.body.style.removeProperty('--custom-background-image');
    setStatus('');
  }
  dom.backgroundRemoveButton.disabled = !hasBackground;
}

export function clearAppliedBackground() {
  document.body.classList.remove('has-custom-background');
  document.body.style.removeProperty('--custom-background-image');
  dom.backgroundRemoveButton.disabled = true;
  setStatus('');
}

export async function loadBackgroundPreference() {
  try {
    const result = await apiRequest('/preferences');
    applyBackgroundPreference(result.background);
  } catch {
    clearAppliedBackground();
  }
}

async function uploadBackground(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch('/api/preferences/background', {
    method: 'POST',
    credentials: 'same-origin',
    body: form
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error || 'Fotografiu sa nepodarilo nahrať.');
  return payload.background;
}

export function initializeBackgroundSettings() {
  dom.backgroundUploadButton.addEventListener('click', () => dom.backgroundFileInput.click());
  dom.backgroundFileInput.addEventListener('change', async () => {
    const [file] = dom.backgroundFileInput.files;
    dom.backgroundFileInput.value = '';
    if (!file) return;
    if (file.type && !supportedTypes.has(file.type)) {
      setStatus('Vyber JPEG, PNG, WebP alebo GIF.', { error: true });
      return;
    }
    if (file.size > MAX_BACKGROUND_BYTES) {
      setStatus('Fotografia môže mať najviac 12 MB.', { error: true });
      return;
    }

    setBusy(true);
    setStatus('Nahrávam fotografiu...');
    try {
      applyBackgroundPreference(await uploadBackground(file));
    } catch (error) {
      setStatus(error.message || 'Fotografiu sa nepodarilo nahrať.', { error: true });
    } finally {
      setBusy(false);
    }
  });
  dom.backgroundRemoveButton.addEventListener('click', async () => {
    if (!document.body.classList.contains('has-custom-background')) return;
    setBusy(true);
    try {
      const result = await apiRequest('/preferences/background', { method: 'DELETE', body: {} });
      applyBackgroundPreference(result.background);
    } catch (error) {
      setStatus(error.message || 'Pozadie sa nepodarilo odstrániť.', { error: true });
    } finally {
      setBusy(false);
    }
  });
}
