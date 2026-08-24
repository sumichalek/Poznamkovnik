import { apiRequest, ApiError, downloadDocumentProject, uploadDocumentProject } from './api.js';
import { createAppIcon } from './app-icons.js';
import { storageKeys } from './config.js';
import { hasOpenApplicationDialog, installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';

let projects = [];
let activeProjectId = '';
let activeProject = null;
let availableSources = [];
let loadedSource = null;
let panelPinned = false;
let titleSaveTimer = 0;
let draggingPageIds = [];
let selectedPageIds = new Set();
let selectionAnchorPageId = '';
let suppressPageClick = false;
let cropPageIds = [];
let cropPointerDrag = null;
let pagePickerStage = null;
let pagePickerResolver = null;
let batchPageMutationInFlight = false;
let historyMutationInFlight = false;
let pageRotationWheelDelta = 0;
let pageRotationWheelTimer = 0;
let inputsCollapsed = localStorage.getItem(storageKeys.documentInputsCollapsed) === 'true';
let sourcePickerOpen = false;
let workspaceFileDropActive = false;
let documentPreviewPointerId = null;
let documentPreviewInlineSize = 0;
let documentBuildPageIds = [];
let documentBuildInFlight = false;
let projectTransferInFlight = false;
const imageExtensions = new Set(['.gif', '.jpeg', '.jpg', '.png', '.tif', '.tiff', '.webp']);
const imageMimeTypes = new Set(['image/gif', 'image/jpeg', 'image/png', 'image/tiff', 'image/webp']);
const officeExtensions = new Set(['.csv', '.doc', '.docx', '.ods', '.odt', '.odp', '.ppt', '.pptx', '.rtf', '.txt', '.xls', '.xlsx']);
const DOCUMENT_PREVIEW_MIN_WIDTH = 440;
const DOCUMENT_PREVIEW_NARROW_VIEWPORT_MAX = 800;
const documentOutputPresets = {
  original: { outputPageSize: 'keep', imageDpi: 144 },
  'a4-reading': { outputPageSize: 'a4-portrait', imageDpi: 144 },
  'a4-print': { outputPageSize: 'a4-portrait', imageDpi: 300 },
  'a4-landscape': { outputPageSize: 'a4-landscape', imageDpi: 200 },
};

function setStatus(message = '', { error = false } = {}) {
  dom.documentWorkshopStatus.textContent = message;
  dom.documentWorkshopStatus.classList.toggle('is-error', error);
}

function documentPreviewViewportWidth() {
  return window.visualViewport?.width || window.innerWidth;
}

function isDocumentPreviewResizable() {
  return documentPreviewViewportWidth() > DOCUMENT_PREVIEW_NARROW_VIEWPORT_MAX && isDocumentPreviewOpen();
}

function documentPreviewSizeRange() {
  const viewport = documentPreviewViewportWidth();
  const max = Math.max(0, Math.min(Math.round(viewport * 0.72), viewport - 360));
  return { min: Math.min(DOCUMENT_PREVIEW_MIN_WIDTH, max), max };
}

function clampDocumentPreviewSize(value) {
  const { min, max } = documentPreviewSizeRange();
  return Math.round(Math.min(max, Math.max(min, value)));
}

function currentDocumentPreviewSize() {
  if (Number.isFinite(documentPreviewInlineSize) && documentPreviewInlineSize > 0) return documentPreviewInlineSize;
  return Math.round(dom.documentPreviewDock.getBoundingClientRect().width);
}

function setDocumentPreviewSize(value, { persist = true, refresh = true } = {}) {
  const nextSize = clampDocumentPreviewSize(value);
  documentPreviewInlineSize = nextSize;
  document.documentElement.style.setProperty('--document-preview-inline-size', `${nextSize}px`);
  if (persist) localStorage.setItem(storageKeys.documentPreviewInlineSize, String(nextSize));
  if (refresh) refreshDocumentPreviewResizeHandle();
  return nextSize;
}

function refreshDocumentPreviewResizeHandle() {
  const resizable = isDocumentPreviewResizable();
  const { min, max } = documentPreviewSizeRange();
  const size = clampDocumentPreviewSize(currentDocumentPreviewSize());
  dom.documentPreviewResizeHandle.setAttribute('aria-hidden', String(!resizable));
  dom.documentPreviewResizeHandle.tabIndex = resizable ? 0 : -1;
  dom.documentPreviewResizeHandle.setAttribute('aria-valuemin', String(min));
  dom.documentPreviewResizeHandle.setAttribute('aria-valuemax', String(max));
  dom.documentPreviewResizeHandle.setAttribute('aria-valuenow', String(size));
  dom.documentPreviewResizeHandle.setAttribute('aria-valuetext', `${size} px`);
}

function isDocumentPreviewOpen() {
  return dom.documentPreviewDock.classList.contains('is-open');
}

function documentPreviewUrl() {
  return `/api/documents/${encodeURIComponent(activeProjectId)}/preview?v=${Date.now()}`;
}

function updateDocumentPreviewDetails({ refresh = false } = {}) {
  if (!activeProject?.pages?.length || !isDocumentPreviewOpen()) return;
  const pageCount = activeProject.pages.length;
  const url = documentPreviewUrl();
  dom.documentPreviewTitle.textContent = activeProject.project.title || 'Výsledné PDF';
  dom.documentPreviewMeta.textContent = `${pageCount} ${pageNumberWord(pageCount)} · aktuálne nastavenie výsledku`;
  dom.documentPreviewExternal.href = url;
  if (refresh) dom.documentPreviewFrame.src = url;
}

function setDocumentPreviewOpen(open) {
  const visible = Boolean(open);
  dom.documentsPanel.classList.toggle('is-preview-open', visible);
  dom.documentPreviewDock.classList.toggle('is-open', visible);
  dom.documentPreviewDock.setAttribute('aria-hidden', String(!visible));
  dom.documentPreviewButton.setAttribute('aria-expanded', String(visible));
  if (!visible) dom.documentPreviewFrame.removeAttribute('src');
  refreshDocumentPreviewResizeHandle();
}

function openDocumentPreview() {
  if (!activeProject?.pages?.length) return;
  setDocumentPreviewOpen(true);
  updateDocumentPreviewDetails({ refresh: true });
}

function closeDocumentPreview() {
  setDocumentPreviewOpen(false);
}

function startDocumentPreviewResize(event) {
  if (!isDocumentPreviewResizable() || event.button !== 0) return;
  event.preventDefault();
  documentPreviewPointerId = event.pointerId;
  dom.documentPreviewResizeHandle.setPointerCapture(event.pointerId);
  document.body.classList.add('is-document-preview-resizing');
  setDocumentPreviewSize(documentPreviewViewportWidth() - event.clientX, { persist: false });
}

function moveDocumentPreviewResize(event) {
  if (event.pointerId !== documentPreviewPointerId) return;
  setDocumentPreviewSize(documentPreviewViewportWidth() - event.clientX, { persist: false });
}

function finishDocumentPreviewResize(event) {
  if (event.pointerId !== documentPreviewPointerId) return;
  if (dom.documentPreviewResizeHandle.hasPointerCapture(event.pointerId)) {
    dom.documentPreviewResizeHandle.releasePointerCapture(event.pointerId);
  }
  documentPreviewPointerId = null;
  document.body.classList.remove('is-document-preview-resizing');
  localStorage.setItem(storageKeys.documentPreviewInlineSize, String(documentPreviewInlineSize));
}

function resizeDocumentPreviewFromKeyboard(event) {
  if (!isDocumentPreviewResizable()) return;
  const step = event.shiftKey ? 32 : 12;
  let nextSize = currentDocumentPreviewSize();
  if (event.key === 'Home') nextSize = documentPreviewSizeRange().min;
  else if (event.key === 'End') nextSize = documentPreviewSizeRange().max;
  else if (event.key === 'ArrowLeft') nextSize += step;
  else if (event.key === 'ArrowRight') nextSize -= step;
  else return;
  event.preventDefault();
  setDocumentPreviewSize(nextSize);
}

function formatCount(count, singular, plural) {
  return count === 1 ? `1 ${singular}` : `${count} ${plural}`;
}

function supportedFile(file) {
  const name = String(file?.originalName || '').toLowerCase();
  const mime = String(file?.mimeType || '').toLowerCase();
  const extension = name.slice(name.lastIndexOf('.'));
  return mime === 'application/pdf' || extension === '.pdf' || imageMimeTypes.has(mime) || imageExtensions.has(extension) || officeExtensions.has(extension);
}

function isFileDrag(event) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
}

function setWorkspaceFileDropActive(active) {
  workspaceFileDropActive = active;
  dom.documentsWorkspace.classList.toggle('is-file-drop-target', active);
}

function needsConversion(file) {
  const name = String(file?.originalName || '').toLowerCase();
  return officeExtensions.has(name.slice(name.lastIndexOf('.')));
}

function projectSummary(project) {
  const pages = Number(project.pageCount || 0);
  const inputs = Number(project.inputCount || 0);
  return `${formatCount(pages, 'strana', 'strán')} · ${formatCount(inputs, 'vstup', 'vstupov')}`;
}

function setProjectControls() {
  const enabled = Boolean(activeProject);
  const hasPages = (activeProject?.pages || []).length > 0;
  const history = activeProject?.history || {};
  const pendingTitleChange = enabled && dom.documentProjectTitle.value.trim() !== activeProject.project.title;
  dom.documentProjectTitle.disabled = !enabled;
  dom.documentProjectUndo.disabled = !enabled || !history.canUndo || historyMutationInFlight || pendingTitleChange;
  dom.documentProjectRedo.disabled = !enabled || !history.canRedo || historyMutationInFlight || pendingTitleChange;
  const undoLabel = history.undoLabel ? `Krok späť: ${history.undoLabel}` : 'Krok späť';
  const redoLabel = history.redoLabel ? `Krok dopredu: ${history.redoLabel}` : 'Krok dopredu';
  dom.documentProjectUndo.setAttribute('aria-label', undoLabel);
  dom.documentProjectUndo.title = undoLabel;
  dom.documentProjectRedo.setAttribute('aria-label', redoLabel);
  dom.documentProjectRedo.title = redoLabel;
  dom.documentProjectDelete.disabled = !enabled;
  dom.documentProjectImport.disabled = projectTransferInFlight;
  dom.documentProjectExport.disabled = !enabled || projectTransferInFlight;
  dom.documentOutputPreset.disabled = !enabled;
  dom.documentOutputPageSize.disabled = !enabled;
  dom.documentImageDpi.disabled = !enabled;
  dom.documentPageNumberPosition.disabled = !enabled;
  dom.documentPageNumberStart.disabled = !enabled || dom.documentPageNumberPosition.value === 'none';
  dom.documentUploadButton.disabled = !enabled;
  dom.documentSourceToggle.disabled = !enabled;
  dom.documentSourceSelect.disabled = !enabled;
  dom.documentSourceFileSelect.disabled = !enabled || !dom.documentSourceSelect.value;
  dom.documentSourceAdd.disabled = !enabled || !dom.documentSourceFileSelect.value;
  dom.documentPreviewButton.disabled = !hasPages;
  dom.documentBuildButton.disabled = !hasPages;
}

function outputPresetFor(outputPageSize, imageDpi) {
  return Object.entries(documentOutputPresets).find(([, preset]) => (
    preset.outputPageSize === outputPageSize && preset.imageDpi === Number(imageDpi)
  ))?.[0] || 'custom';
}

function syncOutputPreset() {
  dom.documentOutputPreset.value = outputPresetFor(
    dom.documentOutputPageSize.value,
    Number(dom.documentImageDpi.value),
  );
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
  const version = [
    page.rotation || 0,
    page.cropTop || 0,
    page.cropRight || 0,
    page.cropBottom || 0,
    page.cropLeft || 0,
  ].join('-');
  return `/api/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}/thumbnail?v=${encodeURIComponent(version)}`;
}

function downloadOriginal(input) {
  const link = document.createElement('a');
  link.href = `/api/documents/${encodeURIComponent(activeProjectId)}/inputs/${encodeURIComponent(input.id)}/original`;
  link.download = '';
  document.body.append(link);
  link.click();
  link.remove();
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

function selectedPageItems() {
  const pages = activeProject?.pages || [];
  return pages.filter((page) => selectedPageIds.has(page.id));
}

function prunePageSelection() {
  const pageIds = new Set((activeProject?.pages || []).map((page) => page.id));
  selectedPageIds = new Set([...selectedPageIds].filter((pageId) => pageIds.has(pageId)));
  if (!pageIds.has(selectionAnchorPageId)) selectionAnchorPageId = '';
}

function updatePageSelectionUi() {
  const pages = activeProject?.pages || [];
  const selected = selectedPageItems();
  const hasSelection = selected.length > 0;
  dom.documentPageSelectionToolbar.hidden = !pages.length;
  dom.documentPageSelectionSummary.textContent = hasSelection
    ? `Vybrané: ${selected.length} ${pageNumberWord(selected.length)}.`
    : 'Nie sú vybrané žiadne strany.';
  dom.documentPageSelectAll.disabled = !pages.length || selected.length === pages.length;
  dom.documentPageClearSelection.disabled = !hasSelection;
  [
    dom.documentPageRotateLeft,
    dom.documentPageRotateRight,
    dom.documentPageCropSelection,
    dom.documentPageDuplicateSelection,
    dom.documentPageBuildSelection,
    dom.documentPageDeleteSelection,
  ].forEach((button) => { button.disabled = !hasSelection || batchPageMutationInFlight || documentBuildInFlight; });
  document.querySelectorAll('.document-page-card').forEach((card) => {
    const selectedCard = selectedPageIds.has(card.dataset.pageId);
    card.classList.toggle('is-selected', selectedCard);
    card.setAttribute('aria-selected', String(selectedCard));
  });
}

function selectPage(page, event = {}) {
  const pages = activeProject?.pages || [];
  const pageIndex = pages.findIndex((item) => item.id === page.id);
  if (pageIndex < 0) return;
  if (event.shiftKey && selectionAnchorPageId) {
    const anchorIndex = pages.findIndex((item) => item.id === selectionAnchorPageId);
    if (anchorIndex >= 0) {
      const start = Math.min(anchorIndex, pageIndex);
      const end = Math.max(anchorIndex, pageIndex);
      selectedPageIds = new Set(pages.slice(start, end + 1).map((item) => item.id));
    } else {
      selectedPageIds = new Set([page.id]);
    }
  } else if (event.ctrlKey || event.metaKey) {
    if (selectedPageIds.has(page.id)) selectedPageIds.delete(page.id);
    else selectedPageIds.add(page.id);
    selectionAnchorPageId = page.id;
  } else {
    selectedPageIds = new Set([page.id]);
    selectionAnchorPageId = page.id;
  }
  updatePageSelectionUi();
}

function selectAllPages() {
  selectedPageIds = new Set((activeProject?.pages || []).map((page) => page.id));
  selectionAnchorPageId = activeProject?.pages?.[0]?.id || '';
  updatePageSelectionUi();
}

function clearPageSelection() {
  selectedPageIds.clear();
  selectionAnchorPageId = '';
  updatePageSelectionUi();
}

function isEditableTarget(target) {
  return target instanceof Element && Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
}

function rotateSelectedPagesFromWheel(event) {
  const card = event.target instanceof Element ? event.target.closest('.document-page-card') : null;
  if (!card || !selectedPageIds.has(card.dataset.pageId)) return;
  event.preventDefault();
  if (batchPageMutationInFlight || !event.deltaY) return;
  pageRotationWheelDelta += event.deltaY;
  window.clearTimeout(pageRotationWheelTimer);
  pageRotationWheelTimer = window.setTimeout(() => { pageRotationWheelDelta = 0; }, 160);
  if (Math.abs(pageRotationWheelDelta) < 40) return;
  const delta = pageRotationWheelDelta > 0 ? 90 : -90;
  pageRotationWheelDelta = 0;
  void rotateSelectedPages(delta);
}

function syncInputsVisibility() {
  const hasProject = Boolean(activeProject);
  const hasInputs = Boolean(activeProject?.inputs?.length);
  const collapsed = hasInputs && inputsCollapsed;
  const sourcePickerVisible = hasProject && sourcePickerOpen && !collapsed;
  dom.documentInputsSection.classList.toggle('is-collapsed', collapsed);
  dom.documentInputsSection.classList.toggle('is-source-picker-open', sourcePickerVisible);
  dom.documentInputsToggle.disabled = !hasInputs;
  dom.documentSourceToggle.disabled = !hasProject;
  dom.documentInputsToggle.setAttribute('aria-expanded', String(!collapsed));
  dom.documentSourceToggle.setAttribute('aria-expanded', String(sourcePickerVisible));
  const label = collapsed ? 'Zobraziť vstupy projektu' : 'Zbaliť vstupy projektu';
  dom.documentInputsToggle.setAttribute('aria-label', label);
  dom.documentInputsToggle.title = label;
  const sourceLabel = sourcePickerVisible ? 'Skryť výber prílohy zo zdroja' : 'Pridať prílohu existujúceho zdroja';
  dom.documentSourceToggle.setAttribute('aria-label', sourceLabel);
  dom.documentSourceToggle.title = sourceLabel;
}

function renderInputs() {
  dom.documentInputsList.replaceChildren();
  if (!activeProject) {
    dom.documentInputsSummary.textContent = '';
    syncInputsVisibility();
    return;
  }
  const inputs = activeProject.inputs || [];
  const pageCountByInput = new Map();
  (activeProject.pages || []).forEach((page) => {
    pageCountByInput.set(page.inputId, (pageCountByInput.get(page.inputId) || 0) + 1);
  });
  dom.documentInputsSummary.textContent = inputs.length
    ? `${formatCount(inputs.length, 'vložený dokument', 'vložených dokumentov')}.`
    : 'Zatiaľ nebol pridaný žiadny dokument.';
  if (!inputs.length) {
    const empty = document.createElement('p');
    empty.className = 'documents-empty document-inputs-empty';
    empty.textContent = 'Pridaj súbor z počítača alebo prílohu existujúceho zdroja.';
    dom.documentInputsList.append(empty);
    syncInputsVisibility();
    return;
  }
  inputs.forEach((input) => {
    const item = document.createElement('article');
    item.className = 'document-input-item';
    item.append(createAppIcon(needsConversion(input) ? 'article' : 'file'));
    const body = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = input.originalName || 'Dokument';
    title.title = input.originalName || 'Dokument';
    const detail = document.createElement('small');
    const outputPages = pageCountByInput.get(input.id) || 0;
    const source = input.sourceTitle ? ` · Zdroj: ${input.sourceTitle}` : '';
    detail.textContent = `${outputPages} ${pageNumberWord(outputPages)} v projekte${source}`;
    body.append(title, detail);
    const actions = document.createElement('div');
    actions.className = 'document-input-actions';
    actions.append(
      actionButton('download', 'Stiahnuť pôvodný dokument', () => downloadOriginal(input)),
      actionButton('trash', 'Odstrániť dokument z projektu', () => deleteInput(input), 'danger'),
    );
    item.append(body, actions);
    dom.documentInputsList.append(item);
  });
  syncInputsVisibility();
}

function renderPages() {
  const pages = activeProject?.pages || [];
  dom.documentPagesGrid.replaceChildren();
  prunePageSelection();
  if (!activeProject) {
    dom.documentPagesSummary.textContent = '';
    updatePageSelectionUi();
    return;
  }
  dom.documentPagesSummary.textContent = pages.length
    ? `${formatCount(pages.length, 'strana pripravená', 'strán pripravených')} vo výslednom poradí.`
    : 'Pridaj dokument, PDF alebo obrázky z počítača či zo zdroja.';
  if (!pages.length) {
    const empty = document.createElement('p');
    empty.className = 'documents-empty documents-pages-empty';
    empty.textContent = 'Projekt je prázdny. Pôvodné súbory sa pri úpravách nezmenia.';
    dom.documentPagesGrid.append(empty);
    updatePageSelectionUi();
    return;
  }

  pages.forEach((page, index) => {
    const card = document.createElement('article');
    card.className = 'document-page-card';
    card.draggable = true;
    card.dataset.pageId = page.id;
    card.tabIndex = 0;
    card.setAttribute('aria-selected', String(selectedPageIds.has(page.id)));
    card.classList.toggle('is-selected', selectedPageIds.has(page.id));
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
    originalPage.textContent = needsConversion(page)
      ? `Prevedené do PDF · strana ${Number(page.inputPageIndex || 0) + 1}`
      : `Strana ${Number(page.inputPageIndex || 0) + 1}`;
    details.append(file, originalPage);
    const actions = document.createElement('div');
    actions.className = 'document-page-actions';
    actions.append(
      actionButton('rotate-ccw', 'Otočiť doľava', () => rotatePage(page, -90)),
      actionButton('rotate-ccw', 'Otočiť doprava', () => rotatePage(page, 90), 'is-flipped'),
      actionButton('crop', 'Orezať okraje', () => openCropDialog(page)),
      actionButton('duplicate', 'Duplikovať stranu', () => duplicatePage(page)),
      actionButton('trash', 'Odstrániť stranu', () => deletePage(page), 'danger'),
    );
    footer.append(details);
    card.append(number, preview, footer, actions);
    card.addEventListener('dragstart', (event) => {
      if (!selectedPageIds.has(page.id)) {
        selectedPageIds = new Set([page.id]);
        selectionAnchorPageId = page.id;
        updatePageSelectionUi();
      }
      draggingPageIds = selectedPageItems().map((item) => item.id);
      card.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', draggingPageIds.join(','));
    });
    card.addEventListener('dragend', () => {
      draggingPageIds = [];
      suppressPageClick = true;
      window.setTimeout(() => { suppressPageClick = false; }, 0);
      document.querySelectorAll('.document-page-card.is-drop-target, .document-page-card.is-dragging')
        .forEach((item) => item.classList.remove('is-drop-target', 'is-dragging'));
      dom.documentPagesGrid.classList.remove('is-drop-target');
    });
    card.addEventListener('dragover', (event) => {
      if (!draggingPageIds.length || draggingPageIds.includes(page.id)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      card.classList.add('is-drop-target');
    });
    card.addEventListener('dragleave', () => card.classList.remove('is-drop-target'));
    card.addEventListener('drop', (event) => {
      event.preventDefault();
      event.stopPropagation();
      card.classList.remove('is-drop-target');
      void moveSelectedPages(page.id);
    });
    card.addEventListener('click', (event) => {
      if (suppressPageClick || event.target.closest('button, a, input, label')) return;
      selectPage(page, event);
    });
    card.addEventListener('keydown', (event) => {
      if (event.target.closest('button, a, input, label')) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectPage(page, event);
      }
    });
    dom.documentPagesGrid.append(card);
  });
  updatePageSelectionUi();
}

function renderWorkspace() {
  dom.documentProjectTitle.value = activeProject?.project?.title || '';
  dom.documentOutputPageSize.value = activeProject?.project?.outputPageSize || 'keep';
  dom.documentImageDpi.value = String(activeProject?.project?.imageDpi || 144);
  dom.documentPageNumberPosition.value = activeProject?.project?.pageNumberPosition || 'none';
  dom.documentPageNumberStart.value = String(activeProject?.project?.pageNumberStart || 1);
  syncOutputPreset();
  renderProjectList();
  renderInputs();
  renderPages();
  setProjectControls();
  if (isDocumentPreviewOpen() && !activeProject?.pages?.length) closeDocumentPreview();
  else updateDocumentPreviewDetails();
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
  if (isDocumentPreviewOpen()) updateDocumentPreviewDetails({ refresh: true });
}

function applyProjectDetail(detail, message = '') {
  activeProject = detail;
  activeProjectId = detail.project.id;
  updateProjectSummary(detail);
  setStatus(message);
  renderWorkspace();
  if (isDocumentPreviewOpen()) updateDocumentPreviewDetails({ refresh: true });
}

async function createProject() {
  const detail = await apiRequest('/documents', { method: 'POST', body: { title: 'Nový projekt PDF' } });
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

async function saveProjectOutputSettings(settings = {}, successMessage = '') {
  if (!activeProject) return;
  const outputPageSize = settings.outputPageSize ?? dom.documentOutputPageSize.value;
  const imageDpi = Number(settings.imageDpi ?? dom.documentImageDpi.value);
  const pageNumberPosition = settings.pageNumberPosition ?? dom.documentPageNumberPosition.value;
  const pageNumberStart = Number(settings.pageNumberStart ?? dom.documentPageNumberStart.value);
  try {
    const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}`, {
      method: 'PATCH',
      body: {
        outputPageSize,
        imageDpi,
        pageNumberPosition,
        pageNumberStart,
      }
    });
    activeProject = detail;
    activeProjectId = detail.project.id;
    updateProjectSummary(detail);
    dom.documentOutputPageSize.value = detail.project.outputPageSize || 'keep';
    dom.documentImageDpi.value = String(detail.project.imageDpi || 144);
    dom.documentPageNumberPosition.value = detail.project.pageNumberPosition || 'none';
    dom.documentPageNumberStart.value = String(detail.project.pageNumberStart || 1);
    syncOutputPreset();
    setProjectControls();
    setStatus(successMessage || 'Nastavenie výstupného PDF je uložené. Náhľady strán sa nemenia; presný formát sa uplatní pri vytvorení PDF.');
  } catch (error) {
    setStatus(error.message || 'Nastavenie výstupu sa nepodarilo uložiť.', { error: true });
    renderWorkspace();
  }
}

function applyDocumentOutputPreset() {
  const presetId = dom.documentOutputPreset.value;
  const preset = documentOutputPresets[presetId];
  if (!preset) {
    syncOutputPreset();
    return;
  }
  dom.documentOutputPageSize.value = preset.outputPageSize;
  dom.documentImageDpi.value = String(preset.imageDpi);
  void saveProjectOutputSettings(preset, 'Predvoľba výstupného PDF je uložená.');
}

async function restoreProjectHistory(direction) {
  if (!activeProject || historyMutationInFlight) return;
  window.clearTimeout(titleSaveTimer);
  const history = activeProject.history || {};
  const action = direction === 'undo' ? history.undoLabel : history.redoLabel;
  historyMutationInFlight = true;
  setProjectControls();
  try {
    const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/history/${direction}`, {
      method: 'POST', body: {}
    });
    clearPageSelection();
    applyProjectDetail(detail, direction === 'undo'
      ? `Vrátené späť: ${action || 'posledná úprava'}.`
      : `Zopakované: ${action || 'ďalšia úprava'}.`);
    await loadProjects();
  } catch (error) {
    setStatus(error.message || 'Históriu projektu sa nepodarilo obnoviť.', { error: true });
  } finally {
    historyMutationInFlight = false;
    setProjectControls();
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
  closeDocumentPreview();
  activeProjectId = '';
  activeProject = null;
  loadedSource = null;
  await loadProjects();
  setStatus('Projekt je odstránený.');
  renderWorkspace();
}

function triggerProjectDownload(blob, filename) {
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

async function exportProject() {
  if (!activeProject || projectTransferInFlight) return;
  projectTransferInFlight = true;
  setProjectControls();
  try {
    await saveProjectTitle();
    setStatus('Pripravujem prenosný projekt Dielne PDF...');
    const { blob, filename } = await downloadDocumentProject(activeProjectId);
    triggerProjectDownload(blob, filename);
    setStatus('Projekt Dielne PDF je pripravený na prenos.');
  } catch (error) {
    setStatus(error.message || 'Projekt Dielne PDF sa nepodarilo exportovať.', { error: true });
  } finally {
    projectTransferInFlight = false;
    setProjectControls();
  }
}

async function importProject(file) {
  if (!file || projectTransferInFlight) return;
  projectTransferInFlight = true;
  setProjectControls();
  try {
    await saveProjectTitle();
    setStatus('Importujem projekt Dielne PDF...');
    const detail = await uploadDocumentProject(file);
    await loadProjects();
    clearPageSelection();
    applyProjectDetail(
      detail,
      `Projekt „${detail.project.title}“ je importovaný ako samostatná pracovná kópia.`,
    );
  } catch (error) {
    setStatus(error.message || 'Projekt Dielne PDF sa nepodarilo importovať.', { error: true });
  } finally {
    projectTransferInFlight = false;
    setProjectControls();
  }
}

function closeDocumentBuildDialog() {
  if (dom.documentBuildDialog.open) dom.documentBuildDialog.close();
}

function openDocumentBuildDialog({ pageIds = [] } = {}) {
  if (!activeProject?.pages?.length) return;
  const pages = activeProject.pages || [];
  const availableIds = new Set(pages.map((page) => page.id));
  documentBuildPageIds = [...new Set(pageIds)].filter((pageId) => availableIds.has(pageId));
  const selectedCount = documentBuildPageIds.length;
  const buildingSelection = selectedCount > 0;
  const baseTitle = activeProject.project.title || 'Nový projekt PDF';
  dom.documentBuildTitle.textContent = buildingSelection ? 'Vytvoriť zdroj z vybraných strán' : 'Vytvoriť zdroj PDF';
  dom.documentBuildSubtitle.textContent = buildingSelection
    ? `${selectedCount} ${pageNumberWord(selectedCount)} sa skopíruje do nového zdroja. Projekt zostane nezmenený.`
    : 'Výsledok sa uloží medzi zdroje ako príloha.';
  dom.documentBuildSourceTitle.value = buildingSelection ? `${baseTitle} – výber strán` : baseTitle;
  dom.documentBuildSourceDescription.value = '';
  dom.documentBuildSourceTags.value = '';
  dom.documentBuildOpenSource.checked = false;
  dom.documentBuildSourceTitle.setCustomValidity('');
  dom.documentBuildSubmit.disabled = false;
  if (!dom.documentBuildDialog.open) dom.documentBuildDialog.showModal();
  window.setTimeout(() => {
    dom.documentBuildSourceTitle.focus();
    dom.documentBuildSourceTitle.select();
  }, 0);
}

function documentBuildTags() {
  return [...new Set(
    dom.documentBuildSourceTags.value
      .split(/[,;\n]/u)
      .map((tag) => tag.trim())
      .filter(Boolean)
  )];
}

function pageNumberWord(count) {
  const remainder = count % 100;
  if (remainder >= 11 && remainder <= 14) return 'strán';
  if (count % 10 === 1) return 'strana';
  if (count % 10 >= 2 && count % 10 <= 4) return 'strany';
  return 'strán';
}

function parsePageRange(value, pageCount) {
  const requested = String(value || '').trim();
  if (!requested) return { indices: [], error: 'Zadaj aspoň jednu stranu.' };
  const selected = new Set();
  for (const part of requested.split(/[;,]/u)) {
    const match = part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/u);
    if (!match) return { indices: [], error: `Rozsah „${part.trim() || '?'}“ nie je platný.` };
    const first = Number(match[1]);
    const last = Number(match[2] || match[1]);
    if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last) || first < 1 || last < first || last > pageCount) {
      return { indices: [], error: `Strany musia byť v rozsahu 1 až ${pageCount}.` };
    }
    for (let page = first; page <= last; page += 1) selected.add(page - 1);
  }
  return { indices: [...selected].sort((left, right) => left - right), error: '' };
}

function serializePageRange(indices) {
  const sorted = [...new Set(indices)].sort((left, right) => left - right);
  const ranges = [];
  let start = null;
  let previous = null;
  sorted.forEach((index) => {
    const page = index + 1;
    if (start === null) {
      start = page;
      previous = page;
      return;
    }
    if (page === previous + 1) {
      previous = page;
      return;
    }
    ranges.push(start === previous ? String(start) : `${start}-${previous}`);
    start = page;
    previous = page;
  });
  if (start !== null) ranges.push(start === previous ? String(start) : `${start}-${previous}`);
  return ranges.join(', ');
}

function refreshPagePicker() {
  const pageCount = Number(pagePickerStage?.pageCount || 0);
  const selection = parsePageRange(dom.documentPagePickerRange.value, pageCount);
  const invalid = Boolean(selection.error);
  dom.documentPagePickerStatus.textContent = invalid
    ? selection.error
    : `Vybrané: ${selection.indices.length} ${pageNumberWord(selection.indices.length)} z ${pageCount}.`;
  dom.documentPagePickerStatus.classList.toggle('is-error', invalid);
  dom.documentPagePickerConfirm.disabled = invalid;
  return selection;
}

function settlePagePicker(accepted) {
  const resolve = pagePickerResolver;
  pagePickerResolver = null;
  if (resolve) resolve(accepted);
}

function cancelPagePicker() {
  const stage = pagePickerStage;
  pagePickerStage = null;
  if (dom.documentPagePickerDialog.open) dom.documentPagePickerDialog.close();
  settlePagePicker(false);
  if (!stage) return;
  void apiRequest(`/documents/${encodeURIComponent(stage.projectId)}/input-stages/${encodeURIComponent(stage.id)}`, {
    method: 'DELETE'
  }).catch((error) => setStatus(error.message || 'Dočasný vstup sa nepodarilo upratať.', { error: true }));
}

function openPagePicker(stage) {
  if (pagePickerStage) cancelPagePicker();
  pagePickerStage = stage;
  dom.documentPagePickerSubtitle.textContent = `${stage.originalName} · ${stage.pageCount} ${pageNumberWord(Number(stage.pageCount || 0))}${stage.converted ? ' · prevedené do PDF' : ''}.`;
  dom.documentPagePickerRange.value = serializePageRange(
    Array.from({ length: Number(stage.pageCount || 0) }, (_, index) => index)
  );
  refreshPagePicker();
  if (!dom.documentPagePickerDialog.open) dom.documentPagePickerDialog.showModal();
  window.setTimeout(() => dom.documentPagePickerRange.focus(), 0);
  return new Promise((resolve) => { pagePickerResolver = resolve; });
}

function selectQuickPageRange(mode) {
  const pageCount = Number(pagePickerStage?.pageCount || 0);
  const current = parsePageRange(dom.documentPagePickerRange.value, pageCount);
  let indices = [];
  if (mode === 'all') indices = Array.from({ length: pageCount }, (_, index) => index);
  if (mode === 'even') indices = Array.from({ length: pageCount }, (_, index) => index).filter((index) => (index + 1) % 2 === 0);
  if (mode === 'odd') indices = Array.from({ length: pageCount }, (_, index) => index).filter((index) => (index + 1) % 2 === 1);
  if (mode === 'invert') {
    const selected = new Set(current.indices);
    indices = Array.from({ length: pageCount }, (_, index) => index).filter((index) => !selected.has(index));
  }
  dom.documentPagePickerRange.value = serializePageRange(indices);
  refreshPagePicker();
  dom.documentPagePickerRange.focus();
}

async function confirmPagePicker(event) {
  event.preventDefault();
  const stage = pagePickerStage;
  const selection = refreshPagePicker();
  if (!stage || selection.error) return;
  dom.documentPagePickerConfirm.disabled = true;
  try {
    const detail = await apiRequest(
      `/documents/${encodeURIComponent(stage.projectId)}/input-stages/${encodeURIComponent(stage.id)}/confirm`,
      { method: 'POST', body: { pageIndices: selection.indices } }
    );
    pagePickerStage = null;
    if (dom.documentPagePickerDialog.open) dom.documentPagePickerDialog.close();
    applyProjectDetail(detail, `${selection.indices.length} ${pageNumberWord(selection.indices.length)} boli pridané do projektu.`);
    await loadProjects();
    settlePagePicker(true);
  } catch (error) {
    setStatus(error.message || 'Vybrané strany sa nepodarilo pridať.', { error: true });
    dom.documentPagePickerConfirm.disabled = false;
  }
}

async function prepareUploadStage(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch(`/api/documents/${encodeURIComponent(activeProjectId)}/input-stages`, {
    method: 'POST', credentials: 'same-origin', body: form
  });
  const payload = await response.json();
  if (!response.ok) throw new ApiError(payload?.error || `Súbor ${file.name} sa nepodarilo pripraviť.`, response.status);
  return payload.stage;
}

async function addUploads(files) {
  if (!activeProjectId || !files.length) return;
  let added = 0;
  for (const [index, file] of files.entries()) {
    setStatus(files.length > 1 ? `Pripravujem súbor ${index + 1} z ${files.length}...` : 'Pripravujem vstup dokumentu...');
    const stage = await prepareUploadStage(file);
    if (await openPagePicker(stage)) added += 1;
    if (!isDocumentsPanelOpen()) break;
  }
  if (added) setStatus(`${formatCount(added, 'vstup bol pridaný', 'vstupov bolo pridaných')}.`);
}

async function addDroppedFiles(files) {
  if (!activeProject) {
    setStatus('Najprv vytvor alebo vyber projekt PDF.', { error: true });
    return;
  }
  const supported = files.filter(supportedFile);
  const unsupported = files.length - supported.length;
  if (!supported.length) {
    setStatus('Pridaj PDF, obrázok alebo podporovaný kancelársky dokument.', { error: true });
    return;
  }
  await addUploads(supported);
  if (unsupported) {
    const skipped = unsupported === 1 ? '1 súbor nebol pridaný' : `${unsupported} súbory neboli pridané`;
    setStatus(`${skipped}: formát Dielňa PDF nepodporuje.`, { error: true });
  }
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
  if (!(loadedSource.files || []).some(supportedFile)) setStatus('Vybraný zdroj nemá podporovanú prílohu pre Dielňu dokumentov.', { error: true });
  else setStatus('');
  setProjectControls();
}

async function addSourceFile() {
  const fileId = dom.documentSourceFileSelect.value;
  if (!activeProjectId || !fileId) return;
  const file = (loadedSource?.files || []).find((item) => item.id === fileId);
  setStatus(needsConversion(file) ? 'Príloha sa prevádza do PDF...' : 'Pripravujem prílohu zdroja...');
  const result = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/source-file-stages`, {
    method: 'POST', body: { fileId }
  });
  if (await openPagePicker(result.stage)) {
    sourcePickerOpen = false;
    syncInputsVisibility();
  }
}

async function rotatePage(page, delta) {
  const rotation = (Number(page.rotation || 0) + delta + 360) % 360;
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}`, {
    method: 'PATCH', body: { rotation }
  });
  applyProjectDetail(detail, 'Strana je otočená.');
}

function closeCropDialog() {
  cropPageIds = [];
  cropPointerDrag = null;
  if (dom.documentCropDialog.open) dom.documentCropDialog.close();
}

function cropPreviewUrl(page) {
  return `/api/documents/${encodeURIComponent(activeProjectId)}/pages/${encodeURIComponent(page.id)}/crop-preview?v=${encodeURIComponent(page.rotation || 0)}`;
}

function rawCropValues(page) {
  return {
    top: Number(page.cropTop || 0),
    right: Number(page.cropRight || 0),
    bottom: Number(page.cropBottom || 0),
    left: Number(page.cropLeft || 0),
  };
}

function displayCropValues(page, raw = rawCropValues(page)) {
  switch (Number(page.rotation || 0)) {
    case 90:
      return { top: raw.left, right: raw.top, bottom: raw.right, left: raw.bottom };
    case 180:
      return { top: raw.bottom, right: raw.left, bottom: raw.top, left: raw.right };
    case 270:
      return { top: raw.right, right: raw.bottom, bottom: raw.left, left: raw.top };
    default:
      return raw;
  }
}

function storageCropValues(page, displayed) {
  switch (Number(page.rotation || 0)) {
    case 90:
      return { top: displayed.right, right: displayed.bottom, bottom: displayed.left, left: displayed.top };
    case 180:
      return { top: displayed.bottom, right: displayed.left, bottom: displayed.top, left: displayed.right };
    case 270:
      return { top: displayed.left, right: displayed.top, bottom: displayed.right, left: displayed.bottom };
    default:
      return displayed;
  }
}

function setCropInputs(page) {
  setCropDisplayValues(displayCropValues(page));
}

function openCropDialog(page, pageIds = [page.id]) {
  const knownIds = new Set((activeProject?.pages || []).map((item) => item.id));
  cropPageIds = [...new Set(pageIds)].filter((pageId) => knownIds.has(pageId));
  if (!cropPageIds.includes(page.id)) cropPageIds.unshift(page.id);
  dom.documentCropSubtitle.textContent = cropPageIds.length === 1
    ? `${page.originalName || 'Strana'} · rám označuje viditeľnú časť výslednej strany.`
    : `${cropPageIds.length} vybraných strán · rám určí rovnaké viditeľné okraje po otočení každej strany.`;
  setCropInputs(page);
  dom.documentCropPreview.src = cropPreviewUrl(page);
  dom.documentCropPreview.alt = `Náhľad strany ${page.originalName || ''} na orezanie`;
  if (!dom.documentCropDialog.open) dom.documentCropDialog.showModal();
  window.setTimeout(() => dom.documentCropTop.focus(), 0);
}

function fitCropPreviewToDialog() {
  const { naturalWidth, naturalHeight } = dom.documentCropPreview;
  if (!naturalWidth || !naturalHeight) return;
  dom.documentCropPreviewCanvas.style.aspectRatio = `${naturalWidth} / ${naturalHeight}`;
  updateCropSelection();
}

function cropInputValue(input) {
  const value = Number(input.value);
  return Number.isInteger(value) ? value : 0;
}

function cropDisplayValuesFromInputs() {
  return {
    top: cropInputValue(dom.documentCropTop),
    right: cropInputValue(dom.documentCropRight),
    bottom: cropInputValue(dom.documentCropBottom),
    left: cropInputValue(dom.documentCropLeft),
  };
}

function clampCropValue(value) {
  return Math.round(Math.min(45, Math.max(0, value)));
}

function setCropDisplayValues(values) {
  dom.documentCropTop.value = String(clampCropValue(values.top));
  dom.documentCropRight.value = String(clampCropValue(values.right));
  dom.documentCropBottom.value = String(clampCropValue(values.bottom));
  dom.documentCropLeft.value = String(clampCropValue(values.left));
  updateCropSelection();
}

function updateCropSelection() {
  if (!cropPageIds.length) return;
  const values = cropDisplayValuesFromInputs();
  dom.documentCropSelection.style.top = `${clampCropValue(values.top)}%`;
  dom.documentCropSelection.style.right = `${clampCropValue(values.right)}%`;
  dom.documentCropSelection.style.bottom = `${clampCropValue(values.bottom)}%`;
  dom.documentCropSelection.style.left = `${clampCropValue(values.left)}%`;
}

function startCropDrag(event) {
  if (event.button !== 0 || !cropPageIds.length) return;
  const page = activeProject?.pages?.find((item) => item.id === cropPageIds[0]);
  const bounds = dom.documentCropPreviewCanvas.getBoundingClientRect();
  if (!page || bounds.width < 20 || bounds.height < 20) return;
  const handle = event.target.closest('[data-crop-handle]')?.dataset.cropHandle || 'move';
  cropPointerDrag = {
    pointerId: event.pointerId,
    handle,
    bounds,
    values: cropDisplayValuesFromInputs(),
    startX: event.clientX,
    startY: event.clientY,
  };
  dom.documentCropPreviewCanvas.setPointerCapture(event.pointerId);
  event.preventDefault();
}

function updateCropDrag(event) {
  if (!cropPointerDrag || event.pointerId !== cropPointerDrag.pointerId) return;
  const drag = cropPointerDrag;
  const deltaX = (event.clientX - drag.startX) / drag.bounds.width * 100;
  const deltaY = (event.clientY - drag.startY) / drag.bounds.height * 100;
  const values = { ...drag.values };
  if (drag.handle === 'move') {
    const horizontal = Math.min(45 - drag.values.left, drag.values.right, Math.max(drag.values.right - 45, -drag.values.left, deltaX));
    const vertical = Math.min(45 - drag.values.top, drag.values.bottom, Math.max(drag.values.bottom - 45, -drag.values.top, deltaY));
    values.left = drag.values.left + horizontal;
    values.right = drag.values.right - horizontal;
    values.top = drag.values.top + vertical;
    values.bottom = drag.values.bottom - vertical;
  } else {
    if (drag.handle.includes('top')) values.top = clampCropValue(drag.values.top + deltaY);
    if (drag.handle.includes('bottom')) values.bottom = clampCropValue(drag.values.bottom - deltaY);
    if (drag.handle.includes('left')) values.left = clampCropValue(drag.values.left + deltaX);
    if (drag.handle.includes('right')) values.right = clampCropValue(drag.values.right - deltaX);
  }
  setCropDisplayValues(values);
}

function endCropDrag(event) {
  if (!cropPointerDrag || (event && event.pointerId !== cropPointerDrag.pointerId)) return;
  cropPointerDrag = null;
}

async function saveCrop(event) {
  event.preventDefault();
  const pages = (activeProject?.pages || []).filter((item) => cropPageIds.includes(item.id));
  if (!pages.length) {
    closeCropDialog();
    return;
  }
  try {
    const displayed = cropDisplayValuesFromInputs();
    const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/batch`, {
      method: 'POST',
      body: {
        action: 'crop',
        pageIds: pages.map((page) => page.id),
        crops: pages.map((page) => {
          const crop = storageCropValues(page, displayed);
          return { pageId: page.id, cropTop: crop.top, cropRight: crop.right, cropBottom: crop.bottom, cropLeft: crop.left };
        }),
      }
    });
    applyProjectDetail(detail, pages.length === 1 ? 'Orezanie strany je uložené.' : `Orezanie je uložené pre ${pages.length} strán.`);
    closeCropDialog();
  } catch (error) {
    setStatus(error.message || 'Orezanie sa nepodarilo uložiť.', { error: true });
  }
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

async function applyBatchPageOperation(action, extra = {}) {
  if (batchPageMutationInFlight || !activeProjectId) return false;
  const pages = selectedPageItems();
  if (!pages.length) return false;
  batchPageMutationInFlight = true;
  updatePageSelectionUi();
  try {
    const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/batch`, {
      method: 'POST',
      body: { action, pageIds: pages.map((page) => page.id), ...extra },
    });
    applyProjectDetail(detail);
    if (action === 'duplicate' || action === 'delete') clearPageSelection();
    await loadProjects();
    return true;
  } catch (error) {
    setStatus(error.message || 'Hromadná úprava strán sa nepodarila.', { error: true });
    return false;
  } finally {
    batchPageMutationInFlight = false;
    updatePageSelectionUi();
  }
}

async function rotateSelectedPages(delta) {
  const count = selectedPageItems().length;
  if (!count) return;
  if (await applyBatchPageOperation('rotate', { delta })) {
    setStatus(`${count} ${pageNumberWord(count)} ${count === 1 ? 'je otočená.' : 'sú otočené.'}`);
  }
}

function cropSelectedPages() {
  const pages = selectedPageItems();
  if (!pages.length) return;
  openCropDialog(pages[0], pages.map((page) => page.id));
}

async function duplicateSelectedPages() {
  const count = selectedPageItems().length;
  if (!count) return;
  if (await applyBatchPageOperation('duplicate')) {
    setStatus(`${count} ${pageNumberWord(count)} ${count === 1 ? 'je skopírovaná.' : 'sú skopírované.'}`);
  }
}

async function deleteSelectedPages() {
  const count = selectedPageItems().length;
  if (!count) return;
  const message = count === 1
    ? 'Odstrániť vybranú stranu z výsledného dokumentu? Originál zostane nezmenený.'
    : `Odstrániť ${count} vybraných strán z výsledného dokumentu? Originály zostanú nezmenené.`;
  if (!window.confirm(message)) return;
  if (await applyBatchPageOperation('delete')) {
    setStatus(`${count} ${pageNumberWord(count)} ${count === 1 ? 'je odstránená.' : 'sú odstránené.'}`);
  }
}

async function deleteInput(input) {
  if (!window.confirm(`Odstrániť dokument „${input.originalName || 'Dokument'}“ z projektu aj so všetkými jeho stranami? Pôvodný zdroj zostane nezmenený.`)) return;
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/inputs/${encodeURIComponent(input.id)}`, {
    method: 'DELETE'
  });
  applyProjectDetail(detail, 'Dokument a jeho strany sú odstránené z projektu.');
  await loadProjects();
}

async function moveSelectedPages(beforeId = '') {
  if (!activeProject || !draggingPageIds.length) return;
  const pages = activeProject.pages || [];
  const selected = pages.filter((page) => draggingPageIds.includes(page.id));
  if (!selected.length || (beforeId && selected.some((page) => page.id === beforeId))) return;
  const remaining = pages.filter((page) => !draggingPageIds.includes(page.id));
  const insertAt = beforeId ? remaining.findIndex((page) => page.id === beforeId) : remaining.length;
  if (insertAt < 0) return;
  const reordered = [...remaining];
  reordered.splice(insertAt, 0, ...selected);
  const ids = reordered.map((page) => page.id);
  if (ids.every((pageId, index) => pageId === pages[index]?.id)) return;
  const detail = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/pages/order`, {
    method: 'PUT', body: { pageIds: ids }
  });
  applyProjectDetail(detail, selected.length === 1 ? 'Poradie strany je uložené.' : 'Poradie vybraných strán je uložené.');
  await loadProjects();
}

async function buildSource(data) {
  if (!activeProject?.pages?.length) return;
  const cleanTitle = String(data?.title || '').trim();
  if (!cleanTitle) throw new Error('Zdroj potrebuje názov.');
  const pageIds = Array.isArray(data?.pageIds) ? data.pageIds.filter(Boolean) : [];
  documentBuildInFlight = true;
  setProjectControls();
  updatePageSelectionUi();
  setStatus(pageIds.length ? 'Vytváram zdroj z vybraných strán...' : 'Vytváram nový PDF zdroj...');
  try {
    const result = await apiRequest(`/documents/${encodeURIComponent(activeProjectId)}/build`, {
      method: 'POST',
      body: {
        title: cleanTitle,
        description: String(data?.description || '').trim(),
        tags: Array.isArray(data?.tags) ? data.tags : [],
        ...(pageIds.length ? { pageIds } : {}),
      }
    });
    const source = result.source;
    setStatus(pageIds.length
      ? `Zdroj „${source.title}“ je vytvorený z ${pageIds.length} ${pageNumberWord(pageIds.length)}.`
      : `Zdroj „${source.title}“ je vytvorený.`);
    return source;
  } catch (error) {
    setStatus(error.message || 'PDF zdroj sa nepodarilo vytvoriť.', { error: true });
    throw error;
  } finally {
    documentBuildInFlight = false;
    setProjectControls();
    updatePageSelectionUi();
  }
}

async function submitDocumentBuild(event) {
  event.preventDefault();
  const title = dom.documentBuildSourceTitle.value.trim();
  if (!title) {
    dom.documentBuildSourceTitle.setCustomValidity('Zadaj názov zdroja.');
    dom.documentBuildSourceTitle.reportValidity();
    return;
  }
  dom.documentBuildSourceTitle.setCustomValidity('');
  const openSource = dom.documentBuildOpenSource.checked;
  const pageIds = documentBuildPageIds.slice();
  dom.documentBuildSubmit.disabled = true;
  try {
    const source = await buildSource({
      title,
      description: dom.documentBuildSourceDescription.value,
      tags: documentBuildTags(),
      pageIds,
    });
    closeDocumentBuildDialog();
    if (openSource && source) {
      window.dispatchEvent(new CustomEvent('source-open-request', { detail: { sourceId: source.id } }));
    }
  } catch {
    // The workshop status already carries the server's validation message.
  } finally {
    dom.documentBuildSubmit.disabled = false;
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
  cancelPagePicker();
  closeDocumentBuildDialog();
  setWorkspaceFileDropActive(false);
  closeDocumentPreview();
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
  const storedPreviewSize = Number(localStorage.getItem(storageKeys.documentPreviewInlineSize));
  if (Number.isFinite(storedPreviewSize) && storedPreviewSize > 0) {
    documentPreviewInlineSize = storedPreviewSize;
    document.documentElement.style.setProperty('--document-preview-inline-size', `${storedPreviewSize}px`);
  }
  dom.documentProjectCreate.addEventListener('click', () => void createProject().catch((error) => setStatus(error.message, { error: true })));
  dom.documentProjectDelete.addEventListener('click', () => void deleteProject().catch((error) => setStatus(error.message, { error: true })));
  dom.documentProjectUndo.addEventListener('click', () => void restoreProjectHistory('undo'));
  dom.documentProjectRedo.addEventListener('click', () => void restoreProjectHistory('redo'));
  dom.documentProjectImport.addEventListener('click', () => dom.documentProjectImportInput.click());
  dom.documentProjectImportInput.addEventListener('change', () => {
    const [file] = dom.documentProjectImportInput.files || [];
    dom.documentProjectImportInput.value = '';
    void importProject(file);
  });
  dom.documentProjectExport.addEventListener('click', () => void exportProject());
  dom.documentPreviewButton.addEventListener('click', () => {
    if (isDocumentPreviewOpen()) closeDocumentPreview();
    else openDocumentPreview();
  });
  dom.documentPreviewClose.addEventListener('click', closeDocumentPreview);
  dom.documentPreviewResizeHandle.addEventListener('pointerdown', startDocumentPreviewResize);
  dom.documentPreviewResizeHandle.addEventListener('pointermove', moveDocumentPreviewResize);
  dom.documentPreviewResizeHandle.addEventListener('pointerup', finishDocumentPreviewResize);
  dom.documentPreviewResizeHandle.addEventListener('pointercancel', finishDocumentPreviewResize);
  dom.documentPreviewResizeHandle.addEventListener('keydown', resizeDocumentPreviewFromKeyboard);
  window.addEventListener('resize', refreshDocumentPreviewResizeHandle);
  dom.documentProjectTitle.addEventListener('input', () => {
    queueTitleSave();
    setProjectControls();
  });
  dom.documentProjectTitle.addEventListener('blur', () => void saveProjectTitle());
  dom.documentOutputPreset.addEventListener('change', applyDocumentOutputPreset);
  dom.documentOutputPageSize.addEventListener('change', () => void saveProjectOutputSettings());
  dom.documentImageDpi.addEventListener('change', () => void saveProjectOutputSettings());
  dom.documentPageNumberPosition.addEventListener('change', () => {
    setProjectControls();
    void saveProjectOutputSettings();
  });
  dom.documentPageNumberStart.addEventListener('change', () => void saveProjectOutputSettings());
  dom.documentUploadButton.addEventListener('click', () => dom.documentUploadInput.click());
  dom.documentUploadInput.addEventListener('change', () => {
    const files = [...dom.documentUploadInput.files];
    dom.documentUploadInput.value = '';
    void addUploads(files).catch((error) => setStatus(error.message || 'Súbory sa nepodarilo pridať.', { error: true }));
  });
  dom.documentsWorkspace.addEventListener('dragenter', (event) => {
    if (!isFileDrag(event) || !activeProject) return;
    event.preventDefault();
    setWorkspaceFileDropActive(true);
  });
  dom.documentsWorkspace.addEventListener('dragover', (event) => {
    if (!isFileDrag(event) || !activeProject) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    setWorkspaceFileDropActive(true);
  });
  dom.documentsWorkspace.addEventListener('dragleave', (event) => {
    const nextTarget = event.relatedTarget;
    if (!workspaceFileDropActive || (nextTarget instanceof Node && dom.documentsWorkspace.contains(nextTarget))) return;
    setWorkspaceFileDropActive(false);
  });
  dom.documentsWorkspace.addEventListener('drop', (event) => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    setWorkspaceFileDropActive(false);
    const files = [...(event.dataTransfer?.files || [])];
    void addDroppedFiles(files).catch((error) => setStatus(error.message || 'Súbory sa nepodarilo pridať.', { error: true }));
  });
  dom.documentSourceSelect.addEventListener('change', () => void loadSourceFiles().catch((error) => setStatus(error.message, { error: true })));
  dom.documentSourceFileSelect.addEventListener('change', setProjectControls);
  dom.documentSourceAdd.addEventListener('click', () => void addSourceFile().catch((error) => setStatus(error.message, { error: true })));
  dom.documentInputsToggle.addEventListener('click', () => {
    if (!activeProject?.inputs?.length) return;
    inputsCollapsed = !inputsCollapsed;
    if (inputsCollapsed) sourcePickerOpen = false;
    localStorage.setItem(storageKeys.documentInputsCollapsed, String(inputsCollapsed));
    syncInputsVisibility();
  });
  dom.documentSourceToggle.addEventListener('click', () => {
    if (!activeProject) return;
    sourcePickerOpen = !sourcePickerOpen;
    syncInputsVisibility();
    if (sourcePickerOpen) window.setTimeout(() => dom.documentSourceSelect.focus(), 0);
  });
  dom.documentBuildButton.addEventListener('click', openDocumentBuildDialog);
  dom.documentBuildClose.addEventListener('click', closeDocumentBuildDialog);
  dom.documentBuildForm.addEventListener('submit', (event) => void submitDocumentBuild(event));
  dom.documentBuildDialog.addEventListener('close', () => {
    dom.documentBuildSourceTitle.setCustomValidity('');
    documentBuildPageIds = [];
  });
  installDialogBackdropClose(dom.documentBuildDialog, closeDocumentBuildDialog);
  dom.documentPageSelectAll.addEventListener('click', selectAllPages);
  dom.documentPageClearSelection.addEventListener('click', clearPageSelection);
  dom.documentPageRotateLeft.addEventListener('click', () => void rotateSelectedPages(-90));
  dom.documentPageRotateRight.addEventListener('click', () => void rotateSelectedPages(90));
  dom.documentPageCropSelection.addEventListener('click', cropSelectedPages);
  dom.documentPageDuplicateSelection.addEventListener('click', () => void duplicateSelectedPages());
  dom.documentPageBuildSelection.addEventListener('click', () => {
    openDocumentBuildDialog({ pageIds: selectedPageItems().map((page) => page.id) });
  });
  dom.documentPageDeleteSelection.addEventListener('click', () => void deleteSelectedPages());
  dom.documentPagesGrid.addEventListener('dragover', (event) => {
    if (!draggingPageIds.length || event.target !== dom.documentPagesGrid) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    dom.documentPagesGrid.classList.add('is-drop-target');
  });
  dom.documentPagesGrid.addEventListener('dragleave', (event) => {
    if (event.target === dom.documentPagesGrid) dom.documentPagesGrid.classList.remove('is-drop-target');
  });
  dom.documentPagesGrid.addEventListener('drop', (event) => {
    if (!draggingPageIds.length || event.target !== dom.documentPagesGrid) return;
    event.preventDefault();
    dom.documentPagesGrid.classList.remove('is-drop-target');
    void moveSelectedPages();
  });
  dom.documentPagesGrid.addEventListener('wheel', rotateSelectedPagesFromWheel, { passive: false });
  dom.documentCropClose.addEventListener('click', closeCropDialog);
  dom.documentCropReset.addEventListener('click', () => {
    setCropDisplayValues({ top: 0, right: 0, bottom: 0, left: 0 });
    dom.documentCropTop.focus();
  });
  [dom.documentCropTop, dom.documentCropRight, dom.documentCropBottom, dom.documentCropLeft].forEach((input) => {
    input.addEventListener('input', updateCropSelection);
  });
  dom.documentCropPreviewCanvas.addEventListener('pointerdown', startCropDrag);
  dom.documentCropPreviewCanvas.addEventListener('pointermove', updateCropDrag);
  dom.documentCropPreviewCanvas.addEventListener('pointerup', endCropDrag);
  dom.documentCropPreviewCanvas.addEventListener('pointercancel', endCropDrag);
  dom.documentCropPreview.addEventListener('load', fitCropPreviewToDialog);
  dom.documentCropForm.addEventListener('submit', (event) => void saveCrop(event));
  dom.documentCropDialog.addEventListener('close', () => { cropPageIds = []; });
  installDialogBackdropClose(dom.documentCropDialog, closeCropDialog);
  dom.documentPagePickerRange.addEventListener('input', refreshPagePicker);
  document.querySelectorAll('[data-document-page-selection]').forEach((button) => {
    button.addEventListener('click', () => selectQuickPageRange(button.dataset.documentPageSelection));
  });
  dom.documentPagePickerClose.addEventListener('click', cancelPagePicker);
  dom.documentPagePickerCancel.addEventListener('click', cancelPagePicker);
  dom.documentPagePickerForm.addEventListener('submit', (event) => void confirmPagePicker(event));
  dom.documentPagePickerDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    cancelPagePicker();
  });
  installDialogBackdropClose(dom.documentPagePickerDialog, cancelPagePicker);
  document.addEventListener('keydown', (event) => {
    if (
      event.key !== 'Delete'
      || !isDocumentsPanelOpen()
      || hasOpenApplicationDialog()
      || isEditableTarget(event.target)
      || !selectedPageItems().length
    ) return;
    event.preventDefault();
    void deleteSelectedPages();
  });
  window.addEventListener('sources-changed', () => {
    if (isDocumentsPanelOpen()) void loadSources().catch(() => {});
  });
}
