import { apiRequest } from './api.js';
import { dom } from './dom.js';

const BYTES_PER_MEGABYTE = 1024 * 1024;
const MIN_SOURCE_FILE_LIMIT_MB = 1;
const MAX_SOURCE_FILE_LIMIT_MB = 1024;
const defaults = {
  mainPanelTransparency: 20,
  workspacePanelTransparency: 24,
  editorSurfaceTransparency: 12,
  sourceFileMaxBytes: 100 * BYTES_PER_MEGABYTE
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

function sourceFileLimitMb() {
  return Math.round(preferences.sourceFileMaxBytes / BYTES_PER_MEGABYTE);
}

function setStatus(message = '', { error = false } = {}) {
  dom.sourceFileLimitStatus.textContent = message;
  dom.sourceFileLimitStatus.classList.toggle('is-error', error);
}

function applyPanelTransparency() {
  document.documentElement.style.setProperty('--main-panel-opacity', `${100 - preferences.mainPanelTransparency}%`);
  document.documentElement.style.setProperty('--workspace-panel-opacity', `${100 - preferences.workspacePanelTransparency}%`);
  document.documentElement.style.setProperty('--editor-surface-opacity', `${100 - preferences.editorSurfaceTransparency}%`);
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
  dom.sourceFileLimitMb.value = String(sourceFileLimitMb());
}

function applyPreferences(nextPreferences, { syncControls = true } = {}) {
  preferences = {
    mainPanelTransparency: normalizeTransparency(nextPreferences?.mainPanelTransparency, defaults.mainPanelTransparency),
    workspacePanelTransparency: normalizeTransparency(nextPreferences?.workspacePanelTransparency, defaults.workspacePanelTransparency),
    editorSurfaceTransparency: normalizeTransparency(nextPreferences?.editorSurfaceTransparency, defaults.editorSurfaceTransparency),
    sourceFileMaxBytes: normalizeSourceFileMaxBytes(nextPreferences?.sourceFileMaxBytes)
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
  } catch {
    applyPreferences(defaults);
  }
}

export function clearWorkspacePreferences() {
  window.clearTimeout(saveTimer);
  saveTimer = 0;
  preferenceRevision += 1;
  applyPreferences(defaults);
  setStatus('');
}

export function initializeWorkspacePreferences() {
  applyPreferences(defaults);
  dom.mainPanelTransparency.addEventListener('input', updateMainPanelTransparency);
  dom.workspacePanelTransparency.addEventListener('input', updateWorkspacePanelTransparency);
  dom.editorSurfaceTransparency.addEventListener('input', updateEditorSurfaceTransparency);
  dom.sourceFileLimitMb.addEventListener('change', updateSourceFileLimit);
  dom.sourceFileLimitMb.addEventListener('input', () => dom.sourceFileLimitMb.setCustomValidity(''));
}
