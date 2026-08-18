import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
import { installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';

const SEMANTIC_TARGET_TYPES = new Set(['element', 'source', 'tutorial_page', 'task', 'calendar_event']);
const GROUPS = {
  libraries: { label: 'Knižnica', icon: 'folder' },
  elements: { label: 'Text', icon: 'note' },
  sources: { label: 'Zdroj', icon: 'book-open' },
  tutorial: { label: 'Učebnica', icon: 'book-open' },
  tasks: { label: 'Úloha', icon: 'list-check' },
  calendar: { label: 'Kalendár', icon: 'calendar' }
};

const semanticRelationLabels = {
  related: 'Súvisí s',
  reference: 'Referenčná väzba',
  comparison: 'Porovnanie',
  study: 'Na štúdium'
};
const USES_INITIAL_LIMIT = 8;

let overview = null;
let semanticTargets = [];
let activeTarget = null;
let requestId = 0;
let editingLinkId = '';
const visibleGroups = new Set(Object.keys(GROUPS));
const expandedUseKeys = new Set();
const usesCache = new Map();
const usesDisplayLimits = new Map();

function targetKey(item) {
  return `${item.targetType}:${item.targetId}`;
}

function resetUses() {
  expandedUseKeys.clear();
  usesCache.clear();
  usesDisplayLimits.clear();
}

function overviewItems(value, { excludeTarget = null } = {}) {
  const excludedKey = excludeTarget ? targetKey(excludeTarget) : '';
  return Object.entries(GROUPS).flatMap(([group]) =>
    (value?.groups?.[group] || [])
      .filter((item) => targetKey(item) !== excludedKey)
      .map((item) => ({ item, group }))
  );
}

function itemIcon(item) {
  if (item.targetType === 'source' || item.targetType === 'tutorial_page') return 'book-open';
  if (item.targetType === 'task') return item.status === 'done' ? 'check' : 'list-check';
  if (item.targetType === 'calendar_event') return 'calendar';
  if (item.targetType === 'library') return 'folder';
  return item.elementType === 'article' ? 'article' : item.elementType === 'folder' ? 'folder' : 'note';
}

function relationshipLabel(item, group) {
  if (item.linkId) return semanticRelationLabels[item.relationType] || 'Súvisí s';
  if (group === 'sources') return 'Odkaz na zdroj';
  if (group === 'elements') return 'Textová väzba';
  if (group === 'tasks') return 'Súvisiaca úloha';
  if (group === 'calendar') return 'Súvisiaca udalosť';
  if (group === 'tutorial') return 'Súvisiaca lekcia';
  return 'Súvisiaca knižnica';
}

function useCountLabel(count) {
  if (count === 1) return 'výskyt';
  if (count >= 2 && count <= 4) return 'výskyty';
  return 'výskytov';
}

function updateFilters() {
  dom.relationshipFilterButtons.forEach((button) => {
    const group = button.dataset.relationshipFilter;
    const count = overview?.groups?.[group]?.length || 0;
    const active = visibleGroups.has(group);
    button.classList.toggle('is-active', active);
    button.disabled = !count;
    button.setAttribute('aria-pressed', String(active));
    button.querySelector('small').textContent = count ? String(count) : '';
  });
}

function canCreateLinks() {
  return Boolean(activeTarget && SEMANTIC_TARGET_TYPES.has(activeTarget.targetType));
}

function updateCreateControls() {
  const available = canCreateLinks();
  dom.relationshipsAdd.hidden = !available;
  if (!available) dom.relationshipsCreateForm.hidden = true;
}

function resetLinkForm() {
  editingLinkId = '';
  dom.relationshipTargetType.disabled = false;
  dom.relationshipTarget.disabled = false;
  dom.relationshipTargetType.value = 'element';
  dom.relationshipRelationType.value = 'related';
  dom.relationshipNote.value = '';
  dom.relationshipCreateSave.title = 'Pripojiť';
  dom.relationshipCreateSave.setAttribute('aria-label', 'Uložiť prepojenie');
}

function openTarget(item) {
  closeRelationships();
  window.dispatchEvent(new CustomEvent('relationship-open', { detail: item }));
}

async function removeSemanticLink(linkId) {
  if (!linkId || !activeTarget) return;
  try {
    await apiRequest(`/semantic-links/${encodeURIComponent(linkId)}`, { method: 'DELETE' });
    await loadRelationships(activeTarget);
  } catch (error) {
    dom.relationshipsStatus.textContent = error?.message || 'Prepojenie sa nepodarilo odstrániť.';
  }
}

function createCell(className = '') {
  const cell = document.createElement('td');
  if (className) cell.className = className;
  return cell;
}

function createUsesToggle(item) {
  const key = targetKey(item);
  const expanded = expandedUseKeys.has(key);
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'relationship-uses-toggle';
  toggle.title = expanded ? `Skryť ďalšie použitia: ${item.title}` : `Zobraziť ďalšie použitia: ${item.title}`;
  toggle.setAttribute('aria-label', toggle.title);
  toggle.setAttribute('aria-expanded', String(expanded));
  toggle.append(createAppIcon(expanded ? 'chevron-down' : 'chevron-right'));
  toggle.addEventListener('click', () => void toggleUses(item));
  return toggle;
}

function createUseItem({ item, group }) {
  const use = document.createElement('button');
  use.type = 'button';
  use.className = 'relationship-use-item';
  use.title = `Otvoriť: ${item.title}`;
  use.append(createAppIcon(itemIcon(item), 'relationship-use-icon'));

  const copy = document.createElement('span');
  copy.className = 'relationship-use-copy';
  const title = document.createElement('strong');
  title.textContent = item.title;
  const context = document.createElement('small');
  context.textContent = item.subtitle || GROUPS[group].label;
  copy.append(title, context);

  const kind = document.createElement('span');
  kind.className = 'relationship-kind relationship-use-kind';
  kind.classList.toggle('is-direct', Boolean(item.linkId));
  kind.textContent = relationshipLabel(item, group);
  use.append(copy, kind);
  use.addEventListener('click', () => openTarget(item));
  return use;
}

function createUsesRow(item) {
  const key = targetKey(item);
  const entry = usesCache.get(key);
  const row = document.createElement('tr');
  row.className = 'relationship-uses-row';
  const cell = document.createElement('td');
  cell.colSpan = 5;
  const panel = document.createElement('div');
  panel.className = 'relationship-uses-panel';

  if (!entry || entry.status === 'loading') {
    const message = document.createElement('p');
    message.className = 'relationship-uses-message';
    message.textContent = 'Načítavam ďalšie použitia...';
    panel.append(message);
  } else if (entry.status === 'error') {
    const message = document.createElement('p');
    message.className = 'relationship-uses-message is-error';
    message.textContent = entry.message || 'Ďalšie použitia sa nepodarilo načítať.';
    panel.append(message);
  } else if (!entry.items.length) {
    const message = document.createElement('p');
    message.className = 'relationship-uses-message';
    message.textContent = 'Ďalšie priame použitie sa nenašlo.';
    panel.append(message);
  } else {
    const header = document.createElement('div');
    header.className = 'relationship-uses-header';
    const title = document.createElement('strong');
    title.textContent = 'Použité inde';
    const count = document.createElement('small');
    count.textContent = `${entry.items.length} ${useCountLabel(entry.items.length)}`;
    header.append(title, count);

    const list = document.createElement('div');
    list.className = 'relationship-uses-list';
    const limit = usesDisplayLimits.get(key) || USES_INITIAL_LIMIT;
    entry.items.slice(0, limit).forEach((use) => list.append(createUseItem(use)));
    panel.append(header, list);

    if (entry.items.length > limit) {
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'relationship-uses-more';
      more.textContent = `Zobraziť ďalšie (${entry.items.length - limit})`;
      more.addEventListener('click', () => {
        usesDisplayLimits.set(key, limit + USES_INITIAL_LIMIT);
        renderTable();
      });
      panel.append(more);
    }
  }

  cell.append(panel);
  row.append(cell);
  return row;
}

async function toggleUses(item) {
  const key = targetKey(item);
  if (expandedUseKeys.has(key)) {
    expandedUseKeys.delete(key);
    renderTable();
    return;
  }

  expandedUseKeys.add(key);
  usesDisplayLimits.set(key, USES_INITIAL_LIMIT);
  if (usesCache.has(key)) {
    renderTable();
    return;
  }

  const openedFor = targetKey(activeTarget || {});
  usesCache.set(key, { status: 'loading', items: [] });
  renderTable();
  try {
    const result = await apiRequest(`/relationships/${encodeURIComponent(item.targetType)}/${encodeURIComponent(item.targetId)}`);
    if (openedFor !== targetKey(activeTarget || {})) return;
    usesCache.set(key, { status: 'ready', items: overviewItems(result.overview, { excludeTarget: activeTarget }) });
  } catch (error) {
    if (openedFor !== targetKey(activeTarget || {})) return;
    usesCache.set(key, { status: 'error', items: [], message: error?.message || '' });
  }
  renderTable();
}

function createRelationshipRow(item, group) {
  const row = document.createElement('tr');
  const typeCell = createCell('relationship-type-cell');
  const type = document.createElement('span');
  type.className = `relationship-type relationship-type-${group}`;
  type.append(createAppIcon(itemIcon(item)), document.createTextNode(GROUPS[group].label));
  typeCell.append(type);

  const titleCell = createCell('relationship-title-cell');
  const titleContent = document.createElement('div');
  titleContent.className = 'relationship-title-content';
  titleContent.append(createUsesToggle(item));
  const open = document.createElement('button');
  open.type = 'button';
  open.className = 'relationship-open-button';
  open.textContent = item.title;
  open.title = `Otvoriť: ${item.title}`;
  open.addEventListener('click', () => openTarget(item));
  titleContent.append(open);
  titleCell.append(titleContent);

  const contextCell = createCell('relationship-context-cell');
  contextCell.textContent = item.subtitle || 'Bez doplňujúceho kontextu';

  const linkCell = createCell('relationship-kind-cell');
  const kind = document.createElement('span');
  kind.className = 'relationship-kind';
  kind.classList.toggle('is-direct', Boolean(item.linkId));
  kind.textContent = relationshipLabel(item, group);
  linkCell.append(kind);
  if (item.linkNote) {
    const note = document.createElement('small');
    note.className = 'relationship-link-note';
    note.textContent = item.linkNote;
    note.title = item.linkNote;
    linkCell.append(note);
  }

  const actionCell = createCell('relationship-action-cell');
  if (item.linkId) {
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'relationship-edit-button';
    edit.title = `Upraviť prepojenie: ${item.title}`;
    edit.setAttribute('aria-label', `Upraviť prepojenie: ${item.title}`);
    edit.append(createAppIcon('pencil'));
    edit.addEventListener('click', () => openEditForm(item));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'relationship-unlink-button';
    remove.title = `Odstrániť prepojenie: ${item.title}`;
    remove.setAttribute('aria-label', `Odstrániť prepojenie: ${item.title}`);
    remove.append(createAppIcon('close'));
    remove.addEventListener('click', () => void removeSemanticLink(item.linkId));
    actionCell.append(edit, remove);
  } else {
    actionCell.setAttribute('aria-label', 'Automaticky zistená väzba');
  }

  row.append(typeCell, titleCell, contextCell, linkCell, actionCell);
  return row;
}

function renderTable() {
  updateFilters();
  updateCreateControls();
  dom.relationshipsTableBody.replaceChildren();
  if (!overview) {
    dom.relationshipsTableWrap.hidden = true;
    return;
  }

  let visibleCount = 0;
  Object.entries(GROUPS).forEach(([group]) => {
    if (!visibleGroups.has(group)) return;
    const items = overview.groups?.[group] || [];
    items.forEach((item) => {
      visibleCount += 1;
      dom.relationshipsTableBody.append(createRelationshipRow(item, group));
      if (expandedUseKeys.has(targetKey(item))) {
        dom.relationshipsTableBody.append(createUsesRow(item));
      }
    });
  });

  dom.relationshipsTableWrap.hidden = !visibleCount;
  dom.relationshipsStatus.textContent = visibleCount
    ? `${visibleCount} zobrazených súvislostí. Kliknutím na názov otvoríš príslušný prvok.`
    : 'Tento prvok zatiaľ nemá žiadne zobrazené súvislosti.';
}

function renderCreateTargets() {
  const targetType = dom.relationshipTargetType.value;
  const linked = new Set(Object.values(overview?.groups || {}).flat().map((item) => targetKey(item)));
  const targets = semanticTargets.filter(
    (target) => target.targetType === targetType && targetKey(target) !== targetKey(activeTarget || {}) && !linked.has(targetKey(target))
  );
  dom.relationshipTarget.replaceChildren();
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = targets.length ? 'Vyber prvok' : 'Nie je čo pripojiť';
  dom.relationshipTarget.append(empty);
  targets.forEach((target) => {
    const option = document.createElement('option');
    option.value = target.targetId;
    option.textContent = target.subtitle ? `${target.title} - ${target.subtitle}` : target.title;
    dom.relationshipTarget.append(option);
  });
  dom.relationshipTarget.disabled = !targets.length;
  dom.relationshipCreateSave.disabled = !targets.length;
}

function openCreateForm() {
  if (!canCreateLinks()) return;
  resetLinkForm();
  dom.relationshipsCreateForm.hidden = false;
  renderCreateTargets();
  dom.relationshipTarget.focus();
}

function openEditForm(item) {
  if (!item?.linkId) return;
  editingLinkId = item.linkId;
  dom.relationshipsCreateForm.hidden = false;
  dom.relationshipTargetType.value = item.targetType;
  dom.relationshipTargetType.disabled = true;
  dom.relationshipTarget.replaceChildren();
  const target = document.createElement('option');
  target.value = item.targetId;
  target.textContent = item.subtitle ? `${item.title} - ${item.subtitle}` : item.title;
  dom.relationshipTarget.append(target);
  dom.relationshipTarget.value = item.targetId;
  dom.relationshipTarget.disabled = true;
  dom.relationshipRelationType.value = semanticRelationLabels[item.relationType] ? item.relationType : 'related';
  dom.relationshipNote.value = item.linkNote || '';
  dom.relationshipCreateSave.disabled = false;
  dom.relationshipCreateSave.title = 'Uložiť úpravu prepojenia';
  dom.relationshipCreateSave.setAttribute('aria-label', 'Uložiť úpravu prepojenia');
  dom.relationshipRelationType.focus();
}

async function saveSemanticLink(event) {
  event.preventDefault();
  if (!activeTarget || (!editingLinkId && !dom.relationshipTarget.value)) return;
  try {
    dom.relationshipCreateSave.disabled = true;
    if (editingLinkId) {
      await apiRequest(`/semantic-links/${encodeURIComponent(editingLinkId)}`, {
        method: 'PATCH',
        body: {
          relationType: dom.relationshipRelationType.value,
          note: dom.relationshipNote.value
        }
      });
    } else {
      await apiRequest(`/semantic-links/${encodeURIComponent(activeTarget.targetType)}/${encodeURIComponent(activeTarget.targetId)}`, {
        method: 'POST',
        body: {
          id: crypto.randomUUID(),
          targetType: dom.relationshipTargetType.value,
          targetId: dom.relationshipTarget.value,
          relationType: dom.relationshipRelationType.value,
          note: dom.relationshipNote.value
        }
      });
    }
    resetLinkForm();
    dom.relationshipsCreateForm.hidden = true;
    await loadRelationships(activeTarget);
  } catch (error) {
    dom.relationshipsStatus.textContent = error?.message || 'Prepojenie sa nepodarilo vytvoriť.';
    renderCreateTargets();
  }
}

export function closeRelationships() {
  requestId += 1;
  resetLinkForm();
  resetUses();
  dom.relationshipsCreateForm.hidden = true;
  activeTarget = null;
  if (dom.relationshipsDialog.open) dom.relationshipsDialog.close();
}

async function loadRelationships(target) {
  if (!target?.targetType || !target?.targetId) return;
  const currentRequest = ++requestId;
  activeTarget = { targetType: target.targetType, targetId: target.targetId };
  overview = null;
  semanticTargets = [];
  resetLinkForm();
  resetUses();
  visibleGroups.clear();
  Object.keys(GROUPS).forEach((group) => visibleGroups.add(group));
  dom.relationshipsCreateForm.hidden = true;
  updateFilters();
  updateCreateControls();
  dom.relationshipsTitle.textContent = 'Prepojenia';
  dom.relationshipsSubtitle.textContent = 'Načítavam súvislosti';
  dom.relationshipsStatus.textContent = 'Načítavam prepojenia...';
  dom.relationshipsTableWrap.hidden = true;
  if (!dom.relationshipsDialog.open) dom.relationshipsDialog.showModal();

  try {
    const relationshipRequest = apiRequest(`/relationships/${encodeURIComponent(activeTarget.targetType)}/${encodeURIComponent(activeTarget.targetId)}`);
    const targetsRequest = canCreateLinks() ? apiRequest('/relationship-targets') : Promise.resolve({ targets: [] });
    const [relationshipResult, targetsResult] = await Promise.all([relationshipRequest, targetsRequest]);
    if (currentRequest !== requestId || !dom.relationshipsDialog.open) return;
    overview = relationshipResult.overview;
    semanticTargets = targetsResult.targets || [];
    dom.relationshipsTitle.textContent = overview.focus.title;
    dom.relationshipsSubtitle.textContent = overview.focus.subtitle || 'Prepojenia';
    renderTable();
  } catch (error) {
    if (currentRequest !== requestId || !dom.relationshipsDialog.open) return;
    dom.relationshipsStatus.textContent = error?.message || 'Prepojenia sa nepodarilo načítať.';
  }
}

export async function openRelationships({ targetType, targetId } = {}) {
  await loadRelationships({ targetType, targetId });
}

export function initializeRelationships() {
  dom.relationshipsClose.addEventListener('click', closeRelationships);
  dom.relationshipsAdd.addEventListener('click', openCreateForm);
  dom.relationshipCreateCancel.addEventListener('click', () => {
    resetLinkForm();
    dom.relationshipsCreateForm.hidden = true;
  });
  dom.relationshipTargetType.addEventListener('change', renderCreateTargets);
  dom.relationshipsCreateForm.addEventListener('submit', (event) => void saveSemanticLink(event));
  installDialogBackdropClose(dom.relationshipsDialog, closeRelationships);
  dom.relationshipFilterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const group = button.dataset.relationshipFilter;
      if (!group || button.disabled) return;
      if (visibleGroups.has(group)) visibleGroups.delete(group);
      else visibleGroups.add(group);
      renderTable();
    });
  });
}
