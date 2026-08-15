import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
import { dom } from './dom.js';

const SEARCH_DELAY = 180;

const typeDetails = {
  library: { group: 'Knižnice', label: 'Knižnica', icon: 'folder' },
  folder: { group: 'Knižnice', label: 'Priečinok', icon: 'folder' },
  note: { group: 'Knižnice', label: 'Poznámka', icon: 'note' },
  article: { group: 'Knižnice', label: 'Článok', icon: 'article' },
  source: { group: 'Zdroje', label: 'Zdroj', icon: 'quote' },
  source_collection: { group: 'Zdroje', label: 'Zbierka zdrojov', icon: 'folder' },
  source_file: { group: 'Zdroje', label: 'Súbor zdroja', icon: 'paperclip' },
  task: { group: 'Úlohy', label: 'Úloha', icon: 'list-check' },
  calendar_event: { group: 'Kalendár', label: 'Udalosť', icon: 'calendar' },
  music_track: { group: 'Hudba', label: 'Skladba', icon: 'music' },
  music_playlist: { group: 'Hudba', label: 'Playlist', icon: 'music' },
  tutorial_language: { group: 'Učebnica', label: 'Jazyk', icon: 'book-open' },
  tutorial_page: { group: 'Učebnica', label: 'Časť učebnice', icon: 'article' },
  tutorial_example: { group: 'Učebnica', label: 'Príklad', icon: 'code' },
  tutorial_note: { group: 'Učebnica', label: 'Moja poznámka', icon: 'note' }
};

let searchTimer = 0;
let searchRequestId = 0;

function resultDetail(result) {
  return typeDetails[result.type] || { group: 'Ostatné', label: 'Položka', icon: 'file' };
}

function setStatus(message = '') {
  dom.searchStatus.textContent = message;
  dom.searchStatus.hidden = !message;
}

function clearResults() {
  dom.searchResults.replaceChildren();
}

function renderEmpty(message) {
  clearResults();
  const empty = document.createElement('p');
  empty.className = 'search-empty';
  empty.textContent = message;
  dom.searchResults.append(empty);
}

function renderResults(results) {
  clearResults();
  if (!results.length) {
    renderEmpty('Nenašli sa žiadne položky.');
    return;
  }

  const groups = new Map();
  results.forEach((result) => {
    const detail = resultDetail(result);
    if (!groups.has(detail.group)) groups.set(detail.group, []);
    groups.get(detail.group).push({ result, detail });
  });

  groups.forEach((entries, group) => {
    const section = document.createElement('section');
    section.className = 'search-result-group';
    const heading = document.createElement('h3');
    heading.textContent = group;
    section.append(heading);

    entries.forEach(({ result, detail }) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'search-result';
      button.append(createAppIcon(detail.icon));

      const copy = document.createElement('span');
      copy.className = 'search-result-copy';
      const title = document.createElement('strong');
      title.textContent = result.title;
      const meta = document.createElement('span');
      meta.className = 'search-result-meta';
      meta.textContent = result.preview ? `${detail.label} · ${result.preview}` : detail.label;
      copy.append(title, meta);
      button.append(copy);
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('global-search-open', { detail: result }));
        closeGlobalSearch();
      });
      section.append(button);
    });
    dom.searchResults.append(section);
  });
}

async function requestSearch() {
  const query = dom.searchQuery.value.trim();
  const requestId = ++searchRequestId;
  if (!query) {
    clearResults();
    setStatus('');
    return;
  }

  setStatus('Hľadám...');
  try {
    const result = await apiRequest(`/search?q=${encodeURIComponent(query)}`);
    if (requestId !== searchRequestId || !dom.searchDialog.open) return;
    setStatus('');
    renderResults(result.results || []);
  } catch (error) {
    if (requestId !== searchRequestId || !dom.searchDialog.open) return;
    renderEmpty('Vyhľadávanie sa nepodarilo načítať.');
    setStatus(error?.message || '');
  }
}

function scheduleSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => void requestSearch(), SEARCH_DELAY);
}

export function openGlobalSearch(query = '') {
  if (typeof query === 'string' && query.trim()) dom.searchQuery.value = query.trim();
  if (!dom.searchDialog.open) dom.searchDialog.showModal();
  dom.searchQuery.focus();
  dom.searchQuery.select();
  if (dom.searchQuery.value.trim()) void requestSearch();
}

export function closeGlobalSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = 0;
  if (dom.searchDialog.open) dom.searchDialog.close();
}

export function initializeGlobalSearch() {
  dom.searchButton.addEventListener('click', openGlobalSearch);
  dom.searchClose.addEventListener('click', closeGlobalSearch);
  dom.searchQuery.addEventListener('input', scheduleSearch);
  dom.searchDialog.addEventListener('click', (event) => {
    if (event.target === dom.searchDialog) closeGlobalSearch();
  });
  dom.searchDialog.addEventListener('close', () => {
    window.clearTimeout(searchTimer);
    searchTimer = 0;
    searchRequestId += 1;
    dom.searchQuery.value = '';
    setStatus('');
    clearResults();
  });
}
