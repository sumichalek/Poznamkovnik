import { apiRequest } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';
import { updateTopbarVisibility } from './topbar.js';
import { refreshTutorialPlaygroundResizeHandle } from './tutorial-playground-resize.js';
import { openRelationships } from './relationships.js';
import { downloadTutorialMarkdownArchive } from './markdown-export.js';
import { requestMarkdownImport } from './markdown-import.js';
import { tutorialMarkdownImportPlan, tutorialMarkdownPreview } from './tutorial-markdown-import.js';

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
let practice = null;
let activePractice = false;
let practiceRequestId = 0;

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

function activeRuntimeStatus() {
  const language = activePractice ? 'c' : selectedExample()?.language || tutorial?.language?.code || 'c';
  return runtime.languages?.[language] || runtime;
}

function refreshRuntimeStatus() {
  const currentRuntime = activeRuntimeStatus();
  const applyStatus = (element, { compact = false } = {}) => {
    const message = compact && currentRuntime.available ? 'Skúšobňa pripravená' : currentRuntime.message || '';
    const label = document.createElement('span');
    label.textContent = message;
    element.replaceChildren(createAppIcon('terminal'), label);
    element.title = currentRuntime.message || '';
    element.setAttribute('aria-label', currentRuntime.message || 'Stav skúšobne');
    element.classList.toggle('is-ready', Boolean(currentRuntime.available));
    element.classList.toggle('is-unavailable', !currentRuntime.available);
  };
  applyStatus(dom.tutorialRuntimeStatus, { compact: true });
  applyStatus(dom.tutorialPlaygroundRuntime);
  dom.tutorialPlaygroundRun.disabled = !currentRuntime.available;
}

function setRuntimeStatus(status) {
  runtime = status || { available: false, message: 'Skúšobňa nie je dostupná.' };
  refreshRuntimeStatus();
}

function setReaderMessage(message) {
  dom.tutorialPageContent.replaceChildren();
  const notice = document.createElement('p');
  notice.className = 'tutorial-empty';
  notice.textContent = message;
  dom.tutorialPageContent.append(notice);
  dom.tutorialExamplesSection.hidden = true;
  dom.tutorialPracticeSection.hidden = true;
  dom.tutorialRelationshipsButton.hidden = true;
  dom.tutorialPageProgress.hidden = true;
  dom.tutorialMarkdownImport.disabled = true;
  dom.tutorialMarkdownExport.disabled = true;
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
  practice = null;
  activePractice = false;
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
      button.classList.toggle('is-completed', page.progressStatus === 'completed');
      button.style.setProperty('--tutorial-indent', `${Math.min(depth, 5) * 8}px`);
      button.title = page.summary || page.title;
      button.append(createAppIcon(pageIcon(page)));
      const label = document.createElement('span');
      label.textContent = page.title;
      button.append(label);
      if (page.progressStatus === 'completed') {
        const progress = createAppIcon('check', 'tutorial-page-tree-progress');
        progress.setAttribute('aria-label', 'Prejdené');
        progress.setAttribute('role', 'img');
        button.append(progress);
      }
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

function renderPedagogy(pedagogy) {
  if (!pedagogy || typeof pedagogy !== 'object') return null;
  const hasContext = Boolean(pedagogy.context);
  const hasKeyIdea = Boolean(pedagogy.keyIdea);
  const hasPriorKnowledge = Array.isArray(pedagogy.priorKnowledge) && pedagogy.priorKnowledge.length > 0;
  const hasTransfer = Boolean(pedagogy.transfer);
  if (!hasContext && !hasKeyIdea && !hasPriorKnowledge && !hasTransfer) return null;

  const frame = document.createElement('section');
  frame.className = 'tutorial-lesson-frame';
  const main = document.createElement('div');
  main.className = 'tutorial-lesson-frame-main';

  if (hasContext) {
    const label = document.createElement('span');
    label.className = 'tutorial-lesson-frame-label';
    label.textContent = 'V praxi riešiš';
    const text = document.createElement('p');
    text.textContent = pedagogy.context;
    main.append(label, text);
  }
  if (hasKeyIdea) {
    const idea = document.createElement('div');
    idea.className = 'tutorial-lesson-frame-idea';
    const label = document.createElement('span');
    label.className = 'tutorial-lesson-frame-label';
    label.textContent = 'Kľúčová myšlienka';
    const text = document.createElement('p');
    text.textContent = pedagogy.keyIdea;
    idea.append(label, text);
    main.append(idea);
  }
  if (main.childElementCount) frame.append(main);

  if (hasPriorKnowledge) {
    const prior = document.createElement('aside');
    prior.className = 'tutorial-lesson-frame-prior';
    const heading = document.createElement('h3');
    heading.textContent = 'Nadväzuje na';
    const list = document.createElement('ul');
    pedagogy.priorKnowledge.forEach((item) => {
      const listItem = document.createElement('li');
      listItem.textContent = item;
      list.append(listItem);
    });
    prior.append(heading, list);
    frame.append(prior);
  }

  if (hasTransfer) {
    const transfer = document.createElement('p');
    transfer.className = 'tutorial-lesson-frame-transfer';
    transfer.textContent = pedagogy.transfer;
    frame.append(transfer);
  }
  return frame;
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
  const pedagogy = renderPedagogy(content.pedagogy);
  if (pedagogy) dom.tutorialPageContent.append(pedagogy);
  if (content.goals?.length) {
    const goals = document.createElement('section');
    goals.className = 'tutorial-learning-goals';
    const heading = document.createElement('h3');
    heading.textContent = 'Po tejto lekcii budeš vedieť';
    const list = document.createElement('ul');
    content.goals.forEach((goal) => {
      const item = document.createElement('li');
      item.textContent = goal;
      list.append(item);
    });
    goals.append(heading, list);
    dom.tutorialPageContent.append(goals);
  }
  if (content.blocks?.length) {
    renderContentBlocks(content.blocks);
    renderPageVisualizations(content.visualizationIds);
    return;
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
  renderPageVisualizations(content.visualizationIds);
}

function visualizationModels() {
  return new Map((tutorial?.curriculum?.visualizationModels || []).map((item) => [item.id, item]));
}

function visualizationControl(icon, label, handler) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'tutorial-visualization-control';
  button.title = label;
  button.setAttribute('aria-label', label);
  button.append(createAppIcon(icon));
  button.addEventListener('click', handler);
  return button;
}

function renderVisualization(visualizationId, options = {}) {
  const visualization = visualizationModels().get(visualizationId);
  if (!visualization?.steps?.length) return null;

  let stepIndex = 0;
  const block = document.createElement('section');
  block.className = 'tutorial-visualization';
  const header = document.createElement('header');
  header.className = 'tutorial-visualization-header';
  const headerCopy = document.createElement('div');
  const heading = document.createElement('h3');
  heading.textContent = options.title || visualization.title;
  const summary = document.createElement('p');
  summary.textContent = options.summary || visualization.summary;
  headerCopy.append(heading, summary);
  const position = document.createElement('span');
  position.className = 'tutorial-visualization-position';
  position.setAttribute('aria-live', 'polite');
  header.append(headerCopy, position);

  const surface = document.createElement('div');
  surface.className = 'tutorial-visualization-surface';
  const codePanel = document.createElement('section');
  codePanel.className = 'tutorial-visualization-code';
  const codeTitle = document.createElement('span');
  codeTitle.textContent = 'Kód v tomto kroku';
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  pre.append(code);
  codePanel.append(codeTitle, pre);
  const statePanel = document.createElement('section');
  statePanel.className = 'tutorial-visualization-state';
  surface.append(codePanel, statePanel);

  const explanation = document.createElement('p');
  explanation.className = 'tutorial-visualization-explanation';
  const simplification = document.createElement('p');
  simplification.className = 'tutorial-visualization-simplification';
  simplification.textContent = `Zjednodušenie modelu: ${visualization.simplification}`;

  const controls = document.createElement('div');
  controls.className = 'tutorial-visualization-controls';
  const reset = visualizationControl('rotate-ccw', 'Obnoviť prvý krok', () => updateStep(0));
  const previous = visualizationControl('arrow-left', 'Predchádzajúci krok', () => updateStep(stepIndex - 1));
  const next = visualizationControl('arrow-right', 'Nasledujúci krok', () => updateStep(stepIndex + 1));
  controls.append(reset, previous, next);

  function updateStep(nextIndex) {
    stepIndex = Math.max(0, Math.min(nextIndex, visualization.steps.length - 1));
    const step = visualization.steps[stepIndex];
    position.textContent = `Krok ${stepIndex + 1} z ${visualization.steps.length}`;
    code.textContent = step.code;
    explanation.textContent = `${step.title}: ${step.explanation}`;
    statePanel.replaceChildren();
    (step.groups || []).forEach((group) => {
      const groupElement = document.createElement('section');
      groupElement.className = 'tutorial-visualization-state-group';
      const groupHeading = document.createElement('h4');
      groupHeading.textContent = group.label;
      const table = document.createElement('table');
      const head = document.createElement('thead');
      const headRow = document.createElement('tr');
      const nameHeading = document.createElement('th');
      nameHeading.scope = 'col';
      nameHeading.textContent = 'Meno';
      const valueHeading = document.createElement('th');
      valueHeading.scope = 'col';
      valueHeading.textContent = 'Stav alebo hodnota';
      headRow.append(nameHeading, valueHeading);
      head.append(headRow);
      const body = document.createElement('tbody');
      (group.rows || []).forEach(([name, value]) => {
        const row = document.createElement('tr');
        const nameCell = document.createElement('th');
        nameCell.scope = 'row';
        nameCell.textContent = name;
        const valueCell = document.createElement('td');
        valueCell.textContent = value;
        row.append(nameCell, valueCell);
        body.append(row);
      });
      table.append(head, body);
      groupElement.append(groupHeading, table);
      statePanel.append(groupElement);
    });
    reset.disabled = stepIndex === 0;
    previous.disabled = stepIndex === 0;
    next.disabled = stepIndex === visualization.steps.length - 1;
  }

  block.append(header, surface, explanation, simplification, controls);
  updateStep(0);
  return block;
}

function renderPageVisualizations(visualizationIds) {
  if (!Array.isArray(visualizationIds)) return;
  visualizationIds.forEach((visualizationId) => {
    const visualization = renderVisualization(visualizationId);
    if (visualization) dom.tutorialPageContent.append(visualization);
  });
}

function renderContentBlocks(blocks) {
  const visualizations = new Map((tutorial?.curriculum?.visualizations || []).map((item) => [item.id, item]));
  let section = null;

  function currentSection() {
    if (section) return section;
    section = document.createElement('section');
    section.className = 'tutorial-content-section';
    dom.tutorialPageContent.append(section);
    return section;
  }

  blocks.forEach((item) => {
    if (item.type === 'heading') {
      section = document.createElement('section');
      section.className = 'tutorial-content-section';
      const heading = document.createElement('h3');
      heading.className = 'tutorial-block-heading';
      heading.textContent = item.text;
      section.append(heading);
      dom.tutorialPageContent.append(section);
      return;
    }
    if (item.type === 'paragraph') {
      const paragraph = document.createElement('p');
      paragraph.className = 'tutorial-block-paragraph';
      paragraph.textContent = item.text;
      currentSection().append(paragraph);
      return;
    }
    if (item.type === 'list') {
      const list = document.createElement('ul');
      list.className = 'tutorial-block-list';
      item.items.forEach((text) => {
        const listItem = document.createElement('li');
        listItem.textContent = text;
        list.append(listItem);
      });
      currentSection().append(list);
      return;
    }
    if (item.type === 'callout') {
      const callout = document.createElement('p');
      callout.className = `tutorial-callout is-${item.tone || 'info'}`;
      callout.textContent = item.text;
      currentSection().append(callout);
      return;
    }
    if (item.type === 'code') {
      const block = document.createElement('section');
      block.className = 'tutorial-code-block';
      if (item.title || item.language) {
        const header = document.createElement('header');
        const title = document.createElement('span');
        title.textContent = item.title || 'Príklad';
        const language = document.createElement('small');
        language.textContent = item.language;
        header.append(title, language);
        block.append(header);
      }
      const pre = document.createElement('pre');
      const code = document.createElement('code');
      code.textContent = item.source;
      pre.append(code);
      block.append(pre);
      currentSection().append(block);
      return;
    }
    if (item.type === 'visualization') {
      const interactiveVisualization = renderVisualization(item.visualizationId, item);
      if (interactiveVisualization) {
        currentSection().append(interactiveVisualization);
        return;
      }
      const visualization = visualizations.get(item.visualizationId);
      if (!visualization) return;
      const block = document.createElement('aside');
      block.className = 'tutorial-visualization-note';
      const heading = document.createElement('h3');
      heading.textContent = item.title || visualization.title;
      const description = document.createElement('p');
      description.textContent = item.summary || visualization.purpose;
      block.append(heading, description);
      currentSection().append(block);
      return;
    }
    if (item.type === 'checkpoint') {
      const block = document.createElement('aside');
      block.className = 'tutorial-checkpoint';
      const heading = document.createElement('h3');
      heading.textContent = 'Over si porozumenie';
      const prompt = document.createElement('p');
      prompt.textContent = item.prompt;
      block.append(heading, prompt);
      currentSection().append(block);
    }
  });
}

function checkpointAttemptLabel(checkpoint) {
  if (!checkpoint?.attemptCount) return 'Ešte bez odpovede';
  const suffix = checkpoint.attemptCount === 1
    ? 'pokus'
    : checkpoint.attemptCount >= 2 && checkpoint.attemptCount <= 4
      ? 'pokusy'
      : 'pokusov';
  const attempts = `${checkpoint.attemptCount} ${suffix}`;
  return checkpoint.isCorrect ? `Správne, ${attempts}` : `Zatiaľ nie, ${attempts}`;
}

function createCheckpointBlock(page) {
  const checkpoint = page.checkpoint;
  if (!checkpoint) return null;
  const block = document.createElement('section');
  block.className = 'tutorial-knowledge-check';
  block.classList.toggle('is-correct', Boolean(checkpoint.isCorrect));
  const header = document.createElement('header');
  const heading = document.createElement('h3');
  heading.textContent = 'Over si porozumenie';
  const meta = document.createElement('span');
  meta.className = 'tutorial-knowledge-check-meta';
  meta.textContent = checkpointAttemptLabel(checkpoint);
  header.append(heading, meta);
  const prompt = document.createElement('p');
  prompt.className = 'tutorial-knowledge-check-prompt';
  prompt.textContent = checkpoint.prompt;
  const choices = document.createElement('div');
  choices.className = 'tutorial-knowledge-check-options';
  choices.setAttribute('role', 'group');
  choices.setAttribute('aria-label', 'Možnosti odpovede');
  const feedback = document.createElement('p');
  feedback.className = 'tutorial-knowledge-check-feedback';
  feedback.setAttribute('aria-live', 'polite');
  feedback.textContent = checkpoint.feedback || (
    checkpoint.attemptCount
      ? checkpoint.isCorrect
        ? 'Naposledy zvolená odpoveď bola správna.'
        : 'Naposledy zvolená odpoveď nebola správna. Skús to ešte raz.'
      : ''
  );
  feedback.hidden = !feedback.textContent;

  checkpoint.options.forEach((option) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tutorial-knowledge-check-option';
    const isLastChoice = checkpoint.lastOptionId === option.id;
    button.classList.toggle('is-selected', isLastChoice);
    button.classList.toggle('is-correct', isLastChoice && Boolean(checkpoint.isCorrect));
    button.setAttribute('aria-pressed', String(isLastChoice));
    button.textContent = option.text;
    button.addEventListener('click', () => void answerCheckpoint(page, option.id, block));
    choices.append(button);
  });
  block.append(header, prompt, choices, feedback);
  return block;
}

async function answerCheckpoint(page, optionId, block) {
  if (!page?.checkpoint || block.classList.contains('is-busy')) return;
  block.classList.add('is-busy');
  block.querySelectorAll('button').forEach((button) => { button.disabled = true; });
  try {
    const result = await runOperation(() => apiRequest(
      `/tutorial/pages/${encodeURIComponent(page.id)}/checkpoint`,
      { method: 'POST', body: { optionId } }
    ));
    Object.assign(page.checkpoint, result.checkpoint, { feedback: result.checkpoint.feedback });
    const replacement = createCheckpointBlock(page);
    if (replacement) block.replaceWith(replacement);
  } catch (error) {
    block.classList.remove('is-busy');
    block.querySelectorAll('button').forEach((button) => { button.disabled = false; });
    const feedback = block.querySelector('.tutorial-knowledge-check-feedback');
    if (feedback) {
      feedback.textContent = error?.message || 'Odpoveď sa nepodarilo vyhodnotiť.';
      feedback.hidden = false;
    }
  }
}

function renderCheckpoint(page) {
  const block = createCheckpointBlock(page);
  if (block) dom.tutorialPageContent.append(block);
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

function renderPractice(page) {
  const topic = page.content?.exerciseTopic || '';
  const available = Boolean(topic);
  dom.tutorialPracticeSection.hidden = !available;
  if (!available) return;

  const currentPractice = practice?.pageId === page.id ? practice : null;
  dom.tutorialPracticeGenerate.disabled = activePractice && isTutorialPlaygroundOpen();
  const generateLabel = currentPractice ? 'Pripraviť ďalší variant' : 'Pripraviť cvičenie';
  dom.tutorialPracticeGenerate.title = generateLabel;
  dom.tutorialPracticeGenerate.setAttribute('aria-label', generateLabel);
  dom.tutorialPracticeOpen.disabled = !currentPractice;
  dom.tutorialPracticeContent.hidden = !currentPractice;
  dom.tutorialPracticeHints.replaceChildren();
  if (!currentPractice) {
    dom.tutorialPracticeStatus.textContent = 'Priprav si vlastný variant zadania.';
    dom.tutorialPracticeDescription.textContent = '';
    dom.tutorialPracticeInput.textContent = '';
    return;
  }
  dom.tutorialPracticeStatus.textContent = currentPractice.title;
  dom.tutorialPracticeDescription.textContent = currentPractice.description;
  (currentPractice.hints || []).forEach((hint) => {
    const item = document.createElement('li');
    item.textContent = hint;
    dom.tutorialPracticeHints.append(item);
  });
  dom.tutorialPracticeInput.textContent = currentPractice.stdin || '(bez vstupu)';
}

async function loadPractice({ nextVariant = false } = {}) {
  const page = selectedPage();
  if (!page?.content?.exerciseTopic || dom.tutorialPracticeGenerate.disabled) return;
  const previous = practice?.pageId === page.id ? practice : null;
  const variant = nextVariant && previous ? previous.variant + 1 : previous?.variant || 0;
  const requestId = ++practiceRequestId;
  dom.tutorialPracticeGenerate.disabled = true;
  dom.tutorialPracticeStatus.textContent = 'Pripravujem zadanie...';
  try {
    const result = await runOperation(() => apiRequest(
      `/tutorial/pages/${encodeURIComponent(page.id)}/practice?variant=${encodeURIComponent(variant)}`
    ));
    if (requestId !== practiceRequestId || selectedPageId !== page.id) return;
    practice = result.practice;
    renderPractice(page);
  } catch (error) {
    if (requestId !== practiceRequestId || selectedPageId !== page.id) return;
    practice = null;
    dom.tutorialPracticeStatus.textContent = error?.message || 'Cvičenie sa nepodarilo pripraviť.';
    dom.tutorialPracticeOpen.disabled = true;
    dom.tutorialPracticeContent.hidden = true;
  } finally {
    if (requestId === practiceRequestId && selectedPageId === page.id) {
      dom.tutorialPracticeGenerate.disabled = false;
    }
  }
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

function renderPageProgress(page) {
  const completed = page.progressStatus === 'completed';
  dom.tutorialPageProgress.hidden = false;
  dom.tutorialPageProgress.classList.toggle('is-completed', completed);
  dom.tutorialPageProgress.setAttribute('aria-pressed', String(completed));
  const label = completed ? 'Označiť tému ako neprejdenú' : 'Označiť tému ako prejdenú';
  dom.tutorialPageProgress.title = label;
  dom.tutorialPageProgress.setAttribute('aria-label', label);
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
  renderPageProgress(page);
  dom.tutorialMarkdownImport.disabled = false;
  dom.tutorialMarkdownExport.disabled = false;
  dom.tutorialNotesInput.value = page.note || '';
  noteBaseline = dom.tutorialNotesInput.value;
  dom.tutorialNotesStatus.textContent = page.noteUpdatedAt ? 'Uložené' : '';
  renderContent(page);
  renderCheckpoint(page);
  renderExamples(page);
  renderPractice(page);
}

function renderTutorial() {
  renderTree();
  renderPage();
  refreshRuntimeStatus();
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
  return Boolean(selectedExample()) && isTutorialPlaygroundOpen() && playgroundDraftSnapshot() !== draftBaseline;
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

async function toggleTutorialPageProgress() {
  const page = selectedPage();
  if (!page || dom.tutorialPageProgress.disabled) return;
  const status = page.progressStatus === 'completed' ? 'not_started' : 'completed';
  dom.tutorialPageProgress.disabled = true;
  try {
    const result = await runOperation(() => apiRequest(`/tutorial/pages/${encodeURIComponent(page.id)}/progress`, {
      method: 'PUT',
      body: { status }
    }));
    page.progressStatus = result.progress.status;
    page.progressUpdatedAt = result.progress.updatedAt;
    renderTree();
    renderPageProgress(page);
  } catch (error) {
    window.alert(error?.message || 'Stav témy sa nepodarilo uložiť.');
  } finally {
    dom.tutorialPageProgress.disabled = false;
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
    dom.tutorialRunMeta.textContent = result.evaluation?.message || '';
    return;
  }
  const output = [execution.stdout, execution.stderr].filter(Boolean).join(execution.stdout && execution.stderr ? '\n' : '');
  dom.tutorialRunOutput.textContent = output || 'Program nevypísal žiadny výstup.';
  const runtimeMeta = execution.timedOut
    ? 'Čas behu vypršal'
    : execution.outputLimited
      ? 'Výstup bol skrátený'
      : `${execution.durationMs} ms · kód ${execution.exitCode}`;
  dom.tutorialRunMeta.textContent = result.evaluation?.message
    ? `${runtimeMeta} · ${result.evaluation.message}`
    : runtimeMeta;
}

async function runExample() {
  const example = selectedExample();
  if ((!example && !activePractice) || !activeRuntimeStatus().available) return;
  if (!(await savePlaygroundDraft())) return;
  dom.tutorialPlaygroundRun.disabled = true;
  dom.tutorialCompileMeta.textContent = 'Prekladám...';
  dom.tutorialRunMeta.textContent = '';
  dom.tutorialCompileOutput.textContent = '';
  dom.tutorialRunOutput.textContent = '';
  try {
    const result = activePractice
      ? await runOperation(() => apiRequest('/tutorial/practice/run', {
        method: 'POST',
        body: {
          pageId: practice?.pageId || selectedPageId,
          variant: practice?.variant || 0,
          source: dom.tutorialPlaygroundCode.value,
          stdin: dom.tutorialPlaygroundInput.value
        }
      }))
      : await runOperation(() => apiRequest(`/tutorial/examples/${encodeURIComponent(example.id)}/run`, {
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
    dom.tutorialPlaygroundRun.disabled = !activeRuntimeStatus().available;
  }
}

async function openExample(exampleId) {
  if (!(await saveTutorialChanges())) return;
  const example = tutorial?.examples.find((item) => item.id === exampleId);
  if (!example) return;
  activePractice = false;
  refreshRuntimeStatus();
  selectedExampleId = example.id;
  dom.tutorialPlaygroundOpenDevelopment.disabled = false;
  if (selectedPage()) renderPractice(selectedPage());
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

async function openPractice() {
  const page = selectedPage();
  if (!page?.content?.exerciseTopic) return;
  if (!practice || practice.pageId !== page.id) await loadPractice();
  if (!practice || practice.pageId !== page.id || !(await saveTutorialChanges())) return;
  activePractice = true;
  refreshRuntimeStatus();
  selectedExampleId = '';
  dom.tutorialPlaygroundTopic.textContent = page.title;
  dom.tutorialPlaygroundTitle.textContent = practice.title;
  dom.tutorialPlaygroundCode.value = practice.starterSource;
  dom.tutorialPlaygroundInput.value = practice.stdin;
  draftBaseline = playgroundDraftSnapshot();
  dom.tutorialCompileOutput.textContent = 'Cvičenie ešte nebolo skontrolované.';
  dom.tutorialCompileMeta.textContent = '';
  dom.tutorialRunOutput.textContent = 'Výstup programu sa zobrazí tu.';
  dom.tutorialRunMeta.textContent = '';
  dom.tutorialPlaygroundOpenDevelopment.disabled = true;
  setPlaygroundOpen(true);
  renderExamples(page);
  renderPractice(page);
  dom.tutorialPlaygroundCode.focus();
}

function openDevelopmentProject(projectId, standardInput) {
  return new Promise((resolve) => {
    window.dispatchEvent(new CustomEvent('development-project-created', {
      detail: { projectId, standardInput, showTutorialGuide: true, resolve }
    }));
  });
}

async function openExampleInDevelopment() {
  const example = selectedExample();
  if (!example || dom.tutorialPlaygroundOpenDevelopment.disabled) return;
  if (!(await saveTutorialChanges())) return;
  const source = dom.tutorialPlaygroundCode.value;
  const standardInput = dom.tutorialPlaygroundInput.value;
  const language = tutorial?.language?.code || 'c';
  const tutorialLink = {
    languageId: tutorial?.language?.id || '',
    pageId: selectedPageId,
    exampleId: example.id,
  };
  dom.tutorialPlaygroundOpenDevelopment.disabled = true;
  try {
    const search = new URLSearchParams(tutorialLink);
    const linked = await runOperation(() => apiRequest(`/development/tutorial-project?${search}`));
    const projectId = linked.project?.id || (await runOperation(() => apiRequest('/development/projects', {
      method: 'POST',
      body: {
        title: `Príklad: ${example.title}`,
        language,
        kind: 'program',
        buildProfile: 'debug',
        templateId: 'hello',
        entryContent: source,
        tutorialLink,
      }
    }))).project.id;
    const opened = await openDevelopmentProject(projectId, standardInput);
    if (!opened) dom.tutorialPlaygroundRuntime.textContent = 'Projekt je pripravený vo Vývoji.';
  } catch (error) {
    dom.tutorialPlaygroundRuntime.textContent = error.message || 'Príklad sa nepodarilo otvoriť vo Vývoji.';
  } finally {
    dom.tutorialPlaygroundOpenDevelopment.disabled = false;
  }
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
  activePractice = false;
  refreshRuntimeStatus();
  selectedExampleId = '';
  renderExamples(selectedPage() || { id: '' });
  if (selectedPage()) renderPractice(selectedPage());
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

export async function openTutorialPanel({ pinned = false, languageId = '', pageId = '', exampleId = '' } = {}) {
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
  const example = tutorial?.examples.find((item) => item.id === exampleId);
  if (example?.pageId === selectedPageId) await openExample(example.id);
}

export function closeTutorialPanel({ force = false } = {}) {
  if (!force && hasUnsavedTutorialNoteChanges()) return false;
  if (dom.tutorialPageDialog.open) dom.tutorialPageDialog.close();
  panelPinned = false;
  closeTutorialPlayground();
  setTutorialPanelOpen(false);
  return true;
}

async function exportTutorialMarkdown() {
  if (!tutorial || !(await saveTutorialChanges())) return;
  dom.tutorialMarkdownExport.disabled = true;
  try {
    await runOperation(() => downloadTutorialMarkdownArchive(tutorial));
  } catch (error) {
    window.alert(error?.message || 'Učebnicu sa nepodarilo vyexportovať do Markdownu.');
  } finally {
    dom.tutorialMarkdownExport.disabled = false;
  }
}

async function importTutorialMarkdown() {
  if (!tutorial || !(await saveTutorialChanges())) return;
  const languageId = selectedLanguageId;
  const languageTitle = tutorial.language?.title || 'učebnice';
  requestMarkdownImport({
    libraryName: languageTitle,
    destinationLabel: `učebnice „${languageTitle}“`,
    confirmLabel: 'Pridať do učebnice',
    previewAdapter: tutorialMarkdownPreview,
    onConfirm: async (preview) => {
      const plan = tutorialMarkdownImportPlan(preview);
      if (!plan.pages.length) throw new Error('Nenašli sa žiadne časti vhodné na import do učebnice.');
      const idsByKey = new Map(plan.pages.map((page) => [page.key, crypto.randomUUID()]));
      const pages = plan.pages.map((page) => ({
        id: idsByKey.get(page.key),
        parentId: page.parentKey ? idsByKey.get(page.parentKey) || '' : '',
        kind: page.kind,
        title: page.title,
        summary: page.summary,
        content: page.content,
        note: page.notes
      }));
      if (new Blob([JSON.stringify({ pages })]).size > 2_000_000) {
        throw new Error('Obsah importu učebnice je väčší než 2 MB. Rozdeľ ho na menšie archívy.');
      }
      const result = await runOperation(() => apiRequest(
        `/tutorial/languages/${encodeURIComponent(languageId)}/import`,
        { method: 'POST', body: { pages } }
      ));
      selectedPageId = result.pages?.at(-1)?.id || selectedPageId;
      selectedExampleId = '';
      closeTutorialPlayground();
      await loadLanguage(languageId);
    }
  });
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
  dom.tutorialMarkdownImport.addEventListener('click', () => void importTutorialMarkdown());
  dom.tutorialMarkdownExport.addEventListener('click', () => void exportTutorialMarkdown());
  dom.tutorialPageProgress.addEventListener('click', () => void toggleTutorialPageProgress());
  dom.tutorialPracticeGenerate.addEventListener('click', () => void loadPractice({ nextVariant: true }));
  dom.tutorialPracticeOpen.addEventListener('click', () => void openPractice());
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
  dom.tutorialPlaygroundOpenDevelopment.addEventListener('click', () => void openExampleInDevelopment());
  dom.tutorialPlaygroundReset.addEventListener('click', () => {
    const example = selectedExample();
    if (!example && !activePractice) return;
    dom.tutorialPlaygroundCode.value = activePractice ? practice?.starterSource || '' : example.source;
    dom.tutorialPlaygroundInput.value = activePractice ? practice?.stdin || '' : example.stdin;
    scheduleDraftSave();
  });
  dom.tutorialPlaygroundClose.addEventListener('click', () => void closeTutorialPlayground());
  dom.tutorialPlaygroundFullscreen.addEventListener('click', () => setPlaygroundFullscreen(!dom.tutorialPlaygroundDock.classList.contains('is-fullscreen')));
}
