import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
import { initializeCalendarTransfer } from './calendar-transfer.js';
import { dom } from './dom.js';
import { state } from './state.js';
import { flushWorkspaceSync } from './storage.js';
import { updateTopbarVisibility } from './topbar.js';
import { readTagField, refreshTagSuggestions, setTagField } from './tags.js';
import { openRelationships } from './relationships.js';

const WEEKDAY_LABELS = ['Po', 'Ut', 'St', 'Št', 'Pi', 'So', 'Ne'];
const MONTH_FORMATTER = new Intl.DateTimeFormat('sk-SK', { month: 'long', year: 'numeric' });
const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'short' });
const LONG_DATE_FORMATTER = new Intl.DateTimeFormat('sk-SK', { weekday: 'long', day: 'numeric', month: 'long' });
const REMINDER_WINDOW_DAYS = 35;
const REMINDER_PRESET_VALUES = new Set(['-1', '0', '5', '15', '30', '60', '120', '1440', '10080']);

let calendarView = 'month';
let cursorDate = today();
let calendarEvents = [];
let calendarTasks = [];
let calendarReminderEvents = [];
let calendarLoadRequestId = 0;
let selectedEvent = null;
let selectedEventOccurrenceDate = '';
let selectedEventScope = 'series';
let panelPinned = false;
let eventFormBaseline = '';
let eventOperationCount = 0;
let eventIdleResolvers = [];
let targetSources = null;
let editorCalendarMenuOpen = false;

function eventRelationMeta(event) {
  if (event.allDay) return event.startDate === event.endDate ? event.startDate : `${event.startDate} - ${event.endDate}`;
  const start = event.startTime ? `${event.startDate} ${event.startTime}` : event.startDate;
  const end = event.endTime ? `${event.endDate} ${event.endTime}` : event.endDate;
  return start === end ? start : `${start} - ${end}`;
}

function setEditorCalendarMenuOpen(open) {
  const visible = open && !dom.editorCalendarLinks.hidden;
  editorCalendarMenuOpen = visible;
  dom.editorCalendarMenu.hidden = !visible;
  dom.editorCalendarToggle.setAttribute('aria-expanded', String(visible));
}

export function isEditorCalendarMenuOpen() {
  return editorCalendarMenuOpen;
}

export function closeEditorCalendarMenu() {
  setEditorCalendarMenuOpen(false);
}

export async function refreshElementCalendarLinks() {
  const elementId = state.activeLibraryElementId;
  if (!elementId) {
    closeEditorCalendarMenu();
    dom.editorCalendarLinks.hidden = true;
    dom.editorCalendarMenu.replaceChildren();
    return;
  }
  try {
    const result = await apiRequest(`/calendar-event-links/element/${encodeURIComponent(elementId)}`);
    closeEditorCalendarMenu();
    dom.editorCalendarMenu.replaceChildren();
    if (!result.events.length) {
      dom.editorCalendarLinks.hidden = true;
      return;
    }
    dom.editorCalendarToggleLabel.textContent = `Kalendár (${result.events.length})`;
    result.events.forEach((event) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'editor-source-chip editor-calendar-chip';
      const copy = document.createElement('span');
      copy.className = 'editor-source-chip-copy';
      const title = document.createElement('strong');
      title.textContent = event.title;
      const meta = document.createElement('small');
      meta.textContent = eventRelationMeta(event);
      copy.append(title, meta);
      button.append(createAppIcon('calendar', 'editor-source-chip-icon'), copy);
      button.title = 'Otvoriť udalosť';
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('calendar-open-event', { detail: { eventId: event.id } }));
      });
      dom.editorCalendarMenu.append(button);
    });
    dom.editorCalendarLinks.hidden = false;
  } catch {
    closeEditorCalendarMenu();
    dom.editorCalendarLinks.hidden = true;
  }
}

function notifyCalendarChanged() {
  window.dispatchEvent(new Event('calendar-changed'));
  void refreshElementCalendarLinks();
}

function today() {
  const value = new Date();
  return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 12);
}

function dateFromIso(value) {
  const [year, month, day] = String(value || '').split('-').map(Number);
  return new Date(year, month - 1, day, 12);
}

function isoDate(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function addDays(value, count) {
  const next = new Date(value);
  next.setDate(next.getDate() + count);
  return next;
}

function startOfWeek(value) {
  const result = new Date(value);
  const weekday = result.getDay() || 7;
  result.setDate(result.getDate() - weekday + 1);
  return result;
}

function startOfMonthGrid(value) {
  return startOfWeek(new Date(value.getFullYear(), value.getMonth(), 1, 12));
}

function dateRange() {
  if (calendarView === 'week') {
    const start = startOfWeek(cursorDate);
    return { start, end: addDays(start, 6) };
  }
  if (calendarView === 'agenda') {
    const start = new Date(cursorDate.getFullYear(), cursorDate.getMonth(), 1, 12);
    return { start, end: new Date(cursorDate.getFullYear(), cursorDate.getMonth() + 1, 0, 12) };
  }
  const start = startOfMonthGrid(cursorDate);
  return { start, end: addDays(start, 41) };
}

function isWithinRange(value, start, end) {
  return value >= isoDate(start) && value <= isoDate(end);
}

function reminderMoment(event) {
  const reminderMinutes = Number(event?.reminderMinutes);
  if (!Number.isInteger(reminderMinutes) || reminderMinutes < 0) return null;
  const time = event.allDay ? '09:00' : event.startTime || '00:00';
  const moment = new Date(`${event.startDate}T${time}:00`);
  if (Number.isNaN(moment.getTime())) return null;
  return new Date(moment.getTime() - reminderMinutes * 60_000);
}

function reminderTimeLabel(moment) {
  const dateValue = isoDate(moment);
  const todayValue = isoDate(today());
  const tomorrowValue = isoDate(addDays(today(), 1));
  const time = `${String(moment.getHours()).padStart(2, '0')}:${String(moment.getMinutes()).padStart(2, '0')}`;
  if (dateValue === todayValue) return `Dnes o ${time}`;
  if (dateValue === tomorrowValue) return `Zajtra o ${time}`;
  return `${SHORT_DATE_FORMATTER.format(moment)} o ${time}`;
}

function renderCalendarReminders() {
  dom.calendarRemindersList.replaceChildren();
  const now = new Date();
  const reminders = calendarReminderEvents
    .map((event) => ({ event, moment: reminderMoment(event) }))
    .filter((item) => item.moment && item.moment >= now)
    .sort((left, right) => left.moment - right.moment || left.event.title.localeCompare(right.event.title, 'sk'))
    .slice(0, 5);
  if (!reminders.length) {
    const empty = document.createElement('p');
    empty.className = 'calendar-reminders-empty';
    empty.textContent = `V nasledujúcich ${REMINDER_WINDOW_DAYS} dňoch nie sú žiadne pripomienky.`;
    dom.calendarRemindersList.append(empty);
    return;
  }
  reminders.forEach(({ event, moment }) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'calendar-reminder-item';
    button.append(createAppIcon('timer'));
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = event.title;
    const meta = document.createElement('small');
    meta.textContent = reminderTimeLabel(moment);
    copy.append(title, meta);
    button.append(copy);
    button.title = `Otvoriť udalosť: ${event.title}`;
    button.addEventListener('click', () => void selectCalendarEvent(event.id, event.occurrenceDate || ''));
    dom.calendarRemindersList.append(button);
  });
}

function eventOccursOn(event, dateValue) {
  return event.startDate <= dateValue && event.endDate >= dateValue;
}

function setCalendarPanelOpen(open) {
  dom.calendarPanel.classList.toggle('is-open', open);
  dom.calendarPanel.setAttribute('aria-hidden', String(!open));
  dom.calendarButton.setAttribute('aria-expanded', String(open));
  updateTopbarVisibility();
}

function setCalendarEventDetailOpen(open) {
  dom.calendarEventDock.classList.toggle('is-open', open);
  dom.calendarEventDock.setAttribute('aria-hidden', String(!open));
  if (open) document.body.dataset.calendarEventOpen = 'true';
  else delete document.body.dataset.calendarEventOpen;
  updateTopbarVisibility();
}

export function isCalendarPanelOpen() {
  return dom.calendarPanel.classList.contains('is-open');
}

export function isCalendarEventDetailOpen() {
  return dom.calendarEventDock.classList.contains('is-open');
}

export function isCalendarPanelPinned() {
  return panelPinned;
}

function eventFormSnapshot() {
  return JSON.stringify({
    title: dom.calendarEventTitle.value.trim(),
    allDay: dom.calendarEventAllDay.checked,
    startDate: dom.calendarEventStartDate.value,
    startTime: dom.calendarEventStartTime.value,
    endDate: dom.calendarEventEndDate.value,
    endTime: dom.calendarEventEndTime.value,
    recurrence: dom.calendarEventRecurrence.value,
    recurrenceInterval: dom.calendarEventRecurrenceInterval.value,
    recurrenceUnit: dom.calendarEventRecurrenceUnit.value,
    recurrenceUntil: dom.calendarEventRecurrenceUntil.value,
    reminder: dom.calendarEventReminder.value,
    reminderCustom: dom.calendarEventReminder.value === 'custom' ? dom.calendarEventReminderCustom.value : '',
    description: dom.calendarEventDescription.value.trim(),
    tags: readTagField(dom.calendarEventTags)
  });
}

function rememberEventForm() {
  eventFormBaseline = eventFormSnapshot();
}

export function hasUnsavedCalendarEventChanges() {
  return !dom.calendarEventDetail.hidden && eventFormSnapshot() !== eventFormBaseline;
}

export function discardCalendarEventDraft() {
  if (selectedEvent) renderCalendarEventDetail();
  else closeCalendarEventDetail();
}

function runEventOperation(operation) {
  eventOperationCount += 1;
  return Promise.resolve()
    .then(operation)
    .finally(() => {
      eventOperationCount -= 1;
      if (!eventOperationCount) {
        eventIdleResolvers.forEach((resolve) => resolve());
        eventIdleResolvers = [];
      }
    });
}

export function waitForCalendarEventOperations() {
  if (!eventOperationCount) return Promise.resolve();
  return new Promise((resolve) => eventIdleResolvers.push(resolve));
}

function setEventFormError(message = '') {
  dom.calendarEventTitle.setCustomValidity(message);
  if (message) dom.calendarEventTitle.reportValidity();
}

function syncAllDayFields() {
  const timed = !dom.calendarEventAllDay.checked;
  dom.calendarEventTimeFields.hidden = !timed;
  dom.calendarEventStartTime.required = timed;
  dom.calendarEventEndTime.required = timed;
  syncReminderFields();
}

function syncReminderFields() {
  const custom = dom.calendarEventReminder.value === 'custom';
  dom.calendarEventReminderCustomField.hidden = !custom;
  dom.calendarEventReminderCustom.disabled = !custom;
  dom.calendarEventReminderCustom.required = custom;
  dom.calendarEventReminderNote.textContent = dom.calendarEventAllDay.checked
    ? 'Pri celodennej udalosti sa pripomienka vyhodnotí o 9:00 v deň začiatku.'
    : 'Pripomienka sa vyhodnotí pred časom začiatku udalosti.';
}

function setReminderMinutes(value) {
  const minutes = Number(value);
  if (Number.isInteger(minutes) && REMINDER_PRESET_VALUES.has(String(minutes))) {
    dom.calendarEventReminder.value = String(minutes);
  } else {
    dom.calendarEventReminder.value = 'custom';
    dom.calendarEventReminderCustom.value = String(Math.max(0, Number.isInteger(minutes) ? minutes : 15));
  }
  syncReminderFields();
}

function reminderMinutesFromForm() {
  const value = dom.calendarEventReminder.value === 'custom'
    ? dom.calendarEventReminderCustom.value
    : dom.calendarEventReminder.value;
  return Number(value);
}

function setEventRecurrence(event) {
  const kind = event?.recurrenceKind || 'none';
  const interval = Math.max(1, Number.parseInt(event?.recurrenceInterval, 10) || 1);
  const isCustom = ['daily', 'weekly', 'monthly'].includes(kind) && interval > 1;
  dom.calendarEventRecurrence.value = isCustom ? 'custom' : kind;
  dom.calendarEventRecurrenceInterval.value = String(interval);
  dom.calendarEventRecurrenceUnit.value = ['daily', 'weekly', 'monthly'].includes(kind) ? kind : 'daily';
  dom.calendarEventRecurrenceUntil.value = event?.recurrenceUntil || '';
  syncRecurrenceFields();
}

function recurrenceFromForm() {
  const selected = dom.calendarEventRecurrence.value;
  if (selected === 'none') return { recurrenceKind: 'none', recurrenceInterval: 1, recurrenceUntil: '' };
  const custom = selected === 'custom';
  const kind = custom ? dom.calendarEventRecurrenceUnit.value : selected;
  const interval = custom ? Number(dom.calendarEventRecurrenceInterval.value) : 1;
  return {
    recurrenceKind: kind,
    recurrenceInterval: Number.isInteger(interval) ? interval : 1,
    recurrenceUntil: dom.calendarEventRecurrenceUntil.value
  };
}

function syncRecurrenceFields() {
  const selected = dom.calendarEventRecurrence.value;
  const repeated = selected !== 'none';
  const custom = selected === 'custom';
  const occurrenceOnly = Boolean(selectedEventOccurrenceDate) && selectedEventScope === 'occurrence';
  dom.calendarEventRecurrenceCustomField.hidden = !custom;
  dom.calendarEventRecurrenceUntilField.hidden = !repeated;
  dom.calendarEventRecurrenceInterval.disabled = !custom || occurrenceOnly;
  dom.calendarEventRecurrenceUnit.disabled = !custom || occurrenceOnly;
  dom.calendarEventRecurrenceUntil.disabled = !repeated || occurrenceOnly;
  dom.calendarEventRecurrence.disabled = occurrenceOnly;
  dom.calendarEventScopeField.hidden = !selectedEventOccurrenceDate;
  dom.calendarEventScope.value = selectedEventScope;
  dom.calendarEventScopeNote.hidden = !selectedEventOccurrenceDate;
  dom.calendarEventScopeNote.textContent = occurrenceOnly
    ? 'Menia sa len údaje vybraného výskytu. Pravidlo série ostane nezmenené.'
    : selectedEventOccurrenceDate
      ? 'Mení sa pôvodná udalosť a pravidlo série. Výnimky zostanú iba ak ostanú platné.'
      : '';
}

function setView(view) {
  if (!['month', 'week', 'agenda'].includes(view)) return;
  calendarView = view;
  dom.calendarViewButtons.forEach((button) => {
    const active = button.dataset.calendarView === calendarView;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  renderCalendar();
  void loadCalendarData();
}

function periodTitle() {
  const { start, end } = dateRange();
  if (calendarView === 'month') return MONTH_FORMATTER.format(cursorDate);
  if (calendarView === 'agenda') return `Agenda · ${MONTH_FORMATTER.format(cursorDate)}`;
  const sameMonth = start.getMonth() === end.getMonth();
  const sameYear = start.getFullYear() === end.getFullYear();
  const startLabel = SHORT_DATE_FORMATTER.format(start);
  const endLabel = sameMonth && sameYear
    ? new Intl.DateTimeFormat('sk-SK', { day: 'numeric', month: 'short' }).format(end)
    : SHORT_DATE_FORMATTER.format(end);
  return `${startLabel} - ${endLabel}`;
}

function moveCursor(direction) {
  if (calendarView === 'week') cursorDate = addDays(cursorDate, direction * 7);
  else cursorDate = new Date(cursorDate.getFullYear(), cursorDate.getMonth() + direction, 1, 12);
  renderCalendar();
  void loadCalendarData();
}

function resetCursorToToday() {
  cursorDate = today();
  renderCalendar();
  void loadCalendarData();
}

async function loadCalendarData() {
  if (!isCalendarPanelOpen()) return;
  const { start, end } = dateRange();
  const reminderStart = today();
  const reminderEnd = addDays(reminderStart, REMINDER_WINDOW_DAYS);
  const currentRequest = ++calendarLoadRequestId;
  try {
    const [eventsResult, tasksResult, remindersResult] = await Promise.all([
      apiRequest(`/calendar-events?from=${encodeURIComponent(isoDate(start))}&to=${encodeURIComponent(isoDate(end))}`),
      apiRequest('/tasks'),
      apiRequest(`/calendar-events?from=${encodeURIComponent(isoDate(reminderStart))}&to=${encodeURIComponent(isoDate(reminderEnd))}`)
    ]);
    if (currentRequest !== calendarLoadRequestId || !isCalendarPanelOpen()) return;
    calendarEvents = eventsResult.events;
    calendarTasks = tasksResult.tasks.filter((task) => task.dueDate && isWithinRange(task.dueDate, start, end));
    calendarReminderEvents = remindersResult.events;
    renderCalendar();
  } catch {
    if (currentRequest !== calendarLoadRequestId || !isCalendarPanelOpen()) return;
    calendarEvents = [];
    calendarTasks = [];
    calendarReminderEvents = [];
    renderCalendar('Kalendár sa nepodarilo načítať.');
  }
}

function itemTimeLabel(item, dateValue) {
  if (item.kind === 'task') return item.task.status === 'done' ? 'Hotová' : item.task.priority === 'high' ? 'Vysoká priorita' : 'Úloha';
  if (item.event.allDay) return item.event.startDate !== item.event.endDate ? 'Viac dní' : 'Celý deň';
  if (item.event.startDate === dateValue) return `${item.event.startTime} - ${item.event.endTime}`;
  return 'Pokračuje';
}

function itemsForDate(dateValue) {
  const events = calendarEvents
    .filter((event) => eventOccursOn(event, dateValue))
    .map((event) => ({ kind: 'event', event }));
  const tasks = calendarTasks
    .filter((task) => task.dueDate === dateValue)
    .map((task) => ({ kind: 'task', task }));
  return [...events, ...tasks].sort((left, right) => {
    const leftTime = left.kind === 'event' ? left.event.startTime || '00:00' : '23:59';
    const rightTime = right.kind === 'event' ? right.event.startTime || '00:00' : '23:59';
    return leftTime.localeCompare(rightTime) || itemTitle(left).localeCompare(itemTitle(right), 'sk');
  });
}

function itemTitle(item) {
  return item.kind === 'event' ? item.event.title : item.task.title;
}

function itemTagLabel(item) {
  const tags = item.kind === 'event' ? item.event.tags : item.task.tags;
  return (tags || []).slice(0, 1).map((tag) => `#${tag}`).join('');
}

function createCalendarItem(item, dateValue) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `calendar-item calendar-item-${item.kind}`;
  if (item.kind === 'task') {
    button.classList.toggle('is-done', item.task.status === 'done');
    button.classList.toggle('is-high-priority', item.task.priority === 'high');
  } else {
    button.classList.toggle('is-timed', !item.event.allDay);
    button.classList.toggle('is-multiday', item.event.startDate !== item.event.endDate);
  }
  const time = document.createElement('small');
  time.textContent = [itemTimeLabel(item, dateValue), itemTagLabel(item)].filter(Boolean).join(' · ');
  const title = document.createElement('strong');
  title.textContent = itemTitle(item);
  button.append(time, title);
  if (item.kind === 'task') {
    button.title = `Otvoriť úlohu: ${item.task.title}`;
    button.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('task-open', { detail: { taskId: item.task.id } }));
    });
  } else {
    button.title = `Otvoriť udalosť: ${item.event.title}`;
    button.addEventListener('click', () => void selectCalendarEvent(item.event.id, item.event.occurrenceDate || ''));
  }
  return button;
}

function createDayHeader(value, { compact = false } = {}) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'calendar-day-heading';
  const iso = isoDate(value);
  const isToday = iso === isoDate(today());
  button.classList.toggle('is-today', isToday);
  button.textContent = compact ? `${WEEKDAY_LABELS[(value.getDay() + 6) % 7]} ${value.getDate()}` : String(value.getDate());
  button.title = 'Vytvoriť udalosť v tento deň';
  button.addEventListener('click', () => startNewCalendarEvent(iso));
  return button;
}

function renderMonthView() {
  const fragment = document.createDocumentFragment();
  const weekdays = document.createElement('div');
  weekdays.className = 'calendar-weekdays';
  WEEKDAY_LABELS.forEach((label) => {
    const weekday = document.createElement('span');
    weekday.textContent = label;
    weekdays.append(weekday);
  });
  fragment.append(weekdays);

  const grid = document.createElement('div');
  grid.className = 'calendar-month-grid';
  const first = startOfMonthGrid(cursorDate);
  for (let index = 0; index < 42; index += 1) {
    const value = addDays(first, index);
    const dateValue = isoDate(value);
    const cell = document.createElement('section');
    cell.className = 'calendar-month-day';
    cell.classList.toggle('is-outside-month', value.getMonth() !== cursorDate.getMonth());
    cell.classList.toggle('is-today', dateValue === isoDate(today()));
    const header = document.createElement('header');
    header.append(createDayHeader(value));
    const items = document.createElement('div');
    items.className = 'calendar-day-items';
    itemsForDate(dateValue).forEach((item) => items.append(createCalendarItem(item, dateValue)));
    cell.append(header, items);
    grid.append(cell);
  }
  fragment.append(grid);
  return fragment;
}

function renderWeekView() {
  const grid = document.createElement('div');
  grid.className = 'calendar-week-grid';
  const first = startOfWeek(cursorDate);
  for (let index = 0; index < 7; index += 1) {
    const value = addDays(first, index);
    const dateValue = isoDate(value);
    const column = document.createElement('section');
    column.className = 'calendar-week-day';
    column.classList.toggle('is-today', dateValue === isoDate(today()));
    const header = document.createElement('header');
    header.append(createDayHeader(value, { compact: true }));
    const items = document.createElement('div');
    items.className = 'calendar-day-items';
    itemsForDate(dateValue).forEach((item) => items.append(createCalendarItem(item, dateValue)));
    column.append(header, items);
    grid.append(column);
  }
  return grid;
}

function renderAgendaView() {
  const { start, end } = dateRange();
  const list = document.createElement('div');
  list.className = 'calendar-agenda-list';
  let containsItems = false;
  for (let value = start; value <= end; value = addDays(value, 1)) {
    const dateValue = isoDate(value);
    const items = itemsForDate(dateValue);
    if (!items.length) continue;
    containsItems = true;
    const group = document.createElement('section');
    group.className = 'calendar-agenda-day';
    const heading = document.createElement('h3');
    heading.textContent = LONG_DATE_FORMATTER.format(value);
    const itemList = document.createElement('div');
    itemList.className = 'calendar-agenda-items';
    items.forEach((item) => itemList.append(createCalendarItem(item, dateValue)));
    group.append(heading, itemList);
    list.append(group);
  }
  if (!containsItems) {
    const empty = document.createElement('p');
    empty.className = 'calendar-empty';
    empty.textContent = 'V tomto období zatiaľ nie sú žiadne udalosti ani úlohy s termínom.';
    list.append(empty);
  }
  return list;
}

function renderCalendar(errorMessage = '') {
  dom.calendarPeriodTitle.textContent = periodTitle();
  renderCalendarReminders();
  dom.calendarContent.replaceChildren();
  if (errorMessage) {
    const error = document.createElement('p');
    error.className = 'calendar-empty';
    error.textContent = errorMessage;
    dom.calendarContent.append(error);
    return;
  }
  if (calendarView === 'month') dom.calendarContent.append(renderMonthView());
  else if (calendarView === 'week') dom.calendarContent.append(renderWeekView());
  else dom.calendarContent.append(renderAgendaView());
}

function showCalendarEventDetail() {
  dom.calendarEventDetail.hidden = false;
  panelPinned = true;
  setCalendarEventDetailOpen(true);
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'calendar' } }));
}

export function closeCalendarEventDetail() {
  dom.calendarEventDetail.hidden = true;
  setCalendarEventDetailOpen(false);
}

function renderCalendarEventLinks() {
  dom.calendarEventLinksList.replaceChildren();
  if (!selectedEvent?.links.length) {
    const empty = document.createElement('p');
    empty.className = 'task-links-empty';
    empty.textContent = 'Zatiaľ nie je pripojená k žiadnemu prvku.';
    dom.calendarEventLinksList.append(empty);
    return;
  }
  selectedEvent.links.forEach((link) => {
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
    open.addEventListener('click', () => window.dispatchEvent(new CustomEvent('calendar-open-target', { detail: link })));

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.append(createAppIcon('close'));
    remove.title = `Odpojiť ${link.title}`;
    remove.setAttribute('aria-label', `Odpojiť ${link.title}`);
    remove.addEventListener('click', () => void unlinkCalendarEvent(link.id));
    row.append(open, remove);
    dom.calendarEventLinksList.append(row);
  });
}

function calendarTargets(type) {
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

async function renderCalendarEventTargetOptions() {
  const targetType = dom.calendarEventLinkTargetType.value;
  dom.calendarEventLinkTarget.replaceChildren();
  dom.calendarEventLinkAdd.disabled = !selectedEvent;
  if (!selectedEvent) return;
  if (targetType === 'source' && targetSources === null) {
    const loading = document.createElement('option');
    loading.textContent = 'Načítavam zdroje...';
    dom.calendarEventLinkTarget.append(loading);
    dom.calendarEventLinkTarget.disabled = true;
    try {
      const result = await apiRequest('/sources');
      targetSources = result.sources;
    } catch {
      targetSources = [];
    }
  }
  const linkedIds = new Set(
    selectedEvent.links.filter((link) => link.targetType === targetType).map((link) => link.targetId)
  );
  const targets = calendarTargets(targetType).filter((target) => !linkedIds.has(target.id));
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = targets.length ? 'Vyber prepojenie' : 'Nie je čo pripojiť';
  dom.calendarEventLinkTarget.append(empty);
  targets.forEach((target) => {
    const option = document.createElement('option');
    option.value = target.id;
    option.textContent = target.label;
    dom.calendarEventLinkTarget.append(option);
  });
  dom.calendarEventLinkTarget.disabled = !targets.length;
  dom.calendarEventLinkAdd.disabled = !targets.length;
}

function renderCalendarEventDetail() {
  if (!selectedEvent) return;
  showCalendarEventDetail();
  dom.calendarEventFormTitle.textContent = selectedEvent.title || 'Udalosť';
  dom.calendarEventTitle.value = selectedEvent.title;
  dom.calendarEventAllDay.checked = selectedEvent.allDay;
  dom.calendarEventStartDate.value = selectedEvent.startDate;
  dom.calendarEventEndDate.value = selectedEvent.endDate;
  dom.calendarEventStartTime.value = selectedEvent.startTime || '';
  dom.calendarEventEndTime.value = selectedEvent.endTime || '';
  setEventRecurrence(selectedEvent);
  setReminderMinutes(selectedEvent.reminderMinutes);
  dom.calendarEventDescription.value = selectedEvent.description || '';
  setTagField(dom.calendarEventTags, dom.calendarEventTagChips, selectedEvent.tags || []);
  dom.calendarEventDelete.hidden = false;
  dom.calendarEventRelationships.hidden = false;
  dom.calendarEventLinksSection.hidden = false;
  syncAllDayFields();
  renderCalendarEventLinks();
  void renderCalendarEventTargetOptions();
  rememberEventForm();
}

async function selectCalendarEvent(eventId, occurrenceDate = '') {
  try {
    const query = occurrenceDate ? `?occurrenceDate=${encodeURIComponent(occurrenceDate)}` : '';
    const result = await apiRequest(`/calendar-events/${encodeURIComponent(eventId)}${query}`);
    selectedEvent = result.event;
    selectedEventOccurrenceDate = occurrenceDate || result.event.occurrenceDate || '';
    selectedEventScope = selectedEventOccurrenceDate ? 'occurrence' : 'series';
    renderCalendarEventDetail();
  } catch {
    selectedEvent = null;
    selectedEventOccurrenceDate = '';
    selectedEventScope = 'series';
    await loadCalendarData();
  }
}

async function changeCalendarEventScope() {
  const nextScope = dom.calendarEventScope.value;
  if (!selectedEvent || !selectedEventOccurrenceDate || nextScope === selectedEventScope) return;
  if (hasUnsavedCalendarEventChanges() && !confirm('Zmena rozsahu úpravy vráti neuložené zmeny udalosti. Pokračovať?')) {
    dom.calendarEventScope.value = selectedEventScope;
    return;
  }
  try {
    const query = nextScope === 'occurrence'
      ? `?occurrenceDate=${encodeURIComponent(selectedEventOccurrenceDate)}`
      : '';
    const result = await apiRequest(`/calendar-events/${encodeURIComponent(selectedEvent.id)}${query}`);
    selectedEvent = result.event;
    selectedEventScope = nextScope;
    renderCalendarEventDetail();
  } catch (error) {
    dom.calendarEventScope.value = selectedEventScope;
    setEventFormError(error?.message || 'Rozsah úpravy udalosti sa nepodarilo zmeniť.');
  }
}

function startNewCalendarEvent(dateValue = isoDate(cursorDate)) {
  selectedEvent = null;
  showCalendarEventDetail();
  dom.calendarEventForm.reset();
  setTagField(dom.calendarEventTags, dom.calendarEventTagChips, []);
  dom.calendarEventAllDay.checked = true;
  dom.calendarEventStartDate.value = dateValue;
  dom.calendarEventEndDate.value = dateValue;
  dom.calendarEventRecurrence.value = 'none';
  dom.calendarEventRecurrenceInterval.value = '1';
  dom.calendarEventRecurrenceUnit.value = 'daily';
  dom.calendarEventRecurrenceUntil.value = '';
  selectedEventOccurrenceDate = '';
  selectedEventScope = 'series';
  setReminderMinutes(-1);
  dom.calendarEventDelete.hidden = true;
  dom.calendarEventRelationships.hidden = true;
  dom.calendarEventLinksSection.hidden = true;
  dom.calendarEventLinksList.replaceChildren();
  syncAllDayFields();
  syncRecurrenceFields();
  void renderCalendarEventTargetOptions();
  rememberEventForm();
  dom.calendarEventTitle.focus();
}

export async function saveCalendarEventDraft() {
  if (!hasUnsavedCalendarEventChanges()) return true;
  if (!dom.calendarEventForm.reportValidity()) return false;
  try {
    await runEventOperation(async () => {
      const data = {
        title: dom.calendarEventTitle.value.trim(),
        description: dom.calendarEventDescription.value.trim(),
        allDay: dom.calendarEventAllDay.checked,
        startDate: dom.calendarEventStartDate.value,
        startTime: dom.calendarEventStartTime.value,
        endDate: dom.calendarEventEndDate.value,
        endTime: dom.calendarEventEndTime.value,
        reminderMinutes: reminderMinutesFromForm(),
        tags: readTagField(dom.calendarEventTags),
        ...recurrenceFromForm(),
        scope: selectedEventScope,
        occurrenceDate: selectedEventOccurrenceDate
      };
      const result = selectedEvent
        ? await apiRequest(`/calendar-events/${encodeURIComponent(selectedEvent.id)}`, { method: 'PATCH', body: data })
        : await apiRequest('/calendar-events', { method: 'POST', body: { ...data, id: crypto.randomUUID() } });
      selectedEvent = result.event;
      if (selectedEventScope === 'series') selectedEventOccurrenceDate = '';
      targetSources = null;
      renderCalendarEventDetail();
      await loadCalendarData();
      refreshTagSuggestions();
      notifyCalendarChanged();
    });
    return true;
  } catch (error) {
    setEventFormError(error?.message || 'Udalosť sa nepodarilo uložiť.');
    return false;
  }
}

async function addCalendarEventLink() {
  if (!selectedEvent || !dom.calendarEventLinkTarget.value) return;
  try {
    await runEventOperation(async () => {
      if (dom.calendarEventLinkTargetType.value !== 'source') await flushWorkspaceSync();
      const result = await apiRequest(`/calendar-events/${encodeURIComponent(selectedEvent.id)}/links`, {
        method: 'POST',
        body: {
          id: crypto.randomUUID(),
          targetType: dom.calendarEventLinkTargetType.value,
          targetId: dom.calendarEventLinkTarget.value
        }
      });
      selectedEvent = result.event;
      renderCalendarEventDetail();
      await loadCalendarData();
      notifyCalendarChanged();
    });
  } catch (error) {
    setEventFormError(error?.message || 'Prepojenie sa nepodarilo vytvoriť.');
  }
}

async function unlinkCalendarEvent(linkId) {
  if (!selectedEvent) return;
  try {
    const result = await runEventOperation(() =>
      apiRequest(`/calendar-events/${encodeURIComponent(selectedEvent.id)}/links/${encodeURIComponent(linkId)}`, { method: 'DELETE' })
    );
    selectedEvent = result.event;
    renderCalendarEventDetail();
    await loadCalendarData();
    notifyCalendarChanged();
  } catch (error) {
    setEventFormError(error?.message || 'Prepojenie sa nepodarilo odstrániť.');
  }
}

async function deleteSelectedCalendarEvent() {
  if (!selectedEvent) return;
  const occurrenceOnly = Boolean(selectedEventOccurrenceDate) && selectedEventScope === 'occurrence';
  const question = occurrenceOnly
    ? `Zmazať len výskyt udalosti „${selectedEvent.title}“?`
    : `Zmazať ${selectedEventOccurrenceDate ? 'celú sériu udalosti' : 'udalosť'} „${selectedEvent.title}“?`;
  if (!confirm(question)) return;
  try {
    const query = occurrenceOnly
      ? `?scope=occurrence&occurrenceDate=${encodeURIComponent(selectedEventOccurrenceDate)}`
      : '';
    await runEventOperation(() => apiRequest(`/calendar-events/${encodeURIComponent(selectedEvent.id)}${query}`, { method: 'DELETE' }));
    selectedEvent = null;
    selectedEventOccurrenceDate = '';
    selectedEventScope = 'series';
    closeCalendarEventDetail();
    await loadCalendarData();
    notifyCalendarChanged();
  } catch (error) {
    setEventFormError(error?.message || 'Udalosť sa nepodarilo zmazať.');
  }
}

export function closeCalendarPanel({ force = false } = {}) {
  if (panelPinned && !force) return;
  panelPinned = false;
  selectedEvent = null;
  selectedEventOccurrenceDate = '';
  selectedEventScope = 'series';
  dom.calendarEventDetail.hidden = true;
  setCalendarEventDetailOpen(false);
  setCalendarPanelOpen(false);
}

export async function openCalendarPanel({ eventId = '', pinned = false } = {}) {
  if (pinned) panelPinned = true;
  setCalendarPanelOpen(true);
  await loadCalendarData();
  if (eventId) await selectCalendarEvent(eventId);
}

export function initializeCalendar() {
  initializeCalendarTransfer({
    getRange: () => {
      const range = dateRange();
      return { start: isoDate(range.start), end: isoDate(range.end) };
    },
    onImported: async () => {
      await loadCalendarData();
      notifyCalendarChanged();
    }
  });
  dom.calendarViewButtons.forEach((button) => button.addEventListener('click', () => setView(button.dataset.calendarView || 'month')));
  dom.calendarTodayButton.addEventListener('click', resetCursorToToday);
  dom.calendarPreviousButton.addEventListener('click', () => moveCursor(-1));
  dom.calendarNextButton.addEventListener('click', () => moveCursor(1));
  dom.calendarEventCreate.addEventListener('click', () => startNewCalendarEvent());
  dom.calendarWorkspaceCreate.addEventListener('click', () => startNewCalendarEvent());
  dom.calendarEventBack.addEventListener('click', closeCalendarEventDetail);
  dom.calendarEventDelete.addEventListener('click', () => void deleteSelectedCalendarEvent());
  dom.calendarEventRelationships.addEventListener('click', () => {
    if (selectedEvent) void openRelationships({ targetType: 'calendar_event', targetId: selectedEvent.id });
  });
  dom.calendarEventForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveCalendarEventDraft();
  });
  dom.calendarEventTitle.addEventListener('input', () => setEventFormError(''));
  dom.calendarEventAllDay.addEventListener('change', syncAllDayFields);
  dom.calendarEventRecurrence.addEventListener('change', syncRecurrenceFields);
  dom.calendarEventScope.addEventListener('change', () => void changeCalendarEventScope());
  dom.calendarEventReminder.addEventListener('change', syncReminderFields);
  dom.calendarEventLinkTargetType.addEventListener('change', () => void renderCalendarEventTargetOptions());
  dom.calendarEventLinkAdd.addEventListener('click', () => void addCalendarEventLink());
  dom.editorCalendarToggle.addEventListener('click', () => setEditorCalendarMenuOpen(!editorCalendarMenuOpen));
  document.addEventListener('pointerdown', (event) => {
    if (editorCalendarMenuOpen && !dom.editorCalendarLinks.contains(event.target)) closeEditorCalendarMenu();
  });
  window.addEventListener('tasks-changed', () => {
    if (isCalendarPanelOpen()) void loadCalendarData();
  });
  window.addEventListener('sources-changed', () => {
    targetSources = null;
  });
  window.setInterval(() => {
    if (isCalendarPanelOpen()) renderCalendarReminders();
  }, 60_000);
}
