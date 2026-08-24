import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
import { dom } from './dom.js';
import { state } from './state.js';
import { flushWorkspaceSync } from './storage.js';
import { updateTopbarVisibility } from './topbar.js';
import { readTagField, refreshTagSuggestions, setTagField } from './tags.js';
import { openRelationships } from './relationships.js';
import { downloadTaskMarkdown, downloadTaskPackage } from './markdown-export.js';
import { prepareTaskMarkdownImport, requestMarkdownImport } from './markdown-import.js';
import { installDialogBackdropClose } from './dialogs.js';
import {
  copyImportedSources,
  importedSourceAction,
  importedSourceTitle,
  resolvedImportedSourceId
} from './imported-sources.js';

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
let taskLists = [];
let activeTaskListId = '';
let draftTaskListIds = [];
let editingTaskListId = '';
let panelPinned = false;
let taskFormBaseline = '';
let taskOperationCount = 0;
let taskIdleResolvers = [];
let targetSources = null;
let editorTaskMenuOpen = false;
let taskExportTargetId = '';

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
    tags: readTagField(dom.taskTags),
    listIds: taskMembershipListIds()
  });
}

function taskExportSnapshot() {
  if (!selectedTask) return null;
  return {
    ...selectedTask,
    title: dom.taskTitle.value.trim(),
    status: dom.taskStatus.value,
    priority: dom.taskPriority.value,
    dueDate: dom.taskDueDate.value,
    description: dom.taskDescription.value.trim(),
    tags: readTagField(dom.taskTags)
  };
}

function closeTaskExportDialog() {
  if (dom.taskExportDialog.open) dom.taskExportDialog.close();
  else taskExportTargetId = '';
}

function setTaskExportBusy(busy) {
  dom.taskPackageExport.disabled = busy;
  dom.taskPortableMarkdownExport.disabled = busy;
  dom.taskExportCancel.disabled = busy;
}

function openTaskExportDialog() {
  const task = taskExportSnapshot();
  if (!task?.id) return;
  taskExportTargetId = task.id;
  dom.taskExportDescription.textContent = `Úloha „${task.title || 'Nová úloha'}“ sa vyexportuje až po zvolení formátu.`;
  if (!dom.taskExportDialog.open) dom.taskExportDialog.showModal();
}

async function exportTask(format) {
  const task = taskExportSnapshot();
  if (!task?.id || task.id !== taskExportTargetId) {
    closeTaskExportDialog();
    return;
  }
  setTaskExportBusy(true);
  try {
    if (format === 'package') await downloadTaskPackage(task);
    else await downloadTaskMarkdown(task);
    closeTaskExportDialog();
  } catch (error) {
    window.alert(error?.message || 'Úlohu sa nepodarilo vyexportovať.');
  } finally {
    setTaskExportBusy(false);
  }
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
  const params = new URLSearchParams();
  if (taskStatusFilter) params.set('status', taskStatusFilter);
  if (activeTaskListId) params.set('list', activeTaskListId);
  const suffix = params.size ? `?${params}` : '';
  const result = await apiRequest(`/tasks${suffix}`);
  tasks = result.tasks;
  renderTasksList();
}

async function loadTaskLists() {
  const result = await apiRequest('/task-lists');
  taskLists = result.lists;
  if (activeTaskListId && !taskLists.some((taskList) => taskList.id === activeTaskListId)) {
    activeTaskListId = '';
  }
  renderTaskListTree();
  renderTaskListMemberships();
}

function taskListById(listId) {
  return taskLists.find((taskList) => taskList.id === listId) || null;
}

function taskListChildren(parentId = '') {
  return taskLists
    .filter((taskList) => (taskList.parentId || '') === parentId)
    .sort((left, right) => left.title.localeCompare(right.title, 'sk'));
}

function taskListPath(taskList) {
  const parts = [];
  const visited = new Set();
  let current = taskList;
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    parts.unshift(current.title);
    current = taskListById(current.parentId);
  }
  return parts;
}

function taskListLabel(taskList) {
  return taskListPath(taskList).join(' / ');
}

function taskMembershipListIds() {
  if (selectedTask) return (selectedTask.lists || []).map((taskList) => taskList.id).sort();
  return [...draftTaskListIds].sort();
}

function isTaskListDescendant(candidateId, ancestorId) {
  const visited = new Set();
  let current = taskListById(candidateId);
  while (current && current.parentId && !visited.has(current.id)) {
    visited.add(current.id);
    if (current.parentId === ancestorId) return true;
    current = taskListById(current.parentId);
  }
  return false;
}

function renderTaskListTree() {
  dom.taskListTree.replaceChildren();

  const allRow = document.createElement('div');
  allRow.className = 'task-list-tree-row task-list-tree-all';
  const allButton = document.createElement('button');
  allButton.type = 'button';
  allButton.className = 'task-list-tree-select';
  allButton.classList.toggle('is-active', !activeTaskListId);
  allButton.setAttribute('aria-current', !activeTaskListId ? 'true' : 'false');
  allButton.append(createAppIcon('list-check', 'task-list-tree-icon'));
  const allCopy = document.createElement('span');
  allCopy.textContent = 'Všetky úlohy';
  allButton.append(allCopy);
  allButton.addEventListener('click', () => void selectTaskList(''));
  allRow.append(allButton);
  dom.taskListTree.append(allRow);

  const appendChildren = (parentId, depth) => {
    taskListChildren(parentId).forEach((taskList) => {
      const row = document.createElement('div');
      row.className = 'task-list-tree-row';
      row.style.setProperty('--task-list-level', String(depth));

      const select = document.createElement('button');
      select.type = 'button';
      select.className = 'task-list-tree-select';
      select.classList.toggle('is-active', taskList.id === activeTaskListId);
      select.setAttribute('aria-current', String(taskList.id === activeTaskListId));
      select.title = `Zobraziť úlohy v zozname ${taskListLabel(taskList)}`;
      select.append(createAppIcon('folder', 'task-list-tree-icon'));
      const copy = document.createElement('span');
      copy.className = 'task-list-tree-copy';
      const title = document.createElement('strong');
      title.textContent = taskList.title;
      const count = document.createElement('small');
      count.textContent = `${taskList.taskCount || 0} úloh`;
      copy.append(title, count);
      select.append(copy);
      select.addEventListener('click', () => void selectTaskList(taskList.id));

      const actions = document.createElement('span');
      actions.className = 'task-list-tree-actions';
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'task-list-tree-action';
      edit.title = `Upraviť zoznam ${taskList.title}`;
      edit.setAttribute('aria-label', edit.title);
      edit.append(createAppIcon('pencil'));
      edit.addEventListener('click', (event) => {
        event.stopPropagation();
        openTaskListDialog(taskList);
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'task-list-tree-action danger';
      remove.title = `Zmazať zoznam ${taskList.title}`;
      remove.setAttribute('aria-label', remove.title);
      remove.append(createAppIcon('trash'));
      remove.addEventListener('click', (event) => {
        event.stopPropagation();
        void deleteTaskList(taskList);
      });
      actions.append(edit, remove);
      row.append(select, actions);
      dom.taskListTree.append(row);
      appendChildren(taskList.id, depth + 1);
    });
  };

  appendChildren('', 0);
}

async function selectTaskList(listId) {
  activeTaskListId = listId;
  renderTaskListTree();
  await loadTasks();
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
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'tasks' } }));
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

function renderTaskListMemberships() {
  if (dom.taskDetail.hidden) return;
  dom.taskListsSection.hidden = false;
  dom.taskListMemberships.replaceChildren();

  const assignedIds = new Set(taskMembershipListIds());
  const assignedLists = taskLists
    .filter((taskList) => assignedIds.has(taskList.id))
    .sort((left, right) => taskListLabel(left).localeCompare(taskListLabel(right), 'sk'));
  const availableLists = taskLists
    .filter((taskList) => !assignedIds.has(taskList.id))
    .sort((left, right) => taskListLabel(left).localeCompare(taskListLabel(right), 'sk'));

  dom.taskListMembershipSelect.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = availableLists.length ? 'Vyber zoznam' : 'Nie je ďalší zoznam';
  dom.taskListMembershipSelect.append(placeholder);
  availableLists.forEach((taskList) => {
    const option = document.createElement('option');
    option.value = taskList.id;
    option.textContent = taskListLabel(taskList);
    dom.taskListMembershipSelect.append(option);
  });
  dom.taskListMembershipSelect.disabled = !availableLists.length;
  dom.taskListMembershipAdd.disabled = !availableLists.length;

  if (!assignedLists.length) {
    const empty = document.createElement('p');
    empty.className = 'task-links-empty';
    empty.textContent = selectedTask
      ? 'Táto úloha zatiaľ nie je zaradená v žiadnom zozname.'
      : 'Po uložení bude úloha zaradená do zvolených zoznamov.';
    dom.taskListMemberships.append(empty);
    return;
  }

  assignedLists.forEach((taskList) => {
    const row = document.createElement('div');
    row.className = 'task-link-row task-list-membership-row';
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'task-link-open';
    open.append(createAppIcon('folder'));
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = taskList.title;
    const meta = document.createElement('small');
    meta.textContent = taskListPath(taskList).slice(0, -1).join(' / ') || 'Hlavný zoznam';
    copy.append(title, meta);
    open.append(copy);
    open.title = `Zobraziť zoznam ${taskListLabel(taskList)}`;
    open.addEventListener('click', () => void selectTaskList(taskList.id));

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.append(createAppIcon('close'));
    remove.title = `Vyradiť zo zoznamu ${taskListLabel(taskList)}`;
    remove.setAttribute('aria-label', remove.title);
    remove.addEventListener('click', () => void removeTaskFromList(taskList.id));
    row.append(open, remove);
    dom.taskListMemberships.append(row);
  });
}

async function addTaskToList() {
  const listId = dom.taskListMembershipSelect.value;
  if (!listId) return;
  try {
    if (!selectedTask) {
      draftTaskListIds = [...new Set([...draftTaskListIds, listId])];
      renderTaskListMemberships();
      return;
    }
    const result = await runTaskOperation(() =>
      apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}/lists/${encodeURIComponent(listId)}`, { method: 'PUT' })
    );
    selectedTask = result.task;
    renderTaskDetail();
    await loadTaskLists();
    await loadTasks();
    notifyTasksChanged();
  } catch (error) {
    setTaskFormError(error?.message || 'Úlohu sa nepodarilo zaradiť do zoznamu.');
  }
}

async function removeTaskFromList(listId) {
  try {
    if (!selectedTask) {
      draftTaskListIds = draftTaskListIds.filter((itemId) => itemId !== listId);
      renderTaskListMemberships();
      return;
    }
    const result = await runTaskOperation(() =>
      apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}/lists/${encodeURIComponent(listId)}`, { method: 'DELETE' })
    );
    selectedTask = result.task;
    renderTaskDetail();
    await loadTaskLists();
    await loadTasks();
    notifyTasksChanged();
  } catch (error) {
    setTaskFormError(error?.message || 'Úlohu sa nepodarilo vyradiť zo zoznamu.');
  }
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
  dom.taskMarkdownExport.hidden = false;
  dom.taskListsSection.hidden = false;
  dom.taskLinksSection.hidden = false;
  renderTaskListMemberships();
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
  draftTaskListIds = activeTaskListId ? [activeTaskListId] : [];
  showTaskDetail();
  dom.taskForm.reset();
  setTagField(dom.taskTags, dom.taskTagChips, []);
  dom.taskStatus.value = 'open';
  dom.taskPriority.value = 'none';
  dom.taskFormTitle.textContent = 'Nová úloha';
  dom.taskDeleteButton.hidden = true;
  dom.taskRelationshipsButton.hidden = true;
  dom.taskMarkdownExport.hidden = true;
  dom.taskListsSection.hidden = false;
  dom.taskLinksSection.hidden = true;
  dom.taskLinksList.replaceChildren();
  renderTaskListMemberships();
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
        : await apiRequest('/tasks', {
          method: 'POST',
          body: { ...data, id: crypto.randomUUID(), listIds: draftTaskListIds }
        });
      selectedTask = result.task;
      draftTaskListIds = [];
      targetSources = null;
      renderTaskDetail();
      await loadTaskLists();
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
    await loadTaskLists();
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
    await loadTaskLists();
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
  draftTaskListIds = [];
  dom.taskDetail.hidden = true;
  setTaskDetailOpen(false);
  setTasksPanelOpen(false);
}

export async function openTasksPanel({ taskId = '', pinned = false } = {}) {
  if (pinned) panelPinned = true;
  setTasksPanelOpen(true);
  await loadTaskLists();
  await loadTasks();
  if (taskId) await selectTask(taskId);
}

function importedTaskPreview(preview) {
  return {
    summary: '1 úloha',
    items: [{
      type: 'Úloha',
      title: preview.task.title,
      path: preview.sourceManifest ? 'Prenosový balík Poznámkovníka' : preview.sourceName
    }]
  };
}

function taskImportSourceReference(link) {
  return link?.sourceImportLink || {
    sourceId: link?.targetId || '',
    title: link?.title || '',
    relationType: 'reference',
    locator: '',
    label: '',
    note: ''
  };
}

function taskImportLinkTitle(link) {
  return link?.title || (link?.targetType === 'library' ? 'knižnica' : link?.targetType === 'element' ? 'text' : 'zdroj');
}

async function importTaskFromMarkdown(preview) {
  if (!(await saveTaskDraft())) throw new Error('Pred importom sa nepodarilo uložiť rozpracovanú úlohu.');
  await flushWorkspaceSync();

  return runTaskOperation(async () => {
    const created = await apiRequest('/tasks', {
      method: 'POST',
      body: { ...preview.task, id: crypto.randomUUID() }
    });
    let importedTask = created.task;
    const warnings = [];
    const taskLinks = Array.isArray(preview.taskLinks) ? preview.taskLinks : [];
    const sourceLinks = taskLinks
      .filter((link) => link.targetType === 'source')
      .map(taskImportSourceReference);
    const copyResult = await copyImportedSources({
      links: sourceLinks,
      sourceSnapshots: preview.sourceSnapshots,
      sourceAssets: preview.sourceAssets,
      sourceActions: preview.sourceActions
    });
    warnings.push(...copyResult.warnings);

    for (const link of taskLinks) {
      let targetId = String(link.targetId || '');
      if (link.targetType === 'source') {
        const sourceLink = taskImportSourceReference(link);
        const action = importedSourceAction(preview.sourceActions, sourceLink);
        targetId = resolvedImportedSourceId(sourceLink, preview.sourceActions, copyResult);
        if (!targetId) {
          if (action !== 'skip') {
            warnings.push(`Väzba na zdroj „${importedSourceTitle(sourceLink)}“ sa nepodarilo obnoviť.`);
          }
          continue;
        }
      }
      try {
        const result = await apiRequest(`/tasks/${encodeURIComponent(importedTask.id)}/links`, {
          method: 'POST',
          body: { id: crypto.randomUUID(), targetType: link.targetType, targetId }
        });
        importedTask = result.task;
      } catch {
        warnings.push(`Väzba na „${taskImportLinkTitle(link)}“ nebola obnovená, pretože jej cieľ v tomto Poznámkovníku neexistuje.`);
      }
    }

    selectedTask = importedTask;
    draftTaskListIds = [];
    targetSources = null;
    renderTaskDetail();
    await loadTaskLists();
    await loadTasks();
    refreshTagSuggestions();
    notifyTasksChanged();
    return { warnings: [...new Set(warnings)] };
  });
}

function requestTaskMarkdownImport() {
  requestMarkdownImport({
    destinationLabel: 'novej úlohy',
    confirmLabel: 'Vytvoriť úlohu',
    previewAdapter: importedTaskPreview,
    prepareImport: prepareTaskMarkdownImport,
    onConfirm: importTaskFromMarkdown
  });
}

function setTaskListError(message = '') {
  dom.taskListTitle.setCustomValidity(message);
  if (message) dom.taskListTitle.reportValidity();
}

function populateTaskListParentOptions(selectedParentId = '', excludedListId = '') {
  dom.taskListParent.replaceChildren();
  const root = document.createElement('option');
  root.value = '';
  root.textContent = 'Hlavná úroveň';
  dom.taskListParent.append(root);

  const appendOptions = (parentId, depth) => {
    taskListChildren(parentId).forEach((taskList) => {
      if (taskList.id === excludedListId || isTaskListDescendant(taskList.id, excludedListId)) return;
      const option = document.createElement('option');
      option.value = taskList.id;
      option.textContent = `${'\u00a0\u00a0'.repeat(depth)}${taskList.title}`;
      option.selected = taskList.id === selectedParentId;
      dom.taskListParent.append(option);
      appendOptions(taskList.id, depth + 1);
    });
  };
  appendOptions('', 0);
  dom.taskListParent.value = selectedParentId || '';
}

function openTaskListDialog(taskList = null) {
  editingTaskListId = taskList?.id || '';
  const parentId = taskList?.parentId || activeTaskListId || '';
  dom.taskListForm.reset();
  dom.taskListDialogTitle.textContent = taskList ? 'Upraviť zoznam úloh' : 'Nový zoznam úloh';
  dom.taskListDialogDescription.textContent = taskList
    ? 'Zmena nadradeného zoznamu presunie aj jeho podzoznamy.'
    : parentId
      ? `Nový zoznam bude vložený do „${taskListLabel(taskListById(parentId))}“.`
      : 'Zoznamy slúžia len na usporiadanie úloh.';
  dom.taskListSave.textContent = taskList ? 'Uložiť zmeny' : 'Vytvoriť zoznam';
  dom.taskListTitle.value = taskList?.title || '';
  populateTaskListParentOptions(parentId, editingTaskListId);
  setTaskListError('');
  if (!dom.taskListDialog.open) dom.taskListDialog.showModal();
  requestAnimationFrame(() => dom.taskListTitle.focus());
}

function closeTaskListDialog() {
  if (dom.taskListDialog.open) dom.taskListDialog.close();
  else editingTaskListId = '';
}

async function saveTaskList() {
  if (!dom.taskListForm.reportValidity()) return;
  try {
    const data = {
      title: dom.taskListTitle.value.trim(),
      parentId: dom.taskListParent.value
    };
    const result = editingTaskListId
      ? await apiRequest(`/task-lists/${encodeURIComponent(editingTaskListId)}`, { method: 'PATCH', body: data })
      : await apiRequest('/task-lists', { method: 'POST', body: { ...data, id: crypto.randomUUID() } });
    activeTaskListId = result.list.id;
    closeTaskListDialog();
    await loadTaskLists();
    await loadTasks();
  } catch (error) {
    setTaskListError(error?.message || 'Zoznam úloh sa nepodarilo uložiť.');
  }
}

async function deleteTaskList(taskList) {
  const childrenText = taskList.childCount
    ? ` Podzoznamy sa presunú o jednu úroveň vyššie.`
    : '';
  const accepted = confirm(
    `Zmazať zoznam „${taskList.title}“? Úlohy zostanú zachované, iba sa z neho vyradia.${childrenText}`
  );
  if (!accepted) return;
  try {
    const result = await apiRequest(`/task-lists/${encodeURIComponent(taskList.id)}`, { method: 'DELETE' });
    if (activeTaskListId === taskList.id) activeTaskListId = result.parentId || '';
    if (selectedTask) {
      try {
        selectedTask = (await apiRequest(`/tasks/${encodeURIComponent(selectedTask.id)}`)).task;
        renderTaskDetail();
      } catch {
        selectedTask = null;
        showTaskList();
      }
    }
    await loadTaskLists();
    await loadTasks();
    notifyTasksChanged();
  } catch (error) {
    window.alert(error?.message || 'Zoznam úloh sa nepodarilo zmazať.');
  }
}

export function initializeTasks() {
  dom.taskCreateButton.addEventListener('click', startNewTask);
  dom.taskImportButton.addEventListener('click', requestTaskMarkdownImport);
  dom.taskListCreateButton.addEventListener('click', () => openTaskListDialog());
  dom.taskDetailBack.addEventListener('click', closeTaskDetail);
  dom.taskDeleteButton.addEventListener('click', () => void deleteSelectedTask());
  dom.taskRelationshipsButton.addEventListener('click', () => {
    if (selectedTask) void openRelationships({ targetType: 'task', targetId: selectedTask.id });
  });
  dom.taskMarkdownExport.addEventListener('click', openTaskExportDialog);
  dom.taskExportCancel.addEventListener('click', closeTaskExportDialog);
  dom.taskPackageExport.addEventListener('click', () => void exportTask('package'));
  dom.taskPortableMarkdownExport.addEventListener('click', () => void exportTask('markdown'));
  dom.taskExportDialog.addEventListener('close', () => {
    taskExportTargetId = '';
    setTaskExportBusy(false);
  });
  installDialogBackdropClose(dom.taskExportDialog, closeTaskExportDialog);
  dom.taskListDialogClose.addEventListener('click', closeTaskListDialog);
  dom.taskListDialog.addEventListener('close', () => {
    editingTaskListId = '';
    setTaskListError('');
  });
  installDialogBackdropClose(dom.taskListDialog, closeTaskListDialog);
  dom.taskListForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveTaskList();
  });
  dom.taskListTitle.addEventListener('input', () => setTaskListError(''));
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
  dom.taskListMembershipAdd.addEventListener('click', () => void addTaskToList());
  dom.editorTaskToggle.addEventListener('click', () => setEditorTaskMenuOpen(!editorTaskMenuOpen));
  document.addEventListener('pointerdown', (event) => {
    if (editorTaskMenuOpen && !dom.editorTaskLinks.contains(event.target)) closeEditorTaskMenu();
  });
  window.addEventListener('sources-changed', () => {
    targetSources = null;
  });
}
