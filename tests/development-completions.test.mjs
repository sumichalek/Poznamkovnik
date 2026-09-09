import assert from 'node:assert/strict';
import test from 'node:test';

import { projectCompletionEntries } from '../js/development-completions.js';

function entryMap(language, files) {
  return new Map(projectCompletionEntries(language, files).map((entry) => [entry.label, entry]));
}

test('C suggestions contain declarations and ignore comments and strings', () => {
  const entries = entryMap('c', [{
    title: 'main.c',
    current: true,
    content: [
      '#define MAX_COUNT 16',
      'int sum_values(int first, int second) {',
      '  int total = first + second;',
      '  const char *message = "hiddenName";',
      '  // ignoredName',
      '  return total;',
      '}',
    ].join('\n'),
  }]);

  for (const name of ['MAX_COUNT', 'sum_values', 'first', 'second', 'total', 'message']) {
    assert.ok(entries.has(name), `${name} should be offered`);
  }
  assert.match(entries.get('sum_values')?.detail || '', /^sum_values\(int first, int second\) · /);
  assert.equal(entries.get('sum_values')?.template, 'sum_values(${1:first}, ${2:second})');
  assert.equal(entries.has('hiddenName'), false);
  assert.equal(entries.has('ignoredName'), false);
});

test('current source wins over an older project snapshot', () => {
  const entries = entryMap('javascript', [
    { title: 'main.js', path: 'main.js', content: 'const removedName = 1;\n' },
    { title: 'helper.js', path: 'helper.js', content: 'export function helper() {}\n' },
    { title: 'main.js', path: 'main.js', current: true, content: 'const freshName = helper;\n' },
  ]);

  assert.equal(entries.has('removedName'), false);
  assert.equal(entries.get('freshName')?.detail, 'v otvorenom súbore');
  assert.equal(entries.get('helper')?.detail, 'helper() · v helper.js');
});

test('dynamic languages retain their declaration syntax in suggestions', () => {
  const python = entryMap('python', [{
    title: 'lesson.py',
    current: true,
    content: 'import math as maths\ndef scale(value):\n    result = value * 2\n    return result\n',
  }]);
  for (const name of ['maths', 'scale', 'value', 'result']) assert.ok(python.has(name), name);

  const php = entryMap('php', [{
    title: 'lesson.php',
    current: true,
    content: 'function greet($name) {\n  $message = $name;\n  return $message;\n}\n',
  }]);
  for (const name of ['greet', '$name', '$message']) assert.ok(php.has(name), name);

  const perl = entryMap('perl', [{
    title: 'lesson.pl',
    current: true,
    content: 'my @items = ();\n# my $commentOnly = 1;\nsub total { return scalar @items; }\n',
  }]);
  for (const name of ['@items', 'total']) assert.ok(perl.has(name), name);
  assert.equal(perl.has('$commentOnly'), false);
});

test('compiled, scripting, and assembler declarations are recognized', () => {
  const samples = [
    ['cpp', 'class Counter {};\nint advance(int step) { int result = step; return result; }\n', ['Counter', 'advance', 'step']],
    ['csharp', 'class Program {}\nstatic int Add(int left, int right) { return left + right; }\n', ['Program', 'Add', 'left', 'right']],
    ['java', 'class Main {}\nint add(int left, int right) { return left + right; }\n', ['Main', 'add', 'left', 'right']],
    ['rust', 'fn advance(value: i32) -> i32 { let result = value + 1; result }\n', ['advance', 'value', 'result']],
    ['go', 'func advance(value int) int { result := value + 1; return result }\n', ['advance', 'value', 'result']],
    ['ruby', 'def greet(name)\n  message = name\nend\n', ['greet', 'name', 'message']],
    ['bash', 'build() { echo ok; }\nTARGET=demo\n', ['build', 'TARGET']],
    ['asm', 'start:\n  mov $1, %rax\n', ['start']],
  ];

  for (const [language, content, expected] of samples) {
    const entries = entryMap(language, [{ title: `main.${language}`, current: true, content }]);
    for (const name of expected) assert.ok(entries.has(name), `${language}: ${name}`);
  }
});
