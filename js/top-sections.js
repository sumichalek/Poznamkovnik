import { dom } from './dom.js';
import { hasOpenApplicationDialog, installDialogBackdropClose } from './dialogs.js';
import { state } from './state.js';
import {
  discardFolderRenameDraft,
  hasUnsavedFolderRename,
  saveFolderRenameDraft,
  updateActiveElementFromEditor
} from './library-content.js';
import {
  closeLibrariesPanel,
  discardLibraryFormDraft,
  hasUnsavedLibraryForm,
  openLibrariesPanel,
  saveLibraryFormDraft
} from './library-panels.js';
import { flushWorkspaceSync } from './storage.js';
import {
  closeSourcePreview,
  closeSourcesPanel,
  discardSourceDraft,
  hasUnsavedSourceChanges,
  isSourcesPanelPinned,
  isSourceDetailOpen,
  isSourcePreviewOpen,
  isSourcesPanelOpen,
  openSourcesPanel,
  saveSourceDraft,
  waitForSourceOperations
} from './sources.js';
import {
  closeTasksPanel,
  discardTaskDraft,
  hasUnsavedTaskChanges,
  isTaskDetailOpen,
  isTasksPanelOpen,
  isTasksPanelPinned,
  openTasksPanel,
  saveTaskDraft,
  waitForTaskOperations
} from './tasks.js';
import {
  closeCalendarPanel,
  discardCalendarEventDraft,
  hasUnsavedCalendarEventChanges,
  isCalendarEventDetailOpen,
  isCalendarPanelOpen,
  isCalendarPanelPinned,
  openCalendarPanel,
  saveCalendarEventDraft,
  waitForCalendarEventOperations
} from './calendar.js';
import {
  closeTutorialPanel,
  discardTutorialNoteDraft,
  hasUnsavedTutorialNoteChanges,
  isTutorialPanelOpen,
  isTutorialPanelPinned,
  isTutorialPlaygroundOpen,
  openTutorialPanel,
  saveTutorialNoteDraft,
  waitForTutorialOperations
} from './tutorial.js';

const sectionNames = ['libraries', 'sources', 'tutorial', 'tasks', 'calendar'];
const HOVER_CLOSE_DELAY = 220;

let switchInProgress = false;
let pendingDecision = null;
let pinnedSection = '';
let temporarySection = '';
let workspaceHistory = [];
let hoverCloseTimer = 0;
let hoverRequestId = 0;

function librariesSectionOpen() {
  return (
    dom.librariesPanel.classList.contains('is-open') ||
    dom.libraryDetailPanel.classList.contains('is-open') ||
    dom.libraryEditorDock.classList.contains('is-open')
  );
}

function sourcesSectionOpen() {
  return isSourcesPanelOpen() || isSourcePreviewOpen();
}

function librariesSectionActive() {
  return state.librariesPanelPinned || state.libraryDetailPanelPinned || state.editorLayout !== 'closed';
}

function sourcesSectionActive() {
  return isSourcesPanelPinned() || isSourceDetailOpen() || isSourcePreviewOpen();
}

function tasksSectionOpen() {
  return isTasksPanelOpen() || isTaskDetailOpen();
}

function tasksSectionActive() {
  return isTasksPanelPinned() || isTaskDetailOpen();
}

function calendarSectionOpen() {
  return isCalendarPanelOpen() || isCalendarEventDetailOpen();
}

function calendarSectionActive() {
  return isCalendarPanelPinned() || isCalendarEventDetailOpen();
}

function tutorialSectionOpen() {
  return isTutorialPanelOpen() || isTutorialPlaygroundOpen();
}

function tutorialSectionActive() {
  return isTutorialPanelPinned() || isTutorialPlaygroundOpen();
}

function sectionIsOpen(section) {
  if (section === 'libraries') return librariesSectionOpen();
  if (section === 'sources') return sourcesSectionOpen();
  if (section === 'tutorial') return tutorialSectionOpen();
  if (section === 'tasks') return tasksSectionOpen();
  return calendarSectionOpen();
}

function sectionIsActive(section) {
  if (section === 'libraries') return librariesSectionActive();
  if (section === 'sources') return sourcesSectionActive();
  if (section === 'tutorial') return tutorialSectionActive();
  if (section === 'tasks') return tasksSectionActive();
  return calendarSectionActive();
}

function sectionRoots(section) {
  if (section === 'libraries') return [dom.librariesPanel, dom.libraryDetailPanel, dom.libraryEditorDock];
  if (section === 'sources') return [dom.sourcesPanel, dom.sourceBrowserPanel, dom.sourceDetailDock, dom.sourcePreviewDock];
  if (section === 'tutorial') return [dom.tutorialPanel, dom.tutorialPlaygroundDock];
  if (section === 'tasks') return [dom.tasksPanel, dom.taskDetailDock];
  return [dom.calendarPanel, dom.calendarEventDock];
}

function sectionButton(section) {
  if (section === 'libraries') return dom.librariesButton;
  if (section === 'sources') return dom.sourcesButton;
  if (section === 'tutorial') return dom.tutorialButton;
  if (section === 'tasks') return dom.tasksButton;
  return dom.calendarButton;
}

function sectionHasPointer(section) {
  return sectionButton(section).matches(':hover') || sectionRoots(section).some((root) => root.matches(':hover'));
}

function sectionHasFocus(section) {
  const button = sectionButton(section);
  return button === document.activeElement || sectionRoots(section).some((root) => root.contains(document.activeElement));
}

function syncSectionState() {
  if (pinnedSection && !sectionIsOpen(pinnedSection)) pinnedSection = '';
  if (temporarySection && !sectionIsOpen(temporarySection)) temporarySection = '';
  workspaceHistory = workspaceHistory.filter(
    (section, index) => section !== pinnedSection && sectionIsOpen(section) && workspaceHistory.indexOf(section) === index
  );
  if (!pinnedSection && !temporarySection) {
    const activeSections = sectionNames.filter((section) => sectionIsOpen(section) && sectionIsActive(section));
    if (activeSections.length === 1) pinnedSection = activeSections[0];
  }
}

function updateSectionLayers() {
  syncSectionState();
  const hasTemporary = Boolean(temporarySection);
  const suspendedSections = new Set(workspaceHistory);
  document.body.classList.toggle('has-temporary-top-section', hasTemporary);
  document.body.classList.toggle('has-suspended-workspace', suspendedSections.size > 0);
  if (hasTemporary) document.body.dataset.temporaryTopSection = temporarySection;
  else delete document.body.dataset.temporaryTopSection;

  sectionNames.forEach((section) => {
    const temporary = section === temporarySection;
    const underlay = (hasTemporary && !temporary && sectionIsOpen(section)) || suspendedSections.has(section);
    const workspace = section === pinnedSection;
    sectionRoots(section).forEach((root) => {
      root.classList.toggle('is-top-section-temporary', temporary);
      root.classList.toggle('is-top-section-underlay', underlay);
      root.classList.toggle('is-top-section-workspace', workspace);
    });
  });
}

function closeSourcesSection({ force = true } = {}) {
  closeSourcePreview();
  closeSourcesPanel({ force });
}

function closeTasksSection({ force = true } = {}) {
  closeTasksPanel({ force });
}

function closeCalendarSection({ force = true } = {}) {
  closeCalendarPanel({ force });
}

function closeTutorialSection({ force = true } = {}) {
  closeTutorialPanel({ force });
}

async function openSection(section, { pinned = false } = {}) {
  if (section === 'libraries') {
    openLibrariesPanel({ pinned });
    return;
  }
  if (section === 'sources') {
    await openSourcesPanel({ pinned });
    return;
  }
  if (section === 'tutorial') {
    await openTutorialPanel({ pinned });
    return;
  }
  if (section === 'tasks') {
    await openTasksPanel({ pinned });
    return;
  }
  await openCalendarPanel({ pinned });
}

function closeSection(section, { force = true } = {}) {
  if (section === 'libraries') {
    closeLibrariesPanel({ force });
    return;
  }
  if (section === 'sources') {
    closeSourcesSection({ force });
    return;
  }
  if (section === 'tutorial') {
    closeTutorialSection({ force });
    return;
  }
  if (section === 'tasks') {
    closeTasksSection({ force });
    return;
  }
  closeCalendarSection({ force });
}

function resolvePendingDecision(decision) {
  if (!pendingDecision) return;
  const { resolve } = pendingDecision;
  pendingDecision = null;
  if (dom.sectionSwitchDialog.open) dom.sectionSwitchDialog.close();
  resolve(decision);
}

function requestSaveDecision({ title, description }) {
  dom.sectionSwitchTitle.textContent = title;
  dom.sectionSwitchDescription.textContent = description;
  dom.sectionSwitchDialog.showModal();
  return new Promise((resolve) => {
    pendingDecision = { resolve };
  });
}

async function leaveSourcesSafely() {
  await waitForSourceOperations();
  if (!hasUnsavedSourceChanges()) return true;

  const decision = await requestSaveDecision({
    title: 'Neuložené zmeny zdroja',
    description: 'V otvorenom zdroji sú zmenené údaje. Chceš ich pred prepnutím uložiť?'
  });
  if (decision === 'stay') return false;
  if (decision === 'discard') {
    discardSourceDraft();
    return true;
  }
  return saveSourceDraft();
}

async function leaveLibrariesSafely() {
  updateActiveElementFromEditor();
  await flushWorkspaceSync();

  const hasLibraryForm = hasUnsavedLibraryForm();
  const hasFolderRename = hasUnsavedFolderRename();
  if (!hasLibraryForm && !hasFolderRename) return true;

  const description = hasLibraryForm && hasFolderRename
    ? 'V knižnici aj priečinku sú neuložené zmeny. Chceš ich pred prepnutím uložiť?'
    : hasLibraryForm
      ? 'V knižnici je zmenený názov. Chceš ho pred prepnutím uložiť?'
      : 'Priečinok má zmenený názov. Chceš ho pred prepnutím uložiť?';
  const decision = await requestSaveDecision({ title: 'Neuložené zmeny knižnice', description });
  if (decision === 'stay') return false;
  if (decision === 'discard') {
    if (hasLibraryForm) discardLibraryFormDraft();
    if (hasFolderRename) discardFolderRenameDraft();
    return true;
  }

  if (hasLibraryForm && !saveLibraryFormDraft()) return false;
  if (hasFolderRename && !saveFolderRenameDraft()) return false;
  await flushWorkspaceSync();
  return true;
}

async function leaveTasksSafely() {
  await waitForTaskOperations();
  if (!hasUnsavedTaskChanges()) return true;

  const decision = await requestSaveDecision({
    title: 'Neuložené zmeny úlohy',
    description: 'V otvorenej úlohe sú zmenené údaje. Chceš ich pred prepnutím uložiť?'
  });
  if (decision === 'stay') return false;
  if (decision === 'discard') {
    discardTaskDraft();
    return true;
  }
  return saveTaskDraft();
}

async function leaveCalendarSafely() {
  await waitForCalendarEventOperations();
  if (!hasUnsavedCalendarEventChanges()) return true;

  const decision = await requestSaveDecision({
    title: 'Neuložené zmeny udalosti',
    description: 'V otvorenej udalosti sú zmenené údaje. Chceš ich pred prepnutím uložiť?'
  });
  if (decision === 'stay') return false;
  if (decision === 'discard') {
    discardCalendarEventDraft();
    return true;
  }
  return saveCalendarEventDraft();
}

async function leaveTutorialSafely() {
  await waitForTutorialOperations();
  if (!hasUnsavedTutorialNoteChanges()) return true;
  const decision = await requestSaveDecision({
    title: 'Neuložené zmeny učebnice',
    description: 'V osobných poznámkach alebo upravenom príklade máš neuložené zmeny. Chceš ich pred prepnutím uložiť?'
  });
  if (decision === 'stay') return false;
  if (decision === 'discard') {
    discardTutorialNoteDraft();
    return true;
  }
  return saveTutorialNoteDraft();
}

async function leaveSectionSafely(section) {
  if (section === 'libraries') return leaveLibrariesSafely();
  if (section === 'sources') return leaveSourcesSafely();
  if (section === 'tutorial') return leaveTutorialSafely();
  if (section === 'tasks') return leaveTasksSafely();
  return leaveCalendarSafely();
}

function clearTemporaryLayer() {
  temporarySection = '';
  updateSectionLayers();
}

function restorePreviousWorkspace(closedSection) {
  workspaceHistory = workspaceHistory.filter((section) => section !== closedSection && sectionIsOpen(section));
  if (pinnedSection === closedSection) pinnedSection = workspaceHistory.pop() || '';
  updateSectionLayers();
}

export function promoteTopSectionToWorkspace(section) {
  if (!sectionNames.includes(section) || !sectionIsOpen(section)) return;
  window.clearTimeout(hoverCloseTimer);
  hoverRequestId += 1;
  syncSectionState();

  if (pinnedSection && pinnedSection !== section && sectionIsOpen(pinnedSection)) {
    workspaceHistory = workspaceHistory.filter((item) => item !== pinnedSection && item !== section);
    workspaceHistory.push(pinnedSection);
  } else {
    workspaceHistory = workspaceHistory.filter((item) => item !== section);
  }

  pinnedSection = section;
  if (temporarySection === section) temporarySection = '';
  updateSectionLayers();
}

export async function closeWorkingTopSection(section) {
  if (!sectionNames.includes(section)) return false;
  if (temporarySection === section) return closeTemporarySection();
  if (!sectionIsOpen(section)) {
    restorePreviousWorkspace(section);
    return true;
  }
  if (!(await leaveSectionSafely(section))) return false;
  closeSection(section, { force: true });
  restorePreviousWorkspace(section);
  return true;
}

async function closeTemporarySection() {
  if (!temporarySection) return true;
  const section = temporarySection;
  if (!(await leaveSectionSafely(section))) return false;
  closeSection(section, { force: true });
  clearTemporaryLayer();
  return true;
}

async function openTemporarySection(section, requestId) {
  syncSectionState();
  if (requestId !== hoverRequestId || switchInProgress) return false;
  if (temporarySection === section) return true;

  if (temporarySection) {
    if (!(await closeTemporarySection())) return false;
    if (requestId !== hoverRequestId) return false;
  }

  if (section === pinnedSection) {
    updateSectionLayers();
    return true;
  }

  const opening = openSection(section);
  temporarySection = section;
  updateSectionLayers();
  try {
    await opening;
  } catch {
    if (temporarySection === section) clearTemporaryLayer();
    return false;
  }
  if (requestId !== hoverRequestId && temporarySection === section) {
    closeSection(section, { force: true });
    clearTemporaryLayer();
    return false;
  }
  updateSectionLayers();
  return true;
}

function scheduleSectionClose(section) {
  window.clearTimeout(hoverCloseTimer);
  hoverCloseTimer = window.setTimeout(() => {
    if (sectionHasPointer(section) || sectionHasFocus(section)) return;
    if (hasOpenApplicationDialog()) return;
    if (temporarySection === section) {
      hoverRequestId += 1;
      void closeTemporarySection();
      return;
    }
    if (!sectionIsActive(section)) closeSection(section, { force: false });
  }, HOVER_CLOSE_DELAY);
}

function keepSectionOpen(section) {
  window.clearTimeout(hoverCloseTimer);
  if (temporarySection === section) updateSectionLayers();
}

function requestTemporarySection(section) {
  window.clearTimeout(hoverCloseTimer);
  if (temporarySection === section) return;
  const requestId = ++hoverRequestId;
  void openTemporarySection(section, requestId);
}

export function isTemporaryTopSectionOpen() {
  syncSectionState();
  return Boolean(temporarySection);
}

export async function closeTemporaryTopSection() {
  window.clearTimeout(hoverCloseTimer);
  hoverRequestId += 1;
  return closeTemporarySection();
}

export async function switchTopSection(section) {
  if (switchInProgress || !sectionNames.includes(section)) return false;
  switchInProgress = true;
  window.clearTimeout(hoverCloseTimer);
  hoverRequestId += 1;
  try {
    syncSectionState();
    const hadTemporarySection = Boolean(temporarySection);
    const targetWasTemporary = temporarySection === section;
    const targetWasPinned = pinnedSection === section || (sectionIsOpen(section) && sectionIsActive(section));

    if (temporarySection && temporarySection !== section) {
      if (!(await closeTemporarySection())) return false;
    }

    if (targetWasPinned && sectionIsOpen(section) && !targetWasTemporary) {
      if (!(await closeWorkingTopSection(section))) return false;
      sectionButton(section).blur();
      return true;
    }

    for (const otherSection of sectionNames) {
      if (otherSection === section || !sectionIsOpen(otherSection)) continue;
      if (!(await leaveSectionSafely(otherSection))) return false;
      closeSection(otherSection, { force: true });
      if (pinnedSection === otherSection) pinnedSection = '';
    }
    workspaceHistory = [];

    if (targetWasTemporary) {
      await openSection(section, { pinned: true });
      pinnedSection = section;
      clearTemporaryLayer();
      return true;
    }

    if (hadTemporarySection && sectionIsOpen(section)) {
      await openSection(section, { pinned: true });
      pinnedSection = section;
      updateSectionLayers();
      return true;
    }

    if (targetWasPinned && sectionIsOpen(section)) {
      if (!(await leaveSectionSafely(section))) return false;
      closeSection(section, { force: true });
      pinnedSection = '';
      updateSectionLayers();
      sectionButton(section).blur();
      return true;
    }

    await openSection(section, { pinned: true });
    pinnedSection = section;
    updateSectionLayers();
    return true;
  } finally {
    switchInProgress = false;
  }
}

export async function closeTopSections() {
  if (switchInProgress) return false;
  switchInProgress = true;
  window.clearTimeout(hoverCloseTimer);
  hoverRequestId += 1;
  try {
    const closingOrder = temporarySection
      ? [temporarySection, ...sectionNames.filter((section) => section !== temporarySection)]
      : sectionNames;
    for (const section of closingOrder) {
      if (!sectionIsOpen(section)) continue;
      if (!(await leaveSectionSafely(section))) return false;
      closeSection(section, { force: true });
      if (temporarySection === section) clearTemporaryLayer();
    }
    pinnedSection = '';
    workspaceHistory = [];
    clearTemporaryLayer();
    return true;
  } finally {
    switchInProgress = false;
  }
}

export function initializeTopSections() {
  dom.librariesButton.addEventListener('click', () => void switchTopSection('libraries'));
  dom.sourcesButton.addEventListener('click', () => void switchTopSection('sources'));
  dom.tutorialButton.addEventListener('click', () => void switchTopSection('tutorial'));
  dom.tasksButton.addEventListener('click', () => void switchTopSection('tasks'));
  dom.calendarButton.addEventListener('click', () => void switchTopSection('calendar'));

  sectionNames.forEach((section) => {
    const button = sectionButton(section);
    button.addEventListener('pointerenter', () => requestTemporarySection(section));
    button.addEventListener('pointerleave', () => scheduleSectionClose(section));
    button.addEventListener('focus', () => requestTemporarySection(section));
    button.addEventListener('blur', () => scheduleSectionClose(section));
    sectionRoots(section).forEach((root) => {
      root.addEventListener('pointerenter', () => keepSectionOpen(section));
      root.addEventListener('pointerleave', () => scheduleSectionClose(section));
      root.addEventListener('focusin', () => keepSectionOpen(section));
      root.addEventListener('focusout', () => scheduleSectionClose(section));
    });
  });

  dom.temporarySectionBackdrop.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    event.stopPropagation();
    void closeTemporaryTopSection();
  });
  dom.sectionSwitchSave.addEventListener('click', () => resolvePendingDecision('save'));
  dom.sectionSwitchDiscard.addEventListener('click', () => resolvePendingDecision('discard'));
  dom.sectionSwitchStay.addEventListener('click', () => resolvePendingDecision('stay'));
  dom.sectionSwitchDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    resolvePendingDecision('stay');
  });
  installDialogBackdropClose(dom.sectionSwitchDialog, () => resolvePendingDecision('stay'));
  window.addEventListener('workspace-activate', (event) => {
    promoteTopSectionToWorkspace(event.detail?.section || '');
  });
}
