import { apiRequest } from './api.js';
import { dom } from './dom.js';

const BYTES_PER_MEGABYTE = 1024 * 1024;
const MIN_SOURCE_FILE_LIMIT_MB = 1;
const MAX_SOURCE_FILE_LIMIT_MB = 1024;
const MIN_MUSIC_TRACK_LIMIT_MB = 1;
const MAX_MUSIC_TRACK_LIMIT_MB = 1024;
const MIN_RADIO_RECORDING_LIMIT_MINUTES = 1;
const MAX_RADIO_RECORDING_LIMIT_MINUTES = 720;
const MIN_RADIO_RECORDING_LIMIT_MB = 10;
const MAX_RADIO_RECORDING_LIMIT_MB = 4096;
const defaults = {
  mainPanelTransparency: 20,
  workspacePanelTransparency: 24,
  editorSurfaceTransparency: 12,
  musicPanelTransparency: 12,
  sourceFileMaxBytes: 100 * BYTES_PER_MEGABYTE,
  musicTrackMaxBytes: 250 * BYTES_PER_MEGABYTE,
  radioRecordingMaxSeconds: 120 * 60,
  radioRecordingMaxBytes: 500 * BYTES_PER_MEGABYTE
};

let preferences = { ...defaults };
let saveTimer = 0;
let preferenceRevision = 0;

function normalizeTransparency(value, fallback) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.min(65, Math.max(0, Math.round(numeric)));
}

function normalizeSourceFileMaxBytes(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return defaults.sourceFileMaxBytes;
  const min = MIN_SOURCE_FILE_LIMIT_MB * BYTES_PER_MEGABYTE;
  const max = MAX_SOURCE_FILE_LIMIT_MB * BYTES_PER_MEGABYTE;
  return Math.min(max, Math.max(min, Math.round(numeric)));
}

function normalizeMusicTrackMaxBytes(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return defaults.musicTrackMaxBytes;
  const min = MIN_MUSIC_TRACK_LIMIT_MB * BYTES_PER_MEGABYTE;
  const max = MAX_MUSIC_TRACK_LIMIT_MB * BYTES_PER_MEGABYTE;
  return Math.min(max, Math.max(min, Math.round(numeric)));
}

function normalizeRadioRecordingMaxSeconds(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return defaults.radioRecordingMaxSeconds;
  return Math.min(
    MAX_RADIO_RECORDING_LIMIT_MINUTES * 60,
    Math.max(MIN_RADIO_RECORDING_LIMIT_MINUTES * 60, Math.round(numeric))
  );
}

function normalizeRadioRecordingMaxBytes(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return defaults.radioRecordingMaxBytes;
  const min = MIN_RADIO_RECORDING_LIMIT_MB * BYTES_PER_MEGABYTE;
  const max = MAX_RADIO_RECORDING_LIMIT_MB * BYTES_PER_MEGABYTE;
  return Math.min(max, Math.max(min, Math.round(numeric)));
}

function sourceFileLimitMb() {
  return Math.round(preferences.sourceFileMaxBytes / BYTES_PER_MEGABYTE);
}

function musicTrackLimitMb() {
  return Math.round(preferences.musicTrackMaxBytes / BYTES_PER_MEGABYTE);
}

function radioRecordingLimitMinutes() {
  return Math.round(preferences.radioRecordingMaxSeconds / 60);
}

function radioRecordingLimitMb() {
  return Math.round(preferences.radioRecordingMaxBytes / BYTES_PER_MEGABYTE);
}

function setStatus(message = '', { error = false } = {}) {
  dom.sourceFileLimitStatus.textContent = message;
  dom.sourceFileLimitStatus.classList.toggle('is-error', error);
}

function setMusicStatus(message = '', { error = false } = {}) {
  dom.musicTrackLimitStatus.textContent = message;
  dom.musicTrackLimitStatus.classList.toggle('is-error', error);
}

function setRadioRecordingStatus(message = '', { error = false } = {}) {
  dom.radioRecordingLimitStatus.textContent = message;
  dom.radioRecordingLimitStatus.classList.toggle('is-error', error);
}

function applyPanelTransparency() {
  document.documentElement.style.setProperty('--main-panel-opacity', `${100 - preferences.mainPanelTransparency}%`);
  document.documentElement.style.setProperty('--workspace-panel-opacity', `${100 - preferences.workspacePanelTransparency}%`);
  document.documentElement.style.setProperty('--editor-surface-opacity', `${100 - preferences.editorSurfaceTransparency}%`);
  document.documentElement.style.setProperty('--music-panel-opacity', `${100 - preferences.musicPanelTransparency}%`);
  document.documentElement.style.setProperty(
    '--workspace-surface-opacity',
    `${Math.max(32, 90 - preferences.workspacePanelTransparency)}%`
  );
}

function updateControls() {
  dom.mainPanelTransparency.value = String(preferences.mainPanelTransparency);
  dom.mainPanelTransparencyOutput.value = `${preferences.mainPanelTransparency} %`;
  dom.mainPanelTransparencyOutput.textContent = `${preferences.mainPanelTransparency} %`;
  dom.workspacePanelTransparency.value = String(preferences.workspacePanelTransparency);
  dom.workspacePanelTransparencyOutput.value = `${preferences.workspacePanelTransparency} %`;
  dom.workspacePanelTransparencyOutput.textContent = `${preferences.workspacePanelTransparency} %`;
  dom.editorSurfaceTransparency.value = String(preferences.editorSurfaceTransparency);
  dom.editorSurfaceTransparencyOutput.value = `${preferences.editorSurfaceTransparency} %`;
  dom.editorSurfaceTransparencyOutput.textContent = `${preferences.editorSurfaceTransparency} %`;
  dom.musicPanelTransparency.value = String(preferences.musicPanelTransparency);
  dom.musicPanelTransparencyOutput.value = `${preferences.musicPanelTransparency} %`;
  dom.musicPanelTransparencyOutput.textContent = `${preferences.musicPanelTransparency} %`;
  dom.sourceFileLimitMb.value = String(sourceFileLimitMb());
  dom.musicTrackLimitMb.value = String(musicTrackLimitMb());
  dom.radioRecordingLimitMinutes.value = String(radioRecordingLimitMinutes());
  dom.radioRecordingLimitMb.value = String(radioRecordingLimitMb());
}

function applyPreferences(nextPreferences, { syncControls = true } = {}) {
  preferences = {
    mainPanelTransparency: normalizeTransparency(nextPreferences?.mainPanelTransparency, defaults.mainPanelTransparency),
    workspacePanelTransparency: normalizeTransparency(nextPreferences?.workspacePanelTransparency, defaults.workspacePanelTransparency),
    editorSurfaceTransparency: normalizeTransparency(nextPreferences?.editorSurfaceTransparency, defaults.editorSurfaceTransparency),
    musicPanelTransparency: normalizeTransparency(nextPreferences?.musicPanelTransparency, defaults.musicPanelTransparency),
    sourceFileMaxBytes: normalizeSourceFileMaxBytes(nextPreferences?.sourceFileMaxBytes),
    musicTrackMaxBytes: normalizeMusicTrackMaxBytes(nextPreferences?.musicTrackMaxBytes),
    radioRecordingMaxSeconds: normalizeRadioRecordingMaxSeconds(nextPreferences?.radioRecordingMaxSeconds),
    radioRecordingMaxBytes: normalizeRadioRecordingMaxBytes(nextPreferences?.radioRecordingMaxBytes)
  };
  applyPanelTransparency();
  if (syncControls) updateControls();
}

function scheduleSave() {
  const revision = ++preferenceRevision;
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => void savePreferences(revision), 240);
}

async function savePreferences(revision) {
  const snapshot = { ...preferences };
  try {
    const result = await apiRequest('/preferences', { method: 'POST', body: snapshot });
    if (revision === preferenceRevision) {
      applyPreferences(result);
      setStatus('');
    }
  } catch (error) {
    if (revision === preferenceRevision) setStatus(error.message || 'Nastavenie sa nepodarilo uložiť.', { error: true });
  }
}

function updateMainPanelTransparency() {
  preferences.mainPanelTransparency = normalizeTransparency(
    dom.mainPanelTransparency.value,
    preferences.mainPanelTransparency
  );
  applyPanelTransparency();
  updateControls();
  scheduleSave();
}

function updateWorkspacePanelTransparency() {
  preferences.workspacePanelTransparency = normalizeTransparency(
    dom.workspacePanelTransparency.value,
    preferences.workspacePanelTransparency
  );
  applyPanelTransparency();
  updateControls();
  scheduleSave();
}

function updateEditorSurfaceTransparency() {
  preferences.editorSurfaceTransparency = normalizeTransparency(
    dom.editorSurfaceTransparency.value,
    preferences.editorSurfaceTransparency
  );
  applyPanelTransparency();
  updateControls();
  scheduleSave();
}

function updateMusicPanelTransparency() {
  preferences.musicPanelTransparency = normalizeTransparency(
    dom.musicPanelTransparency.value,
    preferences.musicPanelTransparency
  );
  applyPanelTransparency();
  updateControls();
  scheduleSave();
}

function updateSourceFileLimit() {
  const megabytes = Number(dom.sourceFileLimitMb.value);
  if (!Number.isFinite(megabytes) || megabytes < MIN_SOURCE_FILE_LIMIT_MB || megabytes > MAX_SOURCE_FILE_LIMIT_MB) {
    dom.sourceFileLimitMb.setCustomValidity(`Zadaj hodnotu od ${MIN_SOURCE_FILE_LIMIT_MB} do ${MAX_SOURCE_FILE_LIMIT_MB} MB.`);
    dom.sourceFileLimitMb.reportValidity();
    return;
  }
  dom.sourceFileLimitMb.setCustomValidity('');
  preferences.sourceFileMaxBytes = normalizeSourceFileMaxBytes(megabytes * BYTES_PER_MEGABYTE);
  updateControls();
  setStatus('');
  scheduleSave();
}

function updateMusicTrackLimit() {
  const megabytes = Number(dom.musicTrackLimitMb.value);
  if (!Number.isFinite(megabytes) || megabytes < MIN_MUSIC_TRACK_LIMIT_MB || megabytes > MAX_MUSIC_TRACK_LIMIT_MB) {
    dom.musicTrackLimitMb.setCustomValidity(
      `Zadaj hodnotu od ${MIN_MUSIC_TRACK_LIMIT_MB} do ${MAX_MUSIC_TRACK_LIMIT_MB} MB.`
    );
    dom.musicTrackLimitMb.reportValidity();
    return;
  }
  dom.musicTrackLimitMb.setCustomValidity('');
  preferences.musicTrackMaxBytes = normalizeMusicTrackMaxBytes(megabytes * BYTES_PER_MEGABYTE);
  updateControls();
  setMusicStatus('');
  scheduleSave();
}

function updateRadioRecordingLimit() {
  const minutes = Number(dom.radioRecordingLimitMinutes.value);
  const megabytes = Number(dom.radioRecordingLimitMb.value);
  if (!Number.isFinite(minutes) || minutes < MIN_RADIO_RECORDING_LIMIT_MINUTES || minutes > MAX_RADIO_RECORDING_LIMIT_MINUTES) {
    dom.radioRecordingLimitMinutes.setCustomValidity(
      `Zadaj hodnotu od ${MIN_RADIO_RECORDING_LIMIT_MINUTES} do ${MAX_RADIO_RECORDING_LIMIT_MINUTES} minút.`
    );
    dom.radioRecordingLimitMinutes.reportValidity();
    return;
  }
  if (!Number.isFinite(megabytes) || megabytes < MIN_RADIO_RECORDING_LIMIT_MB || megabytes > MAX_RADIO_RECORDING_LIMIT_MB) {
    dom.radioRecordingLimitMb.setCustomValidity(
      `Zadaj hodnotu od ${MIN_RADIO_RECORDING_LIMIT_MB} do ${MAX_RADIO_RECORDING_LIMIT_MB} MB.`
    );
    dom.radioRecordingLimitMb.reportValidity();
    return;
  }
  dom.radioRecordingLimitMinutes.setCustomValidity('');
  dom.radioRecordingLimitMb.setCustomValidity('');
  preferences.radioRecordingMaxSeconds = normalizeRadioRecordingMaxSeconds(minutes * 60);
  preferences.radioRecordingMaxBytes = normalizeRadioRecordingMaxBytes(megabytes * BYTES_PER_MEGABYTE);
  updateControls();
  setRadioRecordingStatus('');
  scheduleSave();
}

export function getSourceFileMaxBytes() {
  return preferences.sourceFileMaxBytes;
}

export function sourceFileLimitLabel() {
  return `${sourceFileLimitMb()} MB`;
}

export async function loadWorkspacePreferences() {
  try {
    const result = await apiRequest('/preferences');
    applyPreferences(result);
    setStatus('');
    setMusicStatus('');
    setRadioRecordingStatus('');
  } catch {
    applyPreferences(defaults);
    setStatus('');
    setMusicStatus('');
    setRadioRecordingStatus('');
  }
}

export function clearWorkspacePreferences() {
  window.clearTimeout(saveTimer);
  saveTimer = 0;
  preferenceRevision += 1;
  applyPreferences(defaults);
  setStatus('');
  setMusicStatus('');
  setRadioRecordingStatus('');
}

export function initializeWorkspacePreferences() {
  applyPreferences(defaults);
  dom.mainPanelTransparency.addEventListener('input', updateMainPanelTransparency);
  dom.workspacePanelTransparency.addEventListener('input', updateWorkspacePanelTransparency);
  dom.editorSurfaceTransparency.addEventListener('input', updateEditorSurfaceTransparency);
  dom.musicPanelTransparency.addEventListener('input', updateMusicPanelTransparency);
  dom.sourceFileLimitMb.addEventListener('change', updateSourceFileLimit);
  dom.sourceFileLimitMb.addEventListener('input', () => dom.sourceFileLimitMb.setCustomValidity(''));
  dom.musicTrackLimitMb.addEventListener('change', updateMusicTrackLimit);
  dom.musicTrackLimitMb.addEventListener('input', () => dom.musicTrackLimitMb.setCustomValidity(''));
  dom.radioRecordingLimitMinutes.addEventListener('change', updateRadioRecordingLimit);
  dom.radioRecordingLimitMinutes.addEventListener('input', () => dom.radioRecordingLimitMinutes.setCustomValidity(''));
  dom.radioRecordingLimitMb.addEventListener('change', updateRadioRecordingLimit);
  dom.radioRecordingLimitMb.addEventListener('input', () => dom.radioRecordingLimitMb.setCustomValidity(''));
}
