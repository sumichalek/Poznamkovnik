import { apiRequest } from './api.js';
import { dom } from './dom.js';
import { fitDialogResizableSection, installDialogBackdropClose } from './dialogs.js';
import { createStoredZip, downloadBlob } from './markdown-archive.js';
import { readImportEntries } from './markdown-import.js';

const CALENDAR_PACKAGE_PATH = '.poznamkovnik-calendar.json';
const MAX_ICAL_BYTES = 2 * 1024 * 1024;
const MAX_PACKAGE_MANIFEST_BYTES = 2 * 1024 * 1024;
const MAX_EVENTS = 1_000;
const MAX_REMINDER_MINUTES = 365 * 24 * 60;
const LINK_TYPES = new Set(['library', 'element', 'source']);
const RECURRENCE_KINDS = new Set(['none', 'daily', 'weekdays', 'weekly', 'monthly']);

let pendingImport = null;
let currentRange = () => ({ start: '', end: '' });
let importedCallback = async () => {};

function text(value, maximum = 10_000) {
  return String(value || '').trim().slice(0, maximum);
}

function safeFileName(value, fallback = 'kalendar') {
  return text(value, 120)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLocaleLowerCase('sk') || fallback;
}

function validDate(value) {
  const result = text(value, 10);
  const match = result.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return '';
  const [, year, month, day] = match;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day), 12);
  return parsed.getFullYear() === Number(year) && parsed.getMonth() === Number(month) - 1 && parsed.getDate() === Number(day) ? result : '';
}

function validTime(value) {
  const result = text(value, 5);
  return /^\d{2}:\d{2}$/.test(result) && Number(result.slice(0, 2)) < 24 && Number(result.slice(3, 5)) < 60 ? result : '';
}

function validReminderMinutes(value) {
  if (value === undefined || value === null || value === '') return -1;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= -1 && parsed <= MAX_REMINDER_MINUTES ? parsed : -1;
}

function normalizeRecurrence(value, startDate = '') {
  const raw = value && typeof value === 'object' ? value : {};
  const kind = RECURRENCE_KINDS.has(raw.recurrenceKind) ? raw.recurrenceKind : 'none';
  const intervalValue = Number(raw.recurrenceInterval);
  const interval = Number.isInteger(intervalValue) && intervalValue >= 1 && intervalValue <= 365 ? intervalValue : 1;
  const until = validDate(raw.recurrenceUntil);
  if (kind === 'none') return { recurrenceKind: 'none', recurrenceInterval: 1, recurrenceUntil: '' };
  return {
    recurrenceKind: kind,
    recurrenceInterval: kind === 'weekdays' ? 1 : interval,
    recurrenceUntil: until && (!startDate || until >= startDate) ? until : ''
  };
}

function recurrenceFromIcalRule(value, startDate) {
  const entries = new Map(
    String(value || '').split(';').map((part) => {
      const [key, ...rest] = part.split('=');
      return [String(key || '').trim().toUpperCase(), rest.join('=').trim().toUpperCase()];
    })
  );
  const frequency = entries.get('FREQ');
  let recurrenceKind = 'none';
  if (frequency === 'DAILY') recurrenceKind = 'daily';
  if (frequency === 'MONTHLY') recurrenceKind = 'monthly';
  if (frequency === 'WEEKLY') {
    const weekdays = (entries.get('BYDAY') || '').split(',').filter(Boolean).sort().join(',');
    recurrenceKind = weekdays === 'FR,MO,TH,TU,WE' ? 'weekdays' : 'weekly';
  }
  const until = parseIcalTemporal(entries.get('UNTIL') || '')?.date || '';
  return normalizeRecurrence(
    { recurrenceKind, recurrenceInterval: entries.get('INTERVAL') || 1, recurrenceUntil: until },
    startDate
  );
}

function rruleForEvent(event) {
  const recurrence = normalizeRecurrence(event, event.startDate);
  if (recurrence.recurrenceKind === 'none') return '';
  const parts = [];
  if (recurrence.recurrenceKind === 'daily') parts.push('FREQ=DAILY');
  if (recurrence.recurrenceKind === 'weekly') parts.push('FREQ=WEEKLY');
  if (recurrence.recurrenceKind === 'weekdays') parts.push('FREQ=WEEKLY', 'BYDAY=MO,TU,WE,TH,FR');
  if (recurrence.recurrenceKind === 'monthly') parts.push('FREQ=MONTHLY');
  if (recurrence.recurrenceInterval > 1) parts.push(`INTERVAL=${recurrence.recurrenceInterval}`);
  if (recurrence.recurrenceUntil) parts.push(`UNTIL=${icalDate(recurrence.recurrenceUntil)}`);
  return parts.join(';');
}

function nextDate(value) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + 1);
  return toIsoDate(date);
}

function previousDate(value) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() - 1);
  return toIsoDate(date);
}

function toIsoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function unescapeIcal(value) {
  return String(value || '')
    .replace(/\\[nN]/g, '\n')
    .replace(/\\,/g, ',')
    .replace(/\\;/g, ';')
    .replace(/\\\\/g, '\\');
}

function escapeIcal(value) {
  return String(value || '')
    .replace(/\\/g, '\\\\')
    .replace(/\r?\n/g, '\\n')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,');
}

function splitIcalValues(value) {
  const values = [];
  let current = '';
  let escaped = false;
  for (const character of String(value || '')) {
    if (escaped) {
      current += `\\${character}`;
      escaped = false;
    } else if (character === '\\') {
      escaped = true;
    } else if (character === ',') {
      values.push(unescapeIcal(current));
      current = '';
    } else {
      current += character;
    }
  }
  if (escaped) current += '\\';
  values.push(unescapeIcal(current));
  return values.map((item) => text(item, 80)).filter(Boolean);
}

function foldIcalLine(value) {
  const parts = [];
  let remaining = String(value || '');
  while (remaining.length > 75) {
    parts.push(remaining.slice(0, 75));
    remaining = ` ${remaining.slice(75)}`;
  }
  parts.push(remaining);
  return parts.join('\r\n');
}

function icalDate(value) {
  return String(value || '').replace(/-/g, '');
}

function icalDateTime(date, time) {
  return `${icalDate(date)}T${String(time || '00:00').replace(':', '')}00`;
}

function parseIcalTemporal(value) {
  const raw = String(value || '').trim();
  const dateMatch = raw.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (dateMatch) return { date: `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`, time: '', allDay: true };
  const timedMatch = raw.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(?:\d{2})?(Z)?$/i);
  if (!timedMatch) return null;
  const [, year, month, day, hour, minute, utc] = timedMatch;
  if (!utc) return { date: `${year}-${month}-${day}`, time: `${hour}:${minute}`, allDay: false };
  const local = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute)));
  return { date: toIsoDate(local), time: `${String(local.getHours()).padStart(2, '0')}:${String(local.getMinutes()).padStart(2, '0')}`, allDay: false };
}

function parseIcalProperties(block) {
  const values = new Map();
  for (const line of block) {
    const separator = line.indexOf(':');
    if (separator < 1) continue;
    const key = line.slice(0, separator);
    const name = key.split(';', 1)[0].toUpperCase();
    const item = { value: line.slice(separator + 1), params: key.split(';').slice(1) };
    const current = values.get(name) || [];
    current.push(item);
    values.set(name, current);
  }
  return values;
}

function eventFromIcalBlock(lines, index) {
  const properties = parseIcalProperties(lines);
  const issues = [];
  const first = (name) => properties.get(name)?.[0]?.value || '';
  const start = parseIcalTemporal(first('DTSTART'));
  const end = parseIcalTemporal(first('DTEND'));
  const title = text(unescapeIcal(first('SUMMARY')), 240);
  if (!title) issues.push('Chýba názov udalosti.');
  if (!start || !validDate(start?.date)) issues.push('Chýba alebo je neplatný začiatok udalosti.');
  const allDay = Boolean(start?.allDay);
  let endDate = end?.date || start?.date || '';
  let endTime = end?.time || start?.time || '';
  if (allDay && end?.date) endDate = previousDate(end.date);
  if (allDay && endDate && endDate < start.date) {
    endDate = start.date;
    issues.push('Koniec celodennej udalosti bol pred jej začiatkom.');
  }
  if (!allDay && (!validTime(start?.time) || !validTime(endTime))) {
    issues.push('Časovaná udalosť nemá platný čas začiatku alebo konca.');
  }
  if (!allDay && endDate && `${endDate}T${endTime}` < `${start?.date}T${start?.time}`) {
    issues.push('Koniec udalosti je pred začiatkom.');
  }
  if (!end) issues.push(allDay ? 'Chýbal koniec; použil sa jeden deň.' : 'Chýbal koniec; použil sa čas začiatku.');
  const tags = (properties.get('CATEGORIES') || []).flatMap((item) => splitIcalValues(item.value));
  const recurrence = recurrenceFromIcalRule(first('RRULE'), start?.date || '');
  return {
    key: `ics-${index}`,
    event: {
      title: title || 'Udalosť bez názvu',
      description: text(unescapeIcal(first('DESCRIPTION')), 10_000),
      tags: [...new Set(tags)],
      allDay,
      startDate: start?.date || '',
      startTime: allDay ? '' : start?.time || '',
      endDate: endDate || start?.date || '',
      endTime: allDay ? '' : endTime,
      reminderMinutes: validReminderMinutes(first('X-POZNAMKOVNIK-REMINDER-MINUTES')),
      ...recurrence
    },
    links: [],
    issues,
    sourceId: text(unescapeIcal(first('X-POZNAMKOVNIK-ID')), 160),
    include: !issues.some((issue) => issue.includes('Chýba') || issue.includes('neplatný') || issue.includes('pred jej'))
  };
}

function parseIcal(textValue) {
  const lines = String(textValue || '')
    .replace(/^\uFEFF/, '')
    .replace(/\r?\n[ \t]/g, '')
    .replace(/\r\n?/g, '\n')
    .split('\n');
  const events = [];
  let block = null;
  lines.forEach((line) => {
    const normalized = line.trim().toUpperCase();
    if (normalized === 'BEGIN:VEVENT') {
      block = [];
    } else if (normalized === 'END:VEVENT') {
      if (block) events.push(eventFromIcalBlock(block, events.length + 1));
      block = null;
    } else if (block) {
      block.push(line);
    }
  });
  if (!events.length) throw new Error('Súbor ICS neobsahuje žiadne udalosti.');
  if (events.length > MAX_EVENTS) throw new Error(`Import môže obsahovať najviac ${MAX_EVENTS} udalostí.`);
  return events;
}

function normalizePackageEvent(value, index) {
  const raw = value && typeof value === 'object' ? value : {};
  const event = raw.event && typeof raw.event === 'object' ? raw.event : raw;
  const issues = [];
  const title = text(event.title, 240);
  const startDate = validDate(event.startDate);
  const endDate = validDate(event.endDate || startDate);
  const allDay = Boolean(event.allDay);
  const startTime = allDay ? '' : validTime(event.startTime);
  const endTime = allDay ? '' : validTime(event.endTime);
  if (!title) issues.push('Chýba názov udalosti.');
  if (!startDate || !endDate) issues.push('Chýba alebo je neplatný dátum udalosti.');
  if (startDate && endDate && endDate < startDate) issues.push('Koniec udalosti je pred začiatkom.');
  if (!allDay && (!startTime || !endTime)) issues.push('Časovaná udalosť nemá platný čas začiatku alebo konca.');
  if (!allDay && startDate && endDate && `${endDate}T${endTime}` < `${startDate}T${startTime}`) issues.push('Koniec udalosti je pred začiatkom.');
  const links = Array.isArray(raw.links) ? raw.links
    .filter((link) => LINK_TYPES.has(link?.targetType) && text(link?.targetId, 160))
    .map((link) => ({
      targetType: link.targetType,
      targetId: text(link.targetId, 160),
      title: text(link.title, 240),
      subtitle: text(link.subtitle, 300)
    })) : [];
  const recurrence = normalizeRecurrence(event, startDate);
  const occurrenceOverrides = Array.isArray(event.occurrenceOverrides) ? event.occurrenceOverrides
    .filter((override) => validDate(override?.occurrenceDate))
    .map((override) => ({
      occurrenceDate: validDate(override.occurrenceDate),
      cancelled: Boolean(override.cancelled),
      data: override?.data && typeof override.data === 'object' ? override.data : {}
    })) : [];
  return {
    key: `package-${index}`,
    event: {
      title: title || 'Udalosť bez názvu',
      description: text(event.description, 10_000),
      tags: [...new Set((Array.isArray(event.tags) ? event.tags : []).map((tag) => text(tag, 80)).filter(Boolean))],
      allDay,
      startDate,
      startTime,
      endDate,
      endTime,
      reminderMinutes: validReminderMinutes(event.reminderMinutes),
      ...recurrence,
      occurrenceOverrides
    },
    links,
    issues,
    sourceId: text(event.id || raw.id, 160),
    include: !issues.length
  };
}

async function prepareImport(file) {
  const fileName = text(file?.name, 240) || 'import';
  let events;
  let isPackage = false;
  if (/\.zip$/i.test(fileName)) {
    const entries = await readImportEntries(file);
    const manifestEntry = entries.find((entry) => entry.path === CALENDAR_PACKAGE_PATH);
    if (!manifestEntry) throw new Error('ZIP neobsahuje prenosový balík kalendára Poznámkovníka.');
    if (manifestEntry.blob.size > MAX_PACKAGE_MANIFEST_BYTES) throw new Error('Popis prenosového balíka kalendára je príliš veľký.');
    let manifest;
    try {
      manifest = JSON.parse(await manifestEntry.blob.text());
    } catch {
      throw new Error('Prenosový balík kalendára má neplatný popis obsahu.');
    }
    if (manifest?.format !== 'poznamkovnik-calendar-package' || manifest?.version !== 1 || !Array.isArray(manifest.events)) {
      throw new Error('ZIP neobsahuje podporovaný prenosový balík kalendára.');
    }
    if (manifest.events.length > MAX_EVENTS) throw new Error(`Import môže obsahovať najviac ${MAX_EVENTS} udalostí.`);
    events = manifest.events.map(normalizePackageEvent);
    isPackage = true;
  } else {
    if (!/\.(?:ics|ical)$/i.test(fileName)) throw new Error('Vyber súbor ICS alebo prenosový ZIP balík.');
    if (file.size > MAX_ICAL_BYTES) throw new Error('Súbor ICS môže mať najviac 2 MB.');
    events = parseIcal(await file.text());
  }
  const existingResult = await apiRequest('/calendar-events');
  const existing = Array.isArray(existingResult.events) ? existingResult.events : [];
  const duplicateKeys = new Set(existing.map(eventIdentity));
  events.forEach((entry) => {
    entry.duplicate = duplicateKeys.has(eventIdentity(entry.event));
    if (entry.duplicate) entry.include = false;
  });
  return { fileName, events, isPackage };
}

function eventIdentity(event) {
  const title = text(event?.title, 240).toLocaleLowerCase('sk').replace(/\s+/g, ' ');
  return [
    title, event?.allDay ? 'all-day' : 'timed', event?.startDate, event?.startTime, event?.endDate, event?.endTime,
    event?.recurrenceKind || 'none', event?.recurrenceInterval || 1, event?.recurrenceUntil || ''
  ].join('|');
}

function importSummary(preview) {
  const total = preview.events.length;
  const duplicates = preview.events.filter((entry) => entry.duplicate).length;
  const invalid = preview.events.filter((entry) => entry.issues.length).length;
  const relations = preview.events.reduce((count, entry) => count + entry.links.length, 0);
  return [
    `${total} ${total === 1 ? 'udalosť' : total < 5 ? 'udalosti' : 'udalostí'}`,
    duplicates ? `${duplicates} možných duplicít` : '',
    invalid ? `${invalid} s upozornením` : '',
    relations ? `${relations} väzieb` : ''
  ].filter(Boolean).join(' · ');
}

function eventDateLabel(event) {
  if (event.allDay) return event.startDate === event.endDate ? event.startDate : `${event.startDate} - ${event.endDate}`;
  return `${event.startDate} ${event.startTime} - ${event.endDate} ${event.endTime}`;
}

function renderImportEvents(preview) {
  dom.calendarTransferImportEvents.replaceChildren();
  preview.events.forEach((entry) => {
    const row = document.createElement('label');
    row.className = 'calendar-transfer-import-event';
    if (entry.duplicate) row.classList.add('is-duplicate');
    if (entry.issues.length) row.classList.add('has-issues');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = entry.include;
    checkbox.disabled = Boolean(entry.issues.length);
    checkbox.addEventListener('change', () => {
      entry.include = checkbox.checked;
      updateImportConfirmation(preview);
    });
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = entry.event.title;
    const details = document.createElement('small');
    details.textContent = eventDateLabel(entry.event);
    copy.append(title, details);
    const status = document.createElement('em');
    if (entry.issues.length) status.textContent = entry.issues.join(' ');
    else if (entry.duplicate) status.textContent = 'Možná duplicita';
    else status.textContent = entry.links.length ? `${entry.links.length} väzby` : 'Pripravená';
    row.append(checkbox, copy, status);
    dom.calendarTransferImportEvents.append(row);
  });
}

function renderImportRelations(preview) {
  const relations = preview.events.flatMap((entry) => entry.links.map((link) => ({ ...link, eventTitle: entry.event.title })));
  const resizer = document.getElementById('calendar-transfer-import-resizer');
  dom.calendarTransferImportRelations.hidden = !relations.length;
  resizer.hidden = !relations.length;
  dom.calendarTransferImportRelations.replaceChildren();
  if (!relations.length) return;
  const header = document.createElement('header');
  const heading = document.createElement('strong');
  heading.textContent = 'Väzby prenosového balíka';
  const note = document.createElement('small');
  note.textContent = 'Obnovia sa len k prvkom, ktoré v tejto pracovnej ploche existujú.';
  header.append(heading, note);
  const list = document.createElement('div');
  list.className = 'calendar-transfer-relation-list';
  relations.forEach((relation) => {
    const row = document.createElement('div');
    row.className = 'calendar-transfer-relation';
    const type = document.createElement('span');
    type.textContent = relation.targetType === 'library' ? 'Knižnica' : relation.targetType === 'element' ? 'Text' : 'Zdroj';
    const copy = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = relation.title || 'Pôvodný prvok';
    const detail = document.createElement('small');
    detail.textContent = `${relation.eventTitle} · ${relation.subtitle || 'Väzba udalosti'}`;
    copy.append(title, detail);
    row.append(type, copy);
    list.append(row);
  });
  dom.calendarTransferImportRelations.append(header, list);
}

function updateImportConfirmation(preview) {
  const selected = preview.events.filter((entry) => entry.include).length;
  dom.calendarTransferImportConfirm.disabled = !selected;
  dom.calendarTransferImportConfirm.textContent = selected === 1 ? 'Vytvoriť udalosť' : `Vytvoriť udalosti (${selected})`;
}

function renderImport(preview) {
  dom.calendarTransferImportDescription.textContent = `Nič ešte nebolo uložené. Import sa pripravuje zo súboru „${preview.fileName}“.`;
  dom.calendarTransferImportSummary.textContent = importSummary(preview);
  dom.calendarTransferImportStatus.textContent = preview.events.some((entry) => entry.duplicate)
    ? 'Pravdepodobné duplicity nie sú predvolene vybrané. Môžeš ich zaradiť ručne.'
    : 'Vybrané udalosti sa vytvoria ako nové položky; existujúce sa nemenia.';
  dom.calendarTransferImportStatus.classList.remove('is-error');
  renderImportEvents(preview);
  renderImportRelations(preview);
  updateImportConfirmation(preview);
  fitDialogResizableSection(dom.calendarTransferImportEvents);
  if (!dom.calendarTransferImportRelations.hidden) fitDialogResizableSection(dom.calendarTransferImportRelations);
}

function closeImportDialog() {
  pendingImport = null;
  if (dom.calendarTransferImportDialog.open) dom.calendarTransferImportDialog.close();
}

async function requestImport() {
  dom.calendarTransferInput.value = '';
  dom.calendarTransferInput.click();
}

async function handleImportFile() {
  const file = dom.calendarTransferInput.files?.[0];
  if (!file) return;
  pendingImport = null;
  dom.calendarTransferImportConfirm.disabled = true;
  dom.calendarTransferImportDescription.textContent = 'Kontrolujem udalosti a pripravujem náhľad...';
  dom.calendarTransferImportSummary.textContent = '';
  dom.calendarTransferImportEvents.replaceChildren();
  dom.calendarTransferImportRelations.replaceChildren();
  dom.calendarTransferImportRelations.hidden = true;
  document.getElementById('calendar-transfer-import-resizer').hidden = true;
  dom.calendarTransferImportStatus.textContent = '';
  dom.calendarTransferImportStatus.classList.remove('is-error');
  if (!dom.calendarTransferImportDialog.open) dom.calendarTransferImportDialog.showModal();
  try {
    pendingImport = await prepareImport(file);
    renderImport(pendingImport);
  } catch (error) {
    dom.calendarTransferImportDescription.textContent = 'Náhľad importu sa nepodarilo pripraviť.';
    dom.calendarTransferImportStatus.textContent = error?.message || 'Súbor kalendára sa nepodarilo spracovať.';
    dom.calendarTransferImportStatus.classList.add('is-error');
  }
}

async function confirmImport() {
  if (!pendingImport) return;
  const entries = pendingImport.events.filter((entry) => entry.include);
  if (!entries.length) return;
  dom.calendarTransferImportConfirm.disabled = true;
  dom.calendarTransferImportStatus.textContent = 'Vytváram udalosti a obnovujem dostupné väzby...';
  const warnings = [];
  try {
    for (const entry of entries) {
      const result = await apiRequest('/calendar-events', { method: 'POST', body: { ...entry.event, id: crypto.randomUUID() } });
      for (const override of entry.event.occurrenceOverrides || []) {
        try {
          const query = `?scope=occurrence&occurrenceDate=${encodeURIComponent(override.occurrenceDate)}`;
          if (override.cancelled) {
            await apiRequest(`/calendar-events/${encodeURIComponent(result.event.id)}${query}`, { method: 'DELETE' });
          } else {
            await apiRequest(`/calendar-events/${encodeURIComponent(result.event.id)}`, {
              method: 'PATCH',
              body: { ...override.data, scope: 'occurrence', occurrenceDate: override.occurrenceDate }
            });
          }
        } catch {
          warnings.push(`${entry.event.title}: výnimka série z ${override.occurrenceDate} sa nedala obnoviť.`);
        }
      }
      for (const link of entry.links) {
        try {
          await apiRequest(`/calendar-events/${encodeURIComponent(result.event.id)}/links`, {
            method: 'POST',
            body: { id: crypto.randomUUID(), targetType: link.targetType, targetId: link.targetId }
          });
        } catch {
          warnings.push(`${entry.event.title}: väzba na „${link.title || 'pôvodný prvok'}“ sa nedala obnoviť.`);
        }
      }
    }
    closeImportDialog();
    await importedCallback();
    if (warnings.length) window.alert(`Udalosti boli importované, ale niektoré väzby sa nepodarilo obnoviť:\n\n${warnings.slice(0, 10).join('\n')}${warnings.length > 10 ? '\n…' : ''}`);
  } catch (error) {
    dom.calendarTransferImportStatus.textContent = error?.message || 'Udalosti sa nepodarilo importovať.';
    dom.calendarTransferImportStatus.classList.add('is-error');
    updateImportConfirmation(pendingImport);
  }
}

function toggleExportRange() {
  dom.calendarExportRange.hidden = dom.calendarExportAll.checked;
}

function exportRange() {
  if (dom.calendarExportAll.checked) return { start: '', end: '' };
  const start = validDate(dom.calendarExportStart.value);
  const end = validDate(dom.calendarExportEnd.value);
  if (!start || !end) throw new Error('Vyber začiatok aj koniec obdobia exportu.');
  if (end < start) throw new Error('Koniec obdobia nemôže byť pred začiatkom.');
  return { start, end };
}

async function eventsForExport(range) {
  const query = range.start ? `?from=${encodeURIComponent(range.start)}&to=${encodeURIComponent(range.end)}` : '';
  const result = await apiRequest(`/calendar-events${query}`);
  const events = Array.isArray(result.events) ? result.events : [];
  return [...new Map(events.map((event) => [event.id, event])).values()];
}

function icalForEvents(events) {
  const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Poznamkovník//Kalendár//SK', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH'];
  events.forEach((event) => {
    lines.push('BEGIN:VEVENT');
    lines.push(`UID:${event.id}@poznamkovnik.local`);
    lines.push(`DTSTAMP:${timestamp}`);
    lines.push(`SUMMARY:${escapeIcal(event.title)}`);
    if (event.description) lines.push(`DESCRIPTION:${escapeIcal(event.description)}`);
    if (event.tags?.length) lines.push(`CATEGORIES:${event.tags.map(escapeIcal).join(',')}`);
    if (Number(event.reminderMinutes) >= 0) lines.push(`X-POZNAMKOVNIK-REMINDER-MINUTES:${Number(event.reminderMinutes)}`);
    const rrule = rruleForEvent(event);
    if (rrule) lines.push(`RRULE:${rrule}`);
    if (event.allDay) {
      lines.push(`DTSTART;VALUE=DATE:${icalDate(event.startDate)}`);
      lines.push(`DTEND;VALUE=DATE:${icalDate(nextDate(event.endDate))}`);
    } else {
      lines.push(`DTSTART:${icalDateTime(event.startDate, event.startTime)}`);
      lines.push(`DTEND:${icalDateTime(event.endDate, event.endTime)}`);
    }
    lines.push(`X-POZNAMKOVNIK-ID:${event.id}`);
    lines.push('END:VEVENT');
  });
  lines.push('END:VCALENDAR');
  return `${lines.map(foldIcalLine).join('\r\n')}\r\n`;
}

async function completeEventsForPackage(events) {
  return Promise.all(events.map(async (event) => {
    const result = await apiRequest(`/calendar-events/${encodeURIComponent(event.id)}`);
    return { event: result.event, links: result.event.links || [] };
  }));
}

function setExportBusy(busy, message = '') {
  dom.calendarIcsExport.disabled = busy;
  dom.calendarPackageExport.disabled = busy;
  dom.calendarExportStatus.textContent = message;
  dom.calendarExportStatus.classList.toggle('is-error', Boolean(message));
}

async function exportCalendar(format) {
  try {
    const range = exportRange();
    setExportBusy(true, 'Pripravujem export...');
    const events = await eventsForExport(range);
    const completeEvents = await completeEventsForPackage(events);
    const stamp = range.start ? `${range.start}-${range.end}` : 'vsetky-udalosti';
    if (format === 'ics') {
      downloadBlob(new Blob([icalForEvents(completeEvents.map((item) => item.event))], { type: 'text/calendar;charset=utf-8' }), `${safeFileName(stamp, 'kalendar')}.ics`);
    } else {
      const manifest = {
        format: 'poznamkovnik-calendar-package',
        version: 1,
        exportedAt: new Date().toISOString(),
        events: completeEvents
      };
      const readme = [
        '# Kalendár Poznámkovníka',
        '',
        'Prenosový balík udalostí kalendára pre Poznámkovník.',
        'Zachováva názvy, termíny, štítky, poznámky a údaje o väzbách.'
      ].join('\n').concat('\n');
      const archive = await createStoredZip([
        { name: 'README.md', blob: new Blob([readme], { type: 'text/markdown;charset=utf-8' }) },
        { name: CALENDAR_PACKAGE_PATH, blob: new Blob([JSON.stringify(manifest, null, 2).concat('\n')], { type: 'application/json;charset=utf-8' }) }
      ]);
      downloadBlob(archive, `${safeFileName(stamp, 'kalendar')}-poznamkovnik.zip`);
    }
    if (dom.calendarExportDialog.open) dom.calendarExportDialog.close();
  } catch (error) {
    setExportBusy(false, error?.message || 'Kalendár sa nepodarilo vyexportovať.');
    return;
  }
  setExportBusy(false);
}

function openExportDialog() {
  const range = currentRange();
  dom.calendarExportAll.checked = false;
  dom.calendarExportStart.value = range.start || '';
  dom.calendarExportEnd.value = range.end || '';
  dom.calendarExportStatus.textContent = '';
  dom.calendarExportStatus.classList.remove('is-error');
  toggleExportRange();
  if (!dom.calendarExportDialog.open) dom.calendarExportDialog.showModal();
}

export function initializeCalendarTransfer({ getRange = () => ({ start: '', end: '' }), onImported = async () => {} } = {}) {
  currentRange = getRange;
  importedCallback = onImported;
  installDialogBackdropClose(dom.calendarExportDialog, () => dom.calendarExportDialog.close());
  installDialogBackdropClose(dom.calendarTransferImportDialog, closeImportDialog);
  dom.calendarTransferImportButton.addEventListener('click', () => void requestImport());
  dom.calendarTransferExportButton.addEventListener('click', openExportDialog);
  dom.calendarTransferInput.addEventListener('change', () => void handleImportFile());
  dom.calendarTransferImportCancel.addEventListener('click', closeImportDialog);
  dom.calendarTransferImportConfirm.addEventListener('click', () => void confirmImport());
  dom.calendarExportCancel.addEventListener('click', () => dom.calendarExportDialog.close());
  dom.calendarExportAll.addEventListener('change', toggleExportRange);
  dom.calendarIcsExport.addEventListener('click', () => void exportCalendar('ics'));
  dom.calendarPackageExport.addEventListener('click', () => void exportCalendar('package'));
}
