import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const copy = value => JSON.parse(JSON.stringify(value));

function element() {
  const classes = new Set();
  return {
    value: '', textContent: '', hidden: false, disabled: false, children: [], dataset: {}, attributes: {}, className: '',
    get innerHTML() { return this.html || ''; },
    set innerHTML(value) { this.html = value; this.children = []; },
    classList: {
      add(name) { classes.add(name); }, remove(name) { classes.delete(name); }, contains(name) { return classes.has(name); },
      toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
    },
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    addEventListener() {}, focus() {},
    querySelectorAll() { return this.children.filter(child => child.className.split(' ').includes('library-row')); },
  };
}

async function fixture({ crypto = { getRandomValues: bytes => webcrypto.getRandomValues(bytes) }, workspace } = {}) {
  const local = new Map();
  const requests = [];
  let remote = copy(workspace || { libraries: [], libraryElements: {} });
  const state = {
    libraries: [], libraryElements: {}, activeLibraryId: '', activeDetailLibraryId: '', editingLibraryId: '',
    librariesPanelPinned: false, libraryDetailPanelPinned: false,
  };
  const dom = Object.fromEntries([
    'libraryForm', 'libraryNameInput', 'libraryTags', 'libraryTagChips', 'librariesList', 'libraryEditButton',
    'libraryDeleteButton', 'librariesPanel', 'libraryDetailPanel', 'librariesButton',
  ].map(key => [key, element()]));
  dom.libraryForm.hidden = true;
  dom.libraryForm.reset = () => { dom.libraryNameInput.value = ''; dom.libraryTags.value = ''; };
  dom.libraryForm.reportValidity = () => Boolean(dom.libraryNameInput.value.trim()) && dom.libraryNameInput.value.length <= 80;
  const context = vm.createContext({
    state, dom, crypto, isSecureContext: false,
    elementTypes: new Set(['note', 'article', 'folder']), themes: new Set(['focus']),
    storageKeys: { libraries: 'libraries', libraryElements: 'elements', activeLibrary: 'active', workspaceOwner: 'owner' },
    localStorage: {
      getItem: key => local.get(key) ?? null,
      setItem: (key, value) => local.set(key, String(value)),
      removeItem: key => local.delete(key),
    },
    window: { clearTimeout() {}, setTimeout() { return 1; }, dispatchEvent() {} },
    document: { body: element(), createElement: () => element() },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options?.detail; } },
    renderLibraryDetailPanel() {}, updateTopbarVisibility() {},
    apiRequest: async (path, options = {}) => {
      assert.equal(path, '/workspace');
      requests.push({ path, method: options.method || 'GET' });
      if (options.method === 'PUT') remote = copy(options.body);
      return copy(remote);
    },
  });
  // Execute real ID, tag, persistence and form controllers with only external UI/API dependencies replaced.
  for (const name of ['ids', 'tags', 'storage', 'library-panels']) {
    const source = readFileSync(new URL(`../js/${name}.js`, import.meta.url), 'utf8')
      .replace(/^import[\s\S]*?;\n/gm, '')
      .replace(/^export (?=(?:async )?function )/gm, '');
    new vm.Script(`'use strict';\n${source}`, { filename: `js/${name}.js` }).runInContext(context);
  }
  await context.hydrateWorkspace({ id: 'fixture-owner' });
  return { context, dom, state, requests, local, get remote() { return copy(remote); } };
}

test('library form creates and persists the named/tagged library over LAN HTTP without randomUUID', async () => {
  const app = await fixture();
  assert.equal(app.context.isSecureContext, false);
  assert.equal(typeof app.context.crypto.randomUUID, 'undefined');
  app.context.showLibraryForm();
  app.dom.libraryNameInput.value = 'Tvorivá knižnica';
  app.dom.libraryTags.value = 'tvorba';

  assert.equal(app.context.saveLibraryFormDraft(), true);
  await app.context.flushWorkspaceSync();

  const library = app.remote.libraries[0];
  assert.match(library.id, uuidV4);
  assert.equal(library.name, 'Tvorivá knižnica');
  assert.deepEqual(library.tags, ['tvorba']);
  assert.equal(app.state.activeLibraryId, library.id);
  assert.equal(app.dom.libraryForm.hidden, true);
  assert.equal(app.dom.librariesList.children[0].children[0].textContent, library.name);
  assert.equal(JSON.parse(app.local.get('libraries'))[0].id, library.id);
  assert.deepEqual(app.requests.map(request => request.method), ['GET', 'PUT']);
});

test('multiple new libraries receive distinct IDs and are all persisted', async () => {
  const app = await fixture();
  for (const name of ['Prvá knižnica', 'Druhá knižnica']) {
    app.context.showLibraryForm();
    app.dom.libraryNameInput.value = name;
    assert.equal(app.context.saveLibraryFormDraft(), true);
    await app.context.flushWorkspaceSync();
  }
  const libraries = app.remote.libraries;
  assert.equal(libraries.length, 2);
  assert.notEqual(libraries[0].id, libraries[1].id);
  libraries.forEach(library => assert.match(library.id, uuidV4));
  assert.equal(app.dom.librariesList.children.length, 2);
});

test('editing a library preserves its ID, existing note and relationships without generating IDs', async () => {
  const libraryId = '00000000-0000-4000-8000-000000000001';
  const note = { id: '00000000-0000-4000-8000-000000000002', type: 'note', parentId: '', title: 'Poznámka', content: 'Zachovať', tags: [], createdAt: '2026-01-01', updatedAt: '2026-01-01' };
  const app = await fixture({
    crypto: { getRandomValues() { throw new Error('Editing must not generate an ID'); } },
    workspace: {
      libraries: [{ id: libraryId, name: 'Pôvodná', tags: [], createdAt: '2026-01-01' }],
      libraryElements: { [libraryId]: [note] },
    },
  });
  app.context.showLibraryForm(app.state.libraries[0]);
  app.dom.libraryNameInput.value = 'Upravená';
  app.dom.libraryTags.value = 'tvorba';
  assert.equal(app.context.saveLibraryFormDraft(), true);
  await app.context.flushWorkspaceSync();
  assert.equal(app.remote.libraries.length, 1);
  assert.equal(app.remote.libraries[0].id, libraryId);
  assert.equal(app.remote.libraries[0].name, 'Upravená');
  assert.deepEqual(app.remote.libraryElements, { [libraryId]: [note] });
});

test('an invalid library name leaves the form and server unchanged', async () => {
  const app = await fixture();
  app.context.showLibraryForm();
  app.dom.libraryTags.value = 'tvorba';
  assert.equal(app.context.saveLibraryFormDraft(), false);
  assert.equal(app.dom.libraryForm.hidden, false);
  assert.equal(app.state.libraries.length, 0);
  assert.equal(app.remote.libraries.length, 0);
  assert.equal(app.requests.length, 1);
});

test('missing cryptographic randomness never mutates the library draft or workspace', async () => {
  const app = await fixture({ crypto: {} });
  app.context.showLibraryForm();
  app.dom.libraryNameInput.value = 'Zachovať rozpracovanú';
  app.dom.libraryTags.value = 'tvorba';
  assert.throws(() => app.context.saveLibraryFormDraft(), /bezpečné generovanie identifikátorov/);
  assert.equal(app.dom.libraryForm.hidden, false);
  assert.equal(app.dom.libraryNameInput.value, 'Zachovať rozpracovanú');
  assert.equal(app.state.libraries.length, 0);
  assert.equal(app.remote.libraries.length, 0);
  assert.equal(app.requests.length, 1);
});

test('normalizing imported libraries and notes supplies missing UUIDs without replacing existing IDs', async () => {
  const app = await fixture();
  const existing = '00000000-0000-4000-8000-000000000001';
  const libraries = app.context.normalizeLibraries([{ name: 'Import' }, { id: existing, name: 'Pôvodná' }]);
  const notes = app.context.normalizeLibraryElementList([{ type: 'note', title: 'Import' }, { id: existing, type: 'note', title: 'Pôvodná' }]);
  assert.match(libraries[0].id, uuidV4);
  assert.match(notes[0].id, uuidV4);
  assert.equal(libraries[1].id, existing);
  assert.equal(notes[1].id, existing);
});
