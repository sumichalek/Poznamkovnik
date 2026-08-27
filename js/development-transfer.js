import { apiRequest } from './api.js';
import { dom } from './dom.js';
import { installDialogBackdropClose } from './dialogs.js';
import { createStoredZip, downloadBlob } from './markdown-archive.js';
import { readImportEntries } from './markdown-import.js';

const MANIFEST_PATH = '.poznamkovnik-development-project.json';
const TRANSFER_FORMAT = 'poznamkovnik-development-project';
const TRANSFER_VERSION = 1;

let pendingImport = null;
let saveCurrent = async () => true;
let getCurrentProject = () => null;
let importCallback = async () => {};

function safeArchiveName(value) {
  const normalized = String(value || 'projekt')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');
  return (normalized || 'projekt').slice(0, 120);
}

function projectPath(project, item) {
  const items = new Map((project?.files || []).map((candidate) => [candidate.id, candidate]));
  const parts = [];
  const visited = new Set();
  let current = item;
  while (current && !visited.has(current.id)) {
    parts.unshift(String(current.title || 'polozka'));
    visited.add(current.id);
    current = items.get(String(current.parentId || ''));
  }
  return parts.join('/');
}

function projectManifest(project, tests = []) {
  const files = (project?.files || []).map((item) => ({
    path: projectPath(project, item),
    kind: item.kind === 'folder' ? 'folder' : 'file',
    content: item.kind === 'folder' ? undefined : String(item.content || ''),
    position: Number(item.position || 0),
  }));
  const entry = (project?.files || []).find((item) => item.id === project.entryFileId);
  return {
    format: TRANSFER_FORMAT,
    version: TRANSFER_VERSION,
    exportedAt: new Date().toISOString(),
    project: {
      title: String(project?.title || 'Projekt'),
      language: String(project?.language || 'c'),
      kind: String(project?.kind || 'program'),
      firmwareTargetId: String(project?.firmwareTargetId || ''),
      buildProfile: String(project?.buildProfile || 'debug'),
      runArguments: String(project?.runArguments || ''),
      entryPath: entry ? projectPath(project, entry) : '',
      files,
      tests: tests.map((test) => ({
        title: String(test?.title || 'Nový test'),
        stdin: String(test?.stdin || ''),
        arguments: String(test?.arguments || ''),
        expectedOutput: String(test?.expectedOutput || ''),
        position: Number(test?.position || 0),
      })),
    },
  };
}

function testCountLabel(count) {
  if (count === 1) return '1 test';
  if (count >= 2 && count <= 4) return `${count} testy`;
  return `${count} testov`;
}

function importSummary(manifest) {
  const project = manifest?.project || {};
  const files = Array.isArray(project.files) ? project.files : [];
  const tests = Array.isArray(project.tests) ? project.tests : [];
  const fileCount = files.filter((item) => item?.kind !== 'folder').length;
  const folderCount = files.length - fileCount;
  return {
    title: String(project.title || 'Bez názvu'),
    language: String(project.language || 'c'),
    kind: project.kind === 'firmware' ? 'Firmvér' : 'Program',
    files: `${fileCount} ${fileCount === 1 ? 'súbor' : fileCount < 5 ? 'súbory' : 'súborov'}`,
    folders: folderCount ? `${folderCount} ${folderCount === 1 ? 'priečinok' : folderCount < 5 ? 'priečinky' : 'priečinkov'}` : 'Bez priečinkov',
    tests: testCountLabel(tests.length),
  };
}

function renderImportSummary(manifest) {
  const summary = importSummary(manifest);
  const rows = [
    ['Projekt', summary.title],
    ['Typ', summary.kind],
    ['Jazyk', summary.language],
    ['Obsah', `${summary.files} · ${summary.folders}`],
    ['Testy', summary.tests],
  ];
  dom.developmentProjectImportSummary.replaceChildren();
  rows.forEach(([term, value]) => {
    const dt = document.createElement('dt');
    dt.textContent = term;
    const dd = document.createElement('dd');
    dd.textContent = value;
    dom.developmentProjectImportSummary.append(dt, dd);
  });
}

function closeImportDialog() {
  pendingImport = null;
  dom.developmentProjectImportConfirm.disabled = true;
  dom.developmentProjectImportStatus.textContent = '';
  dom.developmentProjectImportStatus.classList.remove('is-error');
  if (dom.developmentProjectImportDialog.open) dom.developmentProjectImportDialog.close();
}

function assertManifest(value) {
  if (!value || typeof value !== 'object' || value.format !== TRANSFER_FORMAT || value.version !== TRANSFER_VERSION) {
    throw new Error('Vybraný súbor nie je export projektu z Poznámkovníka.');
  }
  if (!value.project || typeof value.project !== 'object' || !Array.isArray(value.project.files)) {
    throw new Error('Export projektu nemá platný obsah.');
  }
  if (value.project.tests !== undefined && !Array.isArray(value.project.tests)) {
    throw new Error('Export projektu má neplatné testy.');
  }
  return value;
}

async function readProjectImport(file) {
  const entries = await readImportEntries(file);
  const manifestEntry = entries.find((entry) => entry.path === MANIFEST_PATH);
  if (!manifestEntry) throw new Error('ZIP neobsahuje súbor s projektom Poznámkovníka.');
  const raw = await manifestEntry.blob.text();
  if (raw.length > 22 * 1024 * 1024) throw new Error('Popis projektu je príliš veľký.');
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('Popis projektu nie je platný JSON.');
  }
  return assertManifest(parsed);
}

async function handleImportInput() {
  const file = dom.developmentProjectImportInput.files?.[0];
  if (!file) return;
  pendingImport = null;
  dom.developmentProjectImportConfirm.disabled = true;
  dom.developmentProjectImportDescription.textContent = 'Kontrolujem balík projektu...';
  dom.developmentProjectImportSummary.replaceChildren();
  dom.developmentProjectImportStatus.textContent = '';
  dom.developmentProjectImportStatus.classList.remove('is-error');
  if (!dom.developmentProjectImportDialog.open) dom.developmentProjectImportDialog.showModal();
  try {
    pendingImport = await readProjectImport(file);
    renderImportSummary(pendingImport);
    dom.developmentProjectImportDescription.textContent = 'Vytvorí sa nová kópia projektu. Pôvodný projekt sa nemení.';
    dom.developmentProjectImportConfirm.disabled = false;
  } catch (error) {
    dom.developmentProjectImportDescription.textContent = 'Import sa nepodarilo pripraviť.';
    dom.developmentProjectImportStatus.textContent = error?.message || 'Súbor sa nepodarilo spracovať.';
    dom.developmentProjectImportStatus.classList.add('is-error');
  }
}

async function exportCurrentProject() {
  const initialProject = getCurrentProject();
  if (!initialProject || !(await saveCurrent())) return;
  const project = getCurrentProject();
  if (!project) return;
  try {
    const response = await apiRequest(`/development/projects/${project.id}/tests`);
    const manifest = projectManifest(project, response.tests || []);
    const source = JSON.stringify(manifest, null, 2);
    if (new Blob([source]).size > 20 * 1024 * 1024) {
      window.alert('Projekt vrátane testov má viac než 20 MB a nedá sa preniesť jedným balíkom.');
      return;
    }
    const archive = await createStoredZip([
      { name: MANIFEST_PATH, blob: new Blob([source], { type: 'application/json;charset=utf-8' }) },
    ]);
    downloadBlob(archive, `${safeArchiveName(project.title)}-projekt.zip`);
  } catch (error) {
    window.alert(error?.message || 'Testy projektu sa nepodarilo pripraviť na export.');
  }
}

async function confirmImport() {
  if (!pendingImport) return;
  dom.developmentProjectImportConfirm.disabled = true;
  dom.developmentProjectImportStatus.textContent = 'Vytváram kópiu projektu...';
  try {
    if (!(await saveCurrent())) throw new Error('Rozpracovaný projekt sa nepodarilo uložiť.');
    const result = await apiRequest('/development/projects/import', { method: 'POST', body: pendingImport });
    await importCallback(result.project);
    closeImportDialog();
  } catch (error) {
    dom.developmentProjectImportStatus.textContent = error?.message || 'Projekt sa nepodarilo importovať.';
    dom.developmentProjectImportStatus.classList.add('is-error');
    dom.developmentProjectImportConfirm.disabled = false;
  }
}

export function initializeDevelopmentTransfer({ save = async () => true, currentProject = () => null, onImported = async () => {} } = {}) {
  saveCurrent = save;
  getCurrentProject = currentProject;
  importCallback = onImported;
  dom.developmentProjectImport.addEventListener('click', () => {
    dom.developmentProjectImportInput.value = '';
    dom.developmentProjectImportInput.click();
  });
  dom.developmentProjectExport.addEventListener('click', () => void exportCurrentProject());
  dom.developmentProjectImportInput.addEventListener('change', () => void handleImportInput());
  dom.developmentProjectImportCancel.addEventListener('click', closeImportDialog);
  dom.developmentProjectImportConfirm.addEventListener('click', () => void confirmImport());
  dom.developmentProjectImportDialog.addEventListener('close', () => {
    pendingImport = null;
    dom.developmentProjectImportInput.value = '';
  });
  installDialogBackdropClose(dom.developmentProjectImportDialog, closeImportDialog);
}
