import { apiRequest, downloadBackupArchive, previewBackupArchive, uploadBackupArchive } from './api.js';
import { createAppIcon } from './app-icons.js';
import { decryptBackupArchive, encryptedBackupSupported, encryptBackupArchive, isEncryptedBackup } from './backup-crypto.js';
import { installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';
import { disableWorkspaceSync, flushWorkspaceSync } from './storage.js';

const safetyBackupStorageKey = 'poznamkovnik-last-restore-safety';
let isRestoring = false;
let isBusy = false;
let passwordDialogMode = '';
let pendingEncryptedRestoreFile = null;
let pendingRestore = null;

function setStatus(message = '', isError = false) {
  dom.backupStatus.textContent = message;
  dom.backupStatus.classList.toggle('is-error', isError);
}

function setAutomaticStatus(message = '', isError = false) {
  dom.backupAutomaticStatus.textContent = message;
  dom.backupAutomaticStatus.classList.toggle('is-error', isError);
}

function setPasswordStatus(message = '', isError = false) {
  dom.backupPasswordStatus.textContent = message;
  dom.backupPasswordStatus.classList.toggle('is-error', isError);
}

function setStorageStatus(message = '', isError = false) {
  dom.backupStorageStatus.textContent = message;
  dom.backupStorageStatus.classList.toggle('is-error', isError);
}

function setPreviewStatus(message = '', isError = false) {
  dom.backupPreviewStatus.textContent = message;
  dom.backupPreviewStatus.classList.toggle('is-error', isError);
}

function setBusy(nextBusy) {
  isBusy = nextBusy;
  dom.backupDownloadButton.disabled = nextBusy;
  dom.backupEncryptedDownloadButton.disabled = nextBusy;
  dom.backupRestoreButton.disabled = nextBusy;
  dom.backupAutomaticEnabled.disabled = nextBusy;
  dom.backupIntervalHours.disabled = nextBusy || !dom.backupAutomaticEnabled.checked;
  dom.backupRetentionCount.disabled = nextBusy;
  dom.backupSnapshotList.querySelectorAll('button').forEach((button) => {
    button.disabled = nextBusy;
  });
  dom.backupPasswordSubmit.disabled = nextBusy;
  dom.backupPreviewRestore.disabled = nextBusy;
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

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
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

function formatVerification(verification) {
  if (verification?.status === 'verified') return `Overená ${formatDate(verification.verifiedAt)}`;
  if (verification?.status === 'error') return 'Kontrola zlyhala';
  return 'Ešte neoverená';
}

function describeStorage(storage) {
  if (!storage || !Number.isFinite(Number(storage.freeBytes))) return '';
  const copies = Number(storage.snapshotCount) || 0;
  const used = formatSize(Number(storage.usedBytes));
  const free = formatSize(Number(storage.freeBytes));
  return `Automatické kópie: ${copies} · ${used}. Voľné miesto na disku: ${free}.`;
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
    details.textContent = `${formatSize(Number(snapshot.sizeBytes))} · ${formatVerification(snapshot.verification)}`;
    copy.append(date, details);
    const actions = document.createElement('div');
    actions.className = 'backup-snapshot-actions';
    actions.append(
      iconButton('download', 'Stiahnuť kópiu', 'download', snapshot.id),
      iconButton('shield', snapshot.verification?.status === 'verified' ? 'Overiť znova' : 'Overiť kópiu', 'verify', snapshot.id),
      iconButton('rotate-ccw', 'Skontrolovať a obnoviť túto kópiu', 'restore', snapshot.id),
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
  setStorageStatus(describeStorage(overview?.storage), Boolean(overview?.storage?.lowSpace));
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

async function downloadEncryptedBackup(password) {
  setBusy(true);
  setStatus('Ukladám otvorenú prácu do šifrovanej zálohy...');
  try {
    await flushWorkspaceSync();
    setStatus('Sťahujem a šifrujem zálohu v tomto prehliadači...');
    const archive = await downloadBackupArchive();
    const encrypted = await encryptBackupArchive(archive.blob, password, archive.filename);
    triggerBlobDownload(encrypted.blob, encrypted.filename);
    setStatus('Šifrovaná záloha sa stiahla. Heslo nebolo uložené.');
  } catch (error) {
    setStatus(error.message || 'Šifrovanú zálohu sa nepodarilo pripraviť.', true);
  } finally {
    setBusy(false);
  }
}

function resetPasswordDialog() {
  passwordDialogMode = '';
  pendingEncryptedRestoreFile = null;
  dom.backupPasswordForm.reset();
  dom.backupPasswordConfirmationField.hidden = false;
  dom.backupPasswordConfirmation.required = true;
  setPasswordStatus();
}

function closePasswordDialog() {
  if (dom.backupPasswordDialog.open) dom.backupPasswordDialog.close();
  else resetPasswordDialog();
}

function resetRestorePreview() {
  pendingRestore = null;
  dom.backupPreviewSummary.replaceChildren();
  setPreviewStatus();
}

function closeRestorePreview() {
  if (dom.backupPreviewDialog.open) dom.backupPreviewDialog.close();
  else resetRestorePreview();
}

function renderRestorePreview(preview) {
  const backup = preview?.backup || {};
  const current = preview?.current || {};
  const rows = [
    ['Knižnice', 'libraries'],
    ['Priečinky', 'folders'],
    ['Poznámky', 'notes'],
    ['Články', 'articles'],
    ['Zdroje', 'sources'],
    ['Súbory', 'files'],
    ['Skladby', 'musicTracks'],
    ['Úlohy', 'tasks'],
    ['Udalosti', 'calendarEvents'],
    ['Strany učebnice', 'tutorialPages'],
  ];
  dom.backupPreviewSummary.replaceChildren();
  rows.forEach(([label, key]) => {
    const row = document.createElement('tr');
    const title = document.createElement('th');
    title.scope = 'row';
    title.textContent = label;
    const backedUp = document.createElement('td');
    backedUp.textContent = String(Number(backup[key]) || 0);
    const existing = document.createElement('td');
    existing.textContent = String(Number(current[key]) || 0);
    row.append(title, backedUp, existing);
    dom.backupPreviewSummary.append(row);
  });
}

function openRestorePreview(preview, nextRestore) {
  if (!preview?.backup || !preview?.current) {
    setStatus('Náhľad zálohy neobsahuje očakávané údaje.', true);
    return;
  }
  pendingRestore = nextRestore;
  renderRestorePreview(preview);
  dom.backupPreviewDescription.textContent = 'Záloha prešla kontrolou integrity. Po obnove vznikne ochranná kópia dnešných údajov.';
  setPreviewStatus();
  if (!dom.backupPreviewDialog.open) dom.backupPreviewDialog.showModal();
}

function openPasswordDialog(mode, file = null) {
  if (!encryptedBackupSupported()) {
    setStatus('Tento prehliadač nepodporuje bezpečné šifrovanie záloh.', true);
    return;
  }
  passwordDialogMode = mode;
  pendingEncryptedRestoreFile = file;
  dom.backupPasswordForm.reset();
  const restoring = mode === 'restore';
  dom.backupPasswordTitle.textContent = restoring ? 'Odomknúť šifrovanú zálohu' : 'Stiahnuť šifrovanú zálohu';
  dom.backupPasswordDescription.textContent = restoring
    ? 'Heslo sa použije iba na odomknutie vybraného súboru a nikdy sa neposiela na server.'
    : 'Heslo zostane iba v tomto prehliadači a nebude uložené na serveri.';
  dom.backupPasswordSubmit.textContent = restoring ? 'Odomknúť a obnoviť' : 'Šifrovať a stiahnuť';
  dom.backupPasswordConfirmationField.hidden = restoring;
  dom.backupPasswordConfirmation.required = !restoring;
  dom.backupPassword.autocomplete = 'new-password';
  setPasswordStatus();
  if (!dom.backupPasswordDialog.open) dom.backupPasswordDialog.showModal();
  window.setTimeout(() => dom.backupPassword.focus(), 0);
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

async function restoreBackupFile(file) {
  if (!file || isRestoring) return false;
  isRestoring = true;
  setBusy(true);
  setStatus('Kontrolujem a obnovujem zálohu...');
  try {
    await flushWorkspaceSync();
    finishRestore(await uploadBackupArchive(file));
    return true;
  } catch (error) {
    isRestoring = false;
    setBusy(false);
    setStatus(error.message || 'Zálohu sa nepodarilo obnoviť.', true);
    return false;
  }
}

async function restoreSelectedBackup() {
  const [file] = dom.backupRestoreInput.files;
  dom.backupRestoreInput.value = '';
  if (!file || isRestoring) return;
  try {
    if (await isEncryptedBackup(file)) {
      openPasswordDialog('restore', file);
      return;
    }
    await prepareRestoreFile(file);
  } catch (error) {
    setStatus(error.message || 'Zálohu sa nepodarilo prečítať.', true);
  }
}

async function submitPasswordDialog(event) {
  event.preventDefault();
  const mode = passwordDialogMode;
  let password = dom.backupPassword.value;
  if (password.length < 10) {
    setPasswordStatus('Heslo pre šifrovanú zálohu musí mať aspoň 10 znakov.', true);
    return;
  }
  if (mode === 'export' && password !== dom.backupPasswordConfirmation.value) {
    setPasswordStatus('Heslá sa nezhodujú.', true);
    return;
  }
  if (mode === 'export') {
    closePasswordDialog();
    try {
      await downloadEncryptedBackup(password);
    } finally {
      password = '';
    }
    return;
  }
  if (mode !== 'restore' || !pendingEncryptedRestoreFile) {
    closePasswordDialog();
    return;
  }

  setBusy(true);
  setPasswordStatus('Overujem heslo a odomykám zálohu...');
  let archive;
  try {
    archive = await decryptBackupArchive(pendingEncryptedRestoreFile, password);
  } catch (error) {
    setPasswordStatus(error.message || 'Zálohu sa nepodarilo odomknúť.', true);
    return;
  } finally {
    password = '';
    setBusy(false);
  }
  closePasswordDialog();
  await prepareRestoreFile(archive);
}

async function prepareRestoreFile(file) {
  setBusy(true);
  setStatus('Kontrolujem zálohu pred obnovením...');
  try {
    const preview = await previewBackupArchive(file);
    openRestorePreview(preview, { type: 'file', file });
    setStatus('Záloha je overená. Pred obnovením si skontroluj jej obsah.');
  } catch (error) {
    setStatus(error.message || 'Zálohu sa nepodarilo overiť.', true);
  } finally {
    setBusy(false);
  }
}

async function prepareAutomaticRestore(snapshotId) {
  setBusy(true);
  setAutomaticStatus('Kontrolujem automatickú kópiu pred obnovením...');
  try {
    const preview = await apiRequest(`/backups/snapshots/automatic/${encodeURIComponent(snapshotId)}/preview`, { method: 'POST' });
    openRestorePreview(preview, { type: 'automatic', snapshotId });
    setAutomaticStatus('Automatická kópia je overená. Pred obnovením si skontroluj jej obsah.');
  } catch (error) {
    setAutomaticStatus(error.message || 'Automatickú kópiu sa nepodarilo overiť.', true);
  } finally {
    setBusy(false);
  }
}

async function restoreAutomaticSnapshot(snapshotId) {
  isRestoring = true;
  setBusy(true);
  setStatus('Obnovujem vybranú automatickú kópiu...');
  try {
    await flushWorkspaceSync();
    finishRestore(await apiRequest(`/backups/snapshots/automatic/${encodeURIComponent(snapshotId)}/restore`, { method: 'POST' }));
    return true;
  } catch (error) {
    isRestoring = false;
    setBusy(false);
    setStatus(error.message || 'Automatickú kópiu sa nepodarilo obnoviť.', true);
    return false;
  }
}

async function confirmRestorePreview() {
  const restore = pendingRestore;
  if (!restore || isRestoring) return;
  closeRestorePreview();
  if (restore.type === 'file') {
    await restoreBackupFile(restore.file);
    return;
  }
  if (restore.type === 'automatic') await restoreAutomaticSnapshot(restore.snapshotId);
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
  if (action === 'verify') {
    setBusy(true);
    setAutomaticStatus('Overujem automatickú kópiu...');
    try {
      const result = await apiRequest(`/backups/snapshots/automatic/${encodeURIComponent(snapshotId)}/verify`, { method: 'POST' });
      await loadBackupOverview();
      setAutomaticStatus(`Kópia je overená: ${formatVerification(result)}.`);
    } catch (error) {
      setAutomaticStatus(error.message || 'Automatickú kópiu sa nepodarilo overiť.', true);
    } finally {
      setBusy(false);
    }
    return;
  }
  if (action === 'restore') await prepareAutomaticRestore(snapshotId);
}

export function initializeBackups() {
  dom.backupDownloadButton.addEventListener('click', () => void downloadBackup());
  dom.backupEncryptedDownloadButton.addEventListener('click', () => openPasswordDialog('export'));
  dom.backupRestoreButton.addEventListener('click', () => dom.backupRestoreInput.click());
  dom.backupRestoreInput.addEventListener('change', () => void restoreSelectedBackup());
  dom.backupAutomaticEnabled.addEventListener('change', () => void saveAutomaticSettings());
  dom.backupIntervalHours.addEventListener('change', () => void saveAutomaticSettings());
  dom.backupRetentionCount.addEventListener('change', () => void saveAutomaticSettings());
  dom.backupSnapshotList.addEventListener('click', (event) => void handleSnapshotAction(event));
  dom.backupPasswordCancel.addEventListener('click', closePasswordDialog);
  dom.backupPasswordForm.addEventListener('submit', (event) => void submitPasswordDialog(event));
  installDialogBackdropClose(dom.backupPasswordDialog, closePasswordDialog);
  dom.backupPasswordDialog.addEventListener('close', resetPasswordDialog);
  dom.backupPreviewCancel.addEventListener('click', closeRestorePreview);
  dom.backupPreviewRestore.addEventListener('click', () => void confirmRestorePreview());
  installDialogBackdropClose(dom.backupPreviewDialog, closeRestorePreview);
  dom.backupPreviewDialog.addEventListener('close', resetRestorePreview);
  restoreRememberedSafetyBackup();
}
