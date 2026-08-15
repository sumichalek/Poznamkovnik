import { apiRequest, uploadBackupArchive } from './api.js';
import { createAppIcon } from './app-icons.js';
import { dom } from './dom.js';
import { disableWorkspaceSync, flushWorkspaceSync } from './storage.js';

const safetyBackupStorageKey = 'poznamkovnik-last-restore-safety';
let isRestoring = false;
let isBusy = false;

function setStatus(message = '', isError = false) {
  dom.backupStatus.textContent = message;
  dom.backupStatus.classList.toggle('is-error', isError);
}

function setAutomaticStatus(message = '', isError = false) {
  dom.backupAutomaticStatus.textContent = message;
  dom.backupAutomaticStatus.classList.toggle('is-error', isError);
}

function setBusy(nextBusy) {
  isBusy = nextBusy;
  dom.backupDownloadButton.disabled = nextBusy;
  dom.backupRestoreButton.disabled = nextBusy;
  dom.backupAutomaticEnabled.disabled = nextBusy;
  dom.backupIntervalHours.disabled = nextBusy || !dom.backupAutomaticEnabled.checked;
  dom.backupRetentionCount.disabled = nextBusy;
  dom.backupSnapshotList.querySelectorAll('button').forEach((button) => {
    button.disabled = nextBusy;
  });
}

function validSafetyBackup(value) {
  return (
    value &&
    typeof value === 'object' &&
    /^[a-f0-9]{32}$/i.test(value.id || '') &&
    typeof value.filename === 'string' &&
    typeof value.createdAt === 'string'
  );
}

function showSafetyBackup(value) {
  if (!validSafetyBackup(value)) return false;
  dom.backupSafetyDownload.href = `/api/backups/snapshots/${encodeURIComponent(value.id)}`;
  dom.backupSafetyDownload.download = value.filename;
  dom.backupSafetyDownload.hidden = false;
  return true;
}

function restoreRememberedSafetyBackup() {
  try {
    const remembered = JSON.parse(sessionStorage.getItem(safetyBackupStorageKey) || 'null');
    if (showSafetyBackup(remembered)) {
      setStatus('Po poslednej obnove je k dispozícii ochranná kópia pôvodných údajov.');
    }
  } catch {
    sessionStorage.removeItem(safetyBackupStorageKey);
  }
}

function triggerDownload(path) {
  const link = document.createElement('a');
  link.href = path;
  link.download = '';
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Neznámy čas';
  return new Intl.DateTimeFormat('sk-SK', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function formatSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 1024) return `${Math.max(0, Number(bytes) || 0)} B`;
  const units = ['KB', 'MB', 'GB'];
  let amount = bytes / 1024;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(amount >= 10 ? 0 : 1)} ${units[unit]}`;
}

function iconButton(icon, title, action, snapshotId) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `icon-button backup-snapshot-action${action === 'delete' ? ' danger' : ''}`;
  button.title = title;
  button.setAttribute('aria-label', title);
  button.dataset.backupAction = action;
  button.dataset.snapshotId = snapshotId;
  button.append(createAppIcon(icon));
  return button;
}

function renderSnapshots(snapshots) {
  dom.backupSnapshotList.replaceChildren();
  if (!Array.isArray(snapshots) || snapshots.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'backup-snapshot-empty';
    empty.textContent = 'Zatiaľ tu nie je automatická kópia.';
    dom.backupSnapshotList.append(empty);
    return;
  }
  snapshots.forEach((snapshot) => {
    if (!/^[a-f0-9]{32}$/i.test(snapshot?.id || '')) return;
    const row = document.createElement('div');
    row.className = 'backup-snapshot-row';
    const copy = document.createElement('div');
    copy.className = 'backup-snapshot-copy';
    const date = document.createElement('strong');
    date.textContent = formatDate(snapshot.createdAt);
    const details = document.createElement('span');
    details.textContent = formatSize(Number(snapshot.sizeBytes));
    copy.append(date, details);
    const actions = document.createElement('div');
    actions.className = 'backup-snapshot-actions';
    actions.append(
      iconButton('download', 'Stiahnuť kópiu', 'download', snapshot.id),
      iconButton('rotate-ccw', 'Obnoviť túto kópiu', 'restore', snapshot.id),
      iconButton('trash', 'Odstrániť kópiu', 'delete', snapshot.id)
    );
    row.append(copy, actions);
    dom.backupSnapshotList.append(row);
  });
}

function describeAutomaticStatus(settings) {
  if (!settings.enabled) return 'Automatické zálohovanie je vypnuté.';
  if (settings.lastError) return `Posledný pokus zlyhal: ${settings.lastError}`;
  if (settings.lastBackupAt) return `Posledná automatická kópia: ${formatDate(settings.lastBackupAt)}.`;
  return 'Prvá automatická kópia sa pripraví pri najbližšej kontrole servera.';
}

function applyAutomaticOverview(overview) {
  const settings = overview?.settings || {};
  dom.backupAutomaticEnabled.checked = settings.enabled !== false;
  dom.backupIntervalHours.value = String(settings.intervalHours || 24);
  dom.backupRetentionCount.value = String(settings.retentionCount || 14);
  setAutomaticStatus(describeAutomaticStatus(settings), Boolean(settings.lastError));
  renderSnapshots(overview?.snapshots || []);
  setBusy(isBusy);
}

export async function loadBackupOverview() {
  try {
    const overview = await apiRequest('/backups');
    applyAutomaticOverview(overview);
    return overview;
  } catch (error) {
    setAutomaticStatus(error.message || 'Stav automatických záloh sa nepodarilo načítať.', true);
    return null;
  }
}

async function downloadBackup() {
  setBusy(true);
  setStatus('Ukladám otvorenú prácu do zálohy...');
  try {
    await flushWorkspaceSync();
    triggerDownload('/api/backups/export');
    setStatus('Záloha sa pripravuje na stiahnutie.');
  } catch (error) {
    setStatus(error.message || 'Zálohu sa nepodarilo pripraviť.', true);
  } finally {
    setBusy(false);
  }
}

function finishRestore(result) {
  const safetyBackup = result?.safetyBackup;
  if (showSafetyBackup(safetyBackup)) {
    sessionStorage.setItem(safetyBackupStorageKey, JSON.stringify(safetyBackup));
  }
  disableWorkspaceSync();
  setStatus('Obnova je hotová. Načítavam obnovené údaje...');
  window.setTimeout(() => window.location.reload(), 700);
}

async function restoreSelectedBackup() {
  const [file] = dom.backupRestoreInput.files;
  dom.backupRestoreInput.value = '';
  if (!file || isRestoring) return;
  if (!window.confirm('Obnova nahradí aktuálne údaje v účte. Predtým vznikne ochranná kópia. Pokračovať?')) return;

  isRestoring = true;
  setBusy(true);
  setStatus('Kontrolujem a obnovujem zálohu...');
  try {
    await flushWorkspaceSync();
    finishRestore(await uploadBackupArchive(file));
  } catch (error) {
    isRestoring = false;
    setBusy(false);
    setStatus(error.message || 'Zálohu sa nepodarilo obnoviť.', true);
  }
}

async function saveAutomaticSettings() {
  const retentionCount = Number(dom.backupRetentionCount.value);
  if (!Number.isInteger(retentionCount) || retentionCount < 3 || retentionCount > 50) {
    setAutomaticStatus('Počet kópií musí byť celé číslo od 3 do 50.', true);
    return;
  }
  setBusy(true);
  try {
    await apiRequest('/backups/settings', {
      method: 'POST',
      body: {
        enabled: dom.backupAutomaticEnabled.checked,
        intervalHours: Number(dom.backupIntervalHours.value),
        retentionCount
      }
    });
    await loadBackupOverview();
  } catch (error) {
    setAutomaticStatus(error.message || 'Nastavenia automatických záloh sa nepodarilo uložiť.', true);
    await loadBackupOverview();
  } finally {
    setBusy(false);
  }
}

async function handleSnapshotAction(event) {
  const button = event.target.closest('button[data-backup-action]');
  if (!button || isBusy || isRestoring) return;
  const snapshotId = button.dataset.snapshotId || '';
  const action = button.dataset.backupAction;
  if (!/^[a-f0-9]{32}$/i.test(snapshotId)) return;
  if (action === 'download') {
    triggerDownload(`/api/backups/snapshots/automatic/${encodeURIComponent(snapshotId)}`);
    return;
  }
  if (action === 'delete') {
    if (!window.confirm('Odstrániť túto automatickú kópiu?')) return;
    setBusy(true);
    try {
      await apiRequest(`/backups/snapshots/automatic/${encodeURIComponent(snapshotId)}`, { method: 'DELETE' });
      await loadBackupOverview();
    } catch (error) {
      setAutomaticStatus(error.message || 'Kópiu sa nepodarilo odstrániť.', true);
    } finally {
      setBusy(false);
    }
    return;
  }
  if (action !== 'restore') return;
  if (!window.confirm('Obnova nahradí aktuálne údaje v účte. Predtým vznikne ochranná kópia. Pokračovať?')) return;
  isRestoring = true;
  setBusy(true);
  setStatus('Obnovujem vybranú automatickú kópiu...');
  try {
    await flushWorkspaceSync();
    finishRestore(await apiRequest(`/backups/snapshots/automatic/${encodeURIComponent(snapshotId)}/restore`, { method: 'POST' }));
  } catch (error) {
    isRestoring = false;
    setBusy(false);
    setStatus(error.message || 'Automatickú kópiu sa nepodarilo obnoviť.', true);
  }
}

export function initializeBackups() {
  dom.backupDownloadButton.addEventListener('click', () => void downloadBackup());
  dom.backupRestoreButton.addEventListener('click', () => dom.backupRestoreInput.click());
  dom.backupRestoreInput.addEventListener('change', () => void restoreSelectedBackup());
  dom.backupAutomaticEnabled.addEventListener('change', () => void saveAutomaticSettings());
  dom.backupIntervalHours.addEventListener('change', () => void saveAutomaticSettings());
  dom.backupRetentionCount.addEventListener('change', () => void saveAutomaticSettings());
  dom.backupSnapshotList.addEventListener('click', (event) => void handleSnapshotAction(event));
  restoreRememberedSafetyBackup();
}
