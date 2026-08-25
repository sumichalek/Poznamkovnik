import { apiRequest } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';
import { updateTopbarVisibility } from './topbar.js';

let projects = [];
let languages = [];
let runtime = { available: false, message: 'Skúšobňa sa pripravuje.' };
let activeProjectId = '';
let activeFileId = '';
let selectedFolderId = '';
let expandedFolderIds = new Set();
let pendingDevelopmentItemKind = 'file';
let panelPinned = false;
let focusMode = false;
let consoleExpanded = false;
let projectTitleBaseline = '';
let fileDraftBaseline = '';
let standardInput = '';
let saveTimer = 0;
let operationCount = 0;
let idleResolvers = [];

function runOperation(operation) {
  operationCount += 1;
  return Promise.resolve()
    .then(operation)
    .finally(() => {
      operationCount -= 1;
      if (!operationCount) {
        idleResolvers.forEach((resolve) => resolve());
        idleResolvers = [];
      }
    });
}

export function waitForDevelopmentOperations() {
  if (!operationCount) return Promise.resolve();
  return new Promise((resolve) => idleResolvers.push(resolve));
}

function activeProject() {
  return projects.find((project) => project.id === activeProjectId) || null;
}

function activeFile() {
  return activeProject()?.files?.find((file) => file.id === activeFileId && file.kind === 'file') || null;
}

function languageLabel(languageId) {
  return languages.find((language) => language.id === languageId)?.label || languageId || 'Neznámy jazyk';
}

function languageRuntime(languageId) {
  return runtime.languages?.[languageId] || {
    available: languageId === 'c' && Boolean(runtime.available),
    message: runtime.message || 'Skúšobňa nie je dostupná.'
  };
}

function projectFiles(project) {
  return (project?.files || []).filter((file) => file.kind === 'file');
}

function projectFolders(project) {
  return (project?.files || []).filter((item) => item.kind === 'folder');
}

function projectItem(project, itemId) {
  return (project?.files || []).find((item) => item.id === itemId) || null;
}

function projectChildren(project, parentId = '') {
  return (project?.files || [])
    .filter((item) => String(item.parentId || '') === parentId)
    .sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === 'folder' ? -1 : 1;
      const position = Number(left.position || 0) - Number(right.position || 0);
      return position || String(left.title).localeCompare(String(right.title), 'sk', { sensitivity: 'base' });
    });
}

function folderPath(project, folderId = selectedFolderId) {
  if (!folderId) return '';
  const names = [];
  const visited = new Set();
  let current = projectItem(project, folderId);
  while (current && current.kind === 'folder' && !visited.has(current.id)) {
    names.unshift(current.title);
    visited.add(current.id);
    current = projectItem(project, current.parentId);
  }
  return names.join(' / ');
}

function folderTargetLabel(project) {
  return folderPath(project) || 'koreň projektu';
}

function expandFolderAncestors(project, folderId) {
  const visited = new Set();
  let current = projectItem(project, folderId);
  while (current && current.kind === 'folder' && !visited.has(current.id)) {
    expandedFolderIds.add(current.id);
    visited.add(current.id);
    current = projectItem(project, current.parentId);
  }
}

function activeFileSnapshot() {
  return JSON.stringify({ title: dom.developmentFileTitle.value, content: dom.developmentCode.value });
}

function fitProjectTitle() {
  const characters = Math.max(8, Math.min(28, dom.developmentProjectTitle.value.trim().length + 2));
  dom.developmentProjectTitle.style.width = `${characters}ch`;
}

function setPanelOpen(open) {
  dom.developmentPanel.classList.toggle('is-open', open);
  dom.developmentPanel.setAttribute('aria-hidden', String(!open));
  dom.developmentButton.setAttribute('aria-expanded', String(open));
  updateTopbarVisibility();
}

function setFocusMode(enabled) {
  focusMode = enabled;
  dom.developmentPanel.classList.toggle('is-focus-mode', enabled);
  dom.developmentFocusMode.setAttribute('aria-pressed', String(enabled));
  dom.developmentFocusMode.title = enabled ? 'Zobraziť projekty' : 'Celá plocha';
  dom.developmentFocusMode.setAttribute(
    'aria-label',
    enabled ? 'Zobraziť zoznam projektov' : 'Otvoriť editor na celej ploche'
  );
  setAppIcon(dom.developmentFocusMode.querySelector('.app-icon'), enabled ? 'minimize' : 'maximize');
}

function setConsoleExpanded(expanded) {
  consoleExpanded = expanded;
  dom.developmentConsoleSection.classList.toggle('is-collapsed', !expanded);
  dom.developmentProjectEditor.classList.toggle('is-console-collapsed', !expanded);
  dom.developmentConsoleToggle.setAttribute('aria-expanded', String(expanded));
  dom.developmentConsoleToggle.title = expanded ? 'Zbaliť konzolu' : 'Zobraziť konzolu';
  dom.developmentConsoleToggle.setAttribute('aria-label', expanded ? 'Zbaliť konzolu' : 'Zobraziť konzolu');
  setAppIcon(dom.developmentConsoleToggle.querySelector('.app-icon'), expanded ? 'chevron-down' : 'terminal');
}

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
}

function setResizeValue(property, value, handle) {
  dom.developmentPanel.style.setProperty(property, `${Math.round(value)}px`);
  handle?.setAttribute('aria-valuenow', String(Math.round(value)));
}

function installResizeHandle(handle, createSession) {
  if (!handle || handle.dataset.resizeReady) return;
  handle.dataset.resizeReady = 'true';
  handle.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    const session = createSession(event);
    if (!session) return;
    event.preventDefault();
    handle.classList.add('is-resizing');
    dom.developmentPanel.classList.add('is-resizing');
    handle.setPointerCapture(event.pointerId);

    const finish = () => {
      handle.classList.remove('is-resizing');
      dom.developmentPanel.classList.remove('is-resizing');
      if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', finish);
      handle.removeEventListener('pointercancel', finish);
    };
    const move = (moveEvent) => session.move(moveEvent);
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', finish);
    handle.addEventListener('pointercancel', finish);
  });
}

function initializePaneResizers() {
  installResizeHandle(dom.developmentSidebarResize, () => {
    const panelRect = dom.developmentPanel.getBoundingClientRect();
    const minimum = 168;
    const maximum = Math.min(440, panelRect.width - 520);
    return {
      move(event) {
        setResizeValue('--development-sidebar-size', clamp(event.clientX - panelRect.left, minimum, maximum), dom.developmentSidebarResize);
      }
    };
  });

  installResizeHandle(dom.developmentEditorResize, () => {
    if (!consoleExpanded) return null;
    const gridRect = dom.developmentEditorResize.parentElement.getBoundingClientRect();
    const minimum = 120;
    const maximum = gridRect.height - 180 - 8;
    return {
      move(event) {
        setResizeValue('--development-console-size', clamp(gridRect.bottom - event.clientY, minimum, maximum), dom.developmentEditorResize);
      }
    };
  });

  installResizeHandle(dom.developmentInputResize, () => {
    const consoleRect = dom.developmentConsoleSection.getBoundingClientRect();
    const minimum = 120;
    const maximum = consoleRect.width - 16 - 180 - 180;
    return {
      move(event) {
        setResizeValue('--development-input-size', clamp(event.clientX - consoleRect.left, minimum, maximum), dom.developmentInputResize);
      }
    };
  });

  installResizeHandle(dom.developmentCompileResize, () => {
    const consoleRect = dom.developmentConsoleSection.getBoundingClientRect();
    const compileRect = dom.developmentCompilePanel.getBoundingClientRect();
    const inputWidth = dom.developmentConsoleInputPanel.getBoundingClientRect().width;
    const minimum = 180;
    const maximum = consoleRect.width - inputWidth - 16 - 180;
    return {
      move(event) {
        setResizeValue('--development-compile-size', clamp(event.clientX - compileRect.left, minimum, maximum), dom.developmentCompileResize);
      }
    };
  });
}

function setRuntimeStatus(status) {
  runtime = status || { available: false, message: 'Skúšobňa nie je dostupná.' };
  const availableLanguages = Object.entries(runtime.languages || {})
    .filter(([, item]) => item?.available)
    .map(([language]) => languageLabel(language));
  const message = availableLanguages.length
    ? `Pripravené: ${availableLanguages.join(', ')}`
    : runtime.message || 'Skúšobňa nie je dostupná.';
  dom.developmentRuntimeStatus.replaceChildren(createAppIcon('terminal'), document.createTextNode(message));
  dom.developmentRuntimeStatus.classList.toggle('is-ready', availableLanguages.length > 0);
  dom.developmentRuntimeStatus.title = availableLanguages.length ? message : runtime.message || '';
}

function setRunStatus(phase) {
  const value = String(phase || 'Pripravená');
  const lowerCaseValue = value.toLocaleLowerCase('sk');
  const state = lowerCaseValue.includes('chyba')
    ? 'error'
    : lowerCaseValue.includes('preklad')
      ? 'working'
      : lowerCaseValue === 'hotovo'
        ? 'success'
        : 'ready';
  dom.developmentConsoleStatus.textContent = value;
  dom.developmentConsoleStatus.dataset.state = state;
  dom.developmentConsoleStatus.setAttribute('aria-label', `Skúšobňa: ${value}`);
  dom.developmentConsoleStatus.title = `Skúšobňa: ${value}`;
}

function setConsole({ phase = 'Pripravená', compile = 'Projekt ešte nebol spustený.', compileMeta = '', output = 'Výstup programu sa zobrazí tu.', outputMeta = '' } = {}) {
  setRunStatus(phase);
  dom.developmentCompileOutput.textContent = compile;
  dom.developmentCompileMeta.textContent = compileMeta;
  dom.developmentRunOutput.textContent = output;
  dom.developmentRunMeta.textContent = outputMeta;
}

function ensureActiveFile(project = activeProject()) {
  if (!project) {
    activeFileId = '';
    selectedFolderId = '';
    return;
  }
  const files = projectFiles(project);
  if (!files.some((file) => file.id === activeFileId)) {
    activeFileId = files.find((file) => file.id === project.entryFileId)?.id || files[0]?.id || '';
  }
  if (selectedFolderId && !projectFolders(project).some((folder) => folder.id === selectedFolderId)) {
    selectedFolderId = '';
  }
}

function renderProjects() {
  dom.developmentProjectDelete.disabled = !activeProject();
  dom.developmentProjectsList.replaceChildren();
  projects.forEach((project) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-project-item';
    button.classList.toggle('is-active', project.id === activeProjectId);
    button.setAttribute('aria-pressed', String(project.id === activeProjectId));
    button.append(createAppIcon('code'));
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = project.title;
    const meta = document.createElement('small');
    meta.textContent = `${languageLabel(project.language)} · ${projectFiles(project).length} súborov`;
    copy.append(title, meta);
    button.append(copy);
    button.addEventListener('click', () => void selectProject(project.id));
    dom.developmentProjectsList.append(button);
  });
  if (!projects.length) {
    const empty = document.createElement('p');
    empty.className = 'development-projects-empty';
    empty.textContent = 'Zatiaľ tu nie je žiadny projekt.';
    dom.developmentProjectsList.append(empty);
  }
  renderFileTree();
}

function renderFileTree() {
  const project = activeProject();
  dom.developmentFileTree.replaceChildren();
  dom.developmentFileBrowserPath.textContent = project ? folderPath(project) : '';
  dom.developmentFileTreeRoot.hidden = !project || !selectedFolderId;
  if (!project) {
    const empty = document.createElement('p');
    empty.className = 'development-file-tree-empty';
    empty.textContent = 'Vyber projekt.';
    dom.developmentFileTree.append(empty);
    return;
  }

  const appendRow = (item, depth) => {
    const row = document.createElement('div');
    row.className = 'development-file-tree-row';
    row.style.setProperty('--development-tree-indent', `${depth * 14}px`);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-file-tree-item';
    button.setAttribute('role', 'treeitem');
    const isFolder = item.kind === 'folder';
    const isExpanded = isFolder && expandedFolderIds.has(item.id);
    const isSelectedFolder = isFolder && item.id === selectedFolderId;
    button.classList.toggle('is-active', item.id === activeFileId);
    button.classList.toggle('is-selected-folder', isSelectedFolder);
    if (isFolder) button.setAttribute('aria-expanded', String(isExpanded));
    if (isFolder) button.append(createAppIcon(isExpanded ? 'chevron-down' : 'chevron-right'));
    else {
      const spacer = document.createElement('span');
      spacer.className = 'development-file-tree-spacer';
      spacer.setAttribute('aria-hidden', 'true');
      button.append(spacer);
    }
    button.append(createAppIcon(isFolder ? 'folder' : 'file'));
    const label = document.createElement('span');
    label.textContent = item.title;
    button.append(label);
    button.addEventListener('click', () => {
      if (isFolder) {
        const wasSelected = selectedFolderId === item.id;
        selectedFolderId = item.id;
        if (wasSelected) {
          if (expandedFolderIds.has(item.id)) expandedFolderIds.delete(item.id);
          else expandedFolderIds.add(item.id);
        } else {
          expandedFolderIds.add(item.id);
        }
        renderFileTree();
        return;
      }
      void selectFile(item.id);
    });
    row.append(button);

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'development-file-tree-delete panel-icon-button danger';
    remove.title = isFolder ? 'Odstrániť priečinok' : 'Odstrániť súbor';
    remove.setAttribute('aria-label', remove.title);
    remove.disabled = !isFolder && projectFiles(project).length <= 1;
    remove.append(createAppIcon('trash'));
    remove.addEventListener('click', (event) => {
      event.stopPropagation();
      void deleteProjectItem(item);
    });
    row.append(remove);
    dom.developmentFileTree.append(row);

    if (isFolder && isExpanded) {
      projectChildren(project, item.id).forEach((child) => appendRow(child, depth + 1));
    }
  };

  projectChildren(project).forEach((item) => appendRow(item, 0));
}

function renderEditor() {
  const project = activeProject();
  const file = activeFile();
  const hasProject = Boolean(project && file);
  dom.developmentProjectEditor.hidden = !hasProject;
  dom.developmentWorkspace.querySelector('.development-empty').hidden = Boolean(projects.length);
  if (!hasProject) return;

  dom.developmentProjectTitle.value = project.title;
  fitProjectTitle();
  projectTitleBaseline = project.title;
  dom.developmentProjectLanguage.textContent = languageLabel(project.language);
  dom.developmentProjectLanguage.dataset.language = project.language;
  dom.developmentFileTitle.value = file.title;
  dom.developmentCode.value = file.content;
  dom.developmentInput.value = standardInput;
  fileDraftBaseline = activeFileSnapshot();
  dom.developmentFileDelete.disabled = projectFiles(project).length <= 1;
  const languageStatus = languageRuntime(project.language);
  const canRun = Boolean(languageStatus.available);
  dom.developmentRun.disabled = !canRun;
  dom.developmentRun.title = canRun ? 'Preložiť a spustiť projekt (Ctrl+Enter)' : languageStatus.message;

  dom.developmentFileTabs.replaceChildren();
  projectFiles(project).forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-file-tab';
    button.classList.toggle('is-active', item.id === activeFileId);
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', String(item.id === activeFileId));
    button.append(createAppIcon('file'));
    const label = document.createElement('span');
    label.textContent = item.title;
    button.append(label);
    button.addEventListener('click', () => void selectFile(item.id));
    dom.developmentFileTabs.append(button);
  });
}

function replaceProject(project) {
  const index = projects.findIndex((item) => item.id === project.id);
  if (index >= 0) projects[index] = project;
  else projects.unshift(project);
  activeProjectId = project.id;
  ensureActiveFile(project);
  renderProjects();
  renderEditor();
}

async function loadWorkspace() {
  const workspace = await apiRequest('/development');
  projects = workspace.projects || [];
  expandedFolderIds = new Set(projects.flatMap((project) => projectFolders(project).map((folder) => folder.id)));
  languages = workspace.languages || [];
  setRuntimeStatus(workspace.runtime);
  if (!projects.some((project) => project.id === activeProjectId)) activeProjectId = projects[0]?.id || '';
  ensureActiveFile();
  renderProjects();
  renderEditor();
}

async function selectProject(projectId) {
  if (projectId === activeProjectId) return;
  if (!(await saveDevelopmentChanges())) return;
  activeProjectId = projectId;
  selectedFolderId = '';
  ensureActiveFile();
  standardInput = '';
  setConsole();
  renderProjects();
  renderEditor();
}

async function selectFile(fileId) {
  if (fileId === activeFileId) {
    const currentFile = activeFile();
    selectedFolderId = String(currentFile?.parentId || '');
    expandFolderAncestors(activeProject(), selectedFolderId);
    renderProjects();
    return;
  }
  if (!(await saveActiveFile())) return;
  activeFileId = fileId;
  const file = activeFile();
  selectedFolderId = String(file?.parentId || '');
  expandFolderAncestors(activeProject(), selectedFolderId);
  setConsole();
  renderProjects();
  renderEditor();
}

function populateProjectLanguages() {
  dom.developmentProjectLanguageInput.replaceChildren();
  languages.forEach((language) => {
    const option = document.createElement('option');
    option.value = language.id;
    const status = languageRuntime(language.id);
    option.textContent = status.available ? language.label : `${language.label} · zatiaľ nespustiteľný`;
    option.title = status.message || '';
    dom.developmentProjectLanguageInput.append(option);
  });
}

function openProjectDialog() {
  populateProjectLanguages();
  dom.developmentProjectForm.reset();
  dom.developmentProjectNameInput.value = 'Nový projekt';
  dom.developmentProjectLanguageInput.value = 'c';
  dom.developmentProjectFormStatus.textContent = '';
  dom.developmentProjectDialog.showModal();
  window.setTimeout(() => dom.developmentProjectNameInput.select(), 0);
}

async function openFileDialog(kind = 'file') {
  const project = activeProject();
  if (!project || !(await saveDevelopmentChanges())) return;
  pendingDevelopmentItemKind = kind;
  const isFolder = kind === 'folder';
  const filename = languages.find((language) => language.id === project.language)?.filename || 'novy-subor.txt';
  const extension = filename.includes('.') ? filename.slice(filename.lastIndexOf('.')) : '.txt';
  dom.developmentFileForm.reset();
  dom.developmentFileDialogTitle.textContent = isFolder ? 'Nový priečinok' : 'Nový súbor';
  dom.developmentFileDialogDescription.textContent = isFolder
    ? `Pridá sa do: ${folderTargetLabel(project)}.`
    : `Pridá sa do: ${folderTargetLabel(project)}. Prípona určí typ súboru.`;
  dom.developmentFileNameLabel.textContent = isFolder ? 'Názov priečinka' : 'Názov súboru';
  dom.developmentFileNameInput.value = isFolder ? 'Nový priečinok' : `novy-subor${extension}`;
  const submitIcon = dom.developmentFileSubmit.querySelector('.app-icon');
  setAppIcon(submitIcon, isFolder ? 'folder-plus' : 'file');
  dom.developmentFileSubmit.querySelector('span:last-child').textContent = isFolder ? 'Pridať priečinok' : 'Pridať súbor';
  dom.developmentFileFormStatus.textContent = '';
  dom.developmentFileDialog.showModal();
  window.setTimeout(() => dom.developmentFileNameInput.select(), 0);
}

async function createProject(event) {
  event.preventDefault();
  const title = dom.developmentProjectNameInput.value.trim();
  if (!title) return;
  const submitter = dom.developmentProjectForm.querySelector('button[type="submit"]');
  submitter.disabled = true;
  dom.developmentProjectFormStatus.textContent = 'Vytváram projekt...';
  try {
    const result = await runOperation(() => apiRequest('/development/projects', {
      method: 'POST',
      body: { title, language: dom.developmentProjectLanguageInput.value }
    }));
    activeFileId = result.project.entryFileId;
    standardInput = '';
    setConsole();
    replaceProject(result.project);
    dom.developmentProjectDialog.close();
  } catch (error) {
    dom.developmentProjectFormStatus.textContent = error.message || 'Projekt sa nepodarilo vytvoriť.';
  } finally {
    submitter.disabled = false;
  }
}

async function deleteProject() {
  const project = activeProject();
  if (!project) return;
  if (!window.confirm(`Odstrániť projekt „${project.title}“ aj so všetkými jeho súbormi?`)) return;
  if (!(await saveDevelopmentChanges())) return;
  try {
    await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}`, { method: 'DELETE' }));
    projects = projects.filter((item) => item.id !== project.id);
    activeProjectId = projects[0]?.id || '';
    activeFileId = '';
    standardInput = '';
    ensureActiveFile();
    setConsole();
    renderProjects();
    renderEditor();
  } catch (error) {
    setRunStatus(error.message || 'Projekt sa nepodarilo odstrániť.');
  }
}

async function saveProjectTitle() {
  const project = activeProject();
  const title = dom.developmentProjectTitle.value.trim();
  if (!project || !title || title === projectTitleBaseline) return true;
  const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}`, {
    method: 'PUT', body: { title }
  }));
  replaceProject(result.project);
  return true;
}

async function saveActiveFile() {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file || activeFileSnapshot() === fileDraftBaseline) return true;
  const result = await runOperation(() => apiRequest(
    `/development/projects/${encodeURIComponent(project.id)}/files/${encodeURIComponent(file.id)}`,
    { method: 'PUT', body: { title: dom.developmentFileTitle.value, content: dom.developmentCode.value } }
  ));
  replaceProject(result.project);
  return true;
}

export async function saveDevelopmentChanges() {
  window.clearTimeout(saveTimer);
  try {
    const pendingProjectTitle = dom.developmentProjectTitle.value.trim();
    await saveActiveFile();
    if (pendingProjectTitle && pendingProjectTitle !== projectTitleBaseline) {
      dom.developmentProjectTitle.value = pendingProjectTitle;
      await saveProjectTitle();
    }
    return true;
  } catch (error) {
    setRunStatus(error.message || 'Zmeny sa nepodarilo uložiť.');
    return false;
  }
}

export function hasUnsavedDevelopmentChanges() {
  return dom.developmentProjectTitle.value.trim() !== projectTitleBaseline || activeFileSnapshot() !== fileDraftBaseline;
}

export function discardDevelopmentDraft() {
  window.clearTimeout(saveTimer);
  renderEditor();
}

function scheduleSave() {
  window.clearTimeout(saveTimer);
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'development' } }));
  saveTimer = window.setTimeout(() => void saveDevelopmentChanges(), 650);
}

async function createFile(event) {
  event.preventDefault();
  const project = activeProject();
  const title = dom.developmentFileNameInput.value.trim();
  if (!project || !title || !(await saveDevelopmentChanges())) return;
  const submitter = dom.developmentFileForm.querySelector('button[type="submit"]');
  submitter.disabled = true;
  const isFolder = pendingDevelopmentItemKind === 'folder';
  dom.developmentFileFormStatus.textContent = isFolder ? 'Pridávam priečinok...' : 'Pridávam súbor...';
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}/files`, {
      method: 'POST', body: { title, kind: pendingDevelopmentItemKind, parentId: selectedFolderId }
    }));
    const previousIds = new Set(project.files.map((file) => file.id));
    const created = result.project.files.find((file) => !previousIds.has(file.id));
    if (created?.kind === 'folder') {
      selectedFolderId = created.id;
      expandedFolderIds.add(created.id);
      expandFolderAncestors(result.project, created.id);
    } else if (created) {
      activeFileId = created.id;
      selectedFolderId = String(created.parentId || '');
      expandFolderAncestors(result.project, selectedFolderId);
    }
    replaceProject(result.project);
    dom.developmentFileDialog.close();
  } catch (error) {
    dom.developmentFileFormStatus.textContent = error.message || (isFolder ? 'Priečinok sa nepodarilo vytvoriť.' : 'Súbor sa nepodarilo vytvoriť.');
  } finally {
    submitter.disabled = false;
  }
}

async function deleteProjectItem(item = activeFile()) {
  const project = activeProject();
  if (!project || !item || (item.kind === 'file' && projectFiles(project).length <= 1)) return;
  const noun = item.kind === 'folder' ? 'priečinok aj s jeho obsahom' : 'súbor';
  if (!window.confirm(`Odstrániť ${noun} „${item.title}“?`)) return;
  try {
    const result = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/files/${encodeURIComponent(item.id)}`,
      { method: 'DELETE' }
    ));
    if (!result.project.files.some((file) => file.id === activeFileId && file.kind === 'file')) {
      activeFileId = result.project.entryFileId;
    }
    if (!result.project.files.some((folder) => folder.id === selectedFolderId && folder.kind === 'folder')) {
      selectedFolderId = String(item.parentId || '');
    }
    replaceProject(result.project);
  } catch (error) {
    setRunStatus(error.message || 'Položku sa nepodarilo odstrániť.');
  }
}

async function deleteFile() {
  return deleteProjectItem(activeFile());
}

function formatResultMeta(result) {
  if (!result) return '';
  const parts = [];
  if (Number.isFinite(result.durationMs)) parts.push(`${result.durationMs} ms`);
  if (result.timedOut) parts.push('časový limit');
  if (result.outputLimited) parts.push('limit výstupu');
  return parts.join(' · ');
}

function resultText(result) {
  if (!result) return '';
  return [result.stdout, result.stderr].filter(Boolean).join(result.stdout && result.stderr ? '\n' : '') || 'Bez výstupu.';
}

async function runProject() {
  const project = activeProject();
  if (!project || !(await saveDevelopmentChanges())) return;
  if (!languageRuntime(project.language).available) return;
  setConsoleExpanded(true);
  dom.developmentRun.disabled = true;
  setConsole({ phase: 'Prekladám...', compile: '', output: '' });
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}/run`, {
      method: 'POST', body: { fileId: activeFileId, stdin: dom.developmentInput.value }
    }));
    const compile = result.compile || {};
    const run = result.run || {};
    setConsole({
      phase: result.compiled ? 'Hotovo' : 'Chyba prekladu',
      compile: resultText(compile),
      compileMeta: formatResultMeta(compile),
      output: result.compiled ? resultText(run) : 'Program sa nespustil, pretože preklad zlyhal.',
      outputMeta: result.compiled ? formatResultMeta(run) : ''
    });
  } catch (error) {
    setConsole({ phase: 'Chyba', compile: error.message || 'Projekt sa nepodarilo spustiť.', output: '' });
  } finally {
    dom.developmentRun.disabled = !languageRuntime(project.language).available;
  }
}

export function isDevelopmentPanelOpen() {
  return dom.developmentPanel.classList.contains('is-open');
}

export function isDevelopmentPanelPinned() {
  return panelPinned;
}

export async function openDevelopmentPanel({ pinned = false } = {}) {
  panelPinned = pinned;
  setPanelOpen(true);
  try {
    await runOperation(loadWorkspace);
  } catch (error) {
    projects = [];
    renderProjects();
    renderEditor();
    setRuntimeStatus({ available: false, message: error.message || 'Vývoj sa nepodarilo načítať.' });
  }
}

export function closeDevelopmentPanel({ force = false } = {}) {
  if (!force && hasUnsavedDevelopmentChanges()) return false;
  window.clearTimeout(saveTimer);
  if (dom.developmentProjectDialog.open) dom.developmentProjectDialog.close();
  if (dom.developmentFileDialog.open) dom.developmentFileDialog.close();
  panelPinned = false;
  setFocusMode(false);
  setPanelOpen(false);
  return true;
}

export function initializeDevelopment() {
  setFocusMode(false);
  setConsoleExpanded(false);
  initializePaneResizers();
  dom.developmentProjectCreate.addEventListener('click', openProjectDialog);
  dom.developmentProjectDelete.addEventListener('click', () => void deleteProject());
  dom.developmentEmptyCreate.addEventListener('click', openProjectDialog);
  dom.developmentProjectForm.addEventListener('submit', (event) => void createProject(event));
  dom.developmentProjectCancel.addEventListener('click', () => dom.developmentProjectDialog.close());
  installDialogBackdropClose(dom.developmentProjectDialog, () => dom.developmentProjectDialog.close());
  dom.developmentFileForm.addEventListener('submit', (event) => void createFile(event));
  dom.developmentFileCancel.addEventListener('click', () => dom.developmentFileDialog.close());
  installDialogBackdropClose(dom.developmentFileDialog, () => dom.developmentFileDialog.close());
  dom.developmentProjectTitle.addEventListener('input', () => {
    fitProjectTitle();
    scheduleSave();
  });
  [dom.developmentFileTitle, dom.developmentCode].forEach((field) => {
    field.addEventListener('input', scheduleSave);
  });
  dom.developmentInput.addEventListener('input', () => {
    standardInput = dom.developmentInput.value;
    window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'development' } }));
  });
  dom.developmentSave.addEventListener('click', () => void saveDevelopmentChanges());
  dom.developmentFocusMode.addEventListener('click', () => setFocusMode(!focusMode));
  dom.developmentConsoleToggle.addEventListener('click', () => setConsoleExpanded(!consoleExpanded));
  dom.developmentFileCreate.addEventListener('click', () => void openFileDialog());
  dom.developmentFolderCreate.addEventListener('click', () => void openFileDialog('folder'));
  dom.developmentFileTreeRoot.addEventListener('click', () => {
    selectedFolderId = '';
    renderFileTree();
  });
  dom.developmentFileDelete.addEventListener('click', () => void deleteFile());
  dom.developmentRun.addEventListener('click', () => void runProject());
  window.addEventListener('keydown', (event) => {
    if (!isDevelopmentPanelOpen() || (!event.ctrlKey && !event.metaKey)) return;
    if (event.key.toLowerCase() === 's') {
      event.preventDefault();
      void saveDevelopmentChanges();
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      void runProject();
    }
  });
  [dom.developmentCode, dom.developmentInput].forEach((field) => {
    field.addEventListener('keydown', (event) => {
      if (event.key !== 'Tab') return;
      event.preventDefault();
      const start = field.selectionStart;
      const end = field.selectionEnd;
      field.setRangeText('  ', start, end, 'end');
      field.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
}
