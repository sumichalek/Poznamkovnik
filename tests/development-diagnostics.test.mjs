import assert from 'node:assert/strict';
import test from 'node:test';

import { firstTestFailureDiagnostic, parseDevelopmentDiagnostics } from '../js/development-diagnostics.js';

function only(output) {
  const diagnostics = parseDevelopmentDiagnostics(output);
  assert.equal(diagnostics.length, 1);
  return diagnostics[0];
}

test('compiler diagnostics preserve source locations and warning severity', () => {
  assert.deepEqual(
    only('/work/source/main.c:12:4: warning: unused variable \'value\'\n'),
    { filename: 'source/main.c', line: 12, column: 4, severity: 'warning', message: "unused variable 'value'" }
  );
  assert.deepEqual(
    only('/work/Program.cs(8,17): error CS1002: ; expected\n'),
    { filename: 'Program.cs', line: 8, column: 17, severity: 'error', message: '; expected' }
  );
  assert.deepEqual(
    only('Main.java:4: error: cannot find symbol\n'),
    { filename: 'Main.java', line: 4, column: 1, severity: 'error', message: 'cannot find symbol' }
  );
});

test('interpreters and scripting tools expose their source location', () => {
  assert.deepEqual(
    only('File "/work/lesson.py", line 7\n  print(\n'),
    { filename: 'lesson.py', line: 7, column: 1, severity: 'error', message: 'Chyba interpretácie Pythonu' }
  );
  assert.deepEqual(
    only('/usr/bin/ruby: /work/lesson.rb:3: syntax error, unexpected end-of-input\n'),
    { filename: 'lesson.rb', line: 3, column: 1, severity: 'error', message: 'syntax error, unexpected end-of-input' }
  );
  assert.deepEqual(
    only('syntax error at /work/lesson.pl line 5, near "my"\n'),
    { filename: 'lesson.pl', line: 5, column: 1, severity: 'error', message: 'syntax error near "my"' }
  );
  assert.deepEqual(
    only('PHP Parse error: syntax error, unexpected token "}" in /work/lesson.php on line 6\n'),
    { filename: 'lesson.php', line: 6, column: 1, severity: 'error', message: 'syntax error, unexpected token "}"' }
  );
  assert.deepEqual(
    only('/work/build.sh: line 9: syntax error near unexpected token `fi\'\n'),
    { filename: 'build.sh', line: 9, column: 1, severity: 'error', message: "syntax error near unexpected token `fi'" }
  );
});

test('Rust, Go, JavaScript, and assembler locations are recognized without duplicates', () => {
  const diagnostics = parseDevelopmentDiagnostics([
    'error: expected `;`',
    ' --> /work/main.rs:3:14',
    '/work/main.go:6:2: undefined: missing',
    '/work/main.js:8',
    '/work/start.s:11: Error: operand size mismatch for `mov\'',
    '/work/start.s:11: Error: operand size mismatch for `mov\'',
  ].join('\n'));
  assert.deepEqual(diagnostics, [
    { filename: 'start.s', line: 11, column: 1, severity: 'error', message: 'operand size mismatch for `mov\'' },
    { filename: 'main.go', line: 6, column: 2, severity: 'error', message: 'undefined: missing' },
    { filename: 'main.rs', line: 3, column: 14, severity: 'error', message: 'Chyba prekladu Rustu' },
    { filename: 'main.js', line: 8, column: 1, severity: 'error', message: 'Chyba interpretácie JavaScriptu' },
  ]);
});

test('test failures expose the first actionable compiler or runtime location', () => {
  assert.deepEqual(
    firstTestFailureDiagnostic({
      compiled: false,
      compileOutput: '/work/main.c:9:3: error: expected expression\n',
    }),
    { filename: 'main.c', line: 9, column: 3, severity: 'error', message: 'expected expression' }
  );
  assert.deepEqual(
    firstTestFailureDiagnostic({
      compiled: true,
      runOutput: 'Traceback (most recent call last):\n  File "/work/main.py", line 14\n    explode()\n',
    }),
    { filename: 'main.py', line: 14, column: 1, severity: 'error', message: 'Chyba interpretácie Pythonu' }
  );
  assert.equal(firstTestFailureDiagnostic({ compiled: true, runOutput: 'bežný výstup programu\n' }), null);
});
