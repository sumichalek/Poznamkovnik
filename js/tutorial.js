import { apiRequest } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';
import { updateTopbarVisibility } from './topbar.js';
import { refreshTutorialPlaygroundResizeHandle } from './tutorial-playground-resize.js';
import { openRelationships } from './relationships.js';

let languages = [];
let tutorial = null;
let selectedLanguageId = '';
let selectedPageId = '';
let selectedExampleId = '';
let panelPinned = false;
let runtime = { available: false, message: 'Skúšobňa sa pripravuje.' };
let noteBaseline = '';
let draftBaseline = '';
let operationCount = 0;
let idleResolvers = [];
let draftSaveTimer = 0;
let catalogRequest = null;
let expandedChapterId = '';
let expandedPageIds = new Set();

function pageById(pageId) {
  return tutorial?.pages.find((page) => page.id === pageId) || null;
}

function selectedPage() {
  return pageById(selectedPageId);
}

function selectedExample() {
  return tutorial?.examples.find((example) => example.id === selectedExampleId) || null;
}

function pageExamples(pageId) {
  return tutorial?.examples.filter((example) => example.pageId === pageId) || [];
}

function rootChapterId(pageId) {
  if (!tutorial) return '';
  let current = pageById(pageId);
  while (current) {
    if (current.kind === 'chapter' && !current.parentId) return current.id;
    current = pageById(current.parentId);
  }
  return '';
}

function syncExpandedChapter(pageId) {
  expandedChapterId = rootChapterId(pageId);
  let current = pageById(pageId);
  while (current) {
    if (current.kind === 'chapter' && current.parentId) expandedPageIds.add(current.id);
    current = pageById(current.parentId);
  }
}

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

export function waitForTutorialOperations() {
  if (!operationCount) return Promise.resolve();
  return new Promise((resolve) => idleResolvers.push(resolve));
}

function setTutorialPanelOpen(open) {
  dom.tutorialPanel.classList.toggle('is-open', open);
  dom.tutorialPanel.setAttribute('aria-hidden', String(!open));
  dom.tutorialButton.setAttribute('aria-expanded', String(open));
  updateTopbarVisibility();
}

function setPlaygroundOpen(open) {
  dom.tutorialPlaygroundDock.classList.toggle('is-open', open);
  dom.tutorialPlaygroundDock.setAttribute('aria-hidden', String(!open));
  if (open) document.body.dataset.tutorialPlaygroundOpen = 'true';
  else delete document.body.dataset.tutorialPlaygroundOpen;
  if (!open) setPlaygroundFullscreen(false);
  if (open) window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'tutorial' } }));
  refreshTutorialPlaygroundResizeHandle();
  updateTopbarVisibility();
}

function setPlaygroundFullscreen(fullscreen) {
  dom.tutorialPlaygroundDock.classList.toggle('is-fullscreen', fullscreen);
  setAppIcon(dom.tutorialPlaygroundFullscreen.querySelector('.app-icon'), fullscreen ? 'minimize' : 'maximize');
  dom.tutorialPlaygroundFullscreen.title = fullscreen ? 'Zobraziť vedľa učebnice' : 'Celá plocha';
  dom.tutorialPlaygroundFullscreen.setAttribute(
    'aria-label',
    fullscreen ? 'Zobraziť skúšobňu vedľa učebnice' : 'Otvoriť skúšobňu na celej ploche'
  );
  refreshTutorialPlaygroundResizeHandle();
}

function setRuntimeStatus(status) {
  runtime = status || { available: false, message: 'Skúšobňa nie je dostupná.' };
  const applyStatus = (element, { compact = false } = {}) => {
    const message = compact && runtime.available ? 'Skúšobňa pripravená' : runtime.message || '';
    const label = document.createElement('span');
    label.textContent = message;
    element.replaceChildren(createAppIcon('terminal'), label);
    element.title = runtime.message || '';
    element.setAttribute('aria-label', runtime.message || 'Stav skúšobne');
    element.classList.toggle('is-ready', Boolean(runtime.available));
    element.classList.toggle('is-unavailable', !runtime.available);
  };
  applyStatus(dom.tutorialRuntimeStatus, { compact: true });
  applyStatus(dom.tutorialPlaygroundRuntime);
  dom.tutorialPlaygroundRun.disabled = !runtime.available;
}

function setReaderMessage(message) {
  dom.tutorialPageContent.replaceChildren();
  const notice = document.createElement('p');
  notice.className = 'tutorial-empty';
  notice.textContent = message;
  dom.tutorialPageContent.append(notice);
  dom.tutorialExamplesSection.hidden = true;
  dom.tutorialRelationshipsButton.hidden = true;
  dom.tutorialNotesInput.disabled = true;
  dom.tutorialNotesSave.disabled = true;
}

async function loadLanguages() {
  const result = await apiRequest('/tutorial/languages');
  languages = result.languages || [];
  if (!selectedLanguageId || !languages.some((language) => language.id === selectedLanguageId)) {
    selectedLanguageId = languages[0]?.id || '';
  }
  renderLanguages();
  if (selectedLanguageId) await loadLanguage(selectedLanguageId);
  else setReaderMessage('Zatiaľ nie je dostupná žiadna učebnica.');
}

async function loadLanguage(languageId) {
  const result = await apiRequest(`/tutorial/languages/${encodeURIComponent(languageId)}`);
  tutorial = result;
  selectedLanguageId = result.language.id;
  const overview = tutorial.pages.find((page) => page.kind === 'overview');
  if (!selectedPageId || !tutorial.pages.some((page) => page.id === selectedPageId)) {
    selectedPageId = overview?.id || tutorial.pages[0]?.id || '';
  }
  syncExpandedChapter(selectedPageId);
  renderLanguages();
  renderTutorial();
}

function renderLanguages() {
  dom.tutorialLanguageList.replaceChildren();
  languages.forEach((language) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tutorial-language-button';
    const active = language.id === selectedLanguageId;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
    button.append(createAppIcon('book-open'));
    const label = document.createElement('span');
    label.textContent = language.title;
    button.append(label);
    button.addEventListener('click', () => void selectLanguage(language.id));
    dom.tutorialLanguageList.append(button);
  });
  const language = languages.find((item) => item.id === selectedLanguageId);
  dom.tutorialLanguageSummary.textContent = language?.summary || '';
}

function pageIcon(page) {
  if (page.kind === 'chapter') return 'book-open';
  if (page.kind === 'reference') return 'article';
  return 'note';
}

function matchesPage(page, query) {
  if (!query) return true;
  const haystack = `${page.title} ${page.summary}`.toLocaleLowerCase('sk');
  return haystack.includes(query);
}

function renderTree() {
  dom.tutorialPagesTree.replaceChildren();
  if (!tutorial) return;
  const query = dom.tutorialSearch.value.trim().toLocaleLowerCase('sk');
  const pagesByParent = new Map();
  tutorial.pages.forEach((page) => {
    const parent = page.parentId || '';
    if (!pagesByParent.has(parent)) pagesByParent.set(parent, []);
    pagesByParent.get(parent).push(page);
  });
  const directMatches = new Set(tutorial.pages.filter((page) => matchesPage(page, query)).map((page) => page.id));
  const visible = new Set(directMatches);
  if (query) {
    tutorial.pages.forEach((page) => {
      let current = page;
      if (!directMatches.has(current.id)) return;
      while (current?.parentId) {
        visible.add(current.parentId);
        current = tutorial.pages.find((candidate) => candidate.id === current.parentId) || null;
      }
    });
  }

  const appendNodes = (parentId, depth) => {
    (pagesByParent.get(parentId) || []).forEach((page) => {
      if (query && !visible.has(page.id)) return;
      const children = pagesByParent.get(page.id) || [];
      const isChapter = page.kind === 'chapter' && children.length > 0;
      const isRootChapter = isChapter && !page.parentId;
      const isExpanded = Boolean(query) || (isRootChapter ? expandedChapterId === page.id : expandedPageIds.has(page.id));
      const row = document.createElement('div');
      row.className = 'tutorial-tree-row';
      row.classList.toggle('is-chapter', isChapter);

      if (isChapter) {
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'tutorial-chapter-toggle';
        toggle.setAttribute('aria-label', `${isExpanded ? 'Zbaliť' : 'Rozbaliť'} kapitolu ${page.title}`);
        toggle.setAttribute('aria-expanded', String(isExpanded));
        toggle.title = isExpanded ? 'Zbaliť kapitolu' : 'Rozbaliť kapitolu';
        toggle.append(createAppIcon(isExpanded ? 'chevron-down' : 'chevron-right'));
        toggle.addEventListener('click', () => {
          if (isExpanded) {
            if (isRootChapter) expandedChapterId = '';
            else expandedPageIds.delete(page.id);
            renderTree();
            return;
          }
          if (isRootChapter) {
            void selectPage(page.id);
            return;
          }
          expandedPageIds.add(page.id);
          renderTree();
        });
        row.append(toggle);
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tutorial-page-tree-item';
      button.classList.toggle('is-active', page.id === selectedPageId);
      button.style.setProperty('--tutorial-indent', `${Math.min(depth, 5) * 8}px`);
      button.title = page.summary || page.title;
      button.append(createAppIcon(pageIcon(page)));
      const label = document.createElement('span');
      label.textContent = page.title;
      button.append(label);
      button.addEventListener('click', () => void selectPage(page.id));
      row.append(button);
      dom.tutorialPagesTree.append(row);
      if (children.length && (!isChapter || isExpanded)) appendNodes(page.id, depth + 1);
    });
  };
  appendNodes('', 0);
  if (!dom.tutorialPagesTree.childElementCount) {
    const message = document.createElement('p');
    message.className = 'tutorial-tree-empty';
    message.textContent = 'Žiadna téma nevyhovuje hľadaniu.';
    dom.tutorialPagesTree.append(message);
  }
}

function renderContent(page) {
  dom.tutorialPageContent.replaceChildren();
  const content = page.content || {};
  if (content.lead) {
    const lead = document.createElement('p');
    lead.className = 'tutorial-lead';
    lead.textContent = content.lead;
    dom.tutorialPageContent.append(lead);
  }
  (content.sections || []).forEach((section) => {
    const block = document.createElement('section');
    block.className = 'tutorial-content-section';
    if (section.title) {
      const heading = document.createElement('h3');
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
      const commandLabels = new Set(['Zdroj', 'Preklad', 'Spustenie']);
      section.bullets.forEach((text) => {
        const item = document.createElement('li');
        const separator = text.indexOf(':');
        const label = separator > 0 ? text.slice(0, separator) : '';
        if (commandLabels.has(label)) {
          list.classList.add('tutorial-command-list');
          const commandLabel = document.createElement('span');
          commandLabel.textContent = label;
          const command = document.createElement('code');
          command.textContent = text.slice(separator + 1).trim();
          item.append(commandLabel, command);
        } else {
          item.textContent = text;
        }
        list.append(item);
      });
      block.append(list);
    }
    if (section.callout) {
      const callout = document.createElement('p');
      callout.className = 'tutorial-callout';
      callout.textContent = section.callout;
      block.append(callout);
    }
    dom.tutorialPageContent.append(block);
  });
}

function renderExamples(page) {
  const examples = pageExamples(page.id);
  dom.tutorialExamplesList.replaceChildren();
  dom.tutorialExamplesSection.hidden = !examples.length;
  examples.forEach((example) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tutorial-example-card';
    button.classList.toggle('is-active', example.id === selectedExampleId && isTutorialPlaygroundOpen());
    button.append(createAppIcon('play', 'tutorial-example-icon'));
    const copy = document.createElement('span');
    copy.className = 'tutorial-example-copy';
    const title = document.createElement('strong');
    title.textContent = example.title;
    const description = document.createElement('small');
    description.textContent = example.description;
    copy.append(title, description);
    button.append(copy, createAppIcon('arrow-right', 'tutorial-example-open-icon'));
    button.setAttribute('aria-label', `Otvoriť skúšobný príklad: ${example.title}`);
    button.addEventListener('click', () => void openExample(example.id));
    dom.tutorialExamplesList.append(button);
  });
}

function breadcrumbs(page) {
  const parts = [];
  let current = page;
  while (current) {
    parts.unshift(current.title);
    current = tutorial.pages.find((candidate) => candidate.id === current.parentId);
  }
  return parts.join(' / ');
}

function renderPage() {
  const page = selectedPage();
  if (!page) {
    setReaderMessage('Vyber tému z obsahu učebnice.');
    return;
  }
  dom.tutorialNotesInput.disabled = false;
  dom.tutorialNotesSave.disabled = false;
  dom.tutorialBreadcrumb.textContent = breadcrumbs(page);
  dom.tutorialPageTitle.textContent = page.title;
  dom.tutorialPageSummary.textContent = page.summary;
  dom.tutorialRelationshipsButton.hidden = false;
  dom.tutorialNotesInput.value = page.note || '';
  noteBaseline = dom.tutorialNotesInput.value;
  dom.tutorialNotesStatus.textContent = page.noteUpdatedAt ? 'Uložené' : '';
  renderContent(page);
  renderExamples(page);
}

function renderTutorial() {
  renderTree();
  renderPage();
}

async function selectLanguage(languageId) {
  if (languageId === selectedLanguageId && tutorial) return;
  if (!(await saveTutorialChanges())) return;
  selectedLanguageId = languageId;
  selectedPageId = '';
  selectedExampleId = '';
  closeTutorialPlayground();
  await runOperation(async () => {
    try {
      await loadLanguage(languageId);
    } catch {
      setReaderMessage('Učebnicu sa nepodarilo načítať.');
    }
  });
}

async function selectPage(pageId) {
  if (pageId === selectedPageId) return;
  if (!(await saveTutorialChanges())) return;
  closeTutorialPlayground();
  selectedPageId = pageId;
  syncExpandedChapter(pageId);
  renderTutorial();
}

function creationParentId() {
  const page = selectedPage();
  if (!page) return '';
  return page.kind === 'chapter' ? page.id : page.parentId || '';
}

function populateTutorialPageParents() {
  dom.tutorialPageParent.replaceChildren();
  const root = document.createElement('option');
  root.value = '';
  root.textContent = 'Hlavná úroveň učebnice';
  dom.tutorialPageParent.append(root);
  (tutorial?.pages || [])
    .filter((page) => page.kind === 'chapter')
    .forEach((page) => {
      const option = document.createElement('option');
      option.value = page.id;
      option.textContent = breadcrumbs(page);
      dom.tutorialPageParent.append(option);
    });
}

function syncTutorialPageForm() {
  const needsParent = dom.tutorialPageKind.value !== 'chapter';
  const rootOption = dom.tutorialPageParent.querySelector('option[value=""]');
  if (rootOption) rootOption.disabled = needsParent;
  if (needsParent && !dom.tutorialPageParent.value) {
    const firstChapter = [...dom.tutorialPageParent.options].find((option) => option.value);
    if (firstChapter) dom.tutorialPageParent.value = firstChapter.value;
  }
}

async function openTutorialPageDialog() {
  if (!tutorial || !(await saveTutorialChanges())) return;
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'tutorial' } }));
  populateTutorialPageParents();
  const parentId = creationParentId();
  dom.tutorialPageKind.value = parentId ? 'lesson' : 'chapter';
  dom.tutorialPageParent.value = parentId;
  syncTutorialPageForm();
  dom.tutorialPageTitleInput.value = '';
  dom.tutorialPageSummaryInput.value = '';
  dom.tutorialPageLeadInput.value = '';
  dom.tutorialPageFormStatus.textContent = '';
  if (!dom.tutorialPageDialog.open) dom.tutorialPageDialog.showModal();
  window.setTimeout(() => dom.tutorialPageTitleInput.focus(), 0);
}

async function createTutorialPage(event) {
  event.preventDefault();
  if (!tutorial) return;
  const submit = dom.tutorialPageForm.querySelector('button[type="submit"]');
  if (submit) submit.disabled = true;
  dom.tutorialPageFormStatus.textContent = 'Vytváram...';
  try {
    const result = await runOperation(() => apiRequest(
      `/tutorial/languages/${encodeURIComponent(selectedLanguageId)}/pages`,
      {
        method: 'POST',
        body: {
          title: dom.tutorialPageTitleInput.value,
          kind: dom.tutorialPageKind.value,
          parentId: dom.tutorialPageParent.value,
          summary: dom.tutorialPageSummaryInput.value,
          lead: dom.tutorialPageLeadInput.value
        }
      }
    ));
    selectedPageId = result.page.id;
    selectedExampleId = '';
    closeTutorialPlayground();
    await loadLanguage(selectedLanguageId);
    dom.tutorialPageDialog.close();
  } catch (error) {
    dom.tutorialPageFormStatus.textContent = error.message || 'Časť učebnice sa nepodarilo vytvoriť.';
  } finally {
    if (submit) submit.disabled = false;
  }
}

function playgroundDraftSnapshot() {
  return JSON.stringify({
    source: dom.tutorialPlaygroundCode.value,
    stdin: dom.tutorialPlaygroundInput.value
  });
}

function hasUnsavedPlaygroundDraft() {
  return isTutorialPlaygroundOpen() && playgroundDraftSnapshot() !== draftBaseline;
}

export function hasUnsavedTutorialNoteChanges() {
  return Boolean(selectedPage()) && (dom.tutorialNotesInput.value !== noteBaseline || hasUnsavedPlaygroundDraft());
}

export function discardTutorialNoteDraft() {
  const page = selectedPage();
  if (page) dom.tutorialNotesInput.value = page.note || '';
  noteBaseline = dom.tutorialNotesInput.value;
  const example = selectedExample();
  if (example) {
    dom.tutorialPlaygroundCode.value = example.draftSource;
    dom.tutorialPlaygroundInput.value = example.draftStdin;
    draftBaseline = playgroundDraftSnapshot();
  }
  dom.tutorialNotesStatus.textContent = '';
}

async function saveNote() {
  const page = selectedPage();
  if (!page || dom.tutorialNotesInput.value === noteBaseline) return true;
  dom.tutorialNotesSave.disabled = true;
  dom.tutorialNotesStatus.textContent = 'Ukladám...';
  try {
    const result = await apiRequest(`/tutorial/pages/${encodeURIComponent(page.id)}/note`, {
      method: 'PUT',
      body: { content: dom.tutorialNotesInput.value }
    });
    page.note = result.note.content;
    page.noteUpdatedAt = result.note.updatedAt;
    noteBaseline = dom.tutorialNotesInput.value;
    dom.tutorialNotesStatus.textContent = 'Uložené';
    return true;
  } catch (error) {
    dom.tutorialNotesStatus.textContent = error.message || 'Poznámku sa nepodarilo uložiť.';
    return false;
  } finally {
    dom.tutorialNotesSave.disabled = false;
  }
}

async function persistPlaygroundDraft(example, source, stdin) {
  if (!example) return true;
  try {
    const result = await apiRequest(`/tutorial/examples/${encodeURIComponent(example.id)}/draft`, {
      method: 'PUT',
      body: { source, stdin }
    });
    example.draftSource = result.draft.source;
    example.draftStdin = result.draft.stdin;
    example.draftUpdatedAt = result.draft.updatedAt;
    if (example.id === selectedExampleId) draftBaseline = playgroundDraftSnapshot();
    return true;
  } catch (error) {
    dom.tutorialPlaygroundRuntime.textContent = error.message || 'Úpravu príkladu sa nepodarilo uložiť.';
    return false;
  }
}

async function savePlaygroundDraft() {
  const example = selectedExample();
  if (!example || !hasUnsavedPlaygroundDraft()) return true;
  return persistPlaygroundDraft(example, dom.tutorialPlaygroundCode.value, dom.tutorialPlaygroundInput.value);
}

export async function saveTutorialNoteDraft() {
  return saveTutorialChanges();
}

async function saveTutorialChanges() {
  window.clearTimeout(draftSaveTimer);
  const noteSaved = await runOperation(saveNote);
  if (!noteSaved) return false;
  return runOperation(savePlaygroundDraft);
}

function scheduleDraftSave() {
  window.clearTimeout(draftSaveTimer);
  draftSaveTimer = window.setTimeout(() => {
    if (hasUnsavedPlaygroundDraft()) void runOperation(savePlaygroundDraft);
  }, 700);
}

function setRunResult(result) {
  const compile = result.compile;
  const compileMessages = [compile.stdout, compile.stderr].filter(Boolean).join('\n');
  dom.tutorialCompileOutput.textContent = compileMessages || (compile.exitCode === 0 ? 'Preklad prebehol bez výstupu.' : 'Preklad zlyhal.');
  dom.tutorialCompileMeta.textContent = compile.timedOut
    ? 'Čas prekladu vypršal'
    : compile.outputLimited
      ? 'Výstup bol skrátený'
      : `${compile.durationMs} ms`;
  const execution = result.run;
  if (!execution) {
    dom.tutorialRunOutput.textContent = 'Program nebol spustený, pretože preklad zlyhal.';
    dom.tutorialRunMeta.textContent = '';
    return;
  }
  const output = [execution.stdout, execution.stderr].filter(Boolean).join(execution.stdout && execution.stderr ? '\n' : '');
  dom.tutorialRunOutput.textContent = output || 'Program nevypísal žiadny výstup.';
  dom.tutorialRunMeta.textContent = execution.timedOut
    ? 'Čas behu vypršal'
    : execution.outputLimited
      ? 'Výstup bol skrátený'
      : `${execution.durationMs} ms · kód ${execution.exitCode}`;
}

async function runExample() {
  const example = selectedExample();
  if (!example || !runtime.available) return;
  if (!(await savePlaygroundDraft())) return;
  dom.tutorialPlaygroundRun.disabled = true;
  dom.tutorialCompileMeta.textContent = 'Prekladám...';
  dom.tutorialRunMeta.textContent = '';
  dom.tutorialCompileOutput.textContent = '';
  dom.tutorialRunOutput.textContent = '';
  try {
    const result = await runOperation(() => apiRequest(`/tutorial/examples/${encodeURIComponent(example.id)}/run`, {
      method: 'POST',
      body: {
        source: dom.tutorialPlaygroundCode.value,
        stdin: dom.tutorialPlaygroundInput.value,
        standard: example.standard
      }
    }));
    setRunResult(result);
  } catch (error) {
    dom.tutorialCompileOutput.textContent = error.message || 'Príklad sa nepodarilo spracovať.';
    dom.tutorialCompileMeta.textContent = 'Chyba';
  } finally {
    dom.tutorialPlaygroundRun.disabled = !runtime.available;
  }
}

async function openExample(exampleId) {
  if (!(await saveTutorialChanges())) return;
  const example = tutorial?.examples.find((item) => item.id === exampleId);
  if (!example) return;
  selectedExampleId = example.id;
  dom.tutorialPlaygroundTopic.textContent = selectedPage()?.title || '';
  dom.tutorialPlaygroundTitle.textContent = example.title;
  dom.tutorialPlaygroundCode.value = example.draftSource;
  dom.tutorialPlaygroundInput.value = example.draftStdin;
  draftBaseline = playgroundDraftSnapshot();
  dom.tutorialCompileOutput.textContent = 'Príklad ešte nebol spustený.';
  dom.tutorialCompileMeta.textContent = '';
  dom.tutorialRunOutput.textContent = 'Výstup programu sa zobrazí tu.';
  dom.tutorialRunMeta.textContent = '';
  setPlaygroundOpen(true);
  renderExamples(selectedPage());
  dom.tutorialPlaygroundCode.focus();
}

export function closeTutorialPlayground() {
  window.clearTimeout(draftSaveTimer);
  if (hasUnsavedPlaygroundDraft()) {
    const example = selectedExample();
    const source = dom.tutorialPlaygroundCode.value;
    const stdin = dom.tutorialPlaygroundInput.value;
    void runOperation(() => persistPlaygroundDraft(example, source, stdin));
  }
  setPlaygroundOpen(false);
  selectedExampleId = '';
  renderExamples(selectedPage() || { id: '' });
}

export function isTutorialPlaygroundOpen() {
  return dom.tutorialPlaygroundDock.classList.contains('is-open');
}

export function isTutorialPanelOpen() {
  return dom.tutorialPanel.classList.contains('is-open');
}

export function isTutorialPanelPinned() {
  return panelPinned;
}

export async function openTutorialPanel({ pinned = false, languageId = '', pageId = '' } = {}) {
  panelPinned = pinned;
  setTutorialPanelOpen(true);
  if (!catalogRequest) {
    catalogRequest = runOperation(async () => {
      try {
        const status = await apiRequest('/tutorial/runtime');
        setRuntimeStatus(status);
        await loadLanguages();
      } catch (error) {
        setRuntimeStatus({ available: false, message: error.message || 'Učebnicu sa nepodarilo načítať.' });
        setReaderMessage('Učebnicu sa nepodarilo načítať.');
      } finally {
        catalogRequest = null;
      }
    });
  }
  await catalogRequest;
  if (languageId && languages.some((language) => language.id === languageId)) await selectLanguage(languageId);
  if (pageId && tutorial?.pages.some((page) => page.id === pageId)) await selectPage(pageId);
}

export function closeTutorialPanel({ force = false } = {}) {
  if (!force && hasUnsavedTutorialNoteChanges()) return false;
  if (dom.tutorialPageDialog.open) dom.tutorialPageDialog.close();
  panelPinned = false;
  closeTutorialPlayground();
  setTutorialPanelOpen(false);
  return true;
}

function handleCodeTab(event) {
  if (event.key !== 'Tab') return;
  event.preventDefault();
  const field = event.currentTarget;
  const start = field.selectionStart;
  const end = field.selectionEnd;
  field.setRangeText('  ', start, end, 'end');
  scheduleDraftSave();
}

export function initializeTutorial() {
  dom.tutorialSearch.addEventListener('input', renderTree);
  dom.tutorialPageCreateButton.addEventListener('click', () => void openTutorialPageDialog());
  dom.tutorialRelationshipsButton.addEventListener('click', () => {
    if (selectedPageId) void openRelationships({ targetType: 'tutorial_page', targetId: selectedPageId });
  });
  dom.tutorialPageKind.addEventListener('change', syncTutorialPageForm);
  dom.tutorialPageForm.addEventListener('submit', (event) => void createTutorialPage(event));
  dom.tutorialPageCancelButton.addEventListener('click', () => dom.tutorialPageDialog.close());
  installDialogBackdropClose(dom.tutorialPageDialog, () => dom.tutorialPageDialog.close());
  dom.tutorialNotesInput.addEventListener('input', () => {
    window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'tutorial' } }));
    dom.tutorialNotesStatus.textContent = 'Neuložené zmeny';
  });
  dom.tutorialNotesSave.addEventListener('click', () => void runOperation(saveNote));
  [dom.tutorialPlaygroundCode, dom.tutorialPlaygroundInput].forEach((field) => {
    field.addEventListener('input', scheduleDraftSave);
    field.addEventListener('keydown', handleCodeTab);
  });
  dom.tutorialPlaygroundRun.addEventListener('click', () => void runExample());
  dom.tutorialPlaygroundReset.addEventListener('click', () => {
    const example = selectedExample();
    if (!example) return;
    dom.tutorialPlaygroundCode.value = example.source;
    dom.tutorialPlaygroundInput.value = example.stdin;
    scheduleDraftSave();
  });
  dom.tutorialPlaygroundClose.addEventListener('click', () => void closeTutorialPlayground());
  dom.tutorialPlaygroundFullscreen.addEventListener('click', () => setPlaygroundFullscreen(!dom.tutorialPlaygroundDock.classList.contains('is-fullscreen')));
}
