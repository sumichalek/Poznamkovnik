import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
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

let overview = null;
let semanticTargets = [];
let activeTarget = null;
let requestId = 0;
const visibleGroups = new Set(Object.keys(GROUPS));

function targetKey(item) {
  return `${item.targetType}:${item.targetId}`;
}

function itemIcon(item) {
  if (item.targetType === 'source' || item.targetType === 'tutorial_page') return 'book-open';
  if (item.targetType === 'task') return item.status === 'done' ? 'check' : 'list-check';
  if (item.targetType === 'calendar_event') return 'calendar';
  if (item.targetType === 'library') return 'folder';
  return item.elementType === 'article' ? 'article' : item.elementType === 'folder' ? 'folder' : 'note';
}

function relationshipLabel(item, group) {
  if (item.linkId) return 'Priame prepojenie';
  if (group === 'sources') return 'Odkaz na zdroj';
  if (group === 'elements') return 'Textová väzba';
  if (group === 'tasks') return 'Súvisiaca úloha';
  if (group === 'calendar') return 'Súvisiaca udalosť';
  if (group === 'tutorial') return 'Súvisiaca lekcia';
  return 'Súvisiaca knižnica';
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

function createRelationshipRow(item, group) {
  const row = document.createElement('tr');
  const typeCell = createCell('relationship-type-cell');
  const type = document.createElement('span');
  type.className = `relationship-type relationship-type-${group}`;
  type.append(createAppIcon(itemIcon(item)), document.createTextNode(GROUPS[group].label));
  typeCell.append(type);

  const titleCell = createCell('relationship-title-cell');
  const open = document.createElement('button');
  open.type = 'button';
  open.className = 'relationship-open-button';
  open.textContent = item.title;
  open.title = `Otvoriť: ${item.title}`;
  open.addEventListener('click', () => openTarget(item));
  titleCell.append(open);

  const contextCell = createCell('relationship-context-cell');
  contextCell.textContent = item.subtitle || 'Bez doplňujúceho kontextu';

  const linkCell = createCell('relationship-kind-cell');
  const kind = document.createElement('span');
  kind.className = 'relationship-kind';
  kind.classList.toggle('is-direct', Boolean(item.linkId));
  kind.textContent = relationshipLabel(item, group);
  linkCell.append(kind);

  const actionCell = createCell('relationship-action-cell');
  if (item.linkId) {
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'relationship-unlink-button';
    remove.title = `Odstrániť prepojenie: ${item.title}`;
    remove.setAttribute('aria-label', `Odstrániť prepojenie: ${item.title}`);
    remove.append(createAppIcon('close'));
    remove.addEventListener('click', () => void removeSemanticLink(item.linkId));
    actionCell.append(remove);
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
  dom.relationshipsCreateForm.hidden = false;
  renderCreateTargets();
  dom.relationshipTarget.focus();
}

async function createSemanticLink(event) {
  event.preventDefault();
  if (!activeTarget || !dom.relationshipTarget.value) return;
  try {
    dom.relationshipCreateSave.disabled = true;
    await apiRequest(`/semantic-links/${encodeURIComponent(activeTarget.targetType)}/${encodeURIComponent(activeTarget.targetId)}`, {
      method: 'POST',
      body: {
        id: crypto.randomUUID(),
        targetType: dom.relationshipTargetType.value,
        targetId: dom.relationshipTarget.value
      }
    });
    dom.relationshipsCreateForm.hidden = true;
    await loadRelationships(activeTarget);
  } catch (error) {
    dom.relationshipsStatus.textContent = error?.message || 'Prepojenie sa nepodarilo vytvoriť.';
    renderCreateTargets();
  }
}

export function closeRelationships() {
  requestId += 1;
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
    dom.relationshipsCreateForm.hidden = true;
  });
  dom.relationshipTargetType.addEventListener('change', renderCreateTargets);
  dom.relationshipsCreateForm.addEventListener('submit', (event) => void createSemanticLink(event));
  dom.relationshipsDialog.addEventListener('click', (event) => {
    if (event.target === dom.relationshipsDialog) closeRelationships();
  });
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
