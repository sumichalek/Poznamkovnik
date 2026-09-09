const CONTROL_WORDS = new Set([
  'if', 'for', 'while', 'switch', 'catch', 'return', 'sizeof', 'typeof', 'new', 'delete',
]);

const SYMBOL_LABELS = {
  function: 'Funkcia',
  macro: 'Makro',
  class: 'Trieda',
  type: 'Typ',
  label: 'Náväštie',
};

function blankKeepLines(value) {
  return String(value || '').replace(/[^\n]/g, ' ');
}

const HASH_COMMENT_LANGUAGES = new Set(['python', 'ruby', 'perl', 'php', 'bash', 'asm']);
const SEMICOLON_COMMENT_LANGUAGES = new Set(['asm']);
const SLASH_COMMENT_LANGUAGES = new Set(['c', 'cpp', 'csharp', 'go', 'java', 'javascript', 'php', 'rust']);

export function sourceForSymbolScan(content, languageId = '') {
  let source = String(content || '')
    .replace(/'''[\s\S]*?'''|"""[\s\S]*?"""|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`/g, blankKeepLines)
    .replace(/\/\*[\s\S]*?\*\//g, blankKeepLines)
  if (SLASH_COMMENT_LANGUAGES.has(languageId)) source = source.replace(/\/\/[^\n]*/g, blankKeepLines);
  if (HASH_COMMENT_LANGUAGES.has(languageId)) source = source.replace(/#[^\n]*/g, blankKeepLines);
  if (SEMICOLON_COMMENT_LANGUAGES.has(languageId)) source = source.replace(/;[^\n]*/g, blankKeepLines);
  if (languageId === 'c' || languageId === 'cpp') {
    source = source.replace(/(^|\n)\s*#\s*(?!define\b)[^\n]*/g, blankKeepLines);
  }
  return source;
}

function locationAt(source, offset) {
  const before = source.slice(0, Math.max(0, offset));
  return {
    offset,
    line: before.split('\n').length,
    column: offset - before.lastIndexOf('\n'),
  };
}

function signatureAt(source, offset) {
  const start = source.lastIndexOf('\n', offset) + 1;
  const end = source.indexOf('\n', offset);
  return source.slice(start, end < 0 ? source.length : end).trim().replace(/\s+/g, ' ').slice(0, 180);
}

function addSymbol(symbols, source, match, name, kind) {
  if (!name || CONTROL_WORDS.has(name)) return;
  const nameOffset = match.index + Math.max(0, match[0].indexOf(name));
  const key = `${kind}:${nameOffset}`;
  if (symbols.has(key)) return;
  symbols.set(key, {
    name,
    kind,
    label: SYMBOL_LABELS[kind] || 'Symbol',
    ...locationAt(source, nameOffset),
    signature: signatureAt(source, match.index),
  });
}

function collect(source, expression, kind, symbols) {
  let match;
  while ((match = expression.exec(source))) addSymbol(symbols, source, match, match[1], kind);
}

export function scanSourceSymbols(content, languageId = '') {
  const raw = String(content || '');
  const source = sourceForSymbolScan(raw, languageId);
  const symbols = new Map();

  collect(source, /^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, 'macro', symbols);
  collect(source, /^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|trait)\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, 'class', symbols);
  collect(source, /^\s*(?:export\s+)?(?:struct|enum|union)\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, 'type', symbols);
  collect(source, /^\s*typedef\b(?:[^;\n]*\s)?([A-Za-z_][A-Za-z0-9_]*)\s*;/gm, 'type', symbols);
  collect(source, /^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, 'type', symbols);

  if (languageId === 'python') {
    collect(source, /^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm, 'function', symbols);
  } else if (languageId === 'ruby') {
    collect(source, /^\s*def\s+([A-Za-z_][A-Za-z0-9_!?=]*)(?=\s|\(|$)/gm, 'function', symbols);
    collect(source, /^\s*module\s+([A-Za-z_][A-Za-z0-9_:]*)\b/gm, 'type', symbols);
  } else if (languageId === 'perl') {
    collect(source, /^\s*sub\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, 'function', symbols);
    collect(source, /^\s*package\s+([A-Za-z_][A-Za-z0-9_:]*)\b/gm, 'type', symbols);
  } else if (languageId === 'go') {
    collect(source, /^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm, 'function', symbols);
  } else if (languageId === 'rust') {
    collect(source, /^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]*>)?\s*\(/gm, 'function', symbols);
  } else if (languageId === 'asm') {
    collect(source, /^\s*([A-Za-z_.$][A-Za-z0-9_.$]*)\s*:/gm, 'label', symbols);
  } else if (languageId === 'bash') {
    collect(source, /^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\s*\))?\s*\{/gm, 'function', symbols);
  } else {
    collect(source, /^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/gm, 'function', symbols);
    collect(source, /^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>/gm, 'function', symbols);
    collect(
      source,
      /^\s*(?:(?:public|private|protected|internal|static|inline|extern|virtual|constexpr|const|unsigned|signed|long|short|void|char|int|float|double|bool|auto|size_t|[A-Za-z_][\w:<>]*)\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;\n{}]*\)\s*(?:const\s*)?(?:\{|$)/gm,
      'function',
      symbols,
    );
  }

  return [...symbols.values()].sort((left, right) => left.offset - right.offset || left.name.localeCompare(right.name, 'sk'));
}

export function scanProjectSymbols(files, languageId = '') {
  return (files || []).flatMap((file) => scanSourceSymbols(file.content, languageId).map((symbol) => ({
    ...symbol,
    file,
  })));
}
