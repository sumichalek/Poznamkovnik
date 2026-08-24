import { apiRequest, ApiError } from './api.js';
import { createAppIcon } from './app-icons.js';
import { dom } from './dom.js';

let projects = [];
let activeProjectId = '';
let activeProject = null;
let availableSources = [];
let loadedSource = null;
let panelPinned = false;
let titleSaveTimer = 0;
let draggingPageId = '';

function setStatus(message = '', { error = false } = {}) {
  dom.documentWorkshopStatus.textContent = message;
  dom.documentWorkshopStatus.classList.toggle('is-error', error);
}

function formatCount(count, singular, plural) {
  return count === 1 ? `1 ${singular}` : `${count} ${plural}`;
}

function supportedFile(file) {
  const name = String(file?.originalName || '').toLowerCase();
  const mime = String(file?.mimeType || '').toLowerCase();
  return mime === 'application/pdf' || name.endsWith('.pdf') || mime.startsWith('image/');
}

function projectSummary(project) {
  const pages = Number(project.pageCount || 0);
  const inputs = Number(project.inputCount || 0);
  return `${formatCount(pages, 'strana', 'strán')} · ${formatCount(inputs, 'vstup', 'vstupov')}`;
}

function setProjectControls() {
  const enabled = Boolean(activeProject);
  const hasPages = (activeProject?.pages || []).length > 0;
  dom.documentProjectTitle.disabled = !enabled;
  dom.documentProjectDelete.disabled = !enabled;
  dom.documentUploadButton.disabled = !enabled;
  dom.documentSourceSelect.disabled = !enabled;
  dom.documentSourceFileSelect.disabled = !enabled || !dom.documentSourceSelect.value;
  dom.documentSourceAdd.disabled = !enabled || !dom.documentSourceFileSelect.value;
  dom.documentBuildButton.disabled = !hasPages;
}

function renderProjectList() {
  dom.documentProjectsList.replaceChildren();
  if (!projects.length) {
    const empty = document.createElement('p');
    empty.className = 'documents-empty';
    empty.textContent = 'Zatiaľ tu nie je žiadny projekt.';
    dom.documentProjectsList.append(empty);
    return;
  }
  projects.forEach((project) => {
    const button = document.createElement('button');
    button.className = 'document-project-item';
    button.type = 'button';
    button.classList.toggle('is-active', project.id === activeProjectId);
    button.append(createAppIcon('article'));
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = project.title;
    const summary = document.createElement('small');
    summary.textContent = projectSummary(project);
    copy.append(title, summary);
    button.append(copy);
    button.addEventListener('click', () => void selectProject(project.id));
    dom.documentProjectsList.append(button);
  });
}

function thumbnailUrl(page) {
  return `/api/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}/thumbnail`;
}

function pageLabel(page, index) {
  const source = page.sourceTitle || page.originalName || 'Vstupný dokument';
  const inputPage = Number(page.inputPageIndex || 0) + 1;
  return `${source}, pôvodná strana ${inputPage}, výsledná strana ${index + 1}`;
}

function actionButton(icon, label, handler, extraClass = '') {
  const button = document.createElement('button');
  button.className = `panel-icon-button ${extraClass}`.trim();
  button.type = 'button';
  button.title = label;
  button.setAttribute('aria-label', label);
  button.append(createAppIcon(icon));
  button.addEventListener('click', (event) => {
    event.stopPropagation();
    void handler();
  });
  return button;
}

function renderPages() {
  const pages = activeProject?.pages || [];
  dom.documentPagesGrid.replaceChildren();
  if (!activeProject) {
    dom.documentPagesSummary.textContent = 'Vyber alebo vytvor projekt dokumentu.';
    return;
  }
  dom.documentPagesSummary.textContent = pages.length
    ? `${formatCount(pages.length, 'strana pripravená', 'strán pripravených')} vo výslednom poradí.`
    : 'Pridaj PDF alebo obrázky z počítača či zo zdroja.';
  if (!pages.length) {
    const empty = document.createElement('p');
    empty.className = 'documents-empty documents-pages-empty';
    empty.textContent = 'Projekt je prázdny. Pôvodné súbory sa pri úpravách nezmenia.';
    dom.documentPagesGrid.append(empty);
    return;
  }

  pages.forEach((page, index) => {
    const card = document.createElement('article');
    card.className = 'document-page-card';
    card.draggable = true;
    card.dataset.pageId = page.id;
    card.setAttribute('aria-label', pageLabel(page, index));

    const number = document.createElement('span');
    number.className = 'document-page-number';
    number.textContent = String(index + 1);
    const preview = document.createElement('img');
    preview.className = 'document-page-preview';
    preview.src = thumbnailUrl(page);
    preview.alt = `Náhľad: ${pageLabel(page, index)}`;
    preview.loading = 'lazy';
    const footer = document.createElement('footer');
    const details = document.createElement('span');
    const file = document.createElement('strong');
    file.textContent = page.originalName || 'Dokument';
    file.title = page.originalName || 'Dokument';
    const originalPage = document.createElement('small');
    originalPage.textContent = `Strana ${Number(page.inputPageIndex || 0) + 1}`;
    details.append(file, originalPage);
    const actions = document.createElement('div');
    actions.className = 'document-page-actions';
    actions.append(
      actionButton('rotate-ccw', 'Otočiť doľava', () => rotatePage(page, -90)),
      actionButton('rotate-ccw', 'Otočiť doprava', () => rotatePage(page, 90), 'is-flipped'),
      actionButton('duplicate', 'Duplikovať stranu', () => duplicatePage(page)),
      actionButton('trash', 'Odstrániť stranu', () => deletePage(page), 'danger'),
    );
    footer.append(details, actions);
    card.append(number, preview, footer);
    card.addEventListener('dragstart', (event) => {
      draggingPageId = page.id;
      card.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', page.id);
    });
    card.addEventListener('dragend', () => {
      draggingPageId = '';
      document.querySelectorAll('.document-page-card.is-drop-target, .document-page-card.is-dragging')
        .forEach((item) => item.classList.remove('is-drop-target', 'is-dragging'));
    });
    card.addEventListener('dragover', (event) => {
      if (!draggingPageId || draggingPageId === page.id) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      card.classList.add('is-drop-target');
    });
    card.addEventListener('dragleave', () => card.classList.remove('is-drop-target'));
    card.addEventListener('drop', (event) => {
      event.preventDefault();
      card.classList.remove('is-drop-target');
      void movePage(draggingPageId, page.id);
    });
    dom.documentPagesGrid.append(card);
  });
}

function renderWorkspace() {
  dom.documentProjectTitle.value = activeProject?.project?.title || '';
  renderProjectList();
  renderPages();
  setProjectControls();
}

function updateProjectSummary(detail) {
  const project = detail.project;
  const index = projects.findIndex((item) => item.id === project.id);
  const summary = {
    ...project,
    inputCount: (detail.inputs || []).length,
    pageCount: (detail.pages || []).length,
  };
  if (index >= 0) projects.splice(index, 1, summary);
  else projects.unshift(summary);
}

async function loadProjects() {
  const result = await apiRequest('/documents');
  projects = result.projects || [];
  if (activeProjectId && !projects.some((project) => project.id === activeProjectId)) {
    activeProjectId = '';
    activeProject = null;
  }
  renderProjectList();
}

async function loadSources() {
  const result = await apiRequest('/sources');
  availableSources = result.sources || [];
  const current = dom.documentSourceSelect.value;
  dom.documentSourceSelect.replaceChildren(new Option('Vyber zdroj s prílohou', ''));
  availableSources.forEach((source) => dom.documentSourceSelect.add(new Option(source.title, source.id)));
  dom.documentSourceSelect.value = availableSources.some((source) => source.id === current) ? current : '';
  setProjectControls();
}

async function selectProject(projectId) {
  if (!projectId) return;
  const detail = await apiRequest(`/documents/${encodeURIComponent(projectId)}`);
  activeProjectId = projectId;
  activeProject = detail;
  updateProjectSummary(detail);
  setStatus('');
  renderWorkspace();
}

function applyProjectDetail(detail, message = '') {
  activeProject = detail;
  activeProjectId = detail.project.id;
  updateProjectSummary(detail);
  setStatus(message);
  renderWorkspace();
}

async function createProject() {
  const detail = await apiRequest('/documents', { method: 'POST', body: { title: 'Nový dokument' } });
  activeProjectId = detail.project.id;
  activeProject = detail;
  await loadProjects();
  renderWorkspace();
  dom.documentProjectTitle.focus();
  dom.documentProjectTitle.select();
}

async function saveProjectTitle() {
  window.clearTimeout(titleSaveTimer);
  if (!activeProject) return;
  const title = dom.documentProjectTitle.value.trim();
  if (!title || title === activeProject.project.title) {
    dom.documentProjectTitle.value = activeProject.project.title;
    return;
  }
  try {
    const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}`, {
      method: 'PATCH', body: { title }
    });
    applyProjectDetail(detail, 'Názov projektu je uložený.');
  } catch (error) {
    setStatus(error.message || 'Názov projektu sa nepodarilo uložiť.', { error: true });
  }
}

function queueTitleSave() {
  window.clearTimeout(titleSaveTimer);
  titleSaveTimer = window.setTimeout(() => void saveProjectTitle(), 650);
}

async function deleteProject() {
  if (!activeProject) return;
  if (!window.confirm(`Zmazať projekt „${activeProject.project.title}“? Vstupné súbory bez iného použitia sa odstránia.`)) return;
  await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}`, { method: 'DELETE' });
  activeProjectId = '';
  activeProject = null;
  loadedSource = null;
  await loadProjects();
  setStatus('Projekt je odstránený.');
  renderWorkspace();
}

async function addUploads(files) {
  if (!activeProjectId || !files.length) return;
  setStatus('Pridávam vstupné stránky...');
  for (const file of files) {
    const form = new FormData();
    form.append('file', file, file.name);
    const response = await fetch(`/api/documents/${encodeURIComponent(activeProjectId)}/inputs`, {
      method: 'POST', credentials: 'same-origin', body: form
    });
    const payload = await response.json();
    if (!response.ok) throw new ApiError(payload?.error || `Súbor ${file.name} sa nepodarilo pridať.`, response.status);
    applyProjectDetail(payload);
  }
  await loadProjects();
  setStatus(`${formatCount(files.length, 'vstup bol pridaný', 'vstupov bolo pridaných')}.`);
}

async function loadSourceFiles() {
  const sourceId = dom.documentSourceSelect.value;
  loadedSource = null;
  dom.documentSourceFileSelect.replaceChildren(new Option('Vyber podporovanú prílohu', ''));
  if (!sourceId) {
    setProjectControls();
    return;
  }
  const result = await apiRequest(`/sources/${encodeURIComponent(sourceId)}`);
  loadedSource = result.source;
  (loadedSource.files || []).filter(supportedFile).forEach((file) => {
    dom.documentSourceFileSelect.add(new Option(file.originalName, file.id));
  });
  if (!(loadedSource.files || []).some(supportedFile)) setStatus('Vybraný zdroj nemá podporovanú PDF ani obrazovú prílohu.', { error: true });
  else setStatus('');
  setProjectControls();
}

async function addSourceFile() {
  const fileId = dom.documentSourceFileSelect.value;
  if (!activeProjectId || !fileId) return;
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/source-files`, {
    method: 'POST', body: { fileId }
  });
  applyProjectDetail(detail, 'Príloha zdroja bola pridaná ako nové stránky.');
  await loadProjects();
}

async function rotatePage(page, delta) {
  const rotation = (Number(page.rotation || 0) + delta + 360) % 360;
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}`, {
    method: 'PATCH', body: { rotation }
  });
  applyProjectDetail(detail, 'Strana je otočená.');
}

async function duplicatePage(page) {
  const detail = await apiRequest(
    `/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}/duplicate`,
    { method: 'POST', body: {} }
  );
  applyProjectDetail(detail, 'Strana je duplikovaná.');
  await loadProjects();
}

async function deletePage(page) {
  if (!window.confirm('Odstrániť túto stranu z výsledného dokumentu? Originál zostane nezmenený.')) return;
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}`, {
    method: 'DELETE'
  });
  applyProjectDetail(detail, 'Strana je odstránená.');
  await loadProjects();
}

async function movePage(fromId, beforeId) {
  if (!fromId || !beforeId || fromId === beforeId || !activeProject) return;
  const ids = activeProject.pages.map((page) => page.id);
  const fromIndex = ids.indexOf(fromId);
  const toIndex = ids.indexOf(beforeId);
  if (fromIndex < 0 || toIndex < 0) return;
  ids.splice(fromIndex, 1);
  ids.splice(toIndex, 0, fromId);
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/order`, {
    method: 'PUT', body: { pageIds: ids }
  });
  applyProjectDetail(detail, 'Poradie strán je uložené.');
  await loadProjects();
}

async function buildSource() {
  if (!activeProject?.pages?.length) return;
  const defaultTitle = activeProject.project.title || 'Nový dokument';
  const title = window.prompt('Názov nového zdroja PDF:', defaultTitle);
  if (title === null) return;
  const cleanTitle = title.trim();
  if (!cleanTitle) return;
  dom.documentBuildButton.disabled = true;
  setStatus('Vytváram nový PDF zdroj...');
  try {
    const result = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/build`, {
      method: 'POST', body: { title: cleanTitle }
    });
    const source = result.source;
    setStatus(`Zdroj „${source.title}“ je vytvorený.`);
    const open = window.confirm(`Zdroj „${source.title}“ je hotový. Otvoriť ho teraz?`);
    if (open) window.dispatchEvent(new CustomEvent('source-open-request', { detail: { sourceId: source.id } }));
  } catch (error) {
    setStatus(error.message || 'PDF zdroj sa nepodarilo vytvoriť.', { error: true });
  } finally {
    setProjectControls();
  }
}

export async function openDocumentsPanel({ projectId = '', pinned = false } = {}) {
  dom.documentsPanel.classList.add('is-open');
  dom.documentsPanel.setAttribute('aria-hidden', 'false');
  if (pinned) panelPinned = true;
  await Promise.all([loadProjects(), loadSources()]);
  const target = projectId || activeProjectId || projects[0]?.id || '';
  if (target) await selectProject(target);
  else renderWorkspace();
}

export function closeDocumentsPanel() {
  window.clearTimeout(titleSaveTimer);
  dom.documentsPanel.classList.remove('is-open');
  dom.documentsPanel.setAttribute('aria-hidden', 'true');
  panelPinned = false;
}

export function isDocumentsPanelOpen() {
  return dom.documentsPanel.classList.contains('is-open');
}

export function isDocumentsPanelPinned() {
  return panelPinned;
}

export function hasUnsavedDocumentChanges() {
  return false;
}

export async function saveDocumentDraft() {
  await saveProjectTitle();
  return true;
}

export function discardDocumentDraft() {
  if (activeProject) dom.documentProjectTitle.value = activeProject.project.title;
}

export function initializeDocuments() {
  dom.documentProjectCreate.addEventListener('click', () => void createProject().catch((error) => setStatus(error.message, { error: true })));
  dom.documentProjectDelete.addEventListener('click', () => void deleteProject().catch((error) => setStatus(error.message, { error: true })));
  dom.documentProjectTitle.addEventListener('input', queueTitleSave);
  dom.documentProjectTitle.addEventListener('blur', () => void saveProjectTitle());
  dom.documentUploadButton.addEventListener('click', () => dom.documentUploadInput.click());
  dom.documentUploadInput.addEventListener('change', () => {
    const files = [...dom.documentUploadInput.files];
    dom.documentUploadInput.value = '';
    void addUploads(files).catch((error) => setStatus(error.message || 'Súbory sa nepodarilo pridať.', { error: true }));
  });
  dom.documentSourceSelect.addEventListener('change', () => void loadSourceFiles().catch((error) => setStatus(error.message, { error: true })));
  dom.documentSourceFileSelect.addEventListener('change', setProjectControls);
  dom.documentSourceAdd.addEventListener('click', () => void addSourceFile().catch((error) => setStatus(error.message, { error: true })));
  dom.documentBuildButton.addEventListener('click', () => void buildSource());
  window.addEventListener('sources-changed', () => {
    if (isDocumentsPanelOpen()) void loadSources().catch(() => {});
  });
}
