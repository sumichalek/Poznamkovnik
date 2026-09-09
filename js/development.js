import { apiRequest } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { fitDialogWindowToContent, installDialogBackdropClose } from './dialogs.js';
import {
  developmentEditorSelection,
  developmentEditorSymbol,
  developmentEditorValue,
  formatDevelopmentEditor,
  focusDevelopmentEditor,
  initializeDevelopmentEditor,
  insertDevelopmentEditorSnippet,
  developmentEditorViewState,
  replaceDevelopmentEditorRange,
  restoreDevelopmentEditorViewState,
  selectDevelopmentEditorRange,
  setDevelopmentEditorDocument,
  setDevelopmentEditorDiagnostics,
  setDevelopmentEditorProjectFiles,
} from './development-editor.js';
import { initializeDevelopmentTransfer } from './development-transfer.js';
import { dom } from './dom.js';
import { scanProjectSymbols, scanSourceSymbols, sourceForSymbolScan } from './development-symbols.js';
import { projectSnippetEntries } from './development-completions.js';
import { firstTestFailureDiagnostic, parseDevelopmentDiagnostics } from './development-diagnostics.js';
import { firstOutputDifference, fullOutputComparison, normalizedTestOutput } from './development-test-results.js';
import { updateTopbarVisibility } from './topbar.js';

let projects = [];
let languages = [];
let firmwareTargets = [];
let firmwareTools = {};
let firmwareDevices = { ports: [], programmers: {} };
let firmwareBuild = { targets: {} };
let serialMonitor = { available: false, baudRates: [], defaultBaudRate: 115200, message: 'Sériový monitor sa pripravuje.' };
let firmwareProgrammingChallenge = null;
let serialMonitorSession = null;
let serialMonitorCursor = 0;
let serialMonitorPollTimer = 0;
let buildProfiles = [];
let runtime = { available: false, message: 'Skúšobňa sa pripravuje.' };
let debuggerRuntime = { available: false, message: 'Debugger sa pripravuje.' };
let activeProjectId = '';
let activeFileId = '';
let selectedFolderId = '';
let expandedFolderIds = new Set();
let pendingDevelopmentItemKind = 'file';
let panelPinned = false;
let focusMode = false;
let consoleExpanded = false;
let projectTitleBaseline = '';
let projectRunArgumentsBaseline = '';
let fileDraftBaseline = '';
let standardInput = '';
let runArguments = '';
let saveTimer = 0;
let operationCount = 0;
let idleResolvers = [];
let projectDialogProjectId = '';
let findMatches = [];
let findMatchIndex = -1;
let projectFindMatches = [];
let projectFindIndex = -1;
let findScope = 'file';
let diagnostics = [];
let diagnosticIndex = -1;
let draggedProjectItemId = '';
let projectTests = [];
let activeTestId = '';
let testDraftBaseline = '';
let testRunResults = new Map();
let runningAllTests = false;
let displayedTestEvaluation = null;
let definitionHistory = [];
let symbolBrowserExpanded = true;
let quickOpenMode = 'files';
let quickOpenResults = [];
let quickOpenResultIndex = 0;
let editorViewStates = new Map();
let tutorialGuideOpen = false;
let binaryInspection = null;
let debugSession = null;
let renamePreview = null;
let symbolOutlineRefreshTimer = 0;
let symbolOutlineRefreshKey = '';
const tutorialGuideCache = new Map();
const languageServiceSymbolCache = new Map();

const MAX_PROJECT_FIND_MATCHES = 500;
const MAX_DEFINITION_HISTORY = 64;
const MAX_PROJECT_FIND_RESULT_ROWS = 80;
const MAX_QUICK_OPEN_RESULTS = 120;
const MAX_SYMBOL_REFERENCES = 500;
const DEVELOPMENT_SESSION_KEY = 'poznamkovnik-development-session-v1';
const DEVELOPMENT_LAYOUT_KEY = 'poznamkovnik-development-layout-v1';
const DEVELOPMENT_LAYOUT_PROPERTIES = new Set([
  '--development-sidebar-size',
  '--development-console-size',
  '--development-input-size',
  '--development-compile-size',
  '--development-tutorial-guide-size',
]);

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

function activeProjectTest() {
  return projectTests.find((testCase) => testCase.id === activeTestId) || null;
}

function rememberedDevelopmentSession() {
  try {
    const value = JSON.parse(window.localStorage.getItem(DEVELOPMENT_SESSION_KEY) || 'null');
    return value && typeof value === 'object' ? value : null;
  } catch {
    return null;
  }
}

function rememberDevelopmentSession() {
  try {
    window.localStorage.setItem(DEVELOPMENT_SESSION_KEY, JSON.stringify({
      projectId: activeProjectId,
      fileId: activeFileId,
    }));
  } catch {
    // Private browser settings may deny storage; the editor still remains usable.
  }
}

function rememberedDevelopmentLayout() {
  try {
    const value = JSON.parse(window.localStorage.getItem(DEVELOPMENT_LAYOUT_KEY) || 'null');
    return value && typeof value === 'object' ? value : {};
  } catch {
    return {};
  }
}

function rememberDevelopmentLayout(property, value) {
  if (!DEVELOPMENT_LAYOUT_PROPERTIES.has(property) || !Number.isFinite(value)) return;
  try {
    const layout = rememberedDevelopmentLayout();
    layout[property] = Math.round(value);
    window.localStorage.setItem(DEVELOPMENT_LAYOUT_KEY, JSON.stringify(layout));
  } catch {
    // Private browser settings may deny storage; resizing still remains usable.
  }
}

function forgetDevelopmentLayout(property) {
  if (!DEVELOPMENT_LAYOUT_PROPERTIES.has(property)) return;
  try {
    const layout = rememberedDevelopmentLayout();
    delete layout[property];
    window.localStorage.setItem(DEVELOPMENT_LAYOUT_KEY, JSON.stringify(layout));
  } catch {
    // The default layout still takes effect when storage is unavailable.
  }
}

function layoutBounds(property) {
  const panelWidth = dom.developmentPanel.getBoundingClientRect().width || window.innerWidth;
  const editorHeight = dom.developmentEditorResize.parentElement.getBoundingClientRect().height || window.innerHeight;
  const consoleWidth = dom.developmentConsoleSection.getBoundingClientRect().width || panelWidth;
  if (property === '--development-sidebar-size') {
    return [168, Math.max(168, Math.min(440, panelWidth - 520))];
  }
  if (property === '--development-console-size') {
    return [120, Math.max(120, editorHeight - 188)];
  }
  if (property === '--development-input-size') {
    return [120, Math.max(120, consoleWidth - 376)];
  }
  if (property === '--development-compile-size') {
    const savedInputSize = Number(rememberedDevelopmentLayout()['--development-input-size']);
    const inputWidth = Number.isFinite(savedInputSize) ? savedInputSize : consoleWidth * 0.24;
    return [180, Math.max(180, consoleWidth - Math.max(120, inputWidth) - 196)];
  }
  const codeWidth = dom.developmentCodeSection.getBoundingClientRect().width || panelWidth;
  return [220, Math.max(220, Math.min(1000, codeWidth - 260))];
}

function restoreDevelopmentLayout() {
  const layout = rememberedDevelopmentLayout();
  for (const property of DEVELOPMENT_LAYOUT_PROPERTIES) {
    const value = Number(layout[property]);
    if (!Number.isFinite(value)) continue;
    const [minimum, maximum] = layoutBounds(property);
    setResizeValue(property, clamp(value, minimum, maximum));
  }
}

function editorViewStateKey(projectId = activeProjectId, fileId = activeFileId) {
  return projectId && fileId ? `${projectId}:${fileId}` : '';
}

function rememberEditorViewState() {
  const key = editorViewStateKey();
  const viewState = developmentEditorViewState();
  if (!key || !viewState) return;
  editorViewStates.set(key, viewState);
}

function restoreActiveEditorViewState() {
  const viewState = editorViewStates.get(editorViewStateKey());
  if (viewState) restoreDevelopmentEditorViewState(viewState);
}

function languageLabel(languageId) {
  return languages.find((language) => language.id === languageId)?.label || languageId || 'Neznámy jazyk';
}

function languageShortLabel(languageId) {
  const labels = {
    c: 'C',
    cpp: 'C++',
    csharp: 'C#',
    php: 'PHP',
    python: 'Py',
    javascript: 'JS',
    ruby: 'Rb',
    perl: 'Pl',
    typescript: 'TS',
    java: 'Java',
    rust: 'Rs',
    go: 'Go',
    asm: 'ASM',
    bash: 'sh'
  };
  return labels[languageId] || languageLabel(languageId).slice(0, 4);
}

function createProjectMarker(project) {
  const label = project.kind === 'firmware' ? 'Firmvér' : languageLabel(project.language);
  if (project.kind === 'firmware') {
    const icon = createAppIcon('chip', 'development-project-marker');
    icon.classList.add('is-firmware');
    icon.setAttribute('aria-label', label);
    icon.setAttribute('role', 'img');
    icon.title = label;
    return icon;
  }
  const marker = document.createElement('span');
  marker.className = 'development-project-marker';
  marker.textContent = languageShortLabel(project.language);
  marker.title = `Jazyk: ${label}`;
  marker.setAttribute('aria-label', label);
  return marker;
}

function languageRuntime(languageId) {
  return runtime.languages?.[languageId] || {
    available: languageId === 'c' && Boolean(runtime.available),
    message: runtime.message || 'Skúšobňa nie je dostupná.'
  };
}

function languageTemplates(languageId) {
  return languages.find((language) => language.id === languageId)?.templates || [];
}

function firmwareTarget(targetId) {
  return firmwareTargets.find((target) => target.id === targetId) || null;
}

function firmwareToolchainStatus(targetId) {
  return firmwareTools?.[targetId] || {
    buildAvailable: false,
    programmerAvailable: false,
    message: 'Stav firmvérového toolchainu sa nepodarilo načítať.',
  };
}

function firmwareBuildStatus(targetId, language) {
  return firmwareBuild?.targets?.[targetId]?.languages?.[language] || {
    available: false,
    message: firmwareToolchainStatus(targetId).message,
  };
}

function firmwareProgrammers(targetId) {
  return firmwareDevices?.programmers?.[targetId] || [];
}

function firmwareProgrammer(targetId, programmerId) {
  return firmwareProgrammers(targetId).find((profile) => profile.id === programmerId) || null;
}

function configuredFirmwareDevice(project) {
  if (project?.kind !== 'firmware') return null;
  const programmer = firmwareProgrammer(project.firmwareTargetId, project.firmwareProgrammerId);
  return {
    programmer,
    port: String(project.firmwareSerialPort || ''),
    baudRate: Number(project.firmwareSerialBaud) || Number(serialMonitor.defaultBaudRate) || 115200,
  };
}

function dialogProjectKind() {
  return dom.developmentProjectKind.querySelector('input[name="project-kind"]:checked')?.value || 'program';
}

function setDialogProjectKind(kind) {
  const input = dom.developmentProjectKind.querySelector(`input[name="project-kind"][value="${kind}"]`);
  if (input) input.checked = true;
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

function projectFilePath(project, item) {
  if (!project || !item) return '';
  const names = [];
  const visited = new Set();
  let current = item;
  while (current && !visited.has(current.id)) {
    names.unshift(current.title);
    visited.add(current.id);
    current = projectItem(project, current.parentId);
  }
  return names.join('/');
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
  return JSON.stringify({ title: dom.developmentFileTitle.value, content: developmentEditorValue() });
}

function dispatchCodeInput(field) {
  field.dispatchEvent(new Event('input', { bubbles: true }));
}

function textMatchOffsets(text, query) {
  if (!query) return [];
  const needle = query.toLocaleLowerCase('sk');
  const haystack = text.toLocaleLowerCase('sk');
  const matches = [];
  let offset = 0;
  while (offset <= haystack.length - needle.length) {
    const found = haystack.indexOf(needle, offset);
    if (found < 0) break;
    matches.push(found);
    offset = found + Math.max(needle.length, 1);
  }
  return matches;
}

function findMatchKey(match) {
  return match ? `${match.fileId || ''}:${match.offset}` : '';
}

function updateFindScopeUi() {
  const projectScope = findScope === 'project';
  dom.developmentFindBar.classList.toggle('is-project-scope', projectScope);
  dom.developmentFindInput.placeholder = projectScope ? 'Hľadať v projekte' : 'Hľadať v súbore';
  dom.developmentFindScope.setAttribute('aria-pressed', String(projectScope));
  dom.developmentFindScope.title = projectScope
    ? 'Hľadať len v otvorenom súbore (Ctrl+F)'
    : 'Hľadať v celom projekte (Ctrl+Shift+F)';
  dom.developmentFindScope.setAttribute('aria-label', dom.developmentFindScope.title);
  setAppIcon(dom.developmentFindScope.querySelector('.app-icon'), projectScope ? 'folder' : 'file');
}

function currentProjectSearchFiles() {
  const project = activeProject();
  if (!project) return [];
  return projectFiles(project).map((file) => ({
    ...file,
    content: file.id === activeFileId ? developmentEditorValue() : String(file.content || ''),
  }));
}

function collectProjectFindMatches(query) {
  if (!query) return [];
  const found = [];
  for (const file of currentProjectSearchFiles()) {
    const offsets = textMatchOffsets(file.content, query);
    for (const offset of offsets) {
      found.push({ fileId: file.id, offset });
      if (found.length >= MAX_PROJECT_FIND_MATCHES) return found;
    }
  }
  return found;
}

function projectFindMatchPreview(match) {
  const file = currentProjectSearchFiles().find((item) => item.id === match.fileId);
  const content = String(file?.content || '');
  const lineStart = content.lastIndexOf('\n', Math.max(0, match.offset - 1)) + 1;
  const lineEnd = content.indexOf('\n', match.offset);
  const line = content.slice(lineStart, lineEnd < 0 ? content.length : lineEnd);
  const lineNumber = content.slice(0, lineStart).split('\n').length;
  const normalizedLine = line.replace(/\s+/g, ' ').trim();
  const matchColumn = Math.max(0, match.offset - lineStart);
  const excerptStart = Math.max(0, matchColumn - 46);
  const excerpt = normalizedLine.length > 104
    ? `${excerptStart ? '...' : ''}${normalizedLine.slice(excerptStart, excerptStart + 104)}${excerptStart + 104 < normalizedLine.length ? '...' : ''}`
    : normalizedLine;
  return { file, lineNumber, excerpt };
}

function renderProjectFindResults() {
  const container = dom.developmentProjectFindResults;
  if (!container) return;
  const query = dom.developmentFindInput.value;
  const visible = findScope === 'project' && !dom.developmentFindBar.hidden && Boolean(query) && projectFindMatches.length > 0;
  container.hidden = !visible;
  if (!visible) {
    container.replaceChildren();
    return;
  }
  const project = activeProject();
  container.replaceChildren();
  projectFindMatches.slice(0, MAX_PROJECT_FIND_RESULT_ROWS).forEach((match, index) => {
    const preview = projectFindMatchPreview(match);
    if (!preview.file) return;
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'development-project-find-result';
    row.classList.toggle('is-active', index === projectFindIndex);
    row.setAttribute('role', 'option');
    row.setAttribute('aria-selected', String(index === projectFindIndex));
    row.append(createAppIcon('file'));
    const copy = document.createElement('span');
    copy.className = 'development-project-find-result-copy';
    const path = document.createElement('strong');
    path.textContent = `${projectFilePath(project, preview.file)}:${preview.lineNumber}`;
    const excerpt = document.createElement('small');
    excerpt.textContent = preview.excerpt || '(prázdny riadok)';
    copy.append(path, excerpt);
    row.append(copy);
    row.addEventListener('click', () => {
      projectFindIndex = index;
      void selectFindMatch(0);
    });
    container.append(row);
  });
}

function moveProjectFindSelection(step) {
  if (!projectFindMatches.length) return;
  if (projectFindIndex < 0) {
    projectFindIndex = step < 0 ? projectFindMatches.length - 1 : 0;
  } else {
    projectFindIndex = (projectFindIndex + step + projectFindMatches.length) % projectFindMatches.length;
  }
  renderProjectFindResults();
}

function updateFindMatches({ preserveMatch = true } = {}) {
  const query = dom.developmentFindInput.value;
  if (findScope === 'project') {
    const previousKey = preserveMatch ? findMatchKey(projectFindMatches[projectFindIndex]) : '';
    projectFindMatches = collectProjectFindMatches(query);
    projectFindIndex = previousKey
      ? projectFindMatches.findIndex((match) => findMatchKey(match) === previousKey)
      : -1;
    const fileCount = new Set(projectFindMatches.map((match) => match.fileId)).size;
    const countLabel = projectFindMatches.length === MAX_PROJECT_FIND_MATCHES ? `${MAX_PROJECT_FIND_MATCHES}+` : String(projectFindMatches.length);
    dom.developmentFindCount.textContent = query
      ? `${countLabel} · ${fileCount} ${fileCount === 1 ? 'súbor' : fileCount < 5 ? 'súbory' : 'súborov'}`
      : '';
    const unavailable = !query || !projectFindMatches.length;
    dom.developmentFindPrevious.disabled = unavailable;
    dom.developmentFindNext.disabled = unavailable;
    dom.developmentReplaceOne.disabled = true;
    dom.developmentReplaceAll.disabled = true;
    updateFindScopeUi();
    renderProjectFindResults();
    return;
  }
  const previousOffset = preserveMatch ? findMatches[findMatchIndex] : -1;
  findMatches = textMatchOffsets(developmentEditorValue(), query);
  projectFindMatches = [];
  projectFindIndex = -1;
  findMatchIndex = previousOffset >= 0 ? findMatches.indexOf(previousOffset) : -1;
  if (findMatchIndex < 0 && findMatches.length) {
    const cursor = developmentEditorSelection().from;
    findMatchIndex = findMatches.findIndex((offset) => offset >= cursor);
    if (findMatchIndex < 0) findMatchIndex = 0;
  }
  dom.developmentFindCount.textContent = query
    ? `${findMatches.length} ${findMatches.length === 1 ? 'výskyt' : findMatches.length < 5 ? 'výskyty' : 'výskytov'}`
    : '';
  const unavailable = !query || !findMatches.length;
  dom.developmentFindPrevious.disabled = unavailable;
  dom.developmentFindNext.disabled = unavailable;
  dom.developmentReplaceOne.disabled = unavailable;
  dom.developmentReplaceAll.disabled = unavailable;
  updateFindScopeUi();
  renderProjectFindResults();
}

async function selectFindMatch(step = 0) {
  if (findScope === 'project') {
    if (!projectFindMatches.length) return;
    if (projectFindIndex < 0) projectFindIndex = step < 0 ? projectFindMatches.length - 1 : 0;
    else if (step) projectFindIndex = (projectFindIndex + step + projectFindMatches.length) % projectFindMatches.length;
    const match = projectFindMatches[projectFindIndex];
    if (match.fileId !== activeFileId) await selectFile(match.fileId);
    window.requestAnimationFrame(() => {
      selectDevelopmentEditorRange(match.offset, match.offset + dom.developmentFindInput.value.length);
      updateFindMatches({ preserveMatch: true });
    });
    return;
  }
  if (!findMatches.length) return;
  if (step) findMatchIndex = (findMatchIndex + step + findMatches.length) % findMatches.length;
  if (findMatchIndex < 0) findMatchIndex = 0;
  const start = findMatches[findMatchIndex];
  const end = start + dom.developmentFindInput.value.length;
  selectDevelopmentEditorRange(start, end);
}

function setFindOpen(open, { replace = false } = {}) {
  if (replace) findScope = 'file';
  dom.developmentFindBar.hidden = !open;
  dom.developmentFindToggle.setAttribute('aria-expanded', String(open));
  dom.developmentFindToggle.title = open ? 'Zavrieť vyhľadávanie (Esc)' : 'Hľadať v súbore (Ctrl+F)';
  if (!open) {
    renderProjectFindResults();
    return;
  }
  updateFindMatches({ preserveMatch: false });
  window.requestAnimationFrame(() => {
    const field = replace ? dom.developmentReplaceInput : dom.developmentFindInput;
    field.focus();
    if (replace) field.select();
  });
}

function replaceFindMatch(all = false) {
  if (findScope !== 'file') return;
  const query = dom.developmentFindInput.value;
  if (!query || !findMatches.length) return;
  const replacement = dom.developmentReplaceInput.value;
  const offsets = all ? [...findMatches].reverse() : [findMatches[Math.max(0, findMatchIndex)]];
  offsets.forEach((start) => {
    replaceDevelopmentEditorRange(start, start + query.length, replacement);
  });
  updateFindMatches({ preserveMatch: false });
  if (!all) selectFindMatch(0);
}

function clearDiagnostics() {
  diagnostics = [];
  diagnosticIndex = -1;
  setDevelopmentEditorDiagnostics();
  renderProblems();
  dom.developmentDiagnosticNext.hidden = true;
  dom.developmentDiagnosticCount.textContent = '';
}

function diagnosticsForActiveFile() {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file) return [];
  const path = projectFilePath(project, file);
  return diagnostics.filter((diagnostic) => diagnostic.filename === path || diagnostic.filename === file.title);
}

function readDiagnostics(compileOutput) {
  const found = parseDevelopmentDiagnostics(compileOutput);
  diagnostics = found;
  diagnosticIndex = -1;
  setDevelopmentEditorDiagnostics(diagnosticsForActiveFile());
  renderProblems();
  dom.developmentDiagnosticNext.hidden = !found.length;
  dom.developmentDiagnosticCount.textContent = found.length ? String(found.length) : '';
  dom.developmentDiagnosticNext.title = found.length
    ? `Prejsť na chybu alebo varovanie (1 z ${found.length})`
    : '';
  dom.developmentDiagnosticNext.setAttribute('aria-label', dom.developmentDiagnosticNext.title || 'Diagnostika prekladu');
}

function diagnosticSeverityLabel(diagnostic) {
  return diagnostic.severity === 'warning' ? 'Varovanie' : 'Chyba';
}

function diagnosticSummary() {
  const errors = diagnostics.filter((diagnostic) => diagnostic.severity !== 'warning').length;
  const warnings = diagnostics.length - errors;
  const parts = [];
  if (errors) parts.push(`${errors} ${errors === 1 ? 'chyba' : errors < 5 ? 'chyby' : 'chýb'}`);
  if (warnings) parts.push(`${warnings} ${warnings === 1 ? 'varovanie' : warnings < 5 ? 'varovania' : 'varovaní'}`);
  return parts.join(' · ') || 'Preklad neohlásil žiadne problémy.';
}

function renderProblems() {
  const count = diagnostics.length;
  dom.developmentProblems.hidden = !count;
  dom.developmentProblemsCount.textContent = count ? String(count) : '';
  dom.developmentProblems.title = count ? `Zobraziť problémy prekladu (${diagnosticSummary()})` : '';
  dom.developmentProblems.setAttribute('aria-label', dom.developmentProblems.title || 'Problémy prekladu');
  dom.developmentProblemsSummary.textContent = diagnosticSummary();
  dom.developmentProblemsList.replaceChildren();
  if (!count) {
    const empty = document.createElement('p');
    empty.className = 'development-problems-empty';
    empty.textContent = 'Preklad neohlásil žiadne problémy.';
    dom.developmentProblemsList.append(empty);
    return;
  }
  diagnostics.forEach((diagnostic, index) => {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = `development-problem is-${diagnostic.severity === 'warning' ? 'warning' : 'error'}`;
    row.setAttribute('role', 'option');
    row.setAttribute('aria-selected', String(index === diagnosticIndex));
    const marker = document.createElement('span');
    marker.className = 'development-problem-marker';
    marker.textContent = diagnostic.severity === 'warning' ? '!' : '×';
    const copy = document.createElement('span');
    copy.className = 'development-problem-copy';
    const title = document.createElement('strong');
    title.textContent = diagnostic.message || diagnosticSeverityLabel(diagnostic);
    const detail = document.createElement('small');
    detail.textContent = `${diagnosticSeverityLabel(diagnostic)} · ${diagnostic.filename}:${diagnostic.line}:${diagnostic.column}`;
    copy.append(title, detail);
    row.append(marker, copy);
    row.addEventListener('click', () => void openDiagnostic(diagnostic, index, { closeProblems: true }));
    dom.developmentProblemsList.append(row);
  });
}

function selectEditorLine(line, column = 1) {
  const source = developmentEditorValue();
  const lines = source.split('\n');
  const safeLine = Math.min(Math.max(1, line), lines.length);
  const start = lines.slice(0, safeLine - 1).reduce((total, item) => total + item.length + 1, 0);
  const columnOffset = Math.min(Math.max(0, column - 1), lines[safeLine - 1].length);
  const position = start + columnOffset;
  selectDevelopmentEditorRange(position, Math.min(start + lines[safeLine - 1].length, position + 1));
}

function editorLocation() {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file) return null;
  const source = developmentEditorValue();
  const selection = developmentEditorSelection();
  const position = Math.min(Math.max(0, selection.from), source.length);
  const before = source.slice(0, position);
  return {
    projectId: project.id,
    fileId: file.id,
    line: before.split('\n').length,
    column: position - before.lastIndexOf('\n'),
  };
}

async function requestEditorLanguageService(payload) {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file) return null;
  return apiRequest(`/development/projects/${encodeURIComponent(project.id)}/language-service`, {
    method: 'POST',
    body: {
      ...payload,
      fileId: file.id,
      source: developmentEditorValue(),
    },
  });
}

async function requestLanguageServiceLocations(operation, position = editorLocation()) {
  if (!position) return [];
  try {
    const result = await requestEditorLanguageService({ operation, line: position.line, column: position.column });
    return result?.available && Array.isArray(result.locations) ? result.locations : [];
  } catch {
    // The local symbol index remains the dependable fallback.
    return [];
  }
}

function projectFileForLanguageServicePath(project, path) {
  const normalized = String(path || '').replaceAll('\\', '/');
  return projectFiles(project).find((file) => projectFilePath(project, file) === normalized) || null;
}

function referenceFromLanguageServiceLocation(project, location) {
  const file = projectFileForLanguageServicePath(project, location.path);
  if (!file) return null;
  const source = sourceForProjectFile(file);
  const line = Math.min(Math.max(1, Number(location.line) || 1), source.split('\n').length);
  const lines = source.split('\n');
  const sourceLine = lines[line - 1] || '';
  return {
    file,
    line,
    column: Math.min(Math.max(1, Number(location.column) || 1), sourceLine.length + 1),
    definition: false,
    preview: sourceLine.trim(),
  };
}

function sameEditorLocation(left, right) {
  return Boolean(left && right)
    && left.projectId === right.projectId
    && left.fileId === right.fileId
    && left.line === right.line
    && left.column === right.column;
}

function renderDefinitionNavigation() {
  const available = definitionHistory.length > 0;
  dom.developmentDefinitionBack.hidden = !available;
  dom.developmentDefinitionBack.disabled = !available;
}

function rememberDefinitionOrigin(location) {
  if (!location) return;
  const previous = definitionHistory[definitionHistory.length - 1];
  if (!sameEditorLocation(previous, location)) definitionHistory.push(location);
  if (definitionHistory.length > MAX_DEFINITION_HISTORY) definitionHistory.shift();
  renderDefinitionNavigation();
}

async function openEditorLocation(location) {
  if (!location || !(await saveDevelopmentChanges())) return false;
  if (location.projectId !== activeProjectId) await selectProject(location.projectId);
  if (location.fileId !== activeFileId) await selectFile(location.fileId);
  if (!activeFile() || activeFileId !== location.fileId) return false;
  window.requestAnimationFrame(() => selectEditorLine(location.line, location.column));
  return true;
}

function escapeExpression(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function openSymbolDefinition(symbol, position = editorLocation()) {
  const origin = editorLocation();
  if (!(await saveDevelopmentChanges())) return;
  const project = activeProject();
  if (!project) return;
  const languageServiceLocations = await requestLanguageServiceLocations('definition', position);
  const languageServiceTarget = languageServiceLocations
    .map((location) => ({ location, file: projectFileForLanguageServicePath(project, location.path) }))
    .find((item) => item.file);
  if (languageServiceTarget) {
    const destination = {
      projectId: project.id,
      fileId: languageServiceTarget.file.id,
      line: languageServiceTarget.location.line,
      column: languageServiceTarget.location.column,
    };
    if (!sameEditorLocation(origin, destination)) {
      rememberDefinitionOrigin(origin);
      await openEditorLocation(destination);
    }
    return;
  }
  const kindPriority = { function: 0, macro: 0, class: 1, type: 1, label: 2 };
  const files = projectFiles(project).map((file) => ({ ...file, content: sourceForProjectFile(file) }));
  const target = scanProjectSymbols(files, project.language)
    .filter((item) => item.name === symbol)
    .sort((left, right) => {
      const activeDifference = Number(right.file.id === activeFileId) - Number(left.file.id === activeFileId);
      if (activeDifference) return activeDifference;
      const kindDifference = (kindPriority[left.kind] ?? 9) - (kindPriority[right.kind] ?? 9);
      return kindDifference || left.line - right.line || left.column - right.column;
    })[0];
  if (!target) {
    setRunStatus(`Definícia „${symbol}“ sa nenašla.`);
    return;
  }
  const destination = {
    projectId: project.id,
    fileId: target.file.id,
    line: target.line,
    column: target.column,
  };
  if (sameEditorLocation(origin, destination)) return;
  rememberDefinitionOrigin(origin);
  await openEditorLocation(destination);
}

async function openPreviousDefinition() {
  const destination = definitionHistory[definitionHistory.length - 1];
  if (!destination) return;
  if (await openEditorLocation(destination)) definitionHistory.pop();
  renderDefinitionNavigation();
}

function projectSymbolReferences(symbol) {
  const project = activeProject();
  const name = String(symbol || '').trim();
  if (!project || !name) return [];
  const expression = new RegExp(`\\b${escapeExpression(name)}\\b`, 'g');
  const references = [];
  for (const file of projectFiles(project)) {
    const source = sourceForProjectFile(file);
    const searchable = sourceForSymbolScan(source, project.language);
    const definitions = new Set(
      scanSourceSymbols(source, project.language)
        .filter((item) => item.name === name)
        .map((item) => item.offset)
    );
    let match;
    while ((match = expression.exec(searchable))) {
      const offset = match.index;
      const lineStart = source.lastIndexOf('\n', offset - 1) + 1;
      const lineEnd = source.indexOf('\n', offset);
      const before = source.slice(0, offset);
      references.push({
        file,
        line: before.split('\n').length,
        column: offset - lineStart + 1,
        definition: definitions.has(offset),
        preview: source.slice(lineStart, lineEnd < 0 ? source.length : lineEnd).trim(),
      });
      if (references.length >= MAX_SYMBOL_REFERENCES) return references;
    }
  }
  return references;
}

function renderSymbolReferences(symbol, providedReferences = null) {
  const project = activeProject();
  if (!project) return;
  const references = providedReferences || projectSymbolReferences(symbol);
  const uniqueFiles = new Set(references.map((reference) => reference.file.id)).size;
  const truncated = references.length >= MAX_SYMBOL_REFERENCES;
  dom.developmentReferencesTitle.textContent = `Použitia: ${symbol}`;
  dom.developmentReferencesSummary.textContent = references.length
    ? `${references.length}${truncated ? '+' : ''} ${references.length === 1 ? 'výskyt' : references.length < 5 ? 'výskyty' : 'výskytov'} v ${uniqueFiles} ${uniqueFiles === 1 ? 'súbore' : uniqueFiles < 5 ? 'súboroch' : 'súboroch'}.`
    : 'Bez nájdených použití.';
  dom.developmentReferencesList.replaceChildren();
  if (!references.length) {
    const empty = document.createElement('p');
    empty.className = 'development-references-empty';
    empty.textContent = 'Symbol sa nenachádza v zdrojových súboroch projektu.';
    dom.developmentReferencesList.append(empty);
    return;
  }
  references.forEach((reference) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `development-reference${reference.definition ? ' is-definition' : ''}`;
    button.setAttribute('role', 'option');
    button.title = `${projectFilePath(project, reference.file)}:${reference.line}:${reference.column}`;
    const marker = document.createElement('span');
    marker.className = 'development-reference-marker';
    marker.textContent = reference.definition ? 'D' : '•';
    const copy = document.createElement('span');
    copy.className = 'development-reference-copy';
    const title = document.createElement('strong');
    title.textContent = `${reference.file.title}:${reference.line}`;
    const meta = document.createElement('small');
    meta.textContent = `${reference.definition ? 'Definícia' : 'Použitie'} · ${reference.preview || symbol}`;
    copy.append(title, meta);
    button.append(marker, copy);
    button.addEventListener('click', () => {
      void openEditorLocation({
        projectId: project.id,
        fileId: reference.file.id,
        line: reference.line,
        column: reference.column,
      }).then((opened) => {
        if (!opened) return;
        dom.developmentReferencesDialog.close();
        focusDevelopmentEditor();
      });
    });
    dom.developmentReferencesList.append(button);
  });
}

async function openSymbolReferences(symbol, position = editorLocation()) {
  if (!activeProject() || !symbol) return;
  const project = activeProject();
  const locations = await requestLanguageServiceLocations('references', position);
  const references = locations
    .map((location) => referenceFromLanguageServiceLocation(project, location))
    .filter(Boolean)
    .slice(0, MAX_SYMBOL_REFERENCES);
  renderSymbolReferences(symbol, references.length ? references : null);
  if (!dom.developmentReferencesDialog.open) dom.developmentReferencesDialog.showModal();
}

function resetSymbolRenamePreview() {
  renamePreview = null;
  dom.developmentSymbolRenamePreview.hidden = true;
  dom.developmentSymbolRenamePreviewList.replaceChildren();
  dom.developmentSymbolRenameSubmit.disabled = false;
  dom.developmentSymbolRenameSubmit.querySelector('span:last-child').textContent = 'Náhľad zmien';
  setAppIcon(dom.developmentSymbolRenameSubmit.querySelector('.app-icon'), 'eye');
  fitSymbolRenameDialogToContent();
}

function fitSymbolRenameDialogToContent() {
  const dialog = dom.developmentSymbolRenameDialog;
  if (!dialog.open) return;
  window.requestAnimationFrame(() => {
    const hasPreview = !dom.developmentSymbolRenamePreview.hidden;
    fitDialogWindowToContent(dialog, { preferredWidth: hasPreview ? 520 : 380 });
  });
}

function renamePreviewEditCount(workspaceEdits) {
  return (workspaceEdits || []).reduce((total, item) => total + (item.edits?.length || 0), 0);
}

function selectedRenameWorkspaceEdits() {
  if (!renamePreview) return [];
  return renamePreview.workspaceEdits.map((group) => ({
    path: group.path,
    edits: (group.edits || []).filter((edit) => edit.enabled !== false).map(({ enabled, ...edit }) => edit),
  })).filter((group) => group.edits.length);
}

function updateSymbolRenamePreviewStatus() {
  const workspaceEdits = selectedRenameWorkspaceEdits();
  const editCount = renamePreviewEditCount(workspaceEdits);
  const files = workspaceEdits.length;
  dom.developmentSymbolRenameSubmit.disabled = !editCount;
  dom.developmentSymbolRenameStatus.textContent = editCount
    ? `Náhľad: ${editCount} ${editCount === 1 ? 'zmena' : editCount < 5 ? 'zmeny' : 'zmien'} v ${files} ${files === 1 ? 'súbore' : 'súboroch'}. Potvrď ich.`
    : 'Označ aspoň jednu zmenu na potvrdenie.';
}

function renderSymbolRenamePreview(workspaceEdits) {
  dom.developmentSymbolRenamePreviewList.replaceChildren();
  workspaceEdits.forEach((group) => {
    (group.edits || []).forEach((edit) => {
      const row = document.createElement('div');
      row.className = 'development-symbol-rename-preview-row';
      row.setAttribute('role', 'listitem');
      const select = document.createElement('input');
      select.type = 'checkbox';
      select.checked = edit.enabled !== false;
      select.setAttribute('aria-label', `Použiť zmenu v ${group.path}:${edit.startLine}:${edit.startColumn}`);
      const path = document.createElement('code');
      path.textContent = group.path;
      path.title = group.path;
      const position = document.createElement('span');
      position.textContent = `${edit.startLine}:${edit.startColumn}`;
      const replacement = document.createElement('input');
      replacement.type = 'text';
      replacement.value = String(edit.newText || '');
      replacement.spellcheck = false;
      replacement.setAttribute('aria-label', `Náhradný text pre ${group.path}:${edit.startLine}:${edit.startColumn}`);
      replacement.disabled = !select.checked;
      select.addEventListener('change', () => {
        edit.enabled = select.checked;
        replacement.disabled = !select.checked;
        row.classList.toggle('is-skipped', !select.checked);
        updateSymbolRenamePreviewStatus();
      });
      replacement.addEventListener('input', () => {
        edit.newText = replacement.value;
      });
      replacement.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') event.preventDefault();
      });
      row.classList.toggle('is-skipped', !select.checked);
      row.append(select, path, position, replacement);
      dom.developmentSymbolRenamePreviewList.append(row);
    });
  });
  dom.developmentSymbolRenamePreview.hidden = !dom.developmentSymbolRenamePreviewList.childElementCount;
  dom.developmentSymbolRenameSubmit.querySelector('span:last-child').textContent = 'Potvrdiť zmeny';
  setAppIcon(dom.developmentSymbolRenameSubmit.querySelector('.app-icon'), 'check');
  updateSymbolRenamePreviewStatus();
  fitSymbolRenameDialogToContent();
}

function prepareSymbolRenamePreview(project, oldName, newName, workspaceEdits) {
  const editCount = renamePreviewEditCount(workspaceEdits);
  if (!editCount) return false;
  const editableWorkspaceEdits = workspaceEdits.map((group) => ({
    path: group.path,
    edits: (group.edits || []).map((edit) => ({ ...edit, enabled: true })),
  }));
  renamePreview = { projectId: project.id, oldName, newName, workspaceEdits: editableWorkspaceEdits };
  renderSymbolRenamePreview(editableWorkspaceEdits);
  return true;
}

function renameDialogOrigin() {
  const line = Number(dom.developmentSymbolRenameDialog.dataset.line);
  const column = Number(dom.developmentSymbolRenameDialog.dataset.column);
  return Number.isFinite(line) && Number.isFinite(column) ? { line, column } : editorLocation();
}

function openSymbolRename(symbol = developmentEditorSymbol(), position = editorLocation()) {
  if (!activeProject() || !symbol) {
    setRunStatus('Najprv umiestni kurzor na názov symbolu.');
    return;
  }
  const origin = position || editorLocation();
  dom.developmentSymbolRenameDialog.dataset.symbol = symbol;
  dom.developmentSymbolRenameDialog.dataset.line = String(origin?.line || '');
  dom.developmentSymbolRenameDialog.dataset.column = String(origin?.column || '');
  dom.developmentSymbolRenameInput.value = symbol;
  dom.developmentSymbolRenameStatus.textContent = '';
  resetSymbolRenamePreview();
  if (!dom.developmentSymbolRenameDialog.open) dom.developmentSymbolRenameDialog.showModal();
  fitSymbolRenameDialogToContent();
  window.setTimeout(() => dom.developmentSymbolRenameInput.select(), 0);
}

async function renameProjectSymbol(event) {
  event.preventDefault();
  const project = activeProject();
  const oldName = dom.developmentSymbolRenameDialog.dataset.symbol || '';
  const newName = dom.developmentSymbolRenameInput.value.trim();
  if (!project || !oldName) return;
  if (!newName) {
    dom.developmentSymbolRenameStatus.textContent = 'Zadaj nový názov.';
    return;
  }
  if (newName === oldName) {
    dom.developmentSymbolRenameStatus.textContent = 'Názov sa nezmenil.';
    return;
  }
  dom.developmentSymbolRenameSubmit.disabled = true;
  try {
    if (
      renamePreview
      && renamePreview.projectId === project.id
      && renamePreview.oldName === oldName
      && renamePreview.newName === newName
    ) {
      const workspaceEdits = selectedRenameWorkspaceEdits();
      if (!renamePreviewEditCount(workspaceEdits)) {
        dom.developmentSymbolRenameStatus.textContent = 'Označ aspoň jednu zmenu na potvrdenie.';
        return;
      }
      dom.developmentSymbolRenameStatus.textContent = 'Ukladám potvrdené zmeny...';
      const result = await runOperation(() => apiRequest(
        `/development/projects/${encodeURIComponent(project.id)}/apply-text-edits`,
        { method: 'POST', body: { workspaceEdits } }
      ));
      replaceProject(result.project);
      dom.developmentSymbolRenameDialog.close();
      resetSymbolRenamePreview();
      const files = Number(result.files) || 0;
      setRunStatus(`Premenované: ${result.replacements}× v ${files} ${files === 1 ? 'súbore' : 'súboroch'}.`);
      window.requestAnimationFrame(() => focusDevelopmentEditor());
      return;
    }

    dom.developmentSymbolRenameStatus.textContent = 'Pripravujem náhľad zmien...';
    if (!(await saveDevelopmentChanges())) {
      dom.developmentSymbolRenameStatus.textContent = 'Aktuálny súbor sa nepodarilo uložiť.';
      return;
    }
    let workspaceEdits = [];
    try {
      const languageService = await requestEditorLanguageService({
        operation: 'rename',
        line: renameDialogOrigin()?.line,
        column: renameDialogOrigin()?.column,
        newName,
      });
      workspaceEdits = languageService?.available && Array.isArray(languageService.workspaceEdits)
        ? languageService.workspaceEdits
        : [];
    } catch {
      workspaceEdits = [];
    }
    if (prepareSymbolRenamePreview(project, oldName, newName, workspaceEdits)) return;

    dom.developmentSymbolRenameStatus.textContent = 'Pripravujem miestny náhľad zmien...';
    const fallbackPreview = await apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/preview-symbol-rename`,
      { method: 'POST', body: { oldName, newName } }
    );
    if (prepareSymbolRenamePreview(project, oldName, newName, fallbackPreview.workspaceEdits || [])) return;
    dom.developmentSymbolRenameStatus.textContent = 'Symbol sa v kóde projektu nenašiel.';
  } catch (error) {
    dom.developmentSymbolRenameStatus.textContent = error.message || 'Symbol sa nepodarilo premenovať.';
  } finally {
    dom.developmentSymbolRenameSubmit.disabled = Boolean(renamePreview) && !renamePreviewEditCount(selectedRenameWorkspaceEdits());
  }
}

async function openDiagnostic(diagnostic, index, { closeProblems = false } = {}) {
  const project = activeProject();
  if (!project || !diagnostic) return false;
  const file = projectFiles(project).find((item) => {
    const path = projectFilePath(project, item);
    return path === diagnostic.filename || item.title === diagnostic.filename;
  });
  if (!file) return false;
  diagnosticIndex = index;
  if (file.id !== activeFileId) await selectFile(file.id);
  window.requestAnimationFrame(() => selectEditorLine(diagnostic.line, diagnostic.column));
  dom.developmentDiagnosticNext.title = `Prejsť na chybu alebo varovanie (${diagnosticIndex + 1} z ${diagnostics.length})`;
  renderProblems();
  if (closeProblems && dom.developmentProblemsDialog.open) dom.developmentProblemsDialog.close();
  return true;
}

async function openNextDiagnostic() {
  if (!diagnostics.length) return;
  const nextIndex = (diagnosticIndex + 1) % diagnostics.length;
  await openDiagnostic(diagnostics[nextIndex], nextIndex);
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
  updateTopbarVisibility();
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
  const rounded = Math.round(value);
  dom.developmentPanel.style.setProperty(property, `${rounded}px`);
  handle?.setAttribute('aria-valuenow', String(rounded));
  rememberDevelopmentLayout(property, rounded);
}

function resetResizeValue(property, handle) {
  dom.developmentPanel.style.removeProperty(property);
  handle?.removeAttribute('aria-valuenow');
  forgetDevelopmentLayout(property);
}

function keyboardResizeDelta(event, orientation, reverse = false) {
  let direction = 0;
  if (orientation === 'vertical') {
    if (event.key === 'ArrowUp') direction = 1;
    if (event.key === 'ArrowDown') direction = -1;
  } else {
    if (event.key === 'ArrowRight') direction = 1;
    if (event.key === 'ArrowLeft') direction = -1;
  }
  if (!direction) return 0;
  return direction * (event.shiftKey ? 40 : 12) * (reverse ? -1 : 1);
}

function installResizeHandle(handle, createSession, { property = '', orientation = 'horizontal', reverseKeys = false, onKeyboardResize = null } = {}) {
  if (!handle || handle.dataset.resizeReady) return;
  handle.dataset.resizeReady = 'true';
  if (property && onKeyboardResize) {
    const label = handle.getAttribute('aria-label') || 'Zmeniť veľkosť panela';
    const keys = orientation === 'vertical' ? 'Šípka hore a dole' : 'Šípka vľavo a vpravo';
    const hint = `${keys} mení veľkosť, Shift zrýchli krok a dvojklik obnoví predvolenú veľkosť.`;
    handle.title = `${label}. ${hint}`;
    handle.setAttribute('aria-description', hint);
  }
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
  if (!property || !onKeyboardResize) return;
  handle.addEventListener('keydown', (event) => {
    const delta = keyboardResizeDelta(event, orientation, reverseKeys);
    if (!delta) return;
    event.preventDefault();
    onKeyboardResize(delta);
  });
  handle.addEventListener('dblclick', () => resetResizeValue(property, handle));
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
  }, {
    property: '--development-sidebar-size',
    onKeyboardResize(delta) {
      const panelRect = dom.developmentPanel.getBoundingClientRect();
      const minimum = 168;
      const maximum = Math.min(440, panelRect.width - 520);
      const current = dom.developmentSidebarResize.getBoundingClientRect().left - panelRect.left;
      setResizeValue('--development-sidebar-size', clamp(current + delta, minimum, maximum), dom.developmentSidebarResize);
    },
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
  }, {
    property: '--development-console-size',
    orientation: 'vertical',
    onKeyboardResize(delta) {
      if (!consoleExpanded) return;
      const gridRect = dom.developmentEditorResize.parentElement.getBoundingClientRect();
      const minimum = 120;
      const maximum = gridRect.height - 180 - 8;
      const current = gridRect.bottom - dom.developmentEditorResize.getBoundingClientRect().top;
      setResizeValue('--development-console-size', clamp(current + delta, minimum, maximum), dom.developmentEditorResize);
    },
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
  }, {
    property: '--development-input-size',
    onKeyboardResize(delta) {
      const consoleRect = dom.developmentConsoleSection.getBoundingClientRect();
      const minimum = 120;
      const maximum = consoleRect.width - 16 - 180 - 180;
      const current = dom.developmentInputResize.getBoundingClientRect().left - consoleRect.left;
      setResizeValue('--development-input-size', clamp(current + delta, minimum, maximum), dom.developmentInputResize);
    },
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
  }, {
    property: '--development-compile-size',
    onKeyboardResize(delta) {
      const consoleRect = dom.developmentConsoleSection.getBoundingClientRect();
      const inputWidth = dom.developmentConsoleInputPanel.getBoundingClientRect().width;
      const minimum = 180;
      const maximum = consoleRect.width - inputWidth - 16 - 180;
      const current = dom.developmentCompilePanel.getBoundingClientRect().width;
      setResizeValue('--development-compile-size', clamp(current + delta, minimum, maximum), dom.developmentCompileResize);
    },
  });

  installResizeHandle(dom.developmentTutorialGuideResize, () => {
    if (!tutorialGuideOpen) return null;
    const codeRect = dom.developmentCodeSection.getBoundingClientRect();
    const minimum = 220;
    const maximum = Math.max(minimum, codeRect.width - 260);
    return {
      move(event) {
        setResizeValue('--development-tutorial-guide-size', clamp(codeRect.right - event.clientX, minimum, maximum), dom.developmentTutorialGuideResize);
      }
    };
  }, {
    property: '--development-tutorial-guide-size',
    reverseKeys: true,
    onKeyboardResize(delta) {
      if (!tutorialGuideOpen) return;
      const codeRect = dom.developmentCodeSection.getBoundingClientRect();
      const minimum = 220;
      const maximum = Math.max(minimum, codeRect.width - 260);
      const current = codeRect.right - dom.developmentTutorialGuideResize.getBoundingClientRect().left;
      setResizeValue('--development-tutorial-guide-size', clamp(current + delta, minimum, maximum), dom.developmentTutorialGuideResize);
    },
  });
}

function setRuntimeStatus(status) {
  runtime = status || { available: false, message: 'Skúšobňa nie je dostupná.' };
  const languageStatuses = Object.entries(runtime.languages || {});
  const availableLanguages = languageStatuses
    .filter(([, item]) => item?.available)
    .map(([language]) => languageLabel(language));
  const details = languageStatuses
    .map(([language, item]) => `${languageLabel(language)}: ${item?.available ? 'pripravený' : item?.message || 'nedostupný'}`)
    .join('\n');
  const message = availableLanguages.length
    ? `Pripravené: ${availableLanguages.join(', ')}`
    : runtime.message || 'Skúšobňa nie je dostupná.';
  dom.developmentRuntimeStatus.replaceChildren(createAppIcon('terminal'), document.createTextNode(message));
  dom.developmentRuntimeStatus.classList.toggle('is-ready', availableLanguages.length > 0);
  const title = [message, details].filter(Boolean).join('\n\n');
  dom.developmentRuntimeStatus.title = title;
  dom.developmentSidebarTitle.title = title;
}

function projectSupportsDebugging(project = activeProject()) {
  return Boolean(project && project.kind === 'program' && ['c', 'cpp'].includes(project.language));
}

function renderDebugButton(project = activeProject()) {
  const supported = projectSupportsDebugging(project);
  dom.developmentDebug.hidden = !supported;
  if (!supported) return;
  const available = Boolean(debuggerRuntime.available);
  const title = available
    ? 'Ladiť projekt (zastaví sa na začiatku main)'
    : debuggerRuntime.message || 'Debugger nie je dostupný.';
  dom.developmentDebug.disabled = false;
  dom.developmentDebug.title = title;
  dom.developmentDebug.setAttribute('aria-label', title);
  dom.developmentDebug.dataset.available = String(available);
}

function renderSymbolRenameButton(project = activeProject()) {
  const available = Boolean(project && activeFile());
  const symbol = available ? developmentEditorSymbol() : '';
  dom.developmentSymbolRename.hidden = !available;
  dom.developmentSymbolRename.disabled = !symbol;
  const title = symbol
    ? `Premenovať „${symbol}“ (F2)`
    : 'Umiestni kurzor na názov symbolu, ktorý chceš premenovať.';
  dom.developmentSymbolRename.title = title;
  dom.developmentSymbolRename.setAttribute('aria-label', title);
}

function setRunStatus(phase) {
  const value = String(phase || 'Pripravená');
  const lowerCaseValue = value.toLocaleLowerCase('sk');
  const state = lowerCaseValue.includes('chyba')
    ? 'error'
    : lowerCaseValue === 'hotovo' || lowerCaseValue.startsWith('preložen')
        ? 'success'
        : lowerCaseValue.includes('preklad')
          ? 'working'
          : 'ready';
  dom.developmentConsoleStatus.textContent = value;
  dom.developmentConsoleStatus.dataset.state = state;
  dom.developmentConsoleStatus.setAttribute('aria-label', `Skúšobňa: ${value}`);
  dom.developmentConsoleStatus.title = `Skúšobňa: ${value}`;
}

async function copyDevelopmentConsoleText(value, button, label) {
  const text = String(value || '');
  try {
    let copied = false;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch {
        copied = false;
      }
    }
    if (!copied) {
      const fallback = document.createElement('textarea');
      fallback.value = text;
      fallback.setAttribute('readonly', '');
      fallback.style.position = 'fixed';
      fallback.style.opacity = '0';
      document.body.append(fallback);
      fallback.select();
      const fallbackCopied = document.execCommand('copy');
      fallback.remove();
      if (!fallbackCopied) throw new Error('Prehliadač nepovolil zápis do schránky.');
    }
    const icon = button.querySelector('.app-icon');
    const originalTitle = button.dataset.originalTitle || button.title;
    button.dataset.originalTitle = originalTitle;
    button.title = `${label} skopírovaný.`;
    button.setAttribute('aria-label', button.title);
    setAppIcon(icon, 'check');
    window.setTimeout(() => {
      button.title = originalTitle;
      button.setAttribute('aria-label', originalTitle);
      setAppIcon(icon, 'duplicate');
    }, 1200);
  } catch (error) {
    const message = error?.message || `${label} sa nepodarilo skopírovať.`;
    button.title = message;
    button.setAttribute('aria-label', message);
  }
}

function clearDevelopmentStandardInput() {
  standardInput = '';
  dom.developmentInput.value = '';
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'development' } }));
  dom.developmentInput.focus();
}

function clearDevelopmentCompileOutput() {
  clearDiagnostics();
  dom.developmentCompileOutput.textContent = '';
  dom.developmentCompileMeta.textContent = '';
}

function clearDevelopmentRunOutput() {
  dom.developmentRunOutput.textContent = '';
  dom.developmentRunMeta.textContent = '';
}

function setConsole({ phase = 'Pripravená', compile = 'Projekt ešte nebol spustený.', compileMeta = '', output = 'Výstup programu sa zobrazí tu.', outputMeta = '' } = {}) {
  setRunStatus(phase);
  dom.developmentCompileOutput.textContent = compile;
  dom.developmentCompileMeta.textContent = compileMeta;
  dom.developmentRunOutput.textContent = output;
  dom.developmentRunMeta.textContent = outputMeta;
}

function testDraftData() {
  return {
    title: dom.developmentTestTitle.value.trim(),
    arguments: dom.developmentTestArguments.value,
    stdin: dom.developmentTestInput.value,
    expectedOutput: dom.developmentTestExpectedOutput.value,
  };
}

function testDraftSnapshot() {
  return JSON.stringify(testDraftData());
}

function setTestStatus(message = '') {
  dom.developmentTestStatus.textContent = message;
}

function clearTestResult() {
  displayedTestEvaluation = null;
  dom.developmentTestResult.hidden = true;
  delete dom.developmentTestResult.dataset.state;
  dom.developmentTestResultTitle.textContent = '';
  dom.developmentTestResultSummary.textContent = '';
  dom.developmentTestResultOpenLocation.hidden = true;
  dom.developmentTestResultOpenLocation.disabled = true;
  dom.developmentTestResultOpenLocation.title = '';
  dom.developmentTestResultOpenLocation.setAttribute('aria-label', 'Prejsť na chybu');
  dom.developmentTestResultComparison.replaceChildren();
  dom.developmentTestResultDetails.open = false;
  dom.developmentTestResultDetails.hidden = true;
  dom.developmentTestResultDetailsText.textContent = '';
}

function useLastRunOutputForTest() {
  const output = dom.developmentRunOutput.textContent;
  const untouched = output === 'Výstup programu sa zobrazí tu.';
  if (untouched) {
    setTestStatus('Najprv spusti program, aby bol k dispozícii jeho výstup.');
    return;
  }
  dom.developmentTestExpectedOutput.value = output;
  setTestStatus('Posledný výstup programu je pripravený ako očakávaný výstup. Ulož test.');
  dom.developmentTestExpectedOutput.focus();
}

function testComparisonLine(value) {
  if (value === null) return '(riadok chýba)';
  return value || '(prázdny riadok)';
}

function showTestComparison(comparison) {
  dom.developmentTestResultComparison.replaceChildren();
  if (!comparison) return;
  const appendValue = (label, value, state) => {
    const item = document.createElement('div');
    item.className = `development-test-result-value is-${state}`;
    const term = document.createElement('dt');
    term.textContent = label;
    const description = document.createElement('dd');
    description.textContent = testComparisonLine(value);
    item.append(term, description);
    dom.developmentTestResultComparison.append(item);
  };
  dom.developmentTestResultSummary.textContent = `Prvý rozdiel je na riadku ${comparison.line}.`;
  appendValue('Očakávané', comparison.expected, 'expected');
  appendValue('Skutočné', comparison.actual, 'actual');
}

function showTestResult(evaluation) {
  const {
    passed,
    title = '',
    summary = '',
    comparison = null,
    details = '',
    diagnostic = null,
  } = evaluation;
  displayedTestEvaluation = evaluation;
  dom.developmentTestResult.hidden = false;
  dom.developmentTestResult.dataset.state = passed ? 'success' : 'error';
  dom.developmentTestResultTitle.textContent = title || (passed ? 'Test prešiel.' : 'Test neprešiel.');
  dom.developmentTestResultSummary.textContent = summary || (!comparison ? details : '');
  dom.developmentTestResultOpenLocation.hidden = passed || !diagnostic;
  dom.developmentTestResultOpenLocation.disabled = !diagnostic;
  const locationTitle = diagnostic
    ? `Prejsť na ${diagnostic.filename}:${diagnostic.line}`
    : 'Prejsť na chybu';
  dom.developmentTestResultOpenLocation.title = locationTitle;
  dom.developmentTestResultOpenLocation.setAttribute('aria-label', locationTitle);
  showTestComparison(comparison);
  dom.developmentTestResultDetails.open = false;
  dom.developmentTestResultDetails.hidden = !comparison || !details;
  dom.developmentTestResultDetailsText.textContent = details;
}

function evaluateTestResponse(response) {
  const result = response.result;
  const compile = result.compile || {};
  const run = result.run || {};
  const actual = resultRawText(run);
  const expected = response.test.expectedOutput;
  const compiled = Boolean(result.compiled);
  const exitCode = Number(run.exitCode);
  const compileText = resultText(compile);
  const runText = resultRawText(run);
  const outputMatches = normalizedTestOutput(actual) === normalizedTestOutput(expected);
  const passed = compiled && exitCode === 0 && outputMatches;
  const comparison = compiled && exitCode === 0 ? firstOutputDifference(expected, actual) : null;
  const status = passed
    ? 'passed'
    : !compiled
      ? 'compile_error'
      : exitCode !== 0
        ? 'runtime_error'
        : 'output_mismatch';
  const durationMs = [compile, run].reduce((total, item) => total + Math.max(0, Number(item.durationMs) || 0), 0);
  const title = passed
    ? 'Test prešiel.'
    : !compiled
      ? 'Preklad zlyhal.'
      : exitCode !== 0
        ? `Program skončil kódom ${Number.isFinite(exitCode) ? exitCode : '?'}.'`
        : 'Výstup sa nezhoduje.';
  const summary = passed
    ? 'Skutočný výstup zodpovedá očakávanému výstupu.'
    : !compiled
      ? 'Podrobnosti sú v paneli Preklad.'
      : exitCode !== 0
        ? 'Podrobnosti sú v paneli Výstup.'
        : '';
  return {
    response,
    result,
    passed,
    status,
    durationMs,
    title,
    summary,
    comparison,
    details: comparison ? fullOutputComparison(expected, actual) : '',
    diagnostic: firstTestFailureDiagnostic({ compiled, compileOutput: compileText, runOutput: runText }),
  };
}

function showTestConsole(evaluation) {
  const { result } = evaluation;
  const compile = result.compile || {};
  const run = result.run || {};
  const compileText = resultText(compile);
  const runText = resultRawText(run);
  readDiagnostics([compileText, runText].filter(Boolean).join('\n'));
  setConsole({
    phase: result.compiled ? 'Hotovo' : 'Chyba prekladu',
    compile: compileText,
    compileMeta: formatResultMeta(compile),
    output: result.compiled ? runText : 'Program sa nespustil, pretože preklad zlyhal.',
    outputMeta: result.compiled ? formatResultMeta(run) : '',
  });
}

async function openDisplayedTestFailureLocation() {
  const evaluation = displayedTestEvaluation;
  const diagnostic = evaluation?.diagnostic;
  const project = activeProject();
  if (!project || !diagnostic) return;
  if (!(await saveDevelopmentTest({ quiet: true }))) return;

  let index = diagnostics.findIndex((item) => (
    item.filename === diagnostic.filename
    && item.line === diagnostic.line
    && item.column === diagnostic.column
  ));
  if (index < 0) {
    diagnostics = [diagnostic];
    diagnosticIndex = -1;
    setDevelopmentEditorDiagnostics(diagnosticsForActiveFile());
    renderProblems();
    index = 0;
  }

  if (!(await openDiagnostic(diagnostic, index))) {
    setTestStatus('Miesto chyby sa v súboroch projektu nenašlo.');
    return;
  }
  if (dom.developmentTestDialog.open) dom.developmentTestDialog.close();
  window.requestAnimationFrame(() => focusDevelopmentEditor());
}

function testResultLabel(result, { stored = false } = {}) {
  const labels = {
    passed: stored ? 'naposledy prešiel' : 'prešiel',
    output_mismatch: stored ? 'naposledy sa líšil výstup' : 'výstup sa líši',
    compile_error: stored ? 'naposledy chyba prekladu' : 'chyba prekladu',
    runtime_error: stored ? 'naposledy chyba behu' : 'chyba behu',
    request_error: 'nepodarilo sa spustiť',
  };
  return labels[result?.status] || '';
}

function testResultMeta(result, { stored = false } = {}) {
  const label = testResultLabel(result, { stored });
  if (!label) return '';
  const duration = Number(result.durationMs);
  return Number.isFinite(duration) && duration > 0 ? `${label} · ${duration} ms` : label;
}

function renderDevelopmentTests() {
  const selected = activeProjectTest();
  dom.developmentTestList.replaceChildren();
  projectTests.forEach((testCase) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-test-list-item';
    button.classList.toggle('is-active', testCase.id === activeTestId);
    button.setAttribute('aria-pressed', String(testCase.id === activeTestId));
    const title = document.createElement('strong');
    title.textContent = testCase.title;
    const details = document.createElement('small');
    const inputLines = testCase.stdin ? `${testCase.stdin.split('\n').length} r. vstupu` : 'bez vstupu';
    const sessionResult = testRunResults.get(testCase.id);
    const runResult = sessionResult || testCase.lastResult;
    const resultMeta = testResultMeta(runResult, { stored: !sessionResult && Boolean(testCase.lastResult) });
    details.textContent = runResult
      ? `${inputLines} · ${resultMeta}`
      : `${inputLines} · ${testCase.expectedOutput ? 'výstup' : 'bez očakávania'}`;
    if (runResult) button.classList.add(runResult.status === 'passed' ? 'is-passed' : 'is-failed');
    button.append(title, details);
    button.addEventListener('click', () => void selectDevelopmentTest(testCase.id));
    dom.developmentTestList.append(button);
  });
  if (!projectTests.length) {
    const empty = document.createElement('p');
    empty.className = 'development-test-list-empty';
    empty.textContent = 'Zatiaľ tu nie je žiadny test. Pridaj prvý a ulož vstup aj očakávaný výstup.';
    dom.developmentTestList.append(empty);
  }
  const project = activeProject();
  const canRun = project?.kind !== 'firmware' && Boolean(languageRuntime(project?.language).available);
  dom.developmentTestRunAll.disabled = runningAllTests || !canRun || !projectTests.length;
  dom.developmentTestRunAll.title = canRun
    ? 'Spustiť všetky uložené testy'
    : project?.kind === 'firmware'
      ? 'Firmvérový toolchain pripojíme v ďalšom kroku.'
      : languageRuntime(project?.language).message;
  dom.developmentTestCaseForm.hidden = !selected;
  if (!selected) {
    dom.developmentTestDelete.disabled = true;
    dom.developmentTestRun.disabled = true;
    dom.developmentTestSave.disabled = runningAllTests;
    dom.developmentTestCreate.disabled = runningAllTests;
    return;
  }
  dom.developmentTestTitle.value = selected.title;
  dom.developmentTestArguments.value = selected.arguments;
  dom.developmentTestInput.value = selected.stdin;
  dom.developmentTestExpectedOutput.value = selected.expectedOutput;
  testDraftBaseline = testDraftSnapshot();
  dom.developmentTestDelete.disabled = runningAllTests;
  dom.developmentTestCreate.disabled = runningAllTests;
  dom.developmentTestSave.disabled = runningAllTests;
  dom.developmentTestRun.disabled = runningAllTests || !canRun;
  dom.developmentTestRun.title = canRun
    ? 'Spustiť vybraný test'
    : project?.kind === 'firmware'
      ? 'Firmvérový toolchain pripojíme v ďalšom kroku.'
      : languageRuntime(project?.language).message;
}

async function loadDevelopmentTests() {
  const project = activeProject();
  if (!project) return;
  const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}/tests`));
  projectTests = result.tests || [];
  if (!projectTests.some((testCase) => testCase.id === activeTestId)) activeTestId = projectTests[0]?.id || '';
  testRunResults = new Map();
  clearTestResult();
  setTestStatus('');
  renderDevelopmentTests();
}

async function openDevelopmentTests() {
  if (!activeProject() || !(await saveDevelopmentChanges())) return;
  try {
    await loadDevelopmentTests();
    dom.developmentTestDialog.showModal();
  } catch (error) {
    setRunStatus(error.message || 'Testy projektu sa nepodarilo načítať.');
  }
}

async function closeDevelopmentTests() {
  if (!dom.developmentTestDialog.open) return;
  if (await saveDevelopmentTest({ quiet: true })) dom.developmentTestDialog.close();
}

async function saveDevelopmentTest({ quiet = false } = {}) {
  const project = activeProject();
  const testCase = activeProjectTest();
  if (!project) return false;
  if (!testCase) return true;
  const payload = testDraftData();
  if (!payload.title) {
    setTestStatus('Test potrebuje názov.');
    dom.developmentTestTitle.focus();
    return false;
  }
  if (testDraftSnapshot() === testDraftBaseline) return true;
  if (!quiet) setTestStatus('Ukladám test...');
  try {
    const result = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/tests/${encodeURIComponent(testCase.id)}`,
      { method: 'PUT', body: payload }
    ));
    projectTests = projectTests.map((item) => item.id === result.test.id ? result.test : item);
    testDraftBaseline = JSON.stringify({
      title: result.test.title,
      arguments: result.test.arguments,
      stdin: result.test.stdin,
      expectedOutput: result.test.expectedOutput,
    });
    if (!quiet) setTestStatus('Test je uložený.');
    renderDevelopmentTests();
    return true;
  } catch (error) {
    setTestStatus(error.message || 'Test sa nepodarilo uložiť.');
    return false;
  }
}

async function selectDevelopmentTest(testId) {
  if (testId === activeTestId) return;
  if (!(await saveDevelopmentTest({ quiet: true }))) return;
  activeTestId = testId;
  const evaluation = testRunResults.get(testId);
  if (evaluation) {
    if (evaluation.result) showTestConsole(evaluation);
    showTestResult(evaluation);
  } else {
    clearTestResult();
  }
  setTestStatus('');
  renderDevelopmentTests();
}

async function createDevelopmentTest() {
  const project = activeProject();
  if (!project || !(await saveDevelopmentTest({ quiet: true }))) return;
  dom.developmentTestCreate.disabled = true;
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}/tests`, {
      method: 'POST', body: { title: 'Nový test' }
    }));
    projectTests.push(result.test);
    activeTestId = result.test.id;
    clearTestResult();
    setTestStatus('');
    renderDevelopmentTests();
    window.requestAnimationFrame(() => dom.developmentTestTitle.select());
  } catch (error) {
    setTestStatus(error.message || 'Test sa nepodarilo vytvoriť.');
  } finally {
    dom.developmentTestCreate.disabled = false;
  }
}

async function deleteDevelopmentTest() {
  const project = activeProject();
  const testCase = activeProjectTest();
  if (!project || !testCase) return;
  if (!window.confirm(`Odstrániť test „${testCase.title}“?`)) return;
  try {
    await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/tests/${encodeURIComponent(testCase.id)}`,
      { method: 'DELETE' }
    ));
    projectTests = projectTests.filter((item) => item.id !== testCase.id);
    activeTestId = projectTests[0]?.id || '';
    clearTestResult();
    setTestStatus('');
    renderDevelopmentTests();
  } catch (error) {
    setTestStatus(error.message || 'Test sa nepodarilo odstrániť.');
  }
}

function resultRawText(result) {
  if (!result) return '';
  return [result.stdout, result.stderr].filter(Boolean).join(result.stdout && result.stderr ? '\n' : '');
}

async function runDevelopmentTest() {
  const project = activeProject();
  const testCase = activeProjectTest();
  if (!project || !testCase || !(await saveDevelopmentTest()) || !(await saveDevelopmentChanges())) return;
  dom.developmentTestRun.disabled = true;
  setTestStatus('Spúšťam test...');
  clearDiagnostics();
  try {
    const response = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/tests/${encodeURIComponent(testCase.id)}/run`,
      { method: 'POST', body: {} }
    ));
    const evaluation = evaluateTestResponse(response);
    if (response.test) projectTests = projectTests.map((item) => item.id === response.test.id ? response.test : item);
    testRunResults.set(testCase.id, evaluation);
    showTestConsole(evaluation);
    showTestResult(evaluation);
    setTestStatus(evaluation.passed ? 'Test prešiel.' : 'Test neprešiel. Porovnaj výstupy nižšie.');
    setConsoleExpanded(true);
  } catch (error) {
    setTestStatus(error.message || 'Test sa nepodarilo spustiť.');
  } finally {
    renderDevelopmentTests();
  }
}

async function runAllDevelopmentTests() {
  const project = activeProject();
  if (!project || !projectTests.length || !(await saveDevelopmentTest()) || !(await saveDevelopmentChanges())) return;
  const tests = [...projectTests];
  const canRun = project.kind !== 'firmware' && Boolean(languageRuntime(project.language).available);
  if (!canRun) return;
  runningAllTests = true;
  testRunResults = new Map();
  let lastEvaluation = null;
  let firstFailedTestId = '';
  let passedCount = 0;
  clearDiagnostics();
  try {
    for (let index = 0; index < tests.length; index += 1) {
      const testCase = tests[index];
      setTestStatus(`Spúšťam test ${index + 1} z ${tests.length}: ${testCase.title}`);
      try {
        const response = await runOperation(() => apiRequest(
          `/development/projects/${encodeURIComponent(project.id)}/tests/${encodeURIComponent(testCase.id)}/run`,
          { method: 'POST', body: {} }
        ));
        const evaluation = evaluateTestResponse(response);
        if (response.test) projectTests = projectTests.map((item) => item.id === response.test.id ? response.test : item);
        testRunResults.set(testCase.id, evaluation);
        if (evaluation.passed) passedCount += 1;
        if (!evaluation.passed && !firstFailedTestId) firstFailedTestId = testCase.id;
        if (!evaluation.passed || testCase.id === activeTestId) lastEvaluation = evaluation;
      } catch (error) {
        const evaluation = { passed: false, status: 'request_error', details: error.message || 'Test sa nepodarilo spustiť.' };
        testRunResults.set(testCase.id, evaluation);
        if (!firstFailedTestId) firstFailedTestId = testCase.id;
        lastEvaluation = evaluation;
      }
      renderDevelopmentTests();
    }
    if (firstFailedTestId) activeTestId = firstFailedTestId;
    const selectedEvaluation = testRunResults.get(activeTestId) || lastEvaluation;
    if (selectedEvaluation) {
      if (selectedEvaluation.result) showTestConsole(selectedEvaluation);
      showTestResult(selectedEvaluation);
    }
    setTestStatus(firstFailedTestId
      ? `${passedCount} z ${tests.length} testov prešlo. Otvorený je prvý neúspešný test.`
      : `Všetkých ${tests.length} testov prešlo.`);
    setConsoleExpanded(true);
  } finally {
    runningAllTests = false;
    renderDevelopmentTests();
  }
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
    button.append(createProjectMarker(project));
    const copy = document.createElement('span');
    copy.className = 'development-project-copy';
    const title = document.createElement('strong');
    title.textContent = project.title;
    const meta = document.createElement('small');
    const targetLabel = project.kind === 'firmware' ? project.firmwareTarget?.label || 'bez cieľa' : '';
    meta.textContent = targetLabel
      ? `${languageLabel(project.language)} · ${targetLabel} · ${project.buildProfileLabel || 'Ladenie'}`
      : `${languageLabel(project.language)} · ${project.buildProfileLabel || 'Ladenie'} · ${projectFiles(project).length} súborov`;
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

  const draggedItem = () => project.files.find((item) => item.id === draggedProjectItemId) || null;
  const canMoveTo = (item, parentId) => {
    if (!item || item.id === parentId || String(item.parentId || '') === String(parentId || '')) return false;
    if (item.kind !== 'folder' || !parentId) return true;
    let parent = project.files.find((candidate) => candidate.id === parentId) || null;
    const visited = new Set();
    while (parent && !visited.has(parent.id)) {
      if (parent.id === item.id) return false;
      visited.add(parent.id);
      parent = project.files.find((candidate) => candidate.id === parent.parentId) || null;
    }
    return true;
  };
  const clearDropTargets = () => {
    dom.developmentFileTree.querySelectorAll('.is-drop-target').forEach((item) => item.classList.remove('is-drop-target'));
    dom.developmentFileBrowser.classList.remove('is-drop-target');
  };
  const moveDraggedItem = async (parentId) => {
    const item = draggedItem();
    if (!item || !canMoveTo(item, parentId)) return;
    if (!(await saveDevelopmentChanges())) return;
    try {
      const result = await runOperation(() => apiRequest(
        `/development/projects/${encodeURIComponent(project.id)}/files/${encodeURIComponent(item.id)}/move`,
        { method: 'POST', body: { parentId } }
      ));
      selectedFolderId = String(parentId || '');
      if (parentId) {
        expandedFolderIds.add(parentId);
        expandFolderAncestors(result.project, parentId);
      }
      replaceProject(result.project);
    } catch (error) {
      setRunStatus(error.message || 'Položku sa nepodarilo presunúť.');
    }
  };

  dom.developmentFileTree.ondragover = (event) => {
    if (!draggedItem() || event.target.closest('.development-file-tree-row')) return;
    if (!canMoveTo(draggedItem(), '')) return;
    event.preventDefault();
    dom.developmentFileBrowser.classList.add('is-drop-target');
  };
  dom.developmentFileTree.ondrop = (event) => {
    if (!draggedItem() || event.target.closest('.development-file-tree-row')) return;
    event.preventDefault();
    void moveDraggedItem('');
  };
  dom.developmentFileTree.ondragleave = (event) => {
    if (!dom.developmentFileTree.contains(event.relatedTarget)) dom.developmentFileBrowser.classList.remove('is-drop-target');
  };

  const appendRow = (item, depth) => {
    const row = document.createElement('div');
    row.className = 'development-file-tree-row';
    row.style.setProperty('--development-tree-indent', `${depth * 14}px`);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-file-tree-item';
    button.draggable = true;
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
    button.addEventListener('dragstart', (event) => {
      draggedProjectItemId = item.id;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', item.id);
      row.classList.add('is-dragging');
    });
    button.addEventListener('dragend', () => {
      draggedProjectItemId = '';
      row.classList.remove('is-dragging');
      clearDropTargets();
    });
    if (isFolder) {
      button.addEventListener('dragover', (event) => {
        const dragged = draggedItem();
        if (!canMoveTo(dragged, item.id)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        clearDropTargets();
        row.classList.add('is-drop-target');
      });
      button.addEventListener('dragleave', (event) => {
        if (!row.contains(event.relatedTarget)) row.classList.remove('is-drop-target');
      });
      button.addEventListener('drop', (event) => {
        const dragged = draggedItem();
        if (!canMoveTo(dragged, item.id)) return;
        event.preventDefault();
        void moveDraggedItem(item.id);
      });
    }
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

function symbolMarker(kind) {
  return {
    function: 'F',
    macro: '#',
    class: 'C',
    type: 'T',
    label: ':',
    variable: 'V',
  }[kind] || '*';
}

function sourceForProjectFile(file) {
  if (file?.id === activeFileId) return developmentEditorValue();
  return file?.content || '';
}

function symbolOutlineCacheKey(project, file) {
  return project && file ? `${project.id}:${file.id}` : '';
}

function languageServiceSymbolCategory(kind) {
  const value = Number(kind);
  if ([6, 9, 12].includes(value)) return { kind: 'function', label: 'Funkcia' };
  if ([5, 10, 11, 23, 26].includes(value)) return { kind: value === 5 ? 'class' : 'type', label: value === 5 ? 'Trieda' : 'Typ' };
  if (value === 14) return { kind: 'macro', label: 'Konštanta' };
  if ([7, 8, 13, 22].includes(value)) return { kind: 'variable', label: 'Premenná' };
  return { kind: 'variable', label: 'Symbol' };
}

function languageServiceOutlineSymbols(response) {
  const symbols = Array.isArray(response?.symbols) ? response.symbols : [];
  return symbols.map((symbol) => {
    const category = languageServiceSymbolCategory(symbol.kind);
    return {
      name: String(symbol.name || ''),
      signature: String(symbol.detail || ''),
      kind: category.kind,
      label: category.label,
      line: Math.max(1, Number(symbol.line) || 1),
      column: Math.max(1, Number(symbol.column) || 1),
    };
  }).filter((symbol) => symbol.name);
}

function visibleOutlineSymbols(project, file) {
  const source = sourceForProjectFile(file);
  const cached = languageServiceSymbolCache.get(symbolOutlineCacheKey(project, file));
  if (cached?.source === source && cached.symbols.length) return cached.symbols;
  return scanSourceSymbols(source, project.language);
}

function renderOutlineSymbolRows(symbols) {
  dom.developmentSymbolList.replaceChildren();
  if (!symbols.length) {
    const empty = document.createElement('p');
    empty.className = 'development-symbols-empty';
    empty.textContent = 'Bez rozpoznaných symbolov.';
    dom.developmentSymbolList.append(empty);
    return;
  }
  symbols.forEach((symbol) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-symbol-item';
    button.title = `${symbol.label}: ${symbol.signature || symbol.name} (riadok ${symbol.line})`;
    button.setAttribute('aria-label', button.title);
    const marker = document.createElement('span');
    marker.className = 'development-symbol-marker';
    marker.textContent = symbolMarker(symbol.kind);
    const copy = document.createElement('span');
    copy.className = 'development-symbol-copy';
    const title = document.createElement('strong');
    title.textContent = symbol.name;
    const meta = document.createElement('small');
    meta.textContent = `${symbol.label} · ${symbol.line}`;
    copy.append(title, meta);
    button.append(marker, copy);
    button.addEventListener('click', () => {
      selectEditorLine(symbol.line, symbol.column);
      focusDevelopmentEditor();
    });
    dom.developmentSymbolList.append(button);
  });
}

async function refreshSymbolOutline() {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file) return;
  const key = symbolOutlineCacheKey(project, file);
  const source = sourceForProjectFile(file);
  symbolOutlineRefreshKey = key;
  dom.developmentSymbolBrowserRefresh.disabled = true;
  dom.developmentSymbolBrowserRefresh.title = 'Načítavam presnejšiu osnovu...';
  dom.developmentSymbolBrowserRefresh.setAttribute('aria-label', dom.developmentSymbolBrowserRefresh.title);
  try {
    const response = await requestEditorLanguageService({ operation: 'symbols', line: 1, column: 1 });
    if (!response?.available || activeProjectId !== project.id || activeFileId !== file.id || sourceForProjectFile(file) !== source) return;
    const symbols = languageServiceOutlineSymbols(response);
    languageServiceSymbolCache.set(key, { source, symbols });
    renderSymbolOutline();
  } catch {
    // A local outline is already visible and remains the fallback.
  } finally {
    if (symbolOutlineRefreshKey === key) {
      symbolOutlineRefreshKey = '';
      dom.developmentSymbolBrowserRefresh.disabled = false;
      dom.developmentSymbolBrowserRefresh.title = 'Spresniť osnovu cez jazykový server';
      dom.developmentSymbolBrowserRefresh.setAttribute('aria-label', dom.developmentSymbolBrowserRefresh.title);
    }
  }
}

function queueSymbolOutlineRefresh() {
  window.clearTimeout(symbolOutlineRefreshTimer);
  const project = activeProject();
  const file = activeFile();
  if (!project || !file) return;
  symbolOutlineRefreshTimer = window.setTimeout(() => void refreshSymbolOutline(), 0);
}

function renderSymbolOutline() {
  const project = activeProject();
  const file = activeFile();
  const browser = dom.developmentSymbolBrowser;
  const sidebar = browser.closest('.development-sidebar');
  const available = Boolean(project && file);
  browser.hidden = !available;
  sidebar.classList.toggle('has-symbol-browser', available);
  sidebar.classList.toggle('symbols-collapsed', available && !symbolBrowserExpanded);
  if (!available) return;

  browser.classList.toggle('is-collapsed', !symbolBrowserExpanded);
  dom.developmentSymbolBrowserToggle.setAttribute('aria-expanded', String(symbolBrowserExpanded));
  dom.developmentSymbolBrowserToggle.title = symbolBrowserExpanded ? 'Zbaliť osnovu symbolov' : 'Rozbaliť osnovu symbolov';
  dom.developmentSymbolBrowserToggle.setAttribute('aria-label', dom.developmentSymbolBrowserToggle.title);
  setAppIcon(
    dom.developmentSymbolBrowserToggle.querySelector('.app-icon'),
    symbolBrowserExpanded ? 'chevron-down' : 'chevron-right'
  );
  dom.developmentSymbolBrowserRefresh.disabled = symbolOutlineRefreshKey === symbolOutlineCacheKey(project, file);
  if (!symbolBrowserExpanded) return;
  renderOutlineSymbolRows(visibleOutlineSymbols(project, file));
}

function quickOpenEntriesForMode() {
  const project = activeProject();
  if (!project) return [];
  const files = projectFiles(project).map((file) => ({
    ...file,
    content: sourceForProjectFile(file),
  }));
  if (quickOpenMode === 'files') {
    return files.map((file) => ({
      kind: 'file',
      label: file.title,
      detail: projectFilePath(project, file),
      file,
    }));
  }
  if (quickOpenMode === 'snippets') {
    return projectSnippetEntries(project.language).map((entry) => ({
      kind: 'snippet',
      label: entry.label,
      detail: entry.detail,
      template: entry.template,
    }));
  }
  return scanProjectSymbols(files, project.language).map((symbol) => ({
    kind: symbol.kind,
    label: symbol.name,
    detail: `${projectFilePath(project, symbol.file)}:${symbol.line} · ${symbol.label}`,
    file: symbol.file,
    line: symbol.line,
    column: symbol.column,
  }));
}

function quickOpenSearchTerms() {
  return dom.developmentQuickOpenInput.value.trim().toLocaleLowerCase('sk').split(/\s+/).filter(Boolean);
}

function visibleQuickOpenEntries() {
  const terms = quickOpenSearchTerms();
  return quickOpenEntriesForMode()
    .filter((entry) => {
      if (!terms.length) return true;
      const searchable = `${entry.label} ${entry.detail}`.toLocaleLowerCase('sk');
      return terms.every((term) => searchable.includes(term));
    })
    .slice(0, MAX_QUICK_OPEN_RESULTS);
}

function renderQuickOpen() {
  quickOpenResults = visibleQuickOpenEntries();
  quickOpenResultIndex = Math.min(Math.max(0, quickOpenResultIndex), Math.max(quickOpenResults.length - 1, 0));
  const symbolMode = quickOpenMode === 'symbols';
  const snippetMode = quickOpenMode === 'snippets';
  dom.developmentQuickOpenFiles.setAttribute('aria-pressed', String(quickOpenMode === 'files'));
  dom.developmentQuickOpenSymbols.setAttribute('aria-pressed', String(symbolMode));
  dom.developmentQuickOpenSnippets.setAttribute('aria-pressed', String(snippetMode));
  dom.developmentQuickOpenInput.placeholder = snippetMode
    ? 'Hľadať šablónu'
    : symbolMode
      ? 'Hľadať funkciu, makro alebo triedu'
      : 'Hľadať súbor';
  dom.developmentQuickOpenResults.replaceChildren();
  if (!quickOpenResults.length) {
    const empty = document.createElement('p');
    empty.className = 'development-quick-open-empty';
    empty.textContent = 'Bez výsledkov.';
    dom.developmentQuickOpenResults.append(empty);
    return;
  }
  quickOpenResults.forEach((entry, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-quick-open-result';
    button.setAttribute('role', 'option');
    button.setAttribute('aria-selected', String(index === quickOpenResultIndex));
    if (index === quickOpenResultIndex) button.classList.add('is-active');
    const marker = document.createElement('span');
    marker.className = 'development-quick-open-marker';
    marker.textContent = entry.kind === 'file' ? 'S' : entry.kind === 'snippet' ? '+' : symbolMarker(entry.kind);
    const copy = document.createElement('span');
    copy.className = 'development-quick-open-copy';
    const title = document.createElement('strong');
    title.textContent = entry.label;
    const detail = document.createElement('small');
    detail.textContent = entry.detail;
    copy.append(title, detail);
    button.append(marker, copy);
    button.addEventListener('mouseenter', () => {
      quickOpenResultIndex = index;
      dom.developmentQuickOpenResults.querySelectorAll('.development-quick-open-result').forEach((item, itemIndex) => {
        const active = itemIndex === index;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', String(active));
      });
    });
    button.addEventListener('click', () => void chooseQuickOpenEntry(index));
    dom.developmentQuickOpenResults.append(button);
  });
}

function setQuickOpenMode(mode) {
  quickOpenMode = ['files', 'symbols', 'snippets'].includes(mode) ? mode : 'files';
  quickOpenResultIndex = 0;
  renderQuickOpen();
}

function openQuickOpen(mode = 'files') {
  if (!activeProject()) return;
  quickOpenMode = ['files', 'symbols', 'snippets'].includes(mode) ? mode : 'files';
  quickOpenResultIndex = 0;
  dom.developmentQuickOpenInput.value = '';
  renderQuickOpen();
  if (!dom.developmentQuickOpenDialog.open) dom.developmentQuickOpenDialog.showModal();
  window.requestAnimationFrame(() => dom.developmentQuickOpenInput.focus());
}

function openGoToLine() {
  const location = editorLocation();
  if (!location) return;
  const lastLine = Math.max(1, developmentEditorValue().split('\n').length);
  dom.developmentGoToLineInput.min = '1';
  dom.developmentGoToLineInput.max = String(lastLine);
  dom.developmentGoToLineInput.value = String(location.line);
  dom.developmentGoToLineInput.setCustomValidity('');
  if (!dom.developmentGoToLineDialog.open) dom.developmentGoToLineDialog.showModal();
  window.requestAnimationFrame(() => {
    dom.developmentGoToLineInput.focus();
    dom.developmentGoToLineInput.select();
  });
}

function goToEditorLine(event) {
  event.preventDefault();
  const lastLine = Math.max(1, developmentEditorValue().split('\n').length);
  const line = Number(dom.developmentGoToLineInput.value);
  if (!Number.isInteger(line) || line < 1 || line > lastLine) {
    dom.developmentGoToLineInput.setCustomValidity(`Zadaj riadok od 1 do ${lastLine}.`);
    dom.developmentGoToLineInput.reportValidity();
    return;
  }
  dom.developmentGoToLineInput.setCustomValidity('');
  dom.developmentGoToLineDialog.close();
  selectEditorLine(line);
  focusDevelopmentEditor();
}

async function chooseQuickOpenEntry(index = quickOpenResultIndex) {
  const entry = quickOpenResults[index];
  if (!entry) return;
  if (entry.kind === 'snippet') {
    insertDevelopmentEditorSnippet(entry.template);
    dom.developmentQuickOpenDialog.close();
    return;
  }
  if (entry.file.id !== activeFileId) await selectFile(entry.file.id);
  if (entry.line) {
    window.requestAnimationFrame(() => {
      selectEditorLine(entry.line, entry.column);
      focusDevelopmentEditor();
    });
  }
  dom.developmentQuickOpenDialog.close();
}

function projectTutorialLink(project = activeProject()) {
  const link = project?.tutorialLink;
  return link?.languageId && link?.pageId ? link : null;
}

function renderTutorialGuideMessage(message) {
  dom.developmentTutorialGuideTopic.textContent = '';
  dom.developmentTutorialGuideTitle.textContent = 'Učebnica';
  dom.developmentTutorialGuideContent.replaceChildren();
  const paragraph = document.createElement('p');
  paragraph.className = 'development-tutorial-guide-message';
  paragraph.textContent = message;
  dom.developmentTutorialGuideContent.append(paragraph);
}

function renderTutorialGuidePage(language, page) {
  dom.developmentTutorialGuideTopic.textContent = language.title || 'Učebnica';
  dom.developmentTutorialGuideTitle.textContent = page.title || 'Výklad';
  dom.developmentTutorialGuideContent.replaceChildren();
  const content = page.content || {};
  if (content.lead) {
    const lead = document.createElement('p');
    lead.className = 'development-tutorial-guide-lead';
    lead.textContent = content.lead;
    dom.developmentTutorialGuideContent.append(lead);
  }
  (content.sections || []).forEach((section) => {
    const block = document.createElement('section');
    if (section.title) {
      const heading = document.createElement('h4');
      heading.textContent = section.title;
      block.append(heading);
    }
    (section.paragraphs || []).forEach((text) => {
      const paragraph = document.createElement('p');
      paragraph.textContent = text;
      block.append(paragraph);
    });
    if (section.bullets?.length) {
      const list = document.createElement('ul');
      section.bullets.forEach((text) => {
        const item = document.createElement('li');
        item.textContent = text;
        list.append(item);
      });
      block.append(list);
    }
    if (section.callout) {
      const callout = document.createElement('p');
      callout.className = 'development-tutorial-guide-callout';
      callout.textContent = section.callout;
      block.append(callout);
    }
    dom.developmentTutorialGuideContent.append(block);
  });
  if (!dom.developmentTutorialGuideContent.childElementCount) {
    renderTutorialGuideMessage('Táto stránka zatiaľ nemá výklad.');
  }
}

async function loadTutorialGuide() {
  const project = activeProject();
  const link = projectTutorialLink(project);
  if (!tutorialGuideOpen || !project || !link) return;
  const cacheKey = `${link.languageId}:${link.pageId}`;
  const cached = tutorialGuideCache.get(cacheKey);
  if (cached) {
    renderTutorialGuidePage(cached.language, cached.page);
    return;
  }
  renderTutorialGuideMessage('Načítavam výklad...');
  try {
    const result = await runOperation(() => apiRequest(`/tutorial/languages/${encodeURIComponent(link.languageId)}`));
    const page = (result.pages || []).find((item) => item.id === link.pageId);
    if (!page) throw new Error('Prepojená stránka učebnice už neexistuje.');
    tutorialGuideCache.set(cacheKey, { language: result.language || {}, page });
    const activeLink = projectTutorialLink();
    if (
      tutorialGuideOpen
      && activeProjectId === project.id
      && activeLink?.languageId === link.languageId
      && activeLink?.pageId === link.pageId
    ) {
      renderTutorialGuidePage(result.language || {}, page);
    }
  } catch (error) {
    if (tutorialGuideOpen && activeProjectId === project.id) {
      renderTutorialGuideMessage(error.message || 'Výklad sa nepodarilo načítať.');
    }
  }
}

function setTutorialGuideOpen(open) {
  const enabled = Boolean(open && projectTutorialLink());
  tutorialGuideOpen = enabled;
  dom.developmentCodeSection.classList.toggle('has-tutorial-guide', enabled);
  dom.developmentTutorialGuide.hidden = !enabled;
  dom.developmentTutorialGuideResize.hidden = !enabled;
  dom.developmentTutorialGuideToggle.setAttribute('aria-pressed', String(enabled));
  dom.developmentTutorialGuideToggle.title = enabled ? 'Skryť výklad z učebnice' : 'Výklad z učebnice';
  dom.developmentTutorialGuideToggle.setAttribute('aria-label', enabled ? 'Skryť výklad z učebnice' : 'Zobraziť výklad z učebnice');
  if (enabled) void loadTutorialGuide();
}

function syncTutorialGuide(project) {
  const linked = Boolean(projectTutorialLink(project));
  dom.developmentTutorialGuideToggle.hidden = !linked;
  if (!linked && tutorialGuideOpen) {
    setTutorialGuideOpen(false);
    return;
  }
  dom.developmentTutorialGuideToggle.setAttribute('aria-pressed', String(tutorialGuideOpen));
  if (linked && tutorialGuideOpen) void loadTutorialGuide();
}

function openTutorialSource() {
  const link = projectTutorialLink();
  if (!link) return;
  window.dispatchEvent(new CustomEvent('development-tutorial-open', { detail: link }));
}

function renderEditor() {
  const project = activeProject();
  const file = activeFile();
  const hasProject = Boolean(project && file);
  dom.developmentProjectEditor.hidden = !hasProject;
  dom.developmentProjectExport.disabled = !project;
  dom.developmentWorkspace.querySelector('.development-empty').hidden = Boolean(projects.length);
  if (!hasProject) {
    syncTutorialGuide(null);
    renderDebugButton(null);
    renderSymbolRenameButton(null);
    renderBinaryInspectorButton(null);
    renderFirmwareProgramButton(null);
    renderSerialMonitorButton(null);
    renderSymbolOutline();
    return;
  }

  dom.developmentProjectTitle.value = project.title;
  fitProjectTitle();
  projectTitleBaseline = project.title;
  dom.developmentProjectLanguage.textContent = languageLabel(project.language);
  dom.developmentProjectLanguage.dataset.language = project.language;
  dom.developmentProjectLanguage.title = `${project.title} · ${languageLabel(project.language)} · ${project.buildProfileLabel || 'Ladenie'}`;
  const isFirmware = project.kind === 'firmware';
  const target = project.firmwareTarget;
  const toolchain = isFirmware ? firmwareToolchainStatus(project.firmwareTargetId) : null;
  const firmwareStatus = isFirmware ? firmwareBuildStatus(project.firmwareTargetId, project.language) : null;
  const device = configuredFirmwareDevice(project);
  dom.developmentProjectTarget.hidden = !isFirmware;
  dom.developmentProjectTarget.textContent = target
    ? `${target.label} · ${project.buildProfileLabel || 'Ladenie'}`
    : 'Firmvér bez cieľa';
  dom.developmentProjectTarget.title = target
    ? `${target.family} · ${target.board}\n${target.architecture} · ${target.toolchain}\n\n${toolchain?.message || ''}${device?.programmer ? `\n${device.programmer.label}${device.port ? ` · ${device.port}` : ''}` : ''}`
    : 'Vyber cieľový čip alebo dosku.';
  dom.developmentProjectTarget.dataset.state = firmwareStatus?.available ? 'ready' : toolchain?.programmerAvailable ? 'partial' : 'missing';
  dom.developmentTargetConfigure.hidden = false;
  dom.developmentTargetConfigure.title = isFirmware
    ? `Nastaviť projekt firmvéru\n\n${toolchain?.message || ''}`
    : 'Nastaviť projekt';
  dom.developmentTargetConfigure.setAttribute('aria-label', dom.developmentTargetConfigure.title);
  dom.developmentFileTitle.value = file.title;
  setDevelopmentEditorProjectFiles(projectFiles(project).map((item) => ({
    ...item,
    path: projectFilePath(project, item),
  })), { activePath: projectFilePath(project, file) });
  setDevelopmentEditorDocument(file.content, project.language);
  restoreActiveEditorViewState();
  setDevelopmentEditorDiagnostics(diagnosticsForActiveFile());
  if (!dom.developmentFindBar.hidden) updateFindMatches({ preserveMatch: true });
  dom.developmentInput.value = standardInput;
  runArguments = project.runArguments || '';
  projectRunArgumentsBaseline = runArguments;
  dom.developmentRunArguments.value = runArguments;
  fileDraftBaseline = activeFileSnapshot();
  dom.developmentFileDelete.disabled = projectFiles(project).length <= 1;
  const isEntryFile = file.id === project.entryFileId;
  dom.developmentEntryFile.setAttribute('aria-pressed', String(isEntryFile));
  dom.developmentEntryFile.title = isEntryFile ? 'Hlavný súbor projektu' : 'Nastaviť ako hlavný súbor projektu';
  dom.developmentEntryFile.setAttribute('aria-label', dom.developmentEntryFile.title);
  const languageStatus = languageRuntime(project.language);
  const canRun = !isFirmware && Boolean(languageStatus.available);
  const canBuildFirmware = isFirmware && Boolean(firmwareStatus?.available);
  dom.developmentBuild.disabled = !(canRun || canBuildFirmware);
  dom.developmentBuild.title = canRun
    ? 'Preložiť bez spustenia (Ctrl+Shift+Enter)'
    : isFirmware
      ? firmwareStatus?.available
        ? 'Zostaviť firmvér (Ctrl+Shift+Enter)'
        : firmwareStatus?.message || 'Firmvérový toolchain nie je dostupný.'
      : languageStatus.message;
  dom.developmentRun.disabled = !canRun;
  dom.developmentRun.title = canRun
    ? 'Preložiť a spustiť projekt (Ctrl+Enter)'
    : isFirmware
      ? toolchain?.message || 'Firmvérový toolchain nie je dostupný.'
      : languageStatus.message;
  dom.developmentTests.disabled = !project;
  dom.developmentTests.title = isFirmware
    ? 'Testy projektu sa pripravia; spúšťanie firmvéru pripojíme s toolchainom.'
    : 'Testy projektu';
  renderDebugButton(project);
  renderSymbolRenameButton(project);
  renderBinaryInspectorButton(project);
  renderFirmwareProgramButton(project);
  renderSerialMonitorButton(project);
  syncTutorialGuide(project);

  dom.developmentFileTabs.replaceChildren();
  projectFiles(project).forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-file-tab';
    button.dataset.fileId = String(item.id);
    button.classList.toggle('is-active', item.id === activeFileId);
    button.classList.toggle('is-entry', item.id === project.entryFileId);
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', String(item.id === activeFileId));
    button.title = `${project.title} / ${projectFilePath(project, item)}`;
    button.setAttribute('aria-label', button.title);
    button.append(createAppIcon('file'));
    const label = document.createElement('span');
    label.textContent = item.title;
    button.append(label);
    button.addEventListener('click', () => void selectFile(item.id));
    dom.developmentFileTabs.append(button);
  });
  updateDirtyFileState();
  renderSymbolOutline();
  renderDefinitionNavigation();
}

function updateDirtyFileState() {
  const file = activeFile();
  const isDirty = Boolean(file) && activeFileSnapshot() !== fileDraftBaseline;
  const activeTab = dom.developmentFileTabs?.querySelector(`[data-file-id="${activeFileId}"]`);
  activeTab?.classList.toggle('is-dirty', isDirty);
  dom.developmentSave?.classList.toggle('is-dirty', isDirty);
  if (dom.developmentSave) {
    dom.developmentSave.title = isDirty ? 'Uložiť zmeny (Ctrl+S)' : 'Zmeny sú uložené (Ctrl+S)';
  }
}

function formatActiveFile() {
  if (!activeFile()) return;
  const changed = formatDevelopmentEditor();
  const button = dom.developmentFormat;
  const originalTitle = 'Zarovnať odsadenie (Ctrl+Alt+F)';
  const message = changed ? 'Odsadenie bolo zarovnané.' : 'Odsadenie už bolo zarovnané.';
  button.title = message;
  button.setAttribute('aria-label', message);
  setAppIcon(button.querySelector('.app-icon'), 'check');
  window.setTimeout(() => {
    button.title = originalTitle;
    button.setAttribute('aria-label', 'Zarovnať odsadenie otvoreného súboru');
    setAppIcon(button.querySelector('.app-icon'), 'indent');
  }, 1300);
}

function replaceProject(project) {
  const index = projects.findIndex((item) => item.id === project.id);
  if (index >= 0) projects[index] = project;
  else projects.unshift(project);
  activeProjectId = project.id;
  ensureActiveFile(project);
  rememberDevelopmentSession();
  renderProjects();
  renderEditor();
  queueSymbolOutlineRefresh();
}

async function loadWorkspace() {
  const workspace = await apiRequest('/development');
  projects = workspace.projects || [];
  editorViewStates = new Map();
  expandedFolderIds = new Set(projects.flatMap((project) => projectFolders(project).map((folder) => folder.id)));
  languages = workspace.languages || [];
  firmwareTargets = workspace.firmwareTargets || [];
  firmwareTools = workspace.firmwareTools || {};
  firmwareDevices = workspace.firmwareDevices || { ports: [], programmers: {} };
  firmwareBuild = workspace.firmwareBuild || { targets: {} };
  serialMonitor = workspace.serialMonitor || serialMonitor;
  buildProfiles = workspace.buildProfiles || workspace.firmwareBuildProfiles || [];
  setRuntimeStatus(workspace.runtime);
  debuggerRuntime = workspace.debugger || { available: false, message: 'Debugger nie je dostupný.' };
  const session = rememberedDevelopmentSession();
  const rememberedProject = projects.find((project) => project.id === session?.projectId);
  if (rememberedProject) {
    activeProjectId = rememberedProject.id;
    activeFileId = projectFiles(rememberedProject).some((file) => file.id === session?.fileId)
      ? session.fileId
      : '';
  } else if (!projects.some((project) => project.id === activeProjectId)) {
    activeProjectId = projects[0]?.id || '';
    activeFileId = '';
  }
  ensureActiveFile();
  rememberDevelopmentSession();
  renderProjects();
  renderEditor();
  queueSymbolOutlineRefresh();
}

async function selectProject(projectId) {
  if (projectId === activeProjectId) return;
  void stopDebugging({ quiet: true });
  rememberEditorViewState();
  if (!(await saveDevelopmentChanges())) return;
  activeProjectId = projectId;
  selectedFolderId = '';
  ensureActiveFile();
  standardInput = '';
  runArguments = '';
  projectTests = [];
  activeTestId = '';
  testDraftBaseline = '';
  rememberDevelopmentSession();
  setConsole();
  renderProjects();
  renderEditor();
  queueSymbolOutlineRefresh();
}

async function selectFile(fileId) {
  if (fileId === activeFileId) {
    const currentFile = activeFile();
    selectedFolderId = String(currentFile?.parentId || '');
    expandFolderAncestors(activeProject(), selectedFolderId);
    renderProjects();
    return;
  }
  rememberEditorViewState();
  if (!(await saveActiveFile())) return;
  activeFileId = fileId;
  const file = activeFile();
  selectedFolderId = String(file?.parentId || '');
  expandFolderAncestors(activeProject(), selectedFolderId);
  rememberDevelopmentSession();
  setConsole();
  renderProjects();
  renderEditor();
  queueSymbolOutlineRefresh();
}

function populateProjectLanguages(preferredLanguage = '') {
  const target = dialogProjectKind() === 'firmware'
    ? firmwareTarget(dom.developmentFirmwareTargetInput.value)
    : null;
  const availableLanguages = target
    ? languages.filter((language) => target.languages.includes(language.id))
    : languages;
  const fallbackLanguage = availableLanguages.some((language) => language.id === preferredLanguage)
    ? preferredLanguage
    : availableLanguages[0]?.id || 'c';
  dom.developmentProjectLanguageInput.replaceChildren();
  availableLanguages.forEach((language) => {
    const option = document.createElement('option');
    option.value = language.id;
    const status = languageRuntime(language.id);
    option.textContent = status.available ? language.label : `${language.label} · zatiaľ nespustiteľný`;
    option.title = status.message || '';
    dom.developmentProjectLanguageInput.append(option);
  });
  dom.developmentProjectLanguageInput.value = fallbackLanguage;
}

function populateProjectTemplates(preferredTemplate = 'hello') {
  const templates = languageTemplates(dom.developmentProjectLanguageInput.value);
  const fallbackTemplate = templates.some((template) => template.id === preferredTemplate)
    ? preferredTemplate
    : templates[0]?.id || 'hello';
  dom.developmentProjectTemplateInput.replaceChildren();
  templates.forEach((template) => {
    const option = document.createElement('option');
    option.value = template.id;
    option.textContent = template.label;
    dom.developmentProjectTemplateInput.append(option);
  });
  dom.developmentProjectTemplateInput.value = fallbackTemplate;
}

function populateFirmwareTargets(preferredTarget = '') {
  dom.developmentFirmwareTargetInput.replaceChildren();
  firmwareTargets.forEach((target) => {
    const option = document.createElement('option');
    option.value = target.id;
    option.textContent = `${target.family} · ${target.label}`;
    option.title = `${target.board}\n${target.architecture}\n${target.toolchain}\n\n${firmwareToolchainStatus(target.id).message}`;
    dom.developmentFirmwareTargetInput.append(option);
  });
  dom.developmentFirmwareTargetInput.value = firmwareTargets.some((target) => target.id === preferredTarget)
    ? preferredTarget
    : firmwareTargets[0]?.id || '';
}

function populateFirmwareProgrammers(targetId, preferredProgrammer = '') {
  const select = dom.developmentFirmwareProgrammerInput;
  select.replaceChildren();
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = 'Programátor nevybraný';
  select.append(empty);
  firmwareProgrammers(targetId).forEach((profile) => {
    const option = document.createElement('option');
    option.value = profile.id;
    option.textContent = profile.label;
    option.title = profile.message;
    select.append(option);
  });
  select.value = firmwareProgrammers(targetId).some((profile) => profile.id === preferredProgrammer)
    ? preferredProgrammer
    : '';
}

function populateFirmwarePorts(preferredPort = '') {
  const select = dom.developmentFirmwarePortInput;
  const ports = Array.isArray(firmwareDevices?.ports) ? [...firmwareDevices.ports] : [];
  const currentPort = String(preferredPort || '');
  if (currentPort && !ports.some((port) => port.id === currentPort)) {
    ports.unshift({ id: currentPort, label: `${currentPort} · momentálne neviditeľný` });
  }
  select.replaceChildren();
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = 'Port nevybraný';
  select.append(empty);
  ports.forEach((port) => {
    const option = document.createElement('option');
    option.value = port.id;
    option.textContent = port.label;
    select.append(option);
  });
  select.value = ports.some((port) => port.id === currentPort) ? currentPort : '';
}

function populateFirmwareBaudRate(preferredBaud = '') {
  const select = dom.developmentFirmwareBaudInput;
  const rates = Array.isArray(serialMonitor?.baudRates) && serialMonitor.baudRates.length
    ? serialMonitor.baudRates
    : [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600];
  const current = Number(preferredBaud) || Number(serialMonitor?.defaultBaudRate) || 115200;
  select.replaceChildren();
  rates.forEach((rate) => {
    const option = document.createElement('option');
    option.value = String(rate);
    option.textContent = `${rate} Bd`;
    select.append(option);
  });
  select.value = rates.includes(current) ? String(current) : String(Number(serialMonitor?.defaultBaudRate) || rates[0]);
}

function renderFirmwareDeviceSettings() {
  const isFirmware = dialogProjectKind() === 'firmware';
  const showDeviceSettings = isFirmware && Boolean(projectDialogProjectId);
  dom.developmentFirmwareDeviceFields.hidden = !showDeviceSettings;
  if (!showDeviceSettings) return;

  const targetId = dom.developmentFirmwareTargetInput.value;
  const currentProgrammer = dom.developmentFirmwareProgrammerInput.value;
  const currentPort = dom.developmentFirmwarePortInput.value;
  const currentBaud = dom.developmentFirmwareBaudInput.value;
  populateFirmwareProgrammers(targetId, currentProgrammer);
  populateFirmwarePorts(currentPort);
  populateFirmwareBaudRate(currentBaud);
  const programmer = firmwareProgrammer(targetId, dom.developmentFirmwareProgrammerInput.value);
  const requiresPort = Boolean(programmer?.requiresPort);
  dom.developmentFirmwarePortInput.disabled = !requiresPort;
  if (!programmer) {
    dom.developmentFirmwareDeviceStatus.textContent = 'Programátor nevybraný.';
  } else if (!programmer.available) {
    dom.developmentFirmwareDeviceStatus.textContent = programmer.message;
  } else if (requiresPort && !dom.developmentFirmwarePortInput.value) {
    dom.developmentFirmwareDeviceStatus.textContent = 'Vyber sériový port.';
  } else if (requiresPort) {
    dom.developmentFirmwareDeviceStatus.textContent = 'Pripojenie je uložené; port otvorí až sériový monitor po príkaze.';
  } else {
    dom.developmentFirmwareDeviceStatus.textContent = 'Sériový port sa pre tento programátor nepoužíva.';
  }
}

function populateBuildProfiles(preferredProfile = 'debug') {
  dom.developmentProjectBuildProfileInput.replaceChildren();
  buildProfiles.forEach((profile) => {
    const option = document.createElement('option');
    option.value = profile.id;
    option.textContent = profile.label;
    dom.developmentProjectBuildProfileInput.append(option);
  });
  dom.developmentProjectBuildProfileInput.value = buildProfiles.some((profile) => profile.id === preferredProfile)
    ? preferredProfile
    : buildProfiles[0]?.id || 'debug';
}

function syncProjectKindFields(preferredLanguage = '') {
  const isFirmware = dialogProjectKind() === 'firmware';
  dom.developmentFirmwareFields.hidden = !isFirmware;
  populateProjectLanguages(preferredLanguage || dom.developmentProjectLanguageInput.value);
  dom.developmentProjectTemplateField.hidden = isFirmware || Boolean(projectDialogProjectId);
  if (!isFirmware && !projectDialogProjectId) populateProjectTemplates();
  renderFirmwareDeviceSettings();
  fitProjectDialogToContent();
}

function fitProjectDialogToContent() {
  const dialog = dom.developmentProjectDialog;
  if (!dialog.open) return;
  window.requestAnimationFrame(() => fitDialogWindowToContent(dialog));
}

function setProjectDialogSubmit(editing = false) {
  const icon = dom.developmentProjectSubmit.querySelector('.app-icon');
  setAppIcon(icon, editing ? 'save' : 'plus');
  dom.developmentProjectSubmit.querySelector('span:last-child').textContent = editing
    ? 'Uložiť nastavenie'
    : 'Vytvoriť projekt';
}

function setProjectDialogDescription(text) {
  const description = dom.developmentProjectForm.querySelector('header p');
  if (description) description.textContent = text;
}

function openProjectDialog(project = null) {
  projectDialogProjectId = project?.id || '';
  dom.developmentProjectForm.reset();
  populateFirmwareTargets(project?.firmwareTargetId || 'avr-atmega328p');
  populateBuildProfiles(project?.buildProfile || 'debug');
  setDialogProjectKind(project?.kind || 'program');
  populateProjectLanguages(project?.language || 'c');
  syncProjectKindFields(project?.language || 'c');
  if (project?.kind === 'firmware') {
    populateFirmwareProgrammers(project.firmwareTargetId, project.firmwareProgrammerId || '');
    populateFirmwarePorts(project.firmwareSerialPort || '');
    populateFirmwareBaudRate(project.firmwareSerialBaud);
    renderFirmwareDeviceSettings();
  }
  dom.developmentProjectNameInput.value = project?.title || 'Nový projekt';
  dom.developmentProjectDialog.querySelector('h2').textContent = project ? 'Nastavenie projektu' : 'Nový projekt';
  setProjectDialogDescription(project
    ? 'Profil, jazyk a cieľ menia zostavenie, nie súbory projektu.'
    : 'Vyber bežný program alebo cieľ firmvéru. Vznikne pripravený hlavný súbor.');
  setProjectDialogSubmit(Boolean(project));
  dom.developmentProjectFormStatus.textContent = '';
  dom.developmentProjectDialog.showModal();
  fitProjectDialogToContent();
  window.setTimeout(() => dom.developmentProjectNameInput.select(), 0);
}

async function configureProject() {
  const project = activeProject();
  if (!project || !(await saveDevelopmentChanges())) return;
  openProjectDialog(project);
}

async function refreshFirmwareDevices() {
  const button = dom.developmentFirmwareDevicesRefresh;
  button.disabled = true;
  try {
    firmwareDevices = await runOperation(() => apiRequest('/development/firmware-devices'));
    renderFirmwareDeviceSettings();
    fitProjectDialogToContent();
  } catch (error) {
    dom.developmentFirmwareDeviceStatus.textContent = error.message || 'Zariadenia sa nepodarilo obnoviť.';
  } finally {
    button.disabled = false;
  }
}

async function openFileDialog(kind = 'file') {
  const project = activeProject();
  if (!project || !(await saveDevelopmentChanges())) return;
  pendingDevelopmentItemKind = kind;
  const isFolder = kind === 'folder';
  const isRename = kind === 'rename';
  const file = isRename ? activeFile() : null;
  if (isRename && !file) return;
  const filename = languages.find((language) => language.id === project.language)?.filename || 'novy-subor.txt';
  const extension = filename.includes('.') ? filename.slice(filename.lastIndexOf('.')) : '.txt';
  dom.developmentFileForm.reset();
  dom.developmentFileDialogTitle.textContent = isRename ? 'Premenovať súbor' : isFolder ? 'Nový priečinok' : 'Nový súbor';
  dom.developmentFileDialogDescription.textContent = isRename
    ? `Zmení sa len názov súboru v projekte „${project.title}“.`
    : isFolder
    ? `Pridá sa do: ${folderTargetLabel(project)}.`
    : `Pridá sa do: ${folderTargetLabel(project)}. Prípona určí typ súboru.`;
  dom.developmentFileNameLabel.textContent = isRename ? 'Nový názov súboru' : isFolder ? 'Názov priečinka' : 'Názov súboru';
  dom.developmentFileNameInput.value = isRename ? file.title : isFolder ? 'Nový priečinok' : `novy-subor${extension}`;
  const submitIcon = dom.developmentFileSubmit.querySelector('.app-icon');
  setAppIcon(submitIcon, isRename ? 'save' : isFolder ? 'folder-plus' : 'file');
  dom.developmentFileSubmit.querySelector('span:last-child').textContent = isRename ? 'Uložiť názov' : isFolder ? 'Pridať priečinok' : 'Pridať súbor';
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
  const editing = Boolean(projectDialogProjectId);
  dom.developmentProjectFormStatus.textContent = editing ? 'Ukladám nastavenie...' : 'Vytváram projekt...';
  try {
    const body = {
      title,
      language: dom.developmentProjectLanguageInput.value,
      kind: dialogProjectKind(),
      firmwareTargetId: dom.developmentFirmwareTargetInput.value,
      firmwareProgrammerId: dialogProjectKind() === 'firmware'
        ? dom.developmentFirmwareProgrammerInput.value
        : '',
      firmwareSerialPort: dialogProjectKind() === 'firmware'
        && firmwareProgrammer(
          dom.developmentFirmwareTargetInput.value,
          dom.developmentFirmwareProgrammerInput.value,
        )?.requiresPort
        ? dom.developmentFirmwarePortInput.value
        : '',
      firmwareSerialBaud: dialogProjectKind() === 'firmware'
        ? Number(dom.developmentFirmwareBaudInput.value) || 115200
        : 115200,
      buildProfile: dom.developmentProjectBuildProfileInput.value,
      templateId: dom.developmentProjectTemplateInput.value,
    };
    const result = await runOperation(() => apiRequest(
      editing
        ? `/development/projects/${encodeURIComponent(projectDialogProjectId)}`
        : '/development/projects',
      { method: editing ? 'PUT' : 'POST', body }
    ));
    activeFileId = result.project.entryFileId;
    standardInput = '';
    runArguments = '';
    setConsole();
    replaceProject(result.project);
    dom.developmentProjectDialog.close();
    projectDialogProjectId = '';
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
    runArguments = '';
    projectTests = [];
    activeTestId = '';
    testDraftBaseline = '';
    ensureActiveFile();
    setConsole();
    renderProjects();
    renderEditor();
  } catch (error) {
    setRunStatus(error.message || 'Projekt sa nepodarilo odstrániť.');
  }
}

async function saveProjectSettings() {
  const project = activeProject();
  const title = dom.developmentProjectTitle.value.trim();
  const nextRunArguments = dom.developmentRunArguments.value;
  if (!project || !title || (title === projectTitleBaseline && nextRunArguments === projectRunArgumentsBaseline)) return true;
  const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}`, {
    method: 'PUT', body: { title, runArguments: nextRunArguments }
  }));
  replaceProject(result.project);
  return true;
}

async function setActiveFileAsEntry() {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file || project.entryFileId === file.id || !(await saveActiveFile())) return;
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}`, {
      method: 'PUT', body: { entryFileId: file.id }
    }));
    replaceProject(result.project);
  } catch (error) {
    setRunStatus(error.message || 'Hlavný súbor sa nepodarilo nastaviť.');
  }
}

async function saveActiveFile() {
  const project = activeProject();
  const file = activeFile();
  if (!project || !file || activeFileSnapshot() === fileDraftBaseline) return true;
  const result = await runOperation(() => apiRequest(
    `/development/projects/${encodeURIComponent(project.id)}/files/${encodeURIComponent(file.id)}`,
    { method: 'PUT', body: { title: dom.developmentFileTitle.value, content: developmentEditorValue() } }
  ));
  replaceProject(result.project);
  return true;
}

export async function saveDevelopmentChanges() {
  window.clearTimeout(saveTimer);
  try {
    const pendingProjectTitle = dom.developmentProjectTitle.value.trim();
    const pendingRunArguments = dom.developmentRunArguments.value;
    await saveActiveFile();
    if (pendingProjectTitle && (pendingProjectTitle !== projectTitleBaseline || pendingRunArguments !== projectRunArgumentsBaseline)) {
      dom.developmentProjectTitle.value = pendingProjectTitle;
      dom.developmentRunArguments.value = pendingRunArguments;
      await saveProjectSettings();
    }
    return true;
  } catch (error) {
    setRunStatus(error.message || 'Zmeny sa nepodarilo uložiť.');
    return false;
  }
}

export function hasUnsavedDevelopmentChanges() {
  return dom.developmentProjectTitle.value.trim() !== projectTitleBaseline
    || dom.developmentRunArguments.value !== projectRunArgumentsBaseline
    || activeFileSnapshot() !== fileDraftBaseline;
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
  const isRename = pendingDevelopmentItemKind === 'rename';
  if (!project || !title || (isRename && !activeFile()) || !(await saveDevelopmentChanges())) return;
  const submitter = dom.developmentFileForm.querySelector('button[type="submit"]');
  submitter.disabled = true;
  const isFolder = pendingDevelopmentItemKind === 'folder';
  dom.developmentFileFormStatus.textContent = isRename ? 'Ukladám názov...' : isFolder ? 'Pridávam priečinok...' : 'Pridávam súbor...';
  try {
    if (isRename) {
      const file = activeFile();
      const result = await runOperation(() => apiRequest(
        `/development/projects/${encodeURIComponent(project.id)}/files/${encodeURIComponent(file.id)}`,
        { method: 'PUT', body: { title, content: file.content } }
      ));
      replaceProject(result.project);
      dom.developmentFileDialog.close();
      return;
    }
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
    dom.developmentFileFormStatus.textContent = error.message || (isRename ? 'Súbor sa nepodarilo premenovať.' : isFolder ? 'Priečinok sa nepodarilo vytvoriť.' : 'Súbor sa nepodarilo vytvoriť.');
  } finally {
    submitter.disabled = false;
  }
}

async function importDevelopmentFiles(event) {
  const project = activeProject();
  const files = Array.from(event.target.files || []);
  event.target.value = '';
  if (!project || !files.length || !(await saveDevelopmentChanges())) return;

  const imported = [];
  const skipped = [];
  let updatedProject = project;
  try {
    for (const file of files) {
      if (file.size > 200 * 1024) {
        skipped.push(file.name);
        continue;
      }
      const content = await file.text();
      const result = await runOperation(() => apiRequest(
        `/development/projects/${encodeURIComponent(updatedProject.id)}/files`,
        { method: 'POST', body: { title: file.name, content, parentId: selectedFolderId } }
      ));
      const previousIds = new Set(updatedProject.files.map((item) => item.id));
      updatedProject = result.project;
      const created = updatedProject.files.find((item) => !previousIds.has(item.id));
      if (created) imported.push(created);
    }

    if (imported[0]) {
      activeFileId = imported[0].id;
      selectedFolderId = String(imported[0].parentId || '');
      expandFolderAncestors(updatedProject, selectedFolderId);
    }
    replaceProject(updatedProject);
    const summary = imported.length
      ? `${imported.length} ${imported.length === 1 ? 'súbor bol pridaný' : 'súbory boli pridané'}.`
      : 'Neboli pridané žiadne súbory.';
    setRunStatus(skipped.length ? `${summary} ${skipped.length} bolo príliš veľkých.` : summary);
  } catch (error) {
    if (imported.length) replaceProject(updatedProject);
    setRunStatus(error.message || 'Súbory sa nepodarilo pridať do projektu.');
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

function projectSupportsBinaryInspection(project = activeProject()) {
  return Boolean(project && project.kind === 'program' && ['c', 'cpp', 'asm'].includes(project.language));
}

function projectSupportsFirmwareMemoryMap(project = activeProject()) {
  return Boolean(project?.kind === 'firmware');
}

function activeBinaryInspection() {
  if (!binaryInspection || binaryInspection.projectId !== activeProjectId) return null;
  return binaryInspection;
}

function byteLabel(value) {
  const bytes = Math.max(0, Number(value) || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderBinaryInspectorButton(project = activeProject()) {
  const firmwareMemory = projectSupportsFirmwareMemoryMap(project);
  const supported = firmwareMemory || projectSupportsBinaryInspection(project);
  const inspection = activeBinaryInspection();
  dom.developmentBinaryInspector.hidden = !supported;
  dom.developmentBinaryInspector.disabled = firmwareMemory ? false : !inspection;
  dom.developmentBinaryInspector.title = firmwareMemory
    ? 'Pamäťová mapa posledného zostavenia firmvéru'
    : inspection
      ? 'Rozbor binárky'
      : 'Prelož projekt, aby bol dostupný rozbor binárky.';
  dom.developmentBinaryInspector.setAttribute('aria-label', dom.developmentBinaryInspector.title);
}

function binaryInspectorRow(name, value, title = '') {
  const row = document.createElement('div');
  row.className = 'development-binary-entry';
  row.setAttribute('role', 'listitem');
  row.title = title || `${name}: ${value}`;
  const label = document.createElement('code');
  label.textContent = name;
  const size = document.createElement('span');
  size.textContent = value;
  row.append(label, size);
  return row;
}

function renderBinaryInspector() {
  const project = activeProject();
  const snapshot = activeBinaryInspection();
  if (!project || !snapshot) return false;
  const inspection = snapshot.data;
  const memory = inspection.memory || {};
  document.getElementById('development-binary-inspector-title').textContent = 'Rozbor binárky';
  document.getElementById('development-binary-sections-title').textContent = 'Sekcie';
  document.getElementById('development-binary-symbols-title').textContent = 'Symboly';
  dom.developmentBinaryInspectorSummary.textContent = `${languageLabel(project.language)} · ${snapshot.buildProfileLabel || 'Ladenie'}`;
  dom.developmentBinaryInspectorMemory.replaceChildren();
  [
    ['Kód', memory.text],
    ['Dáta', memory.data],
    ['BSS', memory.bss],
    ['Celkom', memory.total],
  ].forEach(([label, value]) => {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    term.textContent = label;
    const detail = document.createElement('dd');
    detail.textContent = byteLabel(value);
    item.append(term, detail);
    dom.developmentBinaryInspectorMemory.append(item);
  });
  dom.developmentBinaryInspectorSections.replaceChildren(
    ...(inspection.sections || []).map((section) => binaryInspectorRow(
      section.name,
      byteLabel(section.size),
      `${section.name}: ${byteLabel(section.size)} · adresa ${Number(section.address || 0).toString(16)}`
    ))
  );
  dom.developmentBinaryInspectorSymbols.replaceChildren(
    ...(inspection.symbols || []).map((symbol) => binaryInspectorRow(
      symbol.name,
      byteLabel(symbol.size),
      `${symbol.type || '?'} · ${byteLabel(symbol.size)} · adresa ${Number(symbol.address || 0).toString(16)}`
    ))
  );
  return true;
}

function firmwareMapDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('sk-SK', { dateStyle: 'short', timeStyle: 'short' });
}

function firmwareMapAddress(value) {
  return `0x${Math.max(0, Number(value) || 0).toString(16).toUpperCase().padStart(8, '0')}`;
}

function renderFirmwareMemoryMap(snapshot) {
  const memory = snapshot?.memory || {};
  const flash = memory.flash || {};
  const ram = memory.ram || {};
  const target = snapshot?.target || {};
  const flashFree = Math.max(0, Number(flash.capacity || 0) - Number(flash.used || 0));
  const ramFree = Math.max(0, Number(ram.capacity || 0) - Number(ram.used || 0));
  const builtAt = firmwareMapDate(snapshot?.createdAt);
  document.getElementById('development-binary-inspector-title').textContent = 'Pamäťová mapa';
  document.getElementById('development-binary-sections-title').textContent = 'Sekcie';
  document.getElementById('development-binary-symbols-title').textContent = 'Artefakty';
  dom.developmentBinaryInspectorSummary.textContent = [
    target.label || 'Firmvér',
    snapshot?.fresh ? 'zodpovedá aktuálnym zdrojom' : 'zdroje sa od zostavenia zmenili',
    builtAt,
  ].filter(Boolean).join(' · ');
  dom.developmentBinaryInspectorMemory.replaceChildren();
  [
    ['FLASH', `${firmwareBytes(flash.used)} / ${firmwareBytes(flash.capacity)} (${Number(flash.percent || 0)} %)`],
    ['FLASH voľná', firmwareBytes(flashFree)],
    ['RAM', `${firmwareBytes(ram.used)} / ${firmwareBytes(ram.capacity)} (${Number(ram.percent || 0)} %)`],
    ['RAM voľná', firmwareBytes(ramFree)],
  ].forEach(([label, value]) => {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    term.textContent = label;
    const detail = document.createElement('dd');
    detail.textContent = value;
    item.append(term, detail);
    dom.developmentBinaryInspectorMemory.append(item);
  });
  const sections = Array.isArray(memory.sections) ? [...memory.sections] : [];
  sections.sort((left, right) => Number(left.address || 0) - Number(right.address || 0));
  dom.developmentBinaryInspectorSections.replaceChildren(
    ...sections.map((section) => binaryInspectorRow(
      section.name || '?',
      `${firmwareBytes(section.size)} · ${firmwareMapAddress(section.address)}`,
      `${section.name || '?'}: ${firmwareBytes(section.size)} od ${firmwareMapAddress(section.address)}`,
    )),
  );
  const artifacts = Array.isArray(snapshot?.artifacts) ? snapshot.artifacts : [];
  dom.developmentBinaryInspectorSymbols.replaceChildren(
    ...artifacts.map((artifact) => binaryInspectorRow(
      artifact.name || '?',
      firmwareBytes(artifact.bytes),
    )),
  );
}

function renderFirmwareMemoryMapUnavailable(message) {
  document.getElementById('development-binary-inspector-title').textContent = 'Pamäťová mapa';
  document.getElementById('development-binary-sections-title').textContent = 'Sekcie';
  document.getElementById('development-binary-symbols-title').textContent = 'Artefakty';
  dom.developmentBinaryInspectorSummary.textContent = message;
  dom.developmentBinaryInspectorMemory.replaceChildren();
  dom.developmentBinaryInspectorSections.replaceChildren();
  dom.developmentBinaryInspectorSymbols.replaceChildren();
}

async function openBinaryInspector() {
  const project = activeProject();
  if (projectSupportsFirmwareMemoryMap(project)) {
    try {
      if (!(await saveDevelopmentChanges())) return;
      const snapshot = await runOperation(() => apiRequest(
        `/development/projects/${encodeURIComponent(project.id)}/firmware-memory`,
      ));
      renderFirmwareMemoryMap(snapshot);
    } catch (error) {
      renderFirmwareMemoryMapUnavailable(error.message || 'Pamäťovú mapu sa nepodarilo načítať.');
    }
    if (!dom.developmentBinaryInspectorDialog.open) dom.developmentBinaryInspectorDialog.showModal();
    return;
  }
  if (!renderBinaryInspector()) return;
  if (!dom.developmentBinaryInspectorDialog.open) dom.developmentBinaryInspectorDialog.showModal();
}

function debugReasonLabel(reason = '') {
  return {
    'breakpoint-hit': 'Zastavené na bode prerušenia.',
    'end-stepping-range': 'Krok dokončený.',
    'function-finished': 'Funkcia skončila.',
    'exited-normally': 'Program skončil.',
    'exited': 'Program skončil.',
    'signal-received': 'Program bol prerušený signálom.',
  }[reason] || 'Debugger je pripravený.';
}

function debugLocationLabel(location) {
  if (!location?.filename || !Number.isInteger(location.line)) return '';
  return `${location.filename}:${location.line}${location.function ? ` · ${location.function}` : ''}`;
}

function debugListEmpty(message) {
  const empty = document.createElement('p');
  empty.className = 'development-debug-empty';
  empty.textContent = message;
  return empty;
}

function renderDebugList(container, entries, { variables = false } = {}) {
  container.replaceChildren();
  if (!entries.length) {
    container.append(debugListEmpty(variables ? 'Bez dostupných premenných.' : 'Bez dostupných rámcov.'));
    return;
  }
  entries.forEach((entry) => {
    const location = variables ? null : entry.location;
    const item = location ? document.createElement('button') : document.createElement('div');
    if (location) item.type = 'button';
    item.className = 'development-debug-list-item';
    const name = document.createElement('strong');
    name.textContent = variables ? entry.name : entry.function || '?';
    const detail = document.createElement('small');
    detail.textContent = variables ? entry.value : debugLocationLabel(location) || 'bez zdrojovej pozície';
    item.append(name, detail);
    if (location) item.addEventListener('click', () => void openDebugLocation(location));
    container.append(item);
  });
}

function renderDebugSession(snapshot = null, { message = '' } = {}) {
  const paused = snapshot?.state === 'paused';
  const hasSession = Boolean(debugSession?.id);
  dom.developmentDebugStep.disabled = !paused;
  dom.developmentDebugNext.disabled = !paused;
  dom.developmentDebugContinue.disabled = !paused;
  dom.developmentDebugStop.disabled = !hasSession;
  dom.developmentDebugStatus.textContent = message || (snapshot ? debugReasonLabel(snapshot.reason) : debuggerRuntime.message);
  const locationLabel = debugLocationLabel(snapshot?.location);
  dom.developmentDebugLocation.hidden = !locationLabel;
  dom.developmentDebugLocation.textContent = locationLabel;
  dom.developmentDebugLocation.title = locationLabel ? `Prejsť na ${locationLabel}` : '';
  renderDebugList(dom.developmentDebugFrames, snapshot?.frames || []);
  renderDebugList(dom.developmentDebugVariables, snapshot?.variables || [], { variables: true });
  dom.developmentDebugTranscript.textContent = snapshot?.transcript || '';
}

function showDebugDialog() {
  if (!dom.developmentDebugDialog.open) dom.developmentDebugDialog.show();
}

async function openDebugLocation(location) {
  const project = activeProject();
  if (!project || !location?.filename || !Number.isInteger(location.line)) return;
  const diagnostic = {
    filename: location.filename,
    line: location.line,
    column: 1,
    severity: 'error',
    message: location.function ? `Zastavené vo funkcii ${location.function}.` : 'Zastavené debuggerom.',
  };
  diagnostics = [diagnostic];
  diagnosticIndex = -1;
  setDevelopmentEditorDiagnostics(diagnosticsForActiveFile());
  renderProblems();
  if (!(await openDiagnostic(diagnostic, 0))) {
    dom.developmentDebugStatus.textContent = 'Miesto zastavenia sa v projekte nenašlo.';
  }
}

async function startDebugging() {
  const project = activeProject();
  showDebugDialog();
  if (!projectSupportsDebugging(project)) {
    renderDebugSession(null, { message: 'Krokové ladenie je zatiaľ pripravené pre C a C++.' });
    return;
  }
  if (!debuggerRuntime.available) {
    renderDebugSession(null, { message: debuggerRuntime.message || 'Debugger nie je dostupný.' });
    return;
  }
  if (!(await saveDevelopmentChanges())) return;
  if (debugSession) await stopDebugging({ quiet: true });
  renderDebugSession(null, { message: 'Pripravujem ladiacu reláciu...' });
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}/debug`, {
      method: 'POST',
      body: {
        fileId: project.entryFileId,
        stdin: dom.developmentInput.value,
        arguments: dom.developmentRunArguments.value,
      },
    }));
    const compile = result.compile || {};
    const compileText = resultText(compile);
    readDiagnostics(compileText);
    if (!result.compiled || !result.session) {
      setConsole({ phase: 'Chyba prekladu', compile: compileText, compileMeta: formatResultMeta(compile), output: 'Ladenie sa nespustilo.' });
      renderDebugSession(null, { message: 'Preklad pre ladenie zlyhal.' });
      return;
    }
    debugSession = result.session;
    setConsole({
      phase: 'Ladenie',
      compile: compileText,
      compileMeta: formatResultMeta(compile),
      output: result.session.transcript || 'Program je zastavený v debuggeri.',
    });
    renderDebugSession(result.session);
    setConsoleExpanded(true);
  } catch (error) {
    renderDebugSession(null, { message: error.message || 'Ladenie sa nepodarilo spustiť.' });
  }
}

async function runDebugCommand(action) {
  const session = debugSession;
  if (!session?.id) return;
  renderDebugSession(session, { message: 'Debugger pracuje...' });
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(activeProjectId)}/debug/${encodeURIComponent(session.id)}/command`, {
      method: 'POST', body: { action }
    }));
    debugSession = result.session || null;
    if (debugSession) {
      dom.developmentRunOutput.textContent = debugSession.transcript || dom.developmentRunOutput.textContent;
      renderDebugSession(debugSession);
    }
  } catch (error) {
    debugSession = null;
    renderDebugSession(null, { message: error.message || 'Príkaz debuggeru zlyhal.' });
  }
}

async function stopDebugging({ quiet = false } = {}) {
  const session = debugSession;
  debugSession = null;
  renderDebugSession(null, { message: quiet ? '' : 'Ladenie je ukončené.' });
  if (!session?.id || !activeProjectId) return;
  try {
    await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(activeProjectId)}/debug/${encodeURIComponent(session.id)}`, {
      method: 'DELETE'
    }));
  } catch (error) {
    if (!quiet) renderDebugSession(null, { message: error.message || 'Ladiacu reláciu sa nepodarilo ukončiť.' });
  }
}

async function closeDebugDialog() {
  await stopDebugging({ quiet: true });
  if (dom.developmentDebugDialog.open) dom.developmentDebugDialog.close();
}

function firmwareBytes(value) {
  const bytes = Math.max(0, Number(value) || 0);
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
}

function firmwareBuildOutput(result, project) {
  const lines = [];
  const memory = result.memory;
  if (memory?.flash && memory?.ram) {
    lines.push(
      `FLASH: ${firmwareBytes(memory.flash.used)} / ${firmwareBytes(memory.flash.capacity)} (${memory.flash.percent} %)`
    );
    lines.push(`RAM: ${firmwareBytes(memory.ram.used)} / ${firmwareBytes(memory.ram.capacity)} (${memory.ram.percent} %)`);
  }
  const artifacts = Array.isArray(result.artifacts) ? result.artifacts : [];
  if (artifacts.length) {
    lines.push('', ...artifacts.map((artifact) => `${artifact.name} · ${firmwareBytes(artifact.bytes)}`));
  }
  const device = configuredFirmwareDevice(project);
  if (!device?.programmer) {
    lines.push('', 'Na zápis potom vyber programátor v nastavení firmvéru.');
  } else if (device.programmer.requiresPort && !device.port) {
    lines.push('', 'Na zápis potom vyber sériový port v nastavení firmvéru.');
  } else {
    lines.push('', 'Artefakty sú pripravené; zápis do zariadenia vyžiada samostatné potvrdenie.');
  }
  return lines.join('\n');
}

function renderFirmwareProgramButton(project = activeProject()) {
  const isFirmware = project?.kind === 'firmware';
  const device = configuredFirmwareDevice(project);
  const programmer = device?.programmer;
  const portReady = !programmer?.requiresPort || Boolean(device?.port);
  const available = Boolean(isFirmware && programmer?.writeAvailable && portReady);
  dom.developmentFirmwareProgram.hidden = !isFirmware;
  dom.developmentFirmwareProgram.disabled = !available;
  const title = available
    ? 'Zapísať posledný zostavený firmvér do zariadenia'
    : !programmer
      ? 'Najprv vyber programátor v nastavení firmvéru.'
      : !portReady
        ? 'Pre vybraný programátor nastav sériový port.'
        : programmer.message || 'Zápis firmvéru zatiaľ nie je dostupný.';
  dom.developmentFirmwareProgram.title = title;
  dom.developmentFirmwareProgram.setAttribute('aria-label', title);
}

function renderSerialMonitorButton(project = activeProject()) {
  const isFirmware = project?.kind === 'firmware';
  const device = configuredFirmwareDevice(project);
  const available = Boolean(isFirmware && serialMonitor?.available && device?.port);
  dom.developmentSerialMonitor.hidden = !isFirmware;
  dom.developmentSerialMonitor.disabled = !available;
  const title = available
    ? `Otvoriť sériový monitor (${device.port} · ${device.baudRate} Bd)`
    : !serialMonitor?.available
      ? serialMonitor?.message || 'Sériový monitor nie je dostupný.'
      : 'V nastavení firmvéru vyber sériový port.';
  dom.developmentSerialMonitor.title = title;
  dom.developmentSerialMonitor.setAttribute('aria-label', title);
}

function serialMonitorOutputAtEnd() {
  const output = dom.developmentSerialMonitorOutput;
  return output.scrollHeight - output.scrollTop - output.clientHeight < 20;
}

function updateSerialMonitorSnapshot(snapshot) {
  if (!snapshot) return;
  const output = dom.developmentSerialMonitorOutput;
  const wasAtEnd = serialMonitorOutputAtEnd();
  if (snapshot.reset) output.textContent = '';
  if (snapshot.text) {
    output.textContent += snapshot.text;
    if (output.textContent.length > 128 * 1024) {
      output.textContent = output.textContent.slice(-96 * 1024);
    }
  }
  if (wasAtEnd) output.scrollTop = output.scrollHeight;
  serialMonitorCursor = Math.max(0, Number(snapshot.cursor) || serialMonitorCursor);
  dom.developmentSerialMonitorPort.textContent = snapshot.port || '';
  dom.developmentSerialMonitorBaud.textContent = snapshot.baudRate ? `${snapshot.baudRate} Bd` : '';
  dom.developmentSerialMonitorStatus.textContent = snapshot.message || (snapshot.connected ? 'Pripojené.' : 'Odpojené.');
  dom.developmentSerialMonitorStatus.dataset.state = snapshot.connected ? 'ready' : 'idle';
  dom.developmentSerialMonitorSend.disabled = !snapshot.connected;
  dom.developmentSerialMonitorStop.disabled = !serialMonitorSession;
}

function scheduleSerialMonitorPoll() {
  window.clearTimeout(serialMonitorPollTimer);
  if (!serialMonitorSession?.id) return;
  serialMonitorPollTimer = window.setTimeout(() => void pollSerialMonitor(), 260);
}

async function pollSerialMonitor() {
  const session = serialMonitorSession;
  if (!session?.id) return;
  try {
    const snapshot = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(session.projectId)}/serial-monitor/${encodeURIComponent(session.id)}?cursor=${encodeURIComponent(serialMonitorCursor)}`,
    ));
    if (serialMonitorSession?.id !== session.id) return;
    updateSerialMonitorSnapshot(snapshot);
    if (snapshot.connected) scheduleSerialMonitorPoll();
  } catch (error) {
    if (serialMonitorSession?.id !== session.id) return;
    serialMonitorSession = null;
    dom.developmentSerialMonitorStatus.textContent = error.message || 'Sériový monitor sa odpojil.';
    dom.developmentSerialMonitorStatus.dataset.state = 'error';
    dom.developmentSerialMonitorSend.disabled = true;
    dom.developmentSerialMonitorStop.disabled = true;
  }
}

async function stopSerialMonitor() {
  window.clearTimeout(serialMonitorPollTimer);
  serialMonitorPollTimer = 0;
  const session = serialMonitorSession;
  serialMonitorSession = null;
  dom.developmentSerialMonitorSend.disabled = true;
  dom.developmentSerialMonitorStop.disabled = true;
  if (!session?.id) return;
  try {
    await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(session.projectId)}/serial-monitor/${encodeURIComponent(session.id)}`,
      { method: 'DELETE' },
    ));
    dom.developmentSerialMonitorStatus.textContent = 'Odpojené.';
    dom.developmentSerialMonitorStatus.dataset.state = 'idle';
  } catch (error) {
    dom.developmentSerialMonitorStatus.textContent = error.message || 'Sériový monitor sa nepodarilo odpojiť.';
    dom.developmentSerialMonitorStatus.dataset.state = 'error';
  }
}

async function openSerialMonitor() {
  let project = activeProject();
  if (!project || project.kind !== 'firmware' || !(await saveDevelopmentChanges())) return;
  project = activeProject();
  const device = configuredFirmwareDevice(project);
  if (!project || !device?.port) return;
  if (serialMonitorSession) await stopSerialMonitor();
  dom.developmentSerialMonitorOutput.textContent = '';
  serialMonitorCursor = 0;
  dom.developmentSerialMonitorPort.textContent = device.port;
  dom.developmentSerialMonitorBaud.textContent = `${device.baudRate} Bd`;
  dom.developmentSerialMonitorStatus.textContent = 'Pripájam sériový port...';
  dom.developmentSerialMonitorStatus.dataset.state = 'pending';
  dom.developmentSerialMonitorSend.disabled = true;
  dom.developmentSerialMonitorStop.disabled = true;
  if (!dom.developmentSerialMonitorDialog.open) dom.developmentSerialMonitorDialog.showModal();
  try {
    const snapshot = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/serial-monitor`,
      { method: 'POST', body: { baudRate: device.baudRate } },
    ));
    serialMonitorSession = { id: snapshot.sessionId, projectId: project.id };
    updateSerialMonitorSnapshot(snapshot);
    if (snapshot.connected) scheduleSerialMonitorPoll();
    dom.developmentSerialMonitorInput.focus();
  } catch (error) {
    dom.developmentSerialMonitorStatus.textContent = error.message || 'Sériový port sa nepodarilo otvoriť.';
    dom.developmentSerialMonitorStatus.dataset.state = 'error';
    dom.developmentSerialMonitorSend.disabled = true;
  } finally {
    renderEditor();
  }
}

async function sendSerialMonitorInput() {
  const session = serialMonitorSession;
  const text = dom.developmentSerialMonitorInput.value;
  if (!session?.id || !text) return;
  dom.developmentSerialMonitorSend.disabled = true;
  try {
    const snapshot = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(session.projectId)}/serial-monitor/${encodeURIComponent(session.id)}/send`,
      { method: 'POST', body: { text, cursor: serialMonitorCursor } },
    ));
    if (serialMonitorSession?.id !== session.id) return;
    dom.developmentSerialMonitorInput.value = '';
    updateSerialMonitorSnapshot(snapshot);
  } catch (error) {
    dom.developmentSerialMonitorStatus.textContent = error.message || 'Dáta sa nepodarilo odoslať.';
    dom.developmentSerialMonitorStatus.dataset.state = 'error';
  } finally {
    if (serialMonitorSession?.id === session.id && dom.developmentSerialMonitorStatus.dataset.state === 'ready') {
      dom.developmentSerialMonitorSend.disabled = false;
      dom.developmentSerialMonitorInput.focus();
    }
  }
}

function clearFirmwareProgrammingChallenge() {
  firmwareProgrammingChallenge = null;
  dom.developmentFirmwareProgramConfirmation.value = '';
  dom.developmentFirmwareProgramConfirmation.disabled = false;
  dom.developmentFirmwareProgramStatus.textContent = '';
  dom.developmentFirmwareProgramSubmit.disabled = true;
}

function invalidateFirmwareProgrammingChallenge() {
  if (!firmwareProgrammingChallenge) return;
  firmwareProgrammingChallenge = null;
  dom.developmentFirmwareProgramSubmit.disabled = true;
  dom.developmentFirmwareProgramStatus.textContent = 'Kód sa zmenil. Zápis priprav znova.';
}

function syncFirmwareProgrammingConfirmation() {
  const confirmation = dom.developmentFirmwareProgramConfirmation.value.trim().toUpperCase();
  dom.developmentFirmwareProgramSubmit.disabled = !firmwareProgrammingChallenge
    || confirmation !== firmwareProgrammingChallenge.confirmation;
}

function closeFirmwareProgrammingDialog() {
  clearFirmwareProgrammingChallenge();
  if (dom.developmentFirmwareProgramDialog.open) dom.developmentFirmwareProgramDialog.close();
}

async function openFirmwareProgramming() {
  let project = activeProject();
  if (!project || project.kind !== 'firmware') return;
  if (!(await saveDevelopmentChanges())) return;
  project = activeProject();
  if (!project || project.kind !== 'firmware') return;
  dom.developmentFirmwareProgram.disabled = true;
  try {
    const prepared = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/firmware-program`,
      { method: 'POST' },
    ));
    firmwareProgrammingChallenge = prepared;
    dom.developmentFirmwareProgramTarget.textContent = prepared.target || project.firmwareTarget?.label || 'Neznámy cieľ';
    dom.developmentFirmwareProgrammer.textContent = prepared.programmer || 'Neznámy programátor';
    dom.developmentFirmwareProgramPort.textContent = prepared.port || 'Bez sériového portu';
    dom.developmentFirmwareProgramArtifact.textContent = prepared.artifact
      ? `${prepared.artifact.name} (${firmwareBytes(prepared.artifact.bytes)})`
      : 'Neznámy artefakt';
    dom.developmentFirmwareProgramConfirmation.value = '';
    dom.developmentFirmwareProgramStatus.textContent = `Na potvrdenie napíš ${prepared.confirmation}.`;
    syncFirmwareProgrammingConfirmation();
    if (!dom.developmentFirmwareProgramDialog.open) dom.developmentFirmwareProgramDialog.showModal();
    dom.developmentFirmwareProgramConfirmation.focus();
  } catch (error) {
    firmwareProgrammingChallenge = null;
    setConsoleExpanded(true);
    setConsole({
      phase: 'Zápis nepripravený',
      compile: error.message || 'Firmvér sa nepodarilo pripraviť na zápis.',
      output: 'Zariadenie nebolo otvorené ani zmenené.',
    });
  } finally {
    renderEditor();
  }
}

async function submitFirmwareProgramming(event) {
  event.preventDefault();
  const project = activeProject();
  const prepared = firmwareProgrammingChallenge;
  if (!project || !prepared || dom.developmentFirmwareProgramSubmit.disabled) return;
  const confirmation = dom.developmentFirmwareProgramConfirmation.value.trim().toUpperCase();
  dom.developmentFirmwareProgramSubmit.disabled = true;
  dom.developmentFirmwareProgramConfirmation.disabled = true;
  dom.developmentFirmwareProgramStatus.textContent = 'Zapisujem firmvér...';
  try {
    const result = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/firmware-program/confirm`,
      { method: 'POST', body: { challenge: prepared.challenge, confirmation } },
    ));
    const execution = result.result || {};
    setConsoleExpanded(true);
    setConsole({
      phase: result.programmed ? 'Firmvér zapísaný' : 'Chyba zápisu',
      compile: result.summary || resultText(execution),
      compileMeta: formatResultMeta(execution),
      output: result.programmed
        ? 'Zápis do zariadenia bol potvrdený nástrojom programátora.'
        : 'Nástroj programátora firmvér nezapísal.',
    });
    clearFirmwareProgrammingChallenge();
    if (dom.developmentFirmwareProgramDialog.open) dom.developmentFirmwareProgramDialog.close();
  } catch (error) {
    firmwareProgrammingChallenge = null;
    dom.developmentFirmwareProgramConfirmation.disabled = false;
    dom.developmentFirmwareProgramStatus.textContent = error.message || 'Zápis firmvéru zlyhal.';
    setConsoleExpanded(true);
    setConsole({
      phase: 'Chyba zápisu',
      compile: error.message || 'Firmvér sa nepodarilo zapísať.',
      output: 'Skontroluj pripojenie a priprav zápis znova.',
    });
  } finally {
    renderEditor();
  }
}

async function buildFirmwareProject(project) {
  binaryInspection = null;
  renderBinaryInspectorButton(project);
  setConsoleExpanded(true);
  dom.developmentBuild.disabled = true;
  clearDiagnostics();
  setConsole({ phase: 'Zostavujem firmvér...', compile: '', output: 'Zariadenie sa pri zostavení neotvára.' });
  try {
    const result = await runOperation(() => apiRequest(
      `/development/projects/${encodeURIComponent(project.id)}/firmware-build`,
      { method: 'POST', body: { fileId: project.entryFileId } },
    ));
    const compile = result.compile || {};
    const compileText = resultText(compile);
    readDiagnostics(compileText);
    setConsole({
      phase: result.compiled ? 'Firmvér zostavený' : 'Chyba prekladu',
      compile: compileText,
      compileMeta: formatResultMeta(compile),
      output: result.compiled
        ? firmwareBuildOutput(result, project)
        : 'Firmvér nebol vytvorený, pretože zostavenie zlyhalo.',
    });
  } catch (error) {
    setConsole({ phase: 'Chyba prekladu', compile: error.message || 'Firmvér sa nepodarilo zostaviť.', output: '' });
  } finally {
    renderEditor();
  }
}

async function runProject({ execute = true } = {}) {
  const project = activeProject();
  if (!project || !(await saveDevelopmentChanges())) return;
  if (project.kind === 'firmware') {
    const toolchain = firmwareToolchainStatus(project.firmwareTargetId);
    const buildStatus = firmwareBuildStatus(project.firmwareTargetId, project.language);
    if (buildStatus.available) {
      await buildFirmwareProject(project);
      return;
    }
    const device = configuredFirmwareDevice(project);
    clearDiagnostics();
    setConsole({
      phase: toolchain.buildAvailable ? 'Čaká na programovanie' : 'Čaká na toolchain',
      compile: buildStatus.message || toolchain.message,
      output: toolchain.programmerAvailable
        ? !device?.programmer
          ? 'Vyber programátor v nastavení firmvéru. Zápis do zariadenia sa ešte nevykoná.'
          : device.programmer.requiresPort && !device.port
            ? 'Pre vybraný programátor ešte nastav sériový port. Zápis do zariadenia sa ešte nevykoná.'
            : 'Pripojenie je uložené. Zápis do zariadenia pridáme až s výslovným potvrdením.'
        : 'Zatiaľ možno upravovať súbory a nastavovať cieľ projektu.'
    });
    setConsoleExpanded(true);
    return;
  }
  if (!languageRuntime(project.language).available) return;
  setConsoleExpanded(true);
  dom.developmentBuild.disabled = true;
  dom.developmentRun.disabled = true;
  clearDiagnostics();
  setConsole({ phase: 'Prekladám...', compile: '', output: execute ? '' : 'Program sa po preklade nespustí.' });
  try {
    const result = await runOperation(() => apiRequest(`/development/projects/${encodeURIComponent(project.id)}/run`, {
      method: 'POST', body: {
        fileId: project.entryFileId,
        stdin: dom.developmentInput.value,
        arguments: dom.developmentRunArguments.value,
        execute,
      }
    }));
    const compile = result.compile || {};
    const run = result.run || {};
    const inspection = result.inspection?.available ? result.inspection : null;
    binaryInspection = inspection
      ? { projectId: project.id, buildProfileLabel: project.buildProfileLabel, data: inspection }
      : null;
    renderBinaryInspectorButton(project);
    const compileText = resultText(compile);
    readDiagnostics(compileText);
    setConsole({
      phase: result.compiled
        ? `${execute ? 'Hotovo' : 'Preložené'} · ${project.buildProfileLabel || 'Ladenie'}`
        : 'Chyba prekladu',
      compile: compileText,
      compileMeta: formatResultMeta(compile),
      output: result.compiled
        ? (execute ? resultText(run) : 'Program nebol spustený.')
        : 'Program sa nespustil, pretože preklad zlyhal.',
      outputMeta: result.compiled && execute ? formatResultMeta(run) : ''
    });
  } catch (error) {
    binaryInspection = null;
    renderBinaryInspectorButton(project);
    clearDiagnostics();
    setConsole({ phase: 'Chyba', compile: error.message || 'Projekt sa nepodarilo spustiť.', output: '' });
  } finally {
    const canRun = project.kind !== 'firmware' && Boolean(languageRuntime(project.language).available);
    dom.developmentBuild.disabled = !canRun;
    dom.developmentRun.disabled = !canRun;
  }
}

export function isDevelopmentPanelOpen() {
  return dom.developmentPanel.classList.contains('is-open');
}

export function exitDevelopmentFocusMode() {
  if (!focusMode) return false;
  setFocusMode(false);
  return true;
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

export async function activateDevelopmentProject(
  projectId,
  { standardInput: nextStandardInput = '', runArguments: nextRunArguments = '', showTutorialGuide = false } = {}
) {
  if (!projectId || !isDevelopmentPanelOpen()) return false;
  if (!projects.some((project) => project.id === projectId)) {
    try {
      await runOperation(loadWorkspace);
    } catch {
      return false;
    }
  }
  if (!projects.some((project) => project.id === projectId)) return false;
  if (projectId !== activeProjectId) await selectProject(projectId);
  standardInput = String(nextStandardInput || '');
  runArguments = String(nextRunArguments || '');
  dom.developmentInput.value = standardInput;
  dom.developmentRunArguments.value = runArguments;
  if (showTutorialGuide && projectTutorialLink()) setTutorialGuideOpen(true);
  return activeProjectId === projectId;
}

export function closeDevelopmentPanel({ force = false } = {}) {
  if (!force && hasUnsavedDevelopmentChanges()) return false;
  window.clearTimeout(saveTimer);
  window.clearTimeout(symbolOutlineRefreshTimer);
  if (dom.developmentProjectDialog.open) dom.developmentProjectDialog.close();
  if (dom.developmentProjectImportDialog.open) dom.developmentProjectImportDialog.close();
  if (dom.developmentTestDialog.open) dom.developmentTestDialog.close();
  if (dom.developmentQuickOpenDialog.open) dom.developmentQuickOpenDialog.close();
  if (dom.developmentGoToLineDialog.open) dom.developmentGoToLineDialog.close();
  if (dom.developmentShortcutsDialog.open) dom.developmentShortcutsDialog.close();
  if (dom.developmentProblemsDialog.open) dom.developmentProblemsDialog.close();
  if (dom.developmentReferencesDialog.open) dom.developmentReferencesDialog.close();
  if (dom.developmentSymbolRenameDialog.open) dom.developmentSymbolRenameDialog.close();
  if (dom.developmentBinaryInspectorDialog.open) dom.developmentBinaryInspectorDialog.close();
  closeFirmwareProgrammingDialog();
  if (dom.developmentSerialMonitorDialog.open) dom.developmentSerialMonitorDialog.close();
  void stopSerialMonitor();
  void closeDebugDialog();
  setTutorialGuideOpen(false);
  projectDialogProjectId = '';
  if (dom.developmentFileDialog.open) dom.developmentFileDialog.close();
  panelPinned = false;
  setFocusMode(false);
  setPanelOpen(false);
  return true;
}

export function initializeDevelopment() {
  setFocusMode(false);
  setConsoleExpanded(false);
  restoreDevelopmentLayout();
  initializeDevelopmentEditor({
    mount: dom.developmentCodeMount,
    onChange: () => {
      binaryInspection = null;
      invalidateFirmwareProgrammingChallenge();
      renderSymbolRenameButton();
      renderBinaryInspectorButton();
      if (!dom.developmentFindBar.hidden) updateFindMatches({ preserveMatch: true });
      updateDirtyFileState();
      renderSymbolOutline();
      scheduleSave();
    },
    onFind: () => {
      findScope = 'file';
      setFindOpen(true);
    },
    onProjectFind: () => {
      findScope = 'project';
      setFindOpen(true);
    },
    onReplace: () => setFindOpen(true, { replace: true }),
    onSave: () => void saveDevelopmentChanges(),
    onRun: () => void runProject(),
    onGoToLine: openGoToLine,
    onNavigateSymbol: (symbol, position) => void openSymbolDefinition(symbol, position),
    onNavigateBack: () => void openPreviousDefinition(),
    onFindReferences: (symbol, position) => void openSymbolReferences(symbol, position),
    onRenameSymbol: (symbol, position) => openSymbolRename(symbol, position),
    onSelectionChange: () => renderSymbolRenameButton(),
    onFormat: formatActiveFile,
    onLanguageServiceRequest: requestEditorLanguageService,
  });
  initializePaneResizers();
  initializeDevelopmentTransfer({
    save: saveDevelopmentChanges,
    currentProject: activeProject,
    onImported: async (project) => {
      activeFileId = project.entryFileId;
      selectedFolderId = '';
      standardInput = '';
      setConsole();
      replaceProject(project);
    },
  });
  dom.developmentProjectCreate.addEventListener('click', () => openProjectDialog());
  dom.developmentProjectDelete.addEventListener('click', () => void deleteProject());
  dom.developmentEmptyCreate.addEventListener('click', () => openProjectDialog());
  dom.developmentProjectForm.addEventListener('submit', (event) => void createProject(event));
  dom.developmentProjectCancel.addEventListener('click', () => {
    projectDialogProjectId = '';
    dom.developmentProjectDialog.close();
  });
  installDialogBackdropClose(dom.developmentProjectDialog, () => {
    projectDialogProjectId = '';
    dom.developmentProjectDialog.close();
  });
  dom.developmentProjectKind.addEventListener('change', () => syncProjectKindFields());
  dom.developmentFirmwareTargetInput.addEventListener('change', () => syncProjectKindFields());
  dom.developmentFirmwareProgrammerInput.addEventListener('change', () => renderFirmwareDeviceSettings());
  dom.developmentFirmwarePortInput.addEventListener('change', () => renderFirmwareDeviceSettings());
  dom.developmentFirmwareBaudInput.addEventListener('change', () => renderFirmwareDeviceSettings());
  dom.developmentFirmwareDevicesRefresh.addEventListener('click', () => void refreshFirmwareDevices());
  dom.developmentProjectLanguageInput.addEventListener('change', () => populateProjectTemplates());
  dom.developmentTargetConfigure.addEventListener('click', () => void configureProject());
  dom.developmentDefinitionBack.addEventListener('click', () => void openPreviousDefinition());
  dom.developmentSymbolBrowserToggle.addEventListener('click', () => {
    symbolBrowserExpanded = !symbolBrowserExpanded;
    renderSymbolOutline();
  });
  dom.developmentSymbolBrowserRefresh.addEventListener('click', () => void refreshSymbolOutline());
  dom.developmentQuickOpen.addEventListener('click', () => openQuickOpen('files'));
  dom.developmentTutorialGuideToggle.addEventListener('click', () => setTutorialGuideOpen(!tutorialGuideOpen));
  dom.developmentTutorialGuideOpenSource.addEventListener('click', openTutorialSource);
  dom.developmentTutorialGuideClose.addEventListener('click', () => setTutorialGuideOpen(false));
  dom.developmentSymbolRename.addEventListener('click', () => openSymbolRename());
  dom.developmentShortcuts.addEventListener('click', () => {
    if (!dom.developmentShortcutsDialog.open) dom.developmentShortcutsDialog.showModal();
  });
  dom.developmentQuickOpenCancel.addEventListener('click', () => dom.developmentQuickOpenDialog.close());
  dom.developmentGoToLineCancel.addEventListener('click', () => dom.developmentGoToLineDialog.close());
  dom.developmentShortcutsCancel.addEventListener('click', () => dom.developmentShortcutsDialog.close());
  dom.developmentProblemsCancel.addEventListener('click', () => dom.developmentProblemsDialog.close());
  dom.developmentReferencesCancel.addEventListener('click', () => dom.developmentReferencesDialog.close());
  dom.developmentSymbolRenameCancel.addEventListener('click', () => dom.developmentSymbolRenameDialog.close());
  installDialogBackdropClose(dom.developmentQuickOpenDialog, () => dom.developmentQuickOpenDialog.close());
  installDialogBackdropClose(dom.developmentGoToLineDialog, () => dom.developmentGoToLineDialog.close());
  installDialogBackdropClose(dom.developmentShortcutsDialog, () => dom.developmentShortcutsDialog.close());
  installDialogBackdropClose(dom.developmentProblemsDialog, () => dom.developmentProblemsDialog.close());
  installDialogBackdropClose(dom.developmentReferencesDialog, () => dom.developmentReferencesDialog.close());
  installDialogBackdropClose(dom.developmentSymbolRenameDialog, () => dom.developmentSymbolRenameDialog.close());
  dom.developmentSymbolRenameForm.addEventListener('submit', (event) => void renameProjectSymbol(event));
  dom.developmentSymbolRenameInput.addEventListener('input', () => {
    if (renamePreview && renamePreview.newName !== dom.developmentSymbolRenameInput.value.trim()) {
      dom.developmentSymbolRenameStatus.textContent = '';
      resetSymbolRenamePreview();
    }
  });
  dom.developmentQuickOpenFiles.addEventListener('click', () => setQuickOpenMode('files'));
  dom.developmentQuickOpenSymbols.addEventListener('click', () => setQuickOpenMode('symbols'));
  dom.developmentQuickOpenSnippets.addEventListener('click', () => setQuickOpenMode('snippets'));
  dom.developmentQuickOpenInput.addEventListener('input', () => {
    quickOpenResultIndex = 0;
    renderQuickOpen();
  });
  dom.developmentQuickOpenInput.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      dom.developmentQuickOpenDialog.close();
      focusDevelopmentEditor();
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!quickOpenResults.length) return;
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      quickOpenResultIndex = (quickOpenResultIndex + direction + quickOpenResults.length) % quickOpenResults.length;
      renderQuickOpen();
      dom.developmentQuickOpenResults.querySelector('.is-active')?.scrollIntoView({ block: 'nearest' });
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      void chooseQuickOpenEntry();
    }
  });
  dom.developmentGoToLineForm.addEventListener('submit', goToEditorLine);
  dom.developmentGoToLineInput.addEventListener('input', () => dom.developmentGoToLineInput.setCustomValidity(''));
  dom.developmentFileForm.addEventListener('submit', (event) => void createFile(event));
  dom.developmentFileCancel.addEventListener('click', () => dom.developmentFileDialog.close());
  installDialogBackdropClose(dom.developmentFileDialog, () => dom.developmentFileDialog.close());
  dom.developmentProjectTitle.addEventListener('input', () => {
    fitProjectTitle();
    scheduleSave();
  });
  dom.developmentFileTitle.addEventListener('input', scheduleSave);
  dom.developmentInput.addEventListener('input', () => {
    standardInput = dom.developmentInput.value;
    window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'development' } }));
  });
  dom.developmentRunArguments.addEventListener('input', () => {
    runArguments = dom.developmentRunArguments.value;
    window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'development' } }));
  });
  dom.developmentRunArguments.addEventListener('blur', () => void saveProjectSettings());
  dom.developmentInputClear.addEventListener('click', clearDevelopmentStandardInput);
  dom.developmentCompileCopy.addEventListener('click', () => void copyDevelopmentConsoleText(
    dom.developmentCompileOutput.textContent,
    dom.developmentCompileCopy,
    'Preklad'
  ));
  dom.developmentCompileClear.addEventListener('click', clearDevelopmentCompileOutput);
  dom.developmentProblems.addEventListener('click', () => {
    renderProblems();
    if (!dom.developmentProblemsDialog.open) dom.developmentProblemsDialog.showModal();
  });
  dom.developmentRunCopy.addEventListener('click', () => void copyDevelopmentConsoleText(
    dom.developmentRunOutput.textContent,
    dom.developmentRunCopy,
    'Výstup'
  ));
  dom.developmentRunClear.addEventListener('click', clearDevelopmentRunOutput);
  dom.developmentSave.addEventListener('click', () => void saveDevelopmentChanges());
  dom.developmentFocusMode.addEventListener('click', () => setFocusMode(!focusMode));
  dom.developmentConsoleToggle.addEventListener('click', () => setConsoleExpanded(!consoleExpanded));
  dom.developmentFindToggle.addEventListener('click', () => {
    if (dom.developmentFindBar.hidden) findScope = 'file';
    setFindOpen(dom.developmentFindBar.hidden);
  });
  dom.developmentFindScope.addEventListener('click', () => {
    findScope = findScope === 'file' ? 'project' : 'file';
    updateFindMatches({ preserveMatch: false });
    dom.developmentFindInput.focus();
  });
  dom.developmentFindClose.addEventListener('click', () => {
    setFindOpen(false);
    focusDevelopmentEditor();
  });
  dom.developmentFindInput.addEventListener('input', () => {
    updateFindMatches({ preserveMatch: false });
    if (findScope === 'file') void selectFindMatch(0);
  });
  dom.developmentFindInput.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      setFindOpen(false);
      focusDevelopmentEditor();
      return;
    }
    if (findScope === 'project' && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault();
      moveProjectFindSelection(event.key === 'ArrowDown' ? 1 : -1);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (findScope === 'project') {
        if (projectFindIndex < 0) moveProjectFindSelection(1);
        void selectFindMatch(0);
        return;
      }
      void selectFindMatch(event.shiftKey ? -1 : 1);
    }
  });
  dom.developmentFindPrevious.addEventListener('click', () => void selectFindMatch(-1));
  dom.developmentFindNext.addEventListener('click', () => void selectFindMatch(1));
  dom.developmentReplaceOne.addEventListener('click', () => replaceFindMatch(false));
  dom.developmentReplaceAll.addEventListener('click', () => replaceFindMatch(true));
  dom.developmentDiagnosticNext.addEventListener('click', () => void openNextDiagnostic());
  dom.developmentFileCreate.addEventListener('click', () => void openFileDialog());
  dom.developmentFileImport.addEventListener('click', () => dom.developmentFileImportInput.click());
  dom.developmentFileImportInput.addEventListener('change', (event) => void importDevelopmentFiles(event));
  dom.developmentFolderCreate.addEventListener('click', () => void openFileDialog('folder'));
  dom.developmentEntryFile.addEventListener('click', () => void setActiveFileAsEntry());
  dom.developmentFileRename.addEventListener('click', () => void openFileDialog('rename'));
  dom.developmentFormat.addEventListener('click', formatActiveFile);
  dom.developmentFileTreeRoot.addEventListener('click', () => {
    selectedFolderId = '';
    renderFileTree();
  });
  dom.developmentFileDelete.addEventListener('click', () => void deleteFile());
  dom.developmentBuild.addEventListener('click', () => void runProject({ execute: false }));
  dom.developmentSerialMonitor.addEventListener('click', () => void openSerialMonitor());
  dom.developmentFirmwareProgram.addEventListener('click', () => void openFirmwareProgramming());
  dom.developmentBinaryInspector.addEventListener('click', openBinaryInspector);
  dom.developmentBinaryInspectorClose.addEventListener('click', () => dom.developmentBinaryInspectorDialog.close());
  installDialogBackdropClose(dom.developmentBinaryInspectorDialog, () => dom.developmentBinaryInspectorDialog.close());
  dom.developmentFirmwareProgramCancel.addEventListener('click', closeFirmwareProgrammingDialog);
  installDialogBackdropClose(dom.developmentFirmwareProgramDialog, closeFirmwareProgrammingDialog);
  dom.developmentFirmwareProgramDialog.addEventListener('close', clearFirmwareProgrammingChallenge);
  dom.developmentFirmwareProgramConfirmation.addEventListener('input', syncFirmwareProgrammingConfirmation);
  dom.developmentFirmwareProgramForm.addEventListener('submit', (event) => void submitFirmwareProgramming(event));
  dom.developmentSerialMonitorClose.addEventListener('click', () => dom.developmentSerialMonitorDialog.close());
  dom.developmentSerialMonitorStop.addEventListener('click', () => void stopSerialMonitor());
  dom.developmentSerialMonitorClear.addEventListener('click', () => {
    dom.developmentSerialMonitorOutput.textContent = '';
  });
  dom.developmentSerialMonitorCopy.addEventListener('click', () => void copyDevelopmentConsoleText(
    dom.developmentSerialMonitorOutput.textContent,
    dom.developmentSerialMonitorCopy,
    'Sériový výpis'
  ));
  dom.developmentSerialMonitorSend.addEventListener('click', () => void sendSerialMonitorInput());
  dom.developmentSerialMonitorInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      void sendSerialMonitorInput();
    }
  });
  installDialogBackdropClose(dom.developmentSerialMonitorDialog, () => dom.developmentSerialMonitorDialog.close());
  dom.developmentSerialMonitorDialog.addEventListener('close', () => void stopSerialMonitor());
  dom.developmentDebug.addEventListener('click', () => void startDebugging());
  dom.developmentDebugClose.addEventListener('click', () => void closeDebugDialog());
  dom.developmentDebugStop.addEventListener('click', () => void stopDebugging());
  dom.developmentDebugStep.addEventListener('click', () => void runDebugCommand('step'));
  dom.developmentDebugNext.addEventListener('click', () => void runDebugCommand('next'));
  dom.developmentDebugContinue.addEventListener('click', () => void runDebugCommand('continue'));
  dom.developmentDebugLocation.addEventListener('click', () => void openDebugLocation(debugSession?.location));
  dom.developmentDebugDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    void closeDebugDialog();
  });
  dom.developmentRun.addEventListener('click', () => void runProject());
  dom.developmentTests.addEventListener('click', () => void openDevelopmentTests());
  dom.developmentTestCancel.addEventListener('click', () => void closeDevelopmentTests());
  installDialogBackdropClose(dom.developmentTestDialog, () => void closeDevelopmentTests());
  dom.developmentTestDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    void closeDevelopmentTests();
  });
  dom.developmentTestCreate.addEventListener('click', () => void createDevelopmentTest());
  dom.developmentTestUseOutput.addEventListener('click', useLastRunOutputForTest);
  dom.developmentTestRunAll.addEventListener('click', () => void runAllDevelopmentTests());
  dom.developmentTestResultOpenLocation.addEventListener('click', () => void openDisplayedTestFailureLocation());
  dom.developmentTestCaseForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveDevelopmentTest();
  });
  dom.developmentTestDelete.addEventListener('click', () => void deleteDevelopmentTest());
  dom.developmentTestRun.addEventListener('click', () => void runDevelopmentTest());
  window.addEventListener('keydown', (event) => {
    if (!isDevelopmentPanelOpen() || (!event.ctrlKey && !event.metaKey)) return;
    if (event.defaultPrevented) return;
    if (event.key.toLowerCase() === 'p') {
      event.preventDefault();
      openQuickOpen('files');
      return;
    }
    if (event.key.toLowerCase() === 'o' && event.shiftKey) {
      event.preventDefault();
      openQuickOpen('symbols');
      return;
    }
    if (event.key.toLowerCase() === 'f' && event.shiftKey) {
      event.preventDefault();
      findScope = 'project';
      setFindOpen(true);
      return;
    }
    if (event.key.toLowerCase() === 'f') {
      event.preventDefault();
      findScope = 'file';
      setFindOpen(true);
      return;
    }
    if (event.key.toLowerCase() === 'g') {
      event.preventDefault();
      openGoToLine();
      return;
    }
    if (event.key.toLowerCase() === 'h') {
      event.preventDefault();
      setFindOpen(true, { replace: true });
      return;
    }
    if (event.key.toLowerCase() === 's') {
      event.preventDefault();
      void saveDevelopmentChanges();
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      void runProject({ execute: !event.shiftKey });
    }
  });
  window.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !isDevelopmentPanelOpen() || dom.developmentFindBar.hidden) return;
    event.preventDefault();
    setFindOpen(false);
    focusDevelopmentEditor();
  });
  dom.developmentInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab') return;
    event.preventDefault();
    const start = dom.developmentInput.selectionStart;
    const end = dom.developmentInput.selectionEnd;
    dom.developmentInput.setRangeText('  ', start, end, 'end');
    dispatchCodeInput(dom.developmentInput);
  });
}
