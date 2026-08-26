import { apiRequest } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { installDialogBackdropClose } from './dialogs.js';
import {
  developmentEditorSelection,
  developmentEditorValue,
  focusDevelopmentEditor,
  initializeDevelopmentEditor,
  replaceDevelopmentEditorRange,
  selectDevelopmentEditorRange,
  setDevelopmentEditorDocument,
  setDevelopmentEditorDiagnostics,
  setDevelopmentEditorProjectFiles,
} from './development-editor.js';
import { initializeDevelopmentTransfer } from './development-transfer.js';
import { dom } from './dom.js';
import { updateTopbarVisibility } from './topbar.js';

let projects = [];
let languages = [];
let firmwareTargets = [];
let firmwareBuildProfiles = [];
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
let runArguments = '';
let saveTimer = 0;
let operationCount = 0;
let idleResolvers = [];
let projectDialogProjectId = '';
let findMatches = [];
let findMatchIndex = -1;
let diagnostics = [];
let diagnosticIndex = -1;
let draggedProjectItemId = '';
let projectTests = [];
let activeTestId = '';
let testDraftBaseline = '';
let testRunResults = new Map();
let runningAllTests = false;

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

function updateFindMatches({ preserveMatch = true } = {}) {
  const query = dom.developmentFindInput.value;
  const previousOffset = preserveMatch ? findMatches[findMatchIndex] : -1;
  findMatches = textMatchOffsets(developmentEditorValue(), query);
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
}

function selectFindMatch(step = 0) {
  if (!findMatches.length) return;
  if (step) findMatchIndex = (findMatchIndex + step + findMatches.length) % findMatches.length;
  if (findMatchIndex < 0) findMatchIndex = 0;
  const start = findMatches[findMatchIndex];
  const end = start + dom.developmentFindInput.value.length;
  selectDevelopmentEditorRange(start, end);
}

function setFindOpen(open, { replace = false } = {}) {
  dom.developmentFindBar.hidden = !open;
  dom.developmentFindToggle.setAttribute('aria-expanded', String(open));
  dom.developmentFindToggle.title = open ? 'Zavrieť vyhľadávanie (Esc)' : 'Hľadať v súbore (Ctrl+F)';
  if (!open) return;
  updateFindMatches({ preserveMatch: false });
  window.requestAnimationFrame(() => {
    const field = replace ? dom.developmentReplaceInput : dom.developmentFindInput;
    field.focus();
    if (replace) field.select();
  });
}

function replaceFindMatch(all = false) {
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
  const found = [];
  const seen = new Set();
  const add = (filename, line, column = 1, severity = 'error') => {
    const key = `${filename}:${line}:${column}`;
    if (!filename || !Number.isFinite(line) || seen.has(key)) return;
    seen.add(key);
    found.push({ filename, line, column, severity });
  };
  const collect = (pattern, mapper) => {
    let match;
    while ((match = pattern.exec(compileOutput))) mapper(match);
  };

  collect(
    /(?:^|\n)(?:\/work\/)?([^\n:]+(?:\/[^\n:]+)*):(\d+)(?::(\d+))?:\s*(fatal error|error|warning):/gim,
    (match) => add(match[1], Number(match[2]), Number(match[3] || 1), match[4].toLocaleLowerCase('sk'))
  );
  collect(
    /(?:^|\n)(?:\.\/|\/work\/)?([^\n:]+\.go):(\d+):(\d+):\s*([^\n]+)/gim,
    (match) => add(match[1], Number(match[2]), Number(match[3]), /warning/i.test(match[4]) ? 'warning' : 'error')
  );
  collect(
    /(?:^|\n)\s*-->\s+(?:\/work\/)?([^\n:]+\.rs):(\d+):(\d+)/gim,
    (match) => add(match[1], Number(match[2]), Number(match[3]), 'error')
  );
  collect(
    /(?:^|\n)\s*File\s+"(?:\/work\/)?([^"\n]+)",\s+line\s+(\d+)/gim,
    (match) => add(match[1], Number(match[2]), 1, 'error')
  );
  collect(
    /(?:^|\n)(?:\/work\/)?([^\n:]+\.(?:js|mjs|php|sh|bash)):(\d+)(?::(\d+))?/gim,
    (match) => add(match[1], Number(match[2]), Number(match[3] || 1), 'error')
  );
  diagnostics = found;
  diagnosticIndex = -1;
  setDevelopmentEditorDiagnostics(diagnosticsForActiveFile());
  dom.developmentDiagnosticNext.hidden = !found.length;
  dom.developmentDiagnosticCount.textContent = found.length ? String(found.length) : '';
  dom.developmentDiagnosticNext.title = found.length
    ? `Prejsť na chybu alebo varovanie (1 z ${found.length})`
    : '';
  dom.developmentDiagnosticNext.setAttribute('aria-label', dom.developmentDiagnosticNext.title || 'Diagnostika prekladu');
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

async function openNextDiagnostic() {
  const project = activeProject();
  if (!project || !diagnostics.length) return;
  diagnosticIndex = (diagnosticIndex + 1) % diagnostics.length;
  const diagnostic = diagnostics[diagnosticIndex];
  const file = projectFiles(project).find((item) => {
    const path = projectFilePath(project, item);
    return path === diagnostic.filename || item.title === diagnostic.filename;
  });
  if (!file) return;
  if (file.id !== activeFileId) await selectFile(file.id);
  window.requestAnimationFrame(() => selectEditorLine(diagnostic.line, diagnostic.column));
  dom.developmentDiagnosticNext.title = `Prejsť na chybu alebo varovanie (${diagnosticIndex + 1} z ${diagnostics.length})`;
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
  dom.developmentSidebarTitle.title = message;
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
  dom.developmentTestResult.hidden = true;
  delete dom.developmentTestResult.dataset.state;
  dom.developmentTestResultTitle.textContent = '';
  dom.developmentTestResultDetails.textContent = '';
}

function showTestResult({ passed, details }) {
  dom.developmentTestResult.hidden = false;
  dom.developmentTestResult.dataset.state = passed ? 'success' : 'error';
  dom.developmentTestResultTitle.textContent = passed ? 'Test prešiel.' : 'Výstup sa nezhoduje.';
  dom.developmentTestResultDetails.textContent = details;
}

function evaluateTestResponse(response) {
  const result = response.result;
  const compile = result.compile || {};
  const run = result.run || {};
  const actual = resultRawText(run);
  const expected = response.test.expectedOutput;
  const passed = Boolean(result.compiled) && Number(run.exitCode) === 0
    && normalizedTestOutput(actual) === normalizedTestOutput(expected);
  return {
    response,
    result,
    passed,
    details: passed
      ? 'Skutočný výstup zodpovedá očakávanému výstupu.'
      : `Očakávané:\n${expected || '(prázdny výstup)'}\n\nSkutočné:\n${actual || '(prázdny výstup)'}`,
  };
}

function showTestConsole(evaluation) {
  const { result } = evaluation;
  const compile = result.compile || {};
  const run = result.run || {};
  const compileText = resultText(compile);
  readDiagnostics(compileText);
  setConsole({
    phase: result.compiled ? 'Hotovo' : 'Chyba prekladu',
    compile: compileText,
    compileMeta: formatResultMeta(compile),
    output: result.compiled ? resultText(run) : 'Program sa nespustil, pretože preklad zlyhal.',
    outputMeta: result.compiled ? formatResultMeta(run) : '',
  });
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
    const runResult = testRunResults.get(testCase.id);
    details.textContent = runResult
      ? `${inputLines} · ${runResult.passed ? 'prešiel' : 'neprešiel'}`
      : `${inputLines} · ${testCase.expectedOutput ? 'výstup' : 'bez očakávania'}`;
    if (runResult) button.classList.add(runResult.passed ? 'is-passed' : 'is-failed');
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
  clearTestResult();
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

function normalizedTestOutput(value) {
  return String(value || '').replace(/\r\n/g, '\n').replace(/[ \t]+\n/g, '\n').replace(/\n+$/, '');
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
        testRunResults.set(testCase.id, evaluation);
        if (evaluation.passed) passedCount += 1;
        if (!evaluation.passed || testCase.id === activeTestId) lastEvaluation = evaluation;
      } catch (error) {
        const evaluation = { passed: false, details: error.message || 'Test sa nepodarilo spustiť.' };
        testRunResults.set(testCase.id, evaluation);
        lastEvaluation = evaluation;
      }
      renderDevelopmentTests();
    }
    const selectedEvaluation = testRunResults.get(activeTestId) || lastEvaluation;
    if (selectedEvaluation) {
      showTestResult(selectedEvaluation);
      if (selectedEvaluation.result) showTestConsole(selectedEvaluation);
    }
    setTestStatus(`${passedCount} z ${tests.length} testov prešlo.`);
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
      : `${languageLabel(project.language)} · ${projectFiles(project).length} súborov`;
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

function renderEditor() {
  const project = activeProject();
  const file = activeFile();
  const hasProject = Boolean(project && file);
  dom.developmentProjectEditor.hidden = !hasProject;
  dom.developmentProjectExport.disabled = !project;
  dom.developmentWorkspace.querySelector('.development-empty').hidden = Boolean(projects.length);
  if (!hasProject) return;

  dom.developmentProjectTitle.value = project.title;
  fitProjectTitle();
  projectTitleBaseline = project.title;
  dom.developmentProjectLanguage.textContent = languageLabel(project.language);
  dom.developmentProjectLanguage.dataset.language = project.language;
  dom.developmentProjectLanguage.title = `${project.title} · ${languageLabel(project.language)}`;
  const isFirmware = project.kind === 'firmware';
  const target = project.firmwareTarget;
  dom.developmentProjectTarget.hidden = !isFirmware;
  dom.developmentProjectTarget.textContent = target
    ? `${target.label} · ${project.buildProfileLabel || 'Ladenie'}`
    : 'Firmvér bez cieľa';
  dom.developmentProjectTarget.title = target
    ? `${target.family} · ${target.board}\n${target.architecture} · ${target.toolchain}`
    : 'Vyber cieľový čip alebo dosku.';
  dom.developmentTargetConfigure.hidden = false;
  dom.developmentTargetConfigure.title = isFirmware ? 'Nastaviť projekt firmvéru' : 'Nastaviť projekt';
  dom.developmentTargetConfigure.setAttribute('aria-label', dom.developmentTargetConfigure.title);
  dom.developmentFileTitle.value = file.title;
  setDevelopmentEditorProjectFiles(projectFiles(project).map((item) => ({
    ...item,
    path: projectFilePath(project, item),
  })));
  setDevelopmentEditorDocument(file.content, project.language);
  setDevelopmentEditorDiagnostics(diagnosticsForActiveFile());
  if (!dom.developmentFindBar.hidden) updateFindMatches({ preserveMatch: false });
  dom.developmentInput.value = standardInput;
  dom.developmentRunArguments.value = runArguments;
  fileDraftBaseline = activeFileSnapshot();
  dom.developmentFileDelete.disabled = projectFiles(project).length <= 1;
  const isEntryFile = file.id === project.entryFileId;
  dom.developmentEntryFile.setAttribute('aria-pressed', String(isEntryFile));
  dom.developmentEntryFile.title = isEntryFile ? 'Hlavný súbor projektu' : 'Nastaviť ako hlavný súbor projektu';
  dom.developmentEntryFile.setAttribute('aria-label', dom.developmentEntryFile.title);
  const languageStatus = languageRuntime(project.language);
  const canRun = !isFirmware && Boolean(languageStatus.available);
  dom.developmentBuild.disabled = !canRun;
  dom.developmentBuild.title = canRun
    ? 'Preložiť bez spustenia (Ctrl+Shift+Enter)'
    : isFirmware
      ? 'Firmvérový toolchain pripojíme v ďalšom kroku.'
      : languageStatus.message;
  dom.developmentRun.disabled = !canRun;
  dom.developmentRun.title = canRun
    ? 'Preložiť a spustiť projekt (Ctrl+Enter)'
    : isFirmware
      ? 'Firmvérový toolchain pripojíme v ďalšom kroku.'
      : languageStatus.message;
  dom.developmentTests.disabled = !project;
  dom.developmentTests.title = isFirmware
    ? 'Testy projektu sa pripravia; spúšťanie firmvéru pripojíme s toolchainom.'
    : 'Testy projektu';

  dom.developmentFileTabs.replaceChildren();
  projectFiles(project).forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'development-file-tab';
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
  firmwareTargets = workspace.firmwareTargets || [];
  firmwareBuildProfiles = workspace.firmwareBuildProfiles || [];
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
  runArguments = '';
  projectTests = [];
  activeTestId = '';
  testDraftBaseline = '';
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
    option.title = `${target.board}\n${target.architecture}\n${target.toolchain}`;
    dom.developmentFirmwareTargetInput.append(option);
  });
  dom.developmentFirmwareTargetInput.value = firmwareTargets.some((target) => target.id === preferredTarget)
    ? preferredTarget
    : firmwareTargets[0]?.id || '';
}

function populateFirmwareBuildProfiles(preferredProfile = 'debug') {
  dom.developmentFirmwareBuildProfileInput.replaceChildren();
  firmwareBuildProfiles.forEach((profile) => {
    const option = document.createElement('option');
    option.value = profile.id;
    option.textContent = profile.label;
    dom.developmentFirmwareBuildProfileInput.append(option);
  });
  dom.developmentFirmwareBuildProfileInput.value = firmwareBuildProfiles.some((profile) => profile.id === preferredProfile)
    ? preferredProfile
    : firmwareBuildProfiles[0]?.id || 'debug';
}

function syncProjectKindFields(preferredLanguage = '') {
  const isFirmware = dialogProjectKind() === 'firmware';
  dom.developmentFirmwareFields.hidden = !isFirmware;
  populateProjectLanguages(preferredLanguage || dom.developmentProjectLanguageInput.value);
  dom.developmentProjectTemplateField.hidden = isFirmware || Boolean(projectDialogProjectId);
  if (!isFirmware && !projectDialogProjectId) populateProjectTemplates();
  fitProjectDialogToContent();
}

function fitProjectDialogToContent() {
  const dialog = dom.developmentProjectDialog;
  if (!dialog.open) return;
  window.requestAnimationFrame(() => {
    const form = dom.developmentProjectForm;
    const maximum = Math.max(240, window.innerHeight - 24);
    const requiredHeight = Math.max(220, Math.ceil(form.scrollHeight));
    dialog.style.height = `${Math.min(maximum, requiredHeight)}px`;
    dialog.dataset.windowSized = 'true';
  });
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
  populateFirmwareBuildProfiles(project?.buildProfile || 'debug');
  setDialogProjectKind(project?.kind || 'program');
  populateProjectLanguages(project?.language || 'c');
  syncProjectKindFields(project?.language || 'c');
  dom.developmentProjectNameInput.value = project?.title || 'Nový projekt';
  dom.developmentProjectDialog.querySelector('h2').textContent = project ? 'Cieľ firmvéru' : 'Nový projekt';
  setProjectDialogDescription(project
    ? 'Zmeň cieľ, jazyk alebo režim buildu. Obsah súborov zostane zachovaný.'
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
      buildProfile: dom.developmentFirmwareBuildProfileInput.value,
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

async function runProject({ execute = true } = {}) {
  const project = activeProject();
  if (!project || !(await saveDevelopmentChanges())) return;
  if (project.kind === 'firmware') {
    clearDiagnostics();
    setConsole({
      phase: 'Čaká na toolchain',
      compile: 'Pre tento firmvérový cieľ ešte nie je pripojený prekladač ani programátor.',
      output: 'Zatiaľ možno upravovať súbory a nastavovať cieľ projektu.'
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
    const compileText = resultText(compile);
    readDiagnostics(compileText);
    setConsole({
      phase: result.compiled ? (execute ? 'Hotovo' : 'Preložené') : 'Chyba prekladu',
      compile: compileText,
      compileMeta: formatResultMeta(compile),
      output: result.compiled
        ? (execute ? resultText(run) : 'Program nebol spustený.')
        : 'Program sa nespustil, pretože preklad zlyhal.',
      outputMeta: result.compiled && execute ? formatResultMeta(run) : ''
    });
  } catch (error) {
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

export function closeDevelopmentPanel({ force = false } = {}) {
  if (!force && hasUnsavedDevelopmentChanges()) return false;
  window.clearTimeout(saveTimer);
  if (dom.developmentProjectDialog.open) dom.developmentProjectDialog.close();
  if (dom.developmentProjectImportDialog.open) dom.developmentProjectImportDialog.close();
  if (dom.developmentTestDialog.open) dom.developmentTestDialog.close();
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
  initializeDevelopmentEditor({
    mount: dom.developmentCodeMount,
    onChange: () => {
      if (!dom.developmentFindBar.hidden) updateFindMatches({ preserveMatch: true });
      scheduleSave();
    },
    onFind: () => setFindOpen(true),
    onReplace: () => setFindOpen(true, { replace: true }),
    onSave: () => void saveDevelopmentChanges(),
    onRun: () => void runProject(),
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
  dom.developmentProjectLanguageInput.addEventListener('change', () => populateProjectTemplates());
  dom.developmentTargetConfigure.addEventListener('click', () => void configureProject());
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
  dom.developmentSave.addEventListener('click', () => void saveDevelopmentChanges());
  dom.developmentFocusMode.addEventListener('click', () => setFocusMode(!focusMode));
  dom.developmentConsoleToggle.addEventListener('click', () => setConsoleExpanded(!consoleExpanded));
  dom.developmentFindToggle.addEventListener('click', () => setFindOpen(dom.developmentFindBar.hidden));
  dom.developmentFindClose.addEventListener('click', () => {
    setFindOpen(false);
    focusDevelopmentEditor();
  });
  dom.developmentFindInput.addEventListener('input', () => {
    updateFindMatches({ preserveMatch: false });
    selectFindMatch(0);
  });
  dom.developmentFindInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      selectFindMatch(event.shiftKey ? -1 : 1);
    }
  });
  dom.developmentFindPrevious.addEventListener('click', () => selectFindMatch(-1));
  dom.developmentFindNext.addEventListener('click', () => selectFindMatch(1));
  dom.developmentReplaceOne.addEventListener('click', () => replaceFindMatch(false));
  dom.developmentReplaceAll.addEventListener('click', () => replaceFindMatch(true));
  dom.developmentDiagnosticNext.addEventListener('click', () => void openNextDiagnostic());
  dom.developmentFileCreate.addEventListener('click', () => void openFileDialog());
  dom.developmentFileImport.addEventListener('click', () => dom.developmentFileImportInput.click());
  dom.developmentFileImportInput.addEventListener('change', (event) => void importDevelopmentFiles(event));
  dom.developmentFolderCreate.addEventListener('click', () => void openFileDialog('folder'));
  dom.developmentEntryFile.addEventListener('click', () => void setActiveFileAsEntry());
  dom.developmentFileRename.addEventListener('click', () => void openFileDialog('rename'));
  dom.developmentFileTreeRoot.addEventListener('click', () => {
    selectedFolderId = '';
    renderFileTree();
  });
  dom.developmentFileDelete.addEventListener('click', () => void deleteFile());
  dom.developmentBuild.addEventListener('click', () => void runProject({ execute: false }));
  dom.developmentRun.addEventListener('click', () => void runProject());
  dom.developmentTests.addEventListener('click', () => void openDevelopmentTests());
  dom.developmentTestCancel.addEventListener('click', () => void closeDevelopmentTests());
  installDialogBackdropClose(dom.developmentTestDialog, () => void closeDevelopmentTests());
  dom.developmentTestDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    void closeDevelopmentTests();
  });
  dom.developmentTestCreate.addEventListener('click', () => void createDevelopmentTest());
  dom.developmentTestRunAll.addEventListener('click', () => void runAllDevelopmentTests());
  dom.developmentTestCaseForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveDevelopmentTest();
  });
  dom.developmentTestDelete.addEventListener('click', () => void deleteDevelopmentTest());
  dom.developmentTestRun.addEventListener('click', () => void runDevelopmentTest());
  window.addEventListener('keydown', (event) => {
    if (!isDevelopmentPanelOpen() || (!event.ctrlKey && !event.metaKey)) return;
    if (event.key.toLowerCase() === 'f') {
      event.preventDefault();
      setFindOpen(true);
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
