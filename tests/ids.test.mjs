import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../js/ids.js', import.meta.url), 'utf8').replace(/^export /gm, '');
const script = new vm.Script(`'use strict';\n${source}`, { filename: 'js/ids.js' });
const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function generator(crypto) {
  const context = vm.createContext({ crypto });
  script.runInContext(context);
  return context.createId;
}

test('ID generation uses native randomUUID with its Crypto receiver when available', () => {
  let calls = 0;
  const crypto = {
    randomUUID() { assert.equal(this, crypto); calls += 1; return 'fixture-native-id'; },
    getRandomValues() { assert.fail('Native UUID must not need a second randomness source'); },
  };
  assert.equal(generator(crypto)(), 'fixture-native-id');
  assert.equal(calls, 1);
});

test('LAN HTTP fallback produces UUID v4 from all 16 supplied random bytes', () => {
  for (const [values, expected] of [
    [Array(16).fill(0), '00000000-0000-4000-8000-000000000000'],
    [Array(16).fill(255), 'ffffffff-ffff-4fff-bfff-ffffffffffff'],
    [Array.from({ length: 16 }, (_, index) => index), '00010203-0405-4607-8809-0a0b0c0d0e0f'],
  ]) {
    let calls = 0;
    const crypto = {
      getRandomValues(bytes) {
        assert.equal(this, crypto);
        assert.equal(bytes.byteLength, 16);
        bytes.set(values);
        calls += 1;
        return bytes;
      },
    };
    const id = generator(crypto)();
    assert.equal(id, expected);
    assert.match(id, uuidV4);
    assert.equal(calls, 1);
  }
});

test('fallback uses fresh secure randomness for each ID without native randomUUID', () => {
  let calls = 0;
  const createId = generator({ getRandomValues(bytes) { calls += 1; return webcrypto.getRandomValues(bytes); } });
  const ids = Array.from({ length: 1000 }, () => createId());
  ids.forEach(id => assert.match(id, uuidV4));
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(calls, ids.length);
});

test('missing secure randomness fails explicitly instead of using a weak fallback', () => {
  for (const crypto of [undefined, null, {}, { randomUUID: null }]) {
    assert.throws(generator(crypto), /bezpečné generovanie identifikátorov/);
  }
  assert.doesNotMatch(source, /Math\.random|Date\.now/);
});

test('an entropy failure propagates instead of returning a predictable identifier', () => {
  const createId = generator({ getRandomValues() { throw new Error('fixture entropy failure'); } });
  assert.throws(createId, /fixture entropy failure/);
});

test('application modules use the shared ID helper instead of direct randomUUID calls', () => {
  for (const name of readdirSync(new URL('../js/', import.meta.url)).filter(name => name.endsWith('.js'))) {
    if (name === 'ids.js') continue;
    const contents = readFileSync(new URL(`../js/${name}`, import.meta.url), 'utf8');
    assert.equal(/\brandomUUID\s*\(/.test(contents), false, name);
    if (/\bcreateId\s*\(/.test(contents)) {
      assert.equal(/import \{ createId \} from '\.\/ids\.js';/.test(contents), true, name);
    }
  }
});
