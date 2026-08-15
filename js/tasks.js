import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
import { dom } from './dom.js';
import { state } from './state.js';
import { flushWorkspaceSync } from './storage.js';
import { updateTopbarVisibility } from './topbar.js';
import { readTagField, refreshTagSuggestions, setTagField } from './tags.js';
import { openRelationships } from './relationships.js';

const statusLabels = {
  open: 'Otvorená',
  in_progress: 'Rozpracovaná',
  done: 'Hotová'
};

const priorityLabels = {
  none: '',
  low: 'Nízka priorita',
  medium: 'Stredná priorita',
  high: 'Vysoká priorita'
};

const targetTypeLabels = {
  library: 'Knižnica',
  element: 'Článok alebo poznámka',
  source: 'Zdroj'
};

let tasks = [];
let selectedTask = null;
let taskStatusFilter = '';
let panelPinned = false;
let taskFormBaseline = '';
let taskOperationCount = 0;
let taskIdleResolvers = [];
let targetSources = null;
let editorTaskMenuOpen = false;

function notifyTasksChanged() {
  window.dispatchEvent(new Event('tasks-changed'));
  void refreshElementTaskLinks();
}

function formatDueDate(value) {
  if (!value) return '';
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'short' }).format(date);
}

function taskFormSnapshot() {
  return JSON.stringify({
    title: dom.taskTitle.value.trim(),
    status: dom.taskStatus.value,
    priority: dom.taskPriority.value,
    dueDate: dom.taskDueDate.value,
    description: dom.taskDescription.value.trim(),
    tags: readTagField(dom.taskTags)
  });
}

function rememberTaskForm() {
  taskFormBaseline = taskFormSnapshot();
}

async function runTaskOperation(operation) {
  taskOperationCount += 1;
  try {
    return await operation();
  } finally {
    taskOperationCount -= 1;
    if (!taskOperationCount) {
      taskIdleResolvers.forEach((resolve) => resolve());
      taskIdleResolvers = [];
    }
  }
}

export function waitForTaskOperations() {
  if (!taskOperationCount) return Promise.resolve();
  return new Promise((resolve) => taskIdleResolvers.push(resolve));
}

export function hasUnsavedTaskChanges() {
  return !dom.taskDetail.hidden && taskFormSnapshot() !== taskFormBaseline;
}

function setEditorTaskMenuOpen(open) {
  editorTaskMenuOpen = open;
  dom.editorTaskMenu.hidden = !open;
  dom.editorTaskToggle.setAttribute('aria-expanded', String(open));
}

export function closeEditorTaskMenu() {
  setEditorTaskMenuOpen(false);
}

export async function refreshElementTaskLinks() {
  const elementId = state.activeLibraryElementId;
  if (!elementId) {
    closeEditorTaskMenu();
    dom.editorTaskLinks.hidden = true;
    dom.editorTaskMenu.replaceChildren();
    return;
  }
  try {
    const result = await apiRequest(`/task-links/element/${encodeURIComponent(elementId)}`);
    closeEditorTaskMenu();
    dom.editorTaskMenu.replaceChildren();
    if (!result.tasks.length) {
      dom.editorTaskLinks.hidden = true;
      return;
    }
    dom.editorTaskToggleLabel.textContent = `Úlohy (${result.tasks.length})`;
    result.tasks.forEach((task) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'editor-source-chip editor-task-chip';
      button.classList.toggle('is-done', task.status === 'done');
      const copy = document.createElement('span');
      copy.className = 'editor-source-chip-copy';
      const title = document.createElement('strong');
      title.textContent = task.title;
      const meta = document.createElement('small');
      meta.textContent = [statusLabels[task.status], priorityLabels[task.priority], task.dueDate ? `do ${formatDueDate(task.dueDate)}` : '']
        .filter(Boolean)
        .join(' · ');
      copy.append(title, meta);
      button.append(createAppIcon(task.status === 'done' ? 'check' : 'list-check', 'editor-source-chip-icon'), copy);
      button.title = 'Otvoriť úlohu';
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('task-open', { detail: { taskId: task.id } }));
      });
      dom.editorTaskMenu.append(button);
    });
    dom.editorTaskLinks.hidden = false;
  } catch {
    closeEditorTaskMenu();
    dom.editorTaskLinks.hidden = true;
  }
}

function setTasksPanelOpen(open) {
  dom.tasksPanel.classList.toggle('is-open', open);
  dom.tasksPanel.setAttribute('aria-hidden', String(!open));
  dom.tasksButton.setAttribute('aria-expanded', String(open));
  updateTopbarVisibility();
}

function setTaskDetailOpen(open) {
  dom.taskDetailDock.classList.toggle('is-open', open);
  dom.taskDetailDock.setAttribute('aria-hidden', String(!open));
  if (open) document.body.dataset.taskDetailOpen = 'true';
  else delete document.body.dataset.taskDetailOpen;
  updateTopbarVisibility();
}

export function isTasksPanelOpen() {
  return dom.tasksPanel.classList.contains('is-open');
}

export function isTaskDetailOpen() {
  return dom.taskDetailDock.classList.contains('is-open');
}

export function isTasksPanelPinned() {
  return panelPinned;
}

async function loadTasks() {
  const suffix = taskStatusFilter ? `?status=${encodeURIComponent(taskStatusFilter)}` : '';
  const result = await apiRequest(`/tasks${suffix}`);
  tasks = result.tasks;
  renderTasksList();
}

function renderTasksList() {
  dom.taskFilterButtons.forEach((button) => {
    const active = button.dataset.taskStatus === taskStatusFilter;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });

  dom.tasksList.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement('p');
    empty.className = 'tasks-empty';
    empty.textContent = taskStatusFilter ? 'V tomto zobrazení zatiaľ nie sú žiadne úlohy.' : 'Zatiaľ nemáš žiadne úlohy.';
    dom.tasksList.append(empty);
    return;
  }

  tasks.forEach((task) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'task-list-item';
    item.classList.toggle('is-done', task.status === 'done');
    item.classList.toggle('is-active', task.id === selectedTask?.id && isTaskDetailOpen());
    item.title = `Otvoriť úlohu ${task.title}`;
    item.append(createAppIcon(task.status === 'done' ? 'check' : 'list-check', 'task-panel-item-icon'));

    const copy = document.createElement('span');
    copy.className = 'task-list-copy';
    const title = document.createElement('strong');
    title.textContent = task.title;
    const meta = document.createElement('small');
    meta.textContent = [
      statusLabels[task.status],
      priorityLabels[task.priority],
      task.dueDate ? `do ${formatDueDate(task.dueDate)}` : '',
      task.linkCount ? `${task.linkCount} väz.` : '',
      (task.tags || []).slice(0, 2).map((tag) => `#${tag}`).join(' ')
    ]
      .filter(Boolean)
      .join(' · ');
    copy.append(title, meta);
    item.append(copy);
    item.addEventListener('click', () => void selectTask(task.id));
    dom.tasksList.append(item);
  });
}

function setTaskFormError(message = '') {
  dom.taskTitle.setCustomValidity(message);
  if (message) dom.taskTitle.reportValidity();
}

function showTaskDetail() {
  dom.taskDetail.hidden = false;
  panelPinned = true;
  setTaskDetailOpen(true);
}

function showTaskList() {
  dom.taskDetail.hidden = true;
  setTaskDetailOpen(false);
  renderTasksList();
}

function taskTargets(type) {
  if (type === 'library') {
    return state.libraries
      .map((library) => ({ id: library.id, label: library.name || 'Knižnica' }))
      .sort((left, right) => left.label.localeCompare(right.label, 'sk'));
  }
  if (type === 'element') {
    return Object.entries(state.libraryElements)
      .flatMap(([libraryId, elements]) => {
        const library = state.libraries.find((item) => item.id === libraryId);
        return elements
          .filter((element) => element.type === 'note' || element.type === 'article')
          .map((element) => ({
            id: element.id,
            label: `${library?.name || 'Knižnica'} / ${element.title || (element.type === 'article' ? 'Nový článok' : 'Nová poznámka')}`
          }));
      })
      .sort((left, right) => left.label.localeCompare(right.label, 'sk'));
  }
  return (targetSources || []).map((source) => ({ id: source.id, label: source.title })).sort((left, right) =>
    left.label.localeCompare(right.label, 'sk')
  );
}

async function renderTaskTargetOptions() {
  const targetType = dom.taskLinkTargetType.value;
  dom.taskLinkTarget.replaceChildren();
  dom.taskLinkAddButton.disabled = !selectedTask;
  if (!selectedTask) return;

  if (targetType === 'source' && targetSources === null) {
    const loading = document.createElement('option');
    loading.textContent = 'Načítavam zdroje...';
    dom.taskLinkTarget.append(loading);
    dom.taskLinkTarget.disabled = true;
    try {
      const result = await apiRequest('/sources');
      targetSources = result.sources;
    } catch {
      targetSources = [];
    }
  }

  const linkedIds = new Set(
    selectedTask.links.filter((link) => link.targetType === targetType).map((link) => link.targetId)
  );
  const targets = taskTargets(targetType).filter((target) => !linkedIds.has(target.id));
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = targets.length ? `Vyber: ${targetTypeLabels[targetType]}` : 'Nie je čo pripojiť';
  dom.taskLinkTarget.append(empty);
  targets.forEach((target) => {
    const option = document.createElement('option');
    option.value = target.id;
    option.textContent = target.label;
    dom.taskLinkTarget.append(option);
  });
  dom.taskLinkTarget.disabled = !targets.length;
  dom.taskLinkAddButton.disabled = !targets.length;
}

function renderTaskLinks() {
  dom.taskLinksList.replaceChildren();
  if (!selectedTask?.links.length) {
    const empty = document.createElement('p');
    empty.className = 'task-links-empty';
    empty.textContent = 'Zatiaľ nie je pripojená k žiadnemu prvku.';
    dom.taskLinksList.append(empty);
    return;
  }

  selectedTask.links.forEach((link) => {
    const row = document.createElement('div');
    row.className = 'task-link-row';
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'task-link-open';
    open.append(createAppIcon(link.targetType === 'source' ? 'book-open' : link.targetType === 'library' ? 'folder' : 'note'));
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = link.title;
    const meta = document.createElement('small');
    meta.textContent = link.subtitle;
    copy.append(title, meta);
    open.append(copy);
    open.title = `Otvoriť: ${link.title}`;
    open.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('task-open-target', { detail: link }));
    });

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.append(createAppIcon('close'));
    remove.title = `Odpojiť ${link.title}`;
    remove.setAttribute('aria-label', `Odpojiť ${link.title}`);
    remove.addEventListener('click', () => void unlinkTask(link.id));
    row.append(open, remove);
    dom.taskLinksList.append(row);
  });
}

function renderTaskDetail() {
  if (!selectedTask) return;
  showTaskDetail();
  dom.taskFormTitle.textContent = selectedTask.title || 'Úloha';
  dom.taskTitle.value = selectedTask.title;
  dom.taskStatus.value = selectedTask.status;
  dom.taskPriority.value = selectedTask.priority;
  dom.taskDueDate.value = selectedTask.dueDate || '';
  dom.taskDescription.value = selectedTask.description || '';
  setTagField(dom.taskTags, dom.taskTagChips, selectedTask.tags || []);
  dom.taskDeleteButton.hidden = false;
  dom.taskRelationshipsButton.hidden = false;
  dom.taskLinksSection.hidden = false;
  renderTaskLinks();
  void renderTaskTargetOptions();
  rememberTaskForm();
}

async function selectTask(taskId) {
  try {
    const result = await apiRequest(`/tasks/${encodeURIComponent(taskId)}`);
    selectedTask = result.task;
    renderTaskDetail();
    renderTasksList();
  } catch {
    selectedTask = null;
    await loadTasks();
  }
}

function startNewTask() {
  selectedTask = null;
  showTaskDetail();
  dom.taskForm.reset();
  setTagField(dom.taskTags, dom.taskTagChips, []);
  dom.taskStatus.value = 'open';
  dom.taskPriority.value = 'none';
  dom.taskFormTitle.textContent = 'Nová úloha';
  dom.taskDeleteButton.hidden = true;
  dom.taskRelationshipsButton.hidden = true;
  dom.taskLinksSection.hidden = true;
  dom.taskLinksList.replaceChildren();
  void renderTaskTargetOptions();
  rememberTaskForm();
  dom.taskTitle.focus();
}

export function discardTaskDraft() {
  if (selectedTask) renderTaskDetail();
  else showTaskList();
}

export async function saveTaskDraft() {
  if (!hasUnsavedTaskChanges()) return true;
  if (!dom.taskForm.reportValidity()) return false;
  try {
    await runTaskOperation(async () => {
      const data = {
        title: dom.taskTitle.value.trim(),
        status: dom.taskStatus.value,
        priority: dom.taskPriority.value,
        dueDate: dom.taskDueDate.value,
        description: dom.taskDescription.value.trim(),
        tags: readTagField(dom.taskTags)
      };
      const result = selectedTask
        ? await apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}`, { method: 'PATCH', body: data })
        : await apiRequest('/tasks', { method: 'POST', body: { ...data, id: crypto.randomUUID() } });
      selectedTask = result.task;
      targetSources = null;
      renderTaskDetail();
      await loadTasks();
      refreshTagSuggestions();
      notifyTasksChanged();
    });
    return true;
  } catch (error) {
    setTaskFormError(error?.message || 'Úlohu sa nepodarilo uložiť.');
    return false;
  }
}

async function addTaskLink() {
  if (!selectedTask || !dom.taskLinkTarget.value) return;
  try {
    await runTaskOperation(async () => {
      if (dom.taskLinkTargetType.value !== 'source') await flushWorkspaceSync();
      const result = await apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}/links`, {
        method: 'POST',
        body: {
          id: crypto.randomUUID(),
          targetType: dom.taskLinkTargetType.value,
          targetId: dom.taskLinkTarget.value
        }
      });
      selectedTask = result.task;
      renderTaskDetail();
      await loadTasks();
      notifyTasksChanged();
    });
  } catch (error) {
    setTaskFormError(error?.message || 'Prepojenie sa nepodarilo vytvoriť.');
  }
}

async function unlinkTask(linkId) {
  if (!selectedTask) return;
  try {
    const result = await runTaskOperation(() =>
      apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}/links/${encodeURIComponent(linkId)}`, { method: 'DELETE' })
    );
    selectedTask = result.task;
    renderTaskDetail();
    await loadTasks();
    notifyTasksChanged();
  } catch (error) {
    setTaskFormError(error?.message || 'Prepojenie sa nepodarilo odstrániť.');
  }
}

async function deleteSelectedTask() {
  if (!selectedTask || !confirm(`Zmazať úlohu "${selectedTask.title}"?`)) return;
  try {
    await runTaskOperation(() => apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}`, { method: 'DELETE' }));
    selectedTask = null;
    showTaskList();
    await loadTasks();
    notifyTasksChanged();
  } catch (error) {
    setTaskFormError(error?.message || 'Úlohu sa nepodarilo zmazať.');
  }
}

export function closeTaskDetail() {
  showTaskList();
}

export function closeTasksPanel({ force = false } = {}) {
  if (panelPinned && !force) return;
  panelPinned = false;
  selectedTask = null;
  dom.taskDetail.hidden = true;
  setTaskDetailOpen(false);
  setTasksPanelOpen(false);
}

export async function openTasksPanel({ taskId = '', pinned = false } = {}) {
  if (pinned) panelPinned = true;
  setTasksPanelOpen(true);
  await loadTasks();
  if (taskId) await selectTask(taskId);
}

export function initializeTasks() {
  dom.taskCreateButton.addEventListener('click', startNewTask);
  dom.taskDetailBack.addEventListener('click', closeTaskDetail);
  dom.taskDeleteButton.addEventListener('click', () => void deleteSelectedTask());
  dom.taskRelationshipsButton.addEventListener('click', () => {
    if (selectedTask) void openRelationships({ targetType: 'task', targetId: selectedTask.id });
  });
  dom.taskForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveTaskDraft();
  });
  dom.taskTitle.addEventListener('input', () => setTaskFormError(''));
  dom.taskFilterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      taskStatusFilter = button.dataset.taskStatus || '';
      void loadTasks();
    });
  });
  dom.taskLinkTargetType.addEventListener('change', () => void renderTaskTargetOptions());
  dom.taskLinkAddButton.addEventListener('click', () => void addTaskLink());
  dom.editorTaskToggle.addEventListener('click', () => setEditorTaskMenuOpen(!editorTaskMenuOpen));
  document.addEventListener('pointerdown', (event) => {
    if (editorTaskMenuOpen && !dom.editorTaskLinks.contains(event.target)) closeEditorTaskMenu();
  });
  window.addEventListener('sources-changed', () => {
    targetSources = null;
  });
}
