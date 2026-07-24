import { dom } from './dom.js';
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

let switchInProgress = false;
let pendingDecision = null;

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

function closeSourcesSection() {
  closeSourcePreview();
  closeSourcesPanel({ force: true });
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

export async function switchTopSection(section) {
  if (switchInProgress || !['libraries', 'sources'].includes(section)) return false;
  switchInProgress = true;
  try {
    const librariesOpen = librariesSectionOpen();
    const sourcesOpen = sourcesSectionOpen();
    const targetActive = section === 'libraries' ? librariesSectionActive() : sourcesSectionActive();

    if (targetActive) {
      if (section === 'libraries') {
        if (!(await leaveLibrariesSafely())) return false;
        closeLibrariesPanel({ force: true });
        dom.librariesButton.blur();
      } else {
        if (!(await leaveSourcesSafely())) return false;
        closeSourcesSection();
        dom.sourcesButton.blur();
      }
      return true;
    }

    if (section === 'libraries') {
      if (sourcesOpen) {
        if (!(await leaveSourcesSafely())) return false;
        closeSourcesSection();
      }

      openLibrariesPanel({ pinned: true });
      return true;
    }

    if (librariesOpen) {
      if (!(await leaveLibrariesSafely())) return false;
      closeLibrariesPanel({ force: true });
    }

    await openSourcesPanel({ pinned: true });
    return true;
  } finally {
    switchInProgress = false;
  }
}

export async function closeTopSections() {
  if (switchInProgress) return false;
  switchInProgress = true;
  try {
    if (librariesSectionOpen()) {
      if (!(await leaveLibrariesSafely())) return false;
      closeLibrariesPanel({ force: true });
    }
    if (sourcesSectionOpen()) closeSourcesSection();
    return true;
  } finally {
    switchInProgress = false;
  }
}

export function initializeTopSections() {
  dom.librariesButton.addEventListener('click', () => void switchTopSection('libraries'));
  dom.sourcesButton.addEventListener('click', () => void switchTopSection('sources'));
  dom.sectionSwitchSave.addEventListener('click', () => resolvePendingDecision('save'));
  dom.sectionSwitchDiscard.addEventListener('click', () => resolvePendingDecision('discard'));
  dom.sectionSwitchStay.addEventListener('click', () => resolvePendingDecision('stay'));
  dom.sectionSwitchDialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    resolvePendingDecision('stay');
  });
  dom.sectionSwitchDialog.addEventListener('click', (event) => {
    if (event.target === dom.sectionSwitchDialog) resolvePendingDecision('stay');
  });
}
