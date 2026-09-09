import assert from 'node:assert/strict';
import test from 'node:test';

import { scanProjectSymbols, scanSourceSymbols, sourceForSymbolScan } from '../js/development-symbols.js';

test('symbol scanning keeps positions while removing language-specific comments and strings', () => {
  const source = [
    '# def hidden_comment():',
    'text = """',
    'def hidden_string():',
    '"""',
    'def visible(value):',
    '    return value',
  ].join('\n');
  const masked = sourceForSymbolScan(source, 'python');
  const symbols = scanSourceSymbols(source, 'python');

  assert.equal(masked.length, source.length);
  assert.equal(masked.split('\n').length, source.split('\n').length);
  assert.deepEqual(symbols.map((symbol) => symbol.name), ['visible']);
  assert.deepEqual(symbols[0] && { line: symbols[0].line, column: symbols[0].column }, { line: 5, column: 5 });
});

test('project symbols recognize arrow functions and ignore assembler comments', () => {
  const symbols = scanProjectSymbols([
    {
      id: 'helpers',
      title: 'helpers.js',
      content: 'export const formatValue = (value) => String(value);\n',
    },
    {
      id: 'start',
      title: 'start.s',
      content: '; hidden_label:\nstart:\n  ret\n',
    },
  ], 'javascript');
  assert.equal(symbols.some((symbol) => symbol.name === 'formatValue' && symbol.kind === 'function'), true);

  const assembly = scanSourceSymbols('; hidden_label:\nstart:\n  ret\n', 'asm');
  assert.deepEqual(assembly.map((symbol) => symbol.name), ['start']);
});
