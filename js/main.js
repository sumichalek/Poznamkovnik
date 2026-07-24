import { APP_VERSION, LEFT_PANEL_REVEAL_DISTANCE, TOPBAR_REVEAL_DISTANCE, storageKeys } from './config.js';
import { hydrateAppIcons } from './app-icons.js';
import {
  focusArticleEditor,
  initializeArticleEditor,
  insertArticleFile,
  closeMathDialog,
  openMathDialog,
  resetMathDialog,
  runArticleEditorAction,
  submitMathDialog,
  updateMathPreview
} from './article-editor.js';
import { initializeEditorResizing } from './editor-resize.js';
import { initializeSourceDetailResizing, refreshSourceDetailResizeHandle } from './source-detail-resize.js';
import { loadBackgroundPreference } from './background.js';
import { dom } from './dom.js';
import { initializeLogin, isAuthenticated } from './login.js';
import { state } from './state.js';
import {
  cancelFolderRename,
  closeLibraryElementEditor,
  createLibraryElement,
  deleteLibraryElement,
  exitEditorFullscreen,
  handleLibraryItemClick,
  openLibraryElement,
  openLibraryRoot,
  openParentFolder,
  renderLibraryDetailPanel,
  toggleEditorFullscreen,
  updateEditorDockAxis,
  updateActiveElementFromEditor
} from './library-content.js';
import {
  closeLibrariesPanel,
  closeLibraryDetailPanel,
  hideLibraryForm,
  isTextInput,
  openLibraryDetailPanel,
  openLibrariesPanel,
  renderLibraries,
  scheduleLibrariesPanelClose,
  scheduleLibraryDetailPanelClose,
  showLibraryForm,
  upsertLibrary
} from './library-panels.js';
import {
  applyTheme,
  currentLibrary,
  flushWorkspaceSync,
  hydrateWorkspace,
  loadLibraries,
  loadLibraryElements,
  saveLibraries
} from './storage.js';
import {
  closeEditorSourceMenu,
  closeSourceDetail,
  closeSourcePreview,
  closeSourcesPanel,
  initializeSources,
  isEditorSourceMenuOpen,
  isSourceDetailOpen,
  isSourcePreviewOpen,
  isSourcesPanelOpen,
  refreshElementSourceLinks
} from './sources.js';
import { hideTopbarImmediately, updateTopbarVisibility } from './topbar.js';
import { closeTopSections, initializeTopSections, switchTopSection } from './top-sections.js';
import { initializeSettings } from './settings.js';
import { loadWorkspacePreferences } from './preferences.js';

document.addEventListener('pointermove', (event) => {
  if (!isAuthenticated()) return;
  state.pointerNearTop = event.clientY <= TOPBAR_REVEAL_DISTANCE;
  if (
    event.clientX <= LEFT_PANEL_REVEAL_DISTANCE &&
    !dom.settingsDialog.open &&
    !isSourcesPanelOpen() &&
    !isSourcePreviewOpen()
  ) {
    openLibrariesPanel();
  }
  updateTopbarVisibility();
});
dom.topbar.addEventListener('pointerenter', () => {
  state.pointerNearTop = true;
  updateTopbarVisibility();
});
dom.topbar.addEventListener('pointerleave', () => {
  state.pointerNearTop = false;
  updateTopbarVisibility();
});
dom.topbar.addEventListener('focusin', updateTopbarVisibility);
dom.topbar.addEventListener('focusout', updateTopbarVisibility);

dom.librariesButton.addEventListener('pointerenter', () => openLibrariesPanel());
dom.librariesButton.addEventListener('pointerleave', scheduleLibrariesPanelClose);
dom.librariesButton.addEventListener('focus', () => openLibrariesPanel());
dom.librariesPanel.addEventListener('pointerenter', () => openLibrariesPanel());
dom.librariesPanel.addEventListener('pointerleave', scheduleLibrariesPanelClose);
dom.librariesPanel.addEventListener('focusin', () => openLibrariesPanel());
dom.librariesPanel.addEventListener('focusout', scheduleLibrariesPanelClose);
dom.libraryDetailPanel.addEventListener('pointerenter', () => {
  if (state.activeDetailLibraryId) openLibraryDetailPanel(state.activeDetailLibraryId);
});
dom.libraryDetailPanel.addEventListener('pointerleave', () => {
  scheduleLibraryDetailPanelClose();
  scheduleLibrariesPanelClose();
});
dom.libraryDetailPanel.addEventListener('focusin', () => {
  if (state.activeDetailLibraryId) openLibraryDetailPanel(state.activeDetailLibraryId);
});
dom.libraryDetailPanel.addEventListener('focusout', () => {
  scheduleLibraryDetailPanelClose();
  scheduleLibrariesPanelClose();
});

async function openSourceTarget(libraryId, elementId = '') {
  if (!state.libraries.some((library) => library.id === libraryId)) return;
  if (!(await switchTopSection('libraries'))) return;
  state.activeLibraryId = libraryId;
  saveLibraries();
  openLibrariesPanel({ pinned: true });
  openLibraryDetailPanel(libraryId, { pinned: true });
  if (elementId) openLibraryElement(elementId);
  renderLibraries();
}

window.addEventListener('source-open-library', (event) => {
  void openSourceTarget(event.detail?.libraryId || '');
});

window.addEventListener('source-open-element', (event) => {
  void openSourceTarget(event.detail?.libraryId || '', event.detail?.elementId || '');
});

dom.libraryCreateButton.addEventListener('click', () => showLibraryForm());
dom.libraryEditButton.addEventListener('click', () => {
  const library = currentLibrary();
  if (library) showLibraryForm(library);
});
dom.libraryDeleteButton.addEventListener('click', () => {
  const library = currentLibrary();
  if (library) deleteLibrary(library.id);
});
dom.libraryCancelButton.addEventListener('click', hideLibraryForm);
dom.libraryForm.addEventListener('submit', (event) => {
  event.preventDefault();
  upsertLibrary(dom.libraryNameInput.value);
});
dom.folderHomeButton.addEventListener('click', openLibraryRoot);
dom.folderUpButton.addEventListener('click', openParentFolder);
dom.createFolderButton.addEventListener('click', () => createLibraryElement('folder'));
dom.createNoteButton.addEventListener('click', () => createLibraryElement('note'));
dom.createArticleButton.addEventListener('click', () => createLibraryElement('article'));
dom.libraryItemsList.addEventListener('pointerup', handleLibraryItemClick);
dom.libraryItemsList.addEventListener('click', handleLibraryItemClick);
dom.libraryEditorBack.addEventListener('click', () => closeLibraryElementEditor());
dom.libraryEditorFullscreen.addEventListener('click', toggleEditorFullscreen);
dom.libraryEditorDelete.addEventListener('click', () => deleteLibraryElement());
dom.libraryEditorTitle.addEventListener('input', () => updateActiveElementFromEditor({ renderItems: true }));
dom.libraryEditorTitle.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  updateActiveElementFromEditor({ renderItems: true });
  focusArticleEditor();
});
dom.libraryEditorBody.addEventListener('input', () => updateActiveElementFromEditor());

async function openCitationDialog() {
  if (!state.activeLibraryElementId) return;
  dom.citationForm.reset();
  dom.citationSavedSource.replaceChildren();
  const customOption = document.createElement('option');
  customOption.value = '';
  customOption.textContent = 'Vlastný zápis';
  dom.citationSavedSource.append(customOption);
  try {
    const result = await apiRequest('/sources');
    result.sources.forEach((source) => {
      const option = document.createElement('option');
      option.value = source.id;
      option.textContent = source.title;
      dom.citationSavedSource.append(option);
    });
  } catch {
    // Vlastný citačný zápis funguje aj bez dostupného katalógu zdrojov.
  }
  dom.citationDialog.showModal();
  dom.citationSourceInput.focus();
}

function selectEditorFile(kind) {
  dom.editorFileInput.value = '';
  dom.editorFileInput.dataset.insertKind = kind;
  dom.editorFileInput.accept = kind === 'image' ? 'image/*' : '*/*';
  dom.editorFileInput.click();
}

dom.editorFormatButtons.forEach((button) => {
  button.addEventListener('pointerdown', (event) => event.preventDefault());
  button.addEventListener('click', () => {
    const action = button.dataset.editorAction;
    if (!action) return;
    if (action === 'citation') {
      void openCitationDialog();
      return;
    }
    if (action === 'math-inline' || action === 'math-block') {
      openMathDialog({ kind: action === 'math-block' ? 'block' : 'inline' });
      return;
    }
    if (action === 'image' || action === 'attachment') {
      selectEditorFile(action);
      return;
    }
    if (action === 'link') {
      const href = window.prompt('Adresa odkazu');
      if (!href) return;
      if (runArticleEditorAction(action, { href })) updateActiveElementFromEditor();
      return;
    }
    if (runArticleEditorAction(action)) updateActiveElementFromEditor();
  });
});
dom.editorFileInput.addEventListener('change', async () => {
  const [file] = dom.editorFileInput.files || [];
  const kind = dom.editorFileInput.dataset.insertKind;
  if (file && (kind === 'image' || kind === 'attachment')) {
    if (await insertArticleFile(file, kind)) updateActiveElementFromEditor();
  }
  dom.editorFileInput.value = '';
  delete dom.editorFileInput.dataset.insertKind;
});
dom.citationCancelButton.addEventListener('click', () => dom.citationDialog.close());
dom.citationSavedSource.addEventListener('change', () => {
  const option = dom.citationSavedSource.selectedOptions[0];
  if (option?.value && !dom.citationSourceInput.value.trim()) dom.citationSourceInput.value = option.textContent || '';
});
dom.citationForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const sourceId = dom.citationSavedSource.value;
  const source = dom.citationSourceInput.value.trim();
  const locator = dom.citationLocatorInput.value.trim();
  const elementId = state.activeLibraryElementId;
  const inserted = runArticleEditorAction('citation', {
    source,
    locator,
    sourceId
  });
  if (inserted) {
    updateActiveElementFromEditor();
    dom.citationDialog.close();
    if (sourceId) {
      void (async () => {
        try {
          await flushWorkspaceSync();
          await apiRequest(`/sources/${encodeURIComponent(sourceId)}/element-links`, {
            method: 'POST',
            body: {
              id: crypto.randomUUID(),
              elementId,
              relationType: 'citation',
              locator,
              label: source
            }
          });
          await refreshElementSourceLinks();
        } catch {
          // Textová citácia ostáva v článku aj keď prepojenie na server dočasne zlyhá.
        }
      })();
    }
  }
});
dom.citationDialog.addEventListener('click', (event) => {
  if (event.target === dom.citationDialog) dom.citationDialog.close();
});
dom.mathCancelButton.addEventListener('click', closeMathDialog);
dom.mathLatex.addEventListener('input', updateMathPreview);
dom.mathForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (submitMathDialog()) updateActiveElementFromEditor();
});
dom.mathDialog.addEventListener('click', (event) => {
  if (event.target === dom.mathDialog) closeMathDialog();
});
dom.mathDialog.addEventListener('close', resetMathDialog);

document.addEventListener('pointerdown', (event) => {
  if (!isAuthenticated()) return;
  if (dom.settingsDialog.open || dom.citationDialog.open || dom.mathDialog.open || dom.sectionSwitchDialog.open) return;
  if (!state.librariesPanelPinned && !state.libraryDetailPanelPinned && !isSourcesPanelOpen()) return;
  if (
    dom.topbar.contains(event.target) ||
    dom.librariesPanel.contains(event.target) ||
    dom.libraryDetailPanel.contains(event.target) ||
    dom.libraryEditorDock.contains(event.target) ||
    dom.sourcesPanel.contains(event.target) ||
    dom.sourceBrowserPanel.contains(event.target) ||
    dom.sourceDetailDock.contains(event.target) ||
    dom.sourcePreviewDock.contains(event.target)
  ) {
    return;
  }
  void closeTopSections();
});

document.addEventListener('keydown', (event) => {
  if (!isAuthenticated()) return;
  if (event.key === 'Escape') {
    if (dom.settingsDialog.open || dom.citationDialog.open || dom.mathDialog.open || dom.sectionSwitchDialog.open) return;

    if (isEditorSourceMenuOpen()) {
      event.preventDefault();
      closeEditorSourceMenu();
      return;
    }

    if (isSourcePreviewOpen()) {
      event.preventDefault();
      closeSourcePreview();
      return;
    }

    if (isSourceDetailOpen()) {
      event.preventDefault();
      closeSourceDetail();
      return;
    }

    if (isSourcesPanelOpen()) {
      event.preventDefault();
      closeSourcesPanel({ force: true });
      return;
    }

    if (exitEditorFullscreen()) {
      event.preventDefault();
      return;
    }

    if (state.editingFolderId) {
      event.preventDefault();
      cancelFolderRename();
      renderLibraryDetailPanel();
      return;
    }

    if (dom.libraryDetailPanel.classList.contains('is-open')) {
      event.preventDefault();
      closeLibraryDetailPanel({ force: true });
      return;
    }

    if (dom.librariesPanel.classList.contains('is-open')) {
      event.preventDefault();
      closeLibrariesPanel({ force: true });
      hideTopbarImmediately();
      return;
    }

    if (!dom.topbar.classList.contains('is-hidden')) {
      event.preventDefault();
      hideTopbarImmediately();
    }
    return;
  }

  if (!event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
  if (event.key.toLowerCase() !== 'k') return;
  if (isTextInput(event.target)) return;

  event.preventDefault();
  void (async () => {
    if (await switchTopSection('libraries')) dom.librariesButton.focus();
  })();
});

function refreshDockAxes() {
  updateEditorDockAxis();
  refreshSourceDetailResizeHandle();
}

window.addEventListener('resize', refreshDockAxes);
window.visualViewport?.addEventListener('resize', refreshDockAxes);

document.documentElement.dataset.appVersion = APP_VERSION;
hydrateAppIcons();
if (dom.appVersion) dom.appVersion.textContent = `Verzia ${APP_VERSION}`;
initializeArticleEditor({ onUpdate: () => updateActiveElementFromEditor() });
initializeEditorResizing();
initializeSourceDetailResizing();
initializeSettings();
initializeSources();
initializeTopSections();
applyTheme(localStorage.getItem(storageKeys.theme) || 'focus');
loadLibraries();
loadLibraryElements();
refreshDockAxes();
renderLibraries();
dom.librariesButton.setAttribute('aria-expanded', 'false');
updateTopbarVisibility();
initializeLogin({
  onAuthenticated: async (user) => {
    await Promise.all([hydrateWorkspace(user), loadBackgroundPreference(), loadWorkspacePreferences()]);
    renderLibraries();
    state.pointerNearTop = true;
    updateTopbarVisibility();
  }
});
