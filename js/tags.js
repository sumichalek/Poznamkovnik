import { apiRequest } from './api.js';
import { dom } from './dom.js';
import { openGlobalSearch } from './search.js';

const MAX_TAGS = 20;
const MAX_TAG_LENGTH = 48;

let suggestionTimer = 0;
let suggestionRequestId = 0;
const wiredInputs = new WeakSet();

export function normalizeTags(value) {
  if (!Array.isArray(value)) return [];

  const seen = new Set();
  return value
    .map((tag) => String(tag || '').trim().replace(/^#+/, '').replace(/\s+/g, ' ').slice(0, MAX_TAG_LENGTH))
    .filter((tag) => {
      const key = tag.toLocaleLowerCase('sk');
      if (!tag || seen.has(key) || seen.size >= MAX_TAGS) return false;
      seen.add(key);
      return true;
    });
}

export function parseTagInput(value) {
  return normalizeTags(String(value || '').split(/[;,\n]/));
}

export function formatTags(tags) {
  return normalizeTags(tags).join(', ');
}

export function renderTagChips(container, tags) {
  if (!container) return;
  const normalized = normalizeTags(tags);
  container.replaceChildren();
  container.hidden = !normalized.length;

  normalized.forEach((tag) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'tag-chip';
    chip.textContent = `#${tag}`;
    chip.title = `Vyhľadať štítok „${tag}“`;
    chip.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openGlobalSearch(tag);
    });
    container.append(chip);
  });
}

export function setTagField(input, chips, tags) {
  if (!input) return;
  input.value = formatTags(tags);
  renderTagChips(chips, tags);
}

export function readTagField(input) {
  return parseTagInput(input?.value);
}

function suggestionQuery(value) {
  return String(value || '').split(/[;,\n]/).at(-1).trim().replace(/^#+/, '');
}

function renderSuggestions(tags) {
  if (!dom.tagSuggestions) return;
  dom.tagSuggestions.replaceChildren();
  tags.forEach((tag) => {
    const option = document.createElement('option');
    option.value = tag.name;
    option.label = `${tag.name} (${tag.count})`;
    dom.tagSuggestions.append(option);
  });
}

export function refreshTagSuggestions(query = '') {
  window.clearTimeout(suggestionTimer);
  suggestionTimer = window.setTimeout(async () => {
    const requestId = ++suggestionRequestId;
    try {
      const result = await apiRequest(`/tags?q=${encodeURIComponent(query)}`);
      if (requestId === suggestionRequestId) renderSuggestions(result.tags || []);
    } catch {
      if (requestId === suggestionRequestId) renderSuggestions([]);
    }
  }, 120);
}

export function wireTagInput(input, chips) {
  if (!input || wiredInputs.has(input)) return;
  wiredInputs.add(input);
  input.addEventListener('input', () => {
    renderTagChips(chips, parseTagInput(input.value));
    refreshTagSuggestions(suggestionQuery(input.value));
  });
  input.addEventListener('focus', () => refreshTagSuggestions(suggestionQuery(input.value)));
  input.addEventListener('change', () => {
    const tags = parseTagInput(input.value);
    input.value = formatTags(tags);
    renderTagChips(chips, tags);
  });
}
