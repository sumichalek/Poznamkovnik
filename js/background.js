import { apiRequest } from './api.js';
import { dom } from './dom.js';

const MAX_BACKGROUND_BYTES = 12 * 1024 * 1024;
const supportedTypes = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);
const backgroundPresets = new Map([
  ['misty-forest', { label: 'Hmlistý les', image: 'assets/backgrounds/misty-forest.jpg' }],
  ['forest-lake', { label: 'Tiché jazero', image: 'assets/backgrounds/forest-lake.jpg' }],
  ['calm-ocean', { label: 'Pokojné more', image: 'assets/backgrounds/calm-ocean.jpg' }],
  ['foggy-mountain', { label: 'Horská hmla', image: 'assets/backgrounds/foggy-mountain.jpg' }]
]);

function setStatus(message = '', { error = false } = {}) {
  dom.backgroundStatus.textContent = message;
  dom.backgroundStatus.classList.toggle('is-error', error);
}

function setBusy(busy) {
  dom.backgroundUploadButton.disabled = busy;
  dom.backgroundRemoveButton.disabled = busy || !document.body.classList.contains('has-workspace-background');
  dom.backgroundPresetButtons.forEach((button) => {
    button.disabled = busy;
  });
}

function setActivePreset(presetId = '') {
  dom.backgroundPresetButtons.forEach((button) => {
    const isActive = button.dataset.backgroundPreset === presetId;
    button.classList.toggle('is-active', isActive);
    button.setAttribute('aria-pressed', String(isActive));
  });
}

export function applyBackgroundPreference(background) {
  const preset = background?.kind === 'preset' ? backgroundPresets.get(background.preset) : null;
  const hasCustomBackground = Boolean(background?.kind === 'custom' && background?.hasBackground && background?.version);
  const hasBackground = hasCustomBackground || Boolean(preset);

  document.body.classList.toggle('has-workspace-background', hasBackground);
  if (hasCustomBackground) {
    const version = encodeURIComponent(background.version);
    document.body.style.setProperty('--workspace-background-image', `url("/api/preferences/background?v=${version}")`);
    setStatus('Vlastná fotografia je aktívna.');
  } else if (preset) {
    document.body.style.setProperty('--workspace-background-image', `url("${preset.image}")`);
    setStatus(`Aktívne: ${preset.label}.`);
  } else {
    document.body.style.removeProperty('--workspace-background-image');
    setStatus('');
  }
  setActivePreset(preset ? background.preset : '');
  dom.backgroundRemoveButton.disabled = !hasBackground;
}

export function clearAppliedBackground() {
  document.body.classList.remove('has-workspace-background');
  document.body.style.removeProperty('--workspace-background-image');
  dom.backgroundRemoveButton.disabled = true;
  setActivePreset();
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

async function applyPreset(presetId) {
  const preset = backgroundPresets.get(presetId);
  if (!preset) return;

  setBusy(true);
  setStatus(`Nastavujem: ${preset.label}.`);
  try {
    const result = await apiRequest('/preferences/background/preset', {
      method: 'POST',
      body: { presetId }
    });
    applyBackgroundPreference(result.background);
  } catch (error) {
    setStatus(error.message || 'Pozadie sa nepodarilo nastaviť.', { error: true });
  } finally {
    setBusy(false);
  }
}

export function initializeBackgroundSettings() {
  dom.backgroundPresetButtons.forEach((button) => {
    button.addEventListener('click', () => applyPreset(button.dataset.backgroundPreset));
  });
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
    if (!document.body.classList.contains('has-workspace-background')) return;
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
