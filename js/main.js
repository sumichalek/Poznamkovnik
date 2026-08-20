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
import { initializeSourcePreviewResizing, refreshSourcePreviewResizeHandle } from './source-preview-resize.js';
import { initializeTutorialPlaygroundResizing, refreshTutorialPlaygroundResizeHandle } from './tutorial-playground-resize.js';
import {
  closeEditorCalendarMenu,
  closeCalendarEventDetail,
  closeCalendarPanel,
  initializeCalendar,
  isEditorCalendarMenuOpen,
  isCalendarEventDetailOpen,
  isCalendarPanelOpen,
  openCalendarPanel
} from './calendar.js';
import {
  closeTaskDetail,
  closeTasksPanel,
  initializeTasks,
  isTaskDetailOpen,
  isTasksPanelOpen,
  openTasksPanel
} from './tasks.js';
import { loadBackgroundPreference } from './background.js';
import { loadBackupOverview } from './backups.js';
import { hasOpenApplicationDialog, installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';
import { initializeLogin, isAuthenticated } from './login.js';
import { closeMusicPanel, initializeMusic, isMusicPanelOpen, openMusicPanel } from './music.js';
import { initializeMusicResizing } from './music-resize.js';
import { state } from './state.js';
import {
  cancelFolderRename,
  closeLibraryElementEditor,
  createLibraryElement,
  deleteLibraryElement,
  importMarkdownIntoLibrary,
  initializeLibraryExport,
  openLibraryExportDialog,
  openActiveLibraryElementExportDialog,
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
  deleteLibrary,
  hideLibraryForm,
  importMarkdownAsNewLibrary,
  isTextInput,
  openLibraryDetailPanel,
  openLibrariesPanel,
  renderLibraries,
  saveLibraryFormDraft,
  showLibraryForm,
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
  exitSourcePreviewFullscreen,
  closeSourcesPanel,
  initializeSources,
  isEditorSourceMenuOpen,
  isSourceDetailOpen,
  isSourcePreviewOpen,
  isSourcesPanelOpen,
  openSourcesPanel,
  refreshElementSourceLinks,
  setSourceReturnTarget
} from './sources.js';
import { hideTopbarImmediately, updateTopbarVisibility } from './topbar.js';
import {
  closeTemporaryTopSection,
  closeWorkingTopSection,
  closeTopSections,
  initializeTopSections,
  isTemporaryTopSectionOpen,
  switchTopSection
} from './top-sections.js';
import { initializeSettings } from './settings.js';
import { initializeGlobalSearch, openGlobalSearch } from './search.js';
import { initializeRelationships, openRelationships } from './relationships.js';
import { initializeMarkdownImport } from './markdown-import.js';
import { wireTagInput } from './tags.js';
import { loadWorkspacePreferences } from './preferences.js';
import { loadSecuritySettings, startSecuritySession } from './security.js';
import {
  closeTutorialPlayground,
  initializeTutorial,
  isTutorialPanelOpen,
  isTutorialPlaygroundOpen,
  openTutorialPanel
} from './tutorial.js';

document.addEventListener('pointermove', (event) => {
  if (!isAuthenticated()) return;
  state.pointerNearTop = event.clientY <= TOPBAR_REVEAL_DISTANCE;
  if (
    event.clientX <= LEFT_PANEL_REVEAL_DISTANCE &&
    !dom.settingsDialog.open &&
    !isSourcesPanelOpen() &&
    !isTasksPanelOpen() &&
    !isCalendarPanelOpen() &&
    !isTutorialPanelOpen() &&
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

function openLibraryTarget(libraryId, elementId = '') {
  if (!state.libraries.some((library) => library.id === libraryId)) return;
  state.activeLibraryId = libraryId;
  saveLibraries();
  openLibrariesPanel({ pinned: true });
  openLibraryDetailPanel(libraryId, { pinned: true });
  if (elementId) openLibraryElement(elementId);
  renderLibraries();
}

async function openSourceTarget(libraryId, elementId = '') {
  if (!state.libraries.some((library) => library.id === libraryId)) return;
  if (!(await switchTopSection('libraries'))) return;
  openLibraryTarget(libraryId, elementId);
}

async function openRequestedSource(detail = {}) {
  const sourceId = String(detail.sourceId || '');
  if (!sourceId || !(await switchTopSection('sources'))) return;
  setSourceReturnTarget(detail.returnTarget);
  await openSourcesPanel({ sourceId, pinned: true });
}

dom.libraryDetailPanel.addEventListener('pointerenter', () => {
  if (state.activeDetailLibraryId) openLibraryDetailPanel(state.activeDetailLibraryId);
});
dom.libraryDetailPanel.addEventListener('focusin', () => {
  if (state.activeDetailLibraryId) openLibraryDetailPanel(state.activeDetailLibraryId);
});

window.addEventListener('source-open-library', (event) => {
  void openSourceTarget(event.detail?.libraryId || '');
});

window.addEventListener('source-open-element', (event) => {
  void openSourceTarget(event.detail?.libraryId || '', event.detail?.elementId || '');
});

window.addEventListener('source-open-request', (event) => {
  void openRequestedSource(event.detail || {});
});

window.addEventListener('source-return-request', (event) => {
  const target = event.detail || {};
  void (async () => {
    if (!target.libraryId || !(await switchTopSection('libraries'))) return;
    setSourceReturnTarget();
    openLibraryTarget(target.libraryId, target.elementId || '');
  })();
});

window.addEventListener('task-open', (event) => {
  void (async () => {
    if (await switchTopSection('tasks')) await openTasksPanel({ taskId: event.detail?.taskId || '', pinned: true });
  })();
});

window.addEventListener('task-open-target', (event) => {
  const target = event.detail || {};
  if (target.targetType === 'library') {
    void openSourceTarget(target.libraryId || target.targetId || '');
    return;
  }
  if (target.targetType === 'element') {
    void openSourceTarget(target.libraryId || '', target.targetId || '');
    return;
  }
  if (target.targetType === 'source') {
    void (async () => {
      if (await switchTopSection('sources')) await openSourcesPanel({ sourceId: target.targetId || '', pinned: true });
    })();
  }
});

window.addEventListener('calendar-open-target', (event) => {
  const target = event.detail || {};
  if (target.targetType === 'library') {
    void openSourceTarget(target.libraryId || target.targetId || '');
    return;
  }
  if (target.targetType === 'element') {
    void openSourceTarget(target.libraryId || '', target.targetId || '');
    return;
  }
  if (target.targetType === 'source') {
    void (async () => {
      if (await switchTopSection('sources')) await openSourcesPanel({ sourceId: target.targetId || '', pinned: true });
    })();
  }
});

window.addEventListener('calendar-open-event', (event) => {
  void (async () => {
    if (await switchTopSection('calendar')) await openCalendarPanel({ eventId: event.detail?.eventId || '', pinned: true });
  })();
});

window.addEventListener('relationship-open', (event) => {
  const target = event.detail || {};
  if (target.targetType === 'library') {
    void openSourceTarget(target.targetId || '');
    return;
  }
  if (target.targetType === 'element') {
    void openSourceTarget(target.libraryId || '', target.targetId || '');
    return;
  }
  if (target.targetType === 'source') {
    void (async () => {
      if (await switchTopSection('sources')) await openSourcesPanel({ sourceId: target.targetId || '', pinned: true });
    })();
    return;
  }
  if (target.targetType === 'task') {
    void (async () => {
      if (await switchTopSection('tasks')) await openTasksPanel({ taskId: target.targetId || '', pinned: true });
    })();
    return;
  }
  if (target.targetType === 'calendar_event') {
    void (async () => {
      if (await switchTopSection('calendar')) await openCalendarPanel({ eventId: target.targetId || '', pinned: true });
    })();
    return;
  }
  if (target.targetType === 'tutorial_page') {
    void (async () => {
      if (await switchTopSection('tutorial')) {
        await openTutorialPanel({ languageId: target.languageId || '', pageId: target.targetId || '', pinned: true });
      }
    })();
  }
});

window.addEventListener('global-search-open', (event) => {
  const result = event.detail || {};
  const targetId = result.targetId || result.id || '';
  void (async () => {
    if (result.type === 'library') {
      await openSourceTarget(targetId);
      return;
    }
    if (result.type === 'folder' || result.type === 'note' || result.type === 'article') {
      await openSourceTarget(result.contextId || '', targetId);
      return;
    }
    if (result.type === 'source' || result.type === 'source_file') {
      if (await switchTopSection('sources')) await openSourcesPanel({ sourceId: targetId, pinned: true });
      return;
    }
    if (result.type === 'source_collection') {
      if (await switchTopSection('sources')) await openSourcesPanel({ collectionId: targetId, pinned: true });
      return;
    }
    if (result.type === 'task') {
      if (await switchTopSection('tasks')) await openTasksPanel({ taskId: targetId, pinned: true });
      return;
    }
    if (result.type === 'calendar_event') {
      if (await switchTopSection('calendar')) await openCalendarPanel({ eventId: targetId, pinned: true });
      return;
    }
    if (result.type === 'music_track') {
      await openMusicPanel({ trackId: targetId });
      return;
    }
    if (result.type === 'music_playlist') {
      await openMusicPanel({ playlistId: targetId });
      return;
    }
    if (result.type === 'radio_station') {
      await openMusicPanel({ stationId: targetId });
      return;
    }
    if (result.type === 'podcast_feed') {
      await openMusicPanel({ podcastId: targetId });
      return;
    }
    if (result.type === 'podcast_episode') {
      await openMusicPanel({ podcastEpisodeId: targetId });
      return;
    }
    if (result.type === 'tutorial_language') {
      if (await switchTopSection('tutorial')) await openTutorialPanel({ languageId: targetId, pinned: true });
      return;
    }
    if (result.type === 'tutorial_page' || result.type === 'tutorial_example' || result.type === 'tutorial_note') {
      if (await switchTopSection('tutorial')) {
        await openTutorialPanel({ languageId: result.contextId || '', pageId: targetId, pinned: true });
      }
    }
  })();
});

dom.libraryCreateButton.addEventListener('click', () => showLibraryForm());
dom.libraryImportButton.addEventListener('click', importMarkdownAsNewLibrary);
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
  saveLibraryFormDraft();
});
dom.folderHomeButton.addEventListener('click', openLibraryRoot);
dom.folderUpButton.addEventListener('click', openParentFolder);
dom.createFolderButton.addEventListener('click', () => createLibraryElement('folder'));
dom.createNoteButton.addEventListener('click', () => createLibraryElement('note'));
dom.createArticleButton.addEventListener('click', () => createLibraryElement('article'));
dom.libraryRelationshipsButton.addEventListener('click', () => {
  if (state.activeDetailLibraryId) void openRelationships({ targetType: 'library', targetId: state.activeDetailLibraryId });
});
dom.libraryMarkdownImport.addEventListener('click', importMarkdownIntoLibrary);
dom.libraryMarkdownExport.addEventListener('click', openLibraryExportDialog);
dom.libraryItemsList.addEventListener('pointerup', handleLibraryItemClick);
dom.libraryItemsList.addEventListener('click', handleLibraryItemClick);
dom.libraryEditorBack.addEventListener('click', () => closeLibraryElementEditor());
dom.libraryEditorFullscreen.addEventListener('click', toggleEditorFullscreen);
dom.libraryEditorDelete.addEventListener('click', () => deleteLibraryElement());
dom.libraryEditorRelationships.addEventListener('click', () => {
  if (state.activeLibraryElementId) void openRelationships({ targetType: 'element', targetId: state.activeLibraryElementId });
});
dom.libraryEditorMarkdownExport.addEventListener('click', openActiveLibraryElementExportDialog);
dom.libraryEditorTitle.addEventListener('input', () => updateActiveElementFromEditor({ renderItems: true }));
dom.libraryEditorTitle.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  updateActiveElementFromEditor({ renderItems: true });
  focusArticleEditor();
});
dom.libraryEditorBody.addEventListener('input', () => updateActiveElementFromEditor());
dom.libraryEditorTags.addEventListener('input', () => updateActiveElementFromEditor({ renderItems: true }));

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
installDialogBackdropClose(dom.citationDialog, () => dom.citationDialog.close());
dom.mathCancelButton.addEventListener('click', closeMathDialog);
dom.mathLatex.addEventListener('input', updateMathPreview);
dom.mathForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (submitMathDialog()) updateActiveElementFromEditor();
});
installDialogBackdropClose(dom.mathDialog, closeMathDialog);
dom.mathDialog.addEventListener('close', resetMathDialog);

document.addEventListener('pointerdown', (event) => {
  if (!isAuthenticated()) return;
  if (hasOpenApplicationDialog()) return;
  if (!state.librariesPanelPinned && !state.libraryDetailPanelPinned && !isSourcesPanelOpen() && !isTasksPanelOpen() && !isCalendarPanelOpen() && !isTutorialPanelOpen()) return;
  if (
    dom.topbar.contains(event.target) ||
    dom.librariesPanel.contains(event.target) ||
    dom.libraryDetailPanel.contains(event.target) ||
    dom.libraryEditorDock.contains(event.target) ||
    dom.sourcesPanel.contains(event.target) ||
    dom.sourceBrowserPanel.contains(event.target) ||
    dom.sourceDetailDock.contains(event.target) ||
    dom.sourcePreviewDock.contains(event.target)
    || dom.tasksPanel.contains(event.target)
    || dom.taskDetailDock.contains(event.target)
    || dom.calendarPanel.contains(event.target)
    || dom.calendarEventDock.contains(event.target)
    || dom.tutorialPanel.contains(event.target)
    || dom.tutorialPlaygroundDock.contains(event.target)
    || dom.musicDock.contains(event.target)
  ) {
    return;
  }
  void closeTopSections();
});

document.addEventListener('keydown', (event) => {
  if (!isAuthenticated()) return;
  if (
    event.ctrlKey && event.shiftKey && !event.altKey && !event.metaKey && event.key.toLowerCase() === 'f' &&
    !hasOpenApplicationDialog()
  ) {
    event.preventDefault();
    openGlobalSearch();
    return;
  }
  if (event.key === 'Escape') {
    if (hasOpenApplicationDialog()) return;

    if (isTemporaryTopSectionOpen()) {
      event.preventDefault();
      void closeTemporaryTopSection();
      return;
    }

    if (isMusicPanelOpen()) {
      event.preventDefault();
      closeMusicPanel();
      return;
    }

    if (isEditorSourceMenuOpen()) {
      event.preventDefault();
      closeEditorSourceMenu();
      return;
    }

    if (isEditorCalendarMenuOpen()) {
      event.preventDefault();
      closeEditorCalendarMenu();
      return;
    }

    if (isSourcePreviewOpen()) {
      event.preventDefault();
      if (exitSourcePreviewFullscreen()) return;
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
      void closeWorkingTopSection('sources');
      return;
    }

    if (isTutorialPlaygroundOpen()) {
      event.preventDefault();
      closeTutorialPlayground();
      return;
    }

    if (isTutorialPanelOpen()) {
      event.preventDefault();
      void closeWorkingTopSection('tutorial');
      return;
    }

    if (isCalendarEventDetailOpen()) {
      event.preventDefault();
      closeCalendarEventDetail();
      return;
    }

    if (isCalendarPanelOpen()) {
      event.preventDefault();
      void closeWorkingTopSection('calendar');
      return;
    }

    if (isTaskDetailOpen()) {
      event.preventDefault();
      closeTaskDetail();
      return;
    }

    if (isTasksPanelOpen()) {
      event.preventDefault();
      void closeWorkingTopSection('tasks');
      return;
    }

    if (exitEditorFullscreen()) {
      event.preventDefault();
      return;
    }

    if (state.activeLibraryElementId) {
      event.preventDefault();
      closeLibraryElementEditor();
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
      void closeWorkingTopSection('libraries');
      return;
    }

    if (dom.librariesPanel.classList.contains('is-open')) {
      event.preventDefault();
      void closeWorkingTopSection('libraries');
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
  refreshSourcePreviewResizeHandle();
  refreshTutorialPlaygroundResizeHandle();
}

window.addEventListener('resize', refreshDockAxes);
window.visualViewport?.addEventListener('resize', refreshDockAxes);

document.documentElement.dataset.appVersion = APP_VERSION;
hydrateAppIcons();
if (dom.appVersion) dom.appVersion.textContent = `Verzia ${APP_VERSION}`;
initializeArticleEditor({ onUpdate: () => updateActiveElementFromEditor() });
initializeEditorResizing();
initializeSourceDetailResizing();
initializeSourcePreviewResizing();
initializeTutorialPlaygroundResizing();
initializeMusicResizing();
initializeSettings();
initializeGlobalSearch();
initializeRelationships();
initializeMarkdownImport();
initializeLibraryExport();
[
  [dom.libraryTags, dom.libraryTagChips],
  [dom.libraryEditorTags, dom.libraryEditorTagChips],
  [dom.sourceTags, dom.sourceTagChips],
  [dom.taskTags, dom.taskTagChips],
  [dom.calendarEventTags, dom.calendarEventTagChips]
].forEach(([input, chips]) => wireTagInput(input, chips));
initializeMusic();
initializeSources();
initializeTasks();
initializeCalendar();
initializeTutorial();
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
    await Promise.all([
      hydrateWorkspace(user),
      loadBackgroundPreference(),
      loadWorkspacePreferences(),
      loadBackupOverview(),
      loadSecuritySettings()
    ]);
    startSecuritySession();
    renderLibraries();
    state.pointerNearTop = true;
    updateTopbarVisibility();
  }
});
