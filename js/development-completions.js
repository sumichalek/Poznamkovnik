const MAX_PROJECT_SYMBOLS = 240;
const INCLUDE_LANGUAGES = new Set(['c', 'cpp']);

const SYSTEM_HEADERS = {
  c: [
    'assert.h', 'ctype.h', 'errno.h', 'inttypes.h', 'limits.h', 'math.h',
    'stdarg.h', 'stdbool.h', 'stddef.h', 'stdint.h', 'stdio.h', 'stdlib.h',
    'string.h', 'time.h',
  ],
  cpp: [
    'algorithm', 'array', 'chrono', 'cstdint', 'cstdlib', 'fstream', 'iomanip',
    'iostream', 'memory', 'optional', 'string', 'string_view', 'utility', 'vector',
  ],
};

function keyword(label) {
  return { label, type: 'keyword', detail: 'kľúčové slovo' };
}

function builtin(label, detail = 'štandardná funkcia') {
  return { label, type: 'function', detail };
}

function type(label) {
  return { label, type: 'type', detail: 'typ' };
}

function snippet(label, template, detail) {
  return { label, type: 'snippet', template, detail };
}

const COMMON = [
  keyword('if'),
  keyword('else'),
  keyword('for'),
  keyword('while'),
  keyword('return'),
  keyword('break'),
  keyword('continue'),
];

const COMPLETIONS = {
  c: [
    ...COMMON,
    ...['auto', 'case', 'const', 'default', 'do', 'enum', 'extern', 'goto', 'inline', 'register', 'sizeof', 'static', 'struct', 'switch', 'typedef', 'union', 'volatile'].map(keyword),
    ...['void', 'char', 'short', 'int', 'long', 'float', 'double', 'signed', 'unsigned', 'bool', 'size_t'].map(type),
    ...['printf', 'scanf', 'puts', 'fgets', 'malloc', 'calloc', 'realloc', 'free', 'strlen', 'strcmp', 'strcpy'].map(builtin),
    snippet('main', 'int main(void) {\n\t${}\n\treturn 0;\n}', 'vstupný bod programu'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
    snippet('for', 'for (int ${1:index} = 0; ${1:index} < ${2:count}; ${1:index}++) {\n\t${}\n}', 'cyklus'),
    snippet('include', 'include <${1:stdio.h}>', 'doplní sa za #'),
  ],
  cpp: [
    ...COMMON,
    ...['auto', 'class', 'const', 'constexpr', 'enum', 'namespace', 'private', 'protected', 'public', 'static', 'struct', 'template', 'using', 'virtual'].map(keyword),
    ...['void', 'bool', 'char', 'int', 'long', 'float', 'double', 'string', 'vector', 'size_t'].map(type),
    ...['std::cout', 'std::cin', 'std::getline', 'std::move', 'std::sort'].map(builtin),
    snippet('main', 'int main() {\n\t${}\n\treturn 0;\n}', 'vstupný bod programu'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
    snippet('for', 'for (int ${1:index} = 0; ${1:index} < ${2:count}; ${1:index}++) {\n\t${}\n}', 'cyklus'),
    snippet('include', 'include <${1:iostream}>', 'doplní sa za #'),
  ],
  csharp: [
    ...COMMON,
    ...['class', 'namespace', 'using', 'public', 'private', 'protected', 'internal', 'static', 'readonly', 'new', 'async', 'await', 'try', 'catch', 'finally', 'throw'].map(keyword),
    ...['void', 'bool', 'char', 'int', 'long', 'float', 'double', 'decimal', 'string', 'object', 'var'].map(type),
    ...['Console.WriteLine', 'Console.ReadLine', 'string.IsNullOrEmpty'].map(builtin),
    snippet('main', 'class Program {\n\tstatic void Main() {\n\t\t${}\n\t}\n}', 'vstupný bod programu'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
    snippet('for', 'for (var ${1:index} = 0; ${1:index} < ${2:count}; ${1:index}++) {\n\t${}\n}', 'cyklus'),
  ],
  python: [
    ...COMMON,
    ...['and', 'as', 'assert', 'async', 'await', 'class', 'def', 'del', 'elif', 'except', 'False', 'finally', 'from', 'global', 'import', 'in', 'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'True', 'try', 'with', 'yield'].map(keyword),
    ...['print', 'input', 'len', 'range', 'enumerate', 'zip', 'sum', 'min', 'max', 'sorted', 'open', 'isinstance'].map(builtin),
    snippet('def', 'def ${1:name}(${2:args}):\n\t${}', 'funkcia'),
    snippet('if', 'if ${1:condition}:\n\t${}', 'podmienka'),
    snippet('for', 'for ${1:item} in ${2:items}:\n\t${}', 'cyklus'),
    snippet('try', 'try:\n\t${}\nexcept ${1:Exception} as ${2:error}:\n\t${}', 'ošetrenie chyby'),
  ],
  javascript: [
    ...COMMON,
    ...['async', 'await', 'class', 'const', 'delete', 'export', 'extends', 'function', 'import', 'let', 'new', 'null', 'of', 'switch', 'this', 'throw', 'try', 'catch', 'undefined', 'var'].map(keyword),
    ...['console.log', 'JSON.parse', 'JSON.stringify', 'Array.isArray', 'Object.keys', 'setTimeout'].map(builtin),
    snippet('function', 'function ${1:name}(${2:args}) {\n\t${}\n}', 'funkcia'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
    snippet('for', 'for (const ${1:item} of ${2:items}) {\n\t${}\n}', 'cyklus'),
    snippet('async', 'async function ${1:name}(${2:args}) {\n\t${}\n}', 'asynchrónna funkcia'),
  ],
  ruby: [
    ...['BEGIN', 'END', 'alias', 'and', 'begin', 'break', 'case', 'class', 'def', 'defined?', 'do', 'else', 'elsif', 'end', 'ensure', 'false', 'for', 'if', 'in', 'module', 'next', 'nil', 'not', 'or', 'redo', 'rescue', 'retry', 'return', 'self', 'super', 'then', 'true', 'unless', 'until', 'when', 'while', 'yield'].map(keyword),
    ...['puts', 'print', 'gets', 'chomp', 'length', 'each', 'map', 'select', 'require'].map(builtin),
    snippet('def', 'def ${1:name}(${2:args})\n\t${}\nend', 'funkcia'),
    snippet('if', 'if ${1:condition}\n\t${}\nend', 'podmienka'),
    snippet('each', '${1:items}.each do |${2:item}|\n\t${}\nend', 'cyklus'),
  ],
  perl: [
    ...['BEGIN', 'END', 'else', 'elsif', 'for', 'foreach', 'if', 'last', 'my', 'next', 'our', 'package', 'redo', 'return', 'state', 'sub', 'unless', 'until', 'use', 'while'].map(keyword),
    ...['print', 'say', 'chomp', 'length', 'keys', 'values', 'map', 'grep', 'scalar'].map(builtin),
    snippet('sub', 'sub ${1:name} {\n\t${}\n}', 'funkcia'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
    snippet('foreach', 'foreach my $${1:item} (@${2:items}) {\n\t${}\n}', 'cyklus'),
  ],
  php: [
    ...COMMON,
    ...['class', 'const', 'declare', 'echo', 'elseif', 'endforeach', 'extends', 'function', 'implements', 'include', 'namespace', 'new', 'private', 'protected', 'public', 'require', 'static', 'throw', 'try', 'catch', 'use'].map(keyword),
    ...['array', 'bool', 'float', 'int', 'string', 'mixed', 'void'].map(type),
    ...['count', 'strlen', 'trim', 'json_encode', 'json_decode', 'var_dump'].map(builtin),
    snippet('function', 'function ${1:name}(${2:args}) {\n\t${}\n}', 'funkcia'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
    snippet('foreach', 'foreach (${1:items} as ${2:item}) {\n\t${}\n}', 'cyklus'),
  ],
  java: [
    ...COMMON,
    ...['abstract', 'class', 'extends', 'final', 'implements', 'import', 'interface', 'new', 'package', 'private', 'protected', 'public', 'static', 'super', 'this', 'throws', 'try', 'catch'].map(keyword),
    ...['void', 'boolean', 'byte', 'char', 'double', 'float', 'int', 'long', 'short', 'String'].map(type),
    ...['System.out.println', 'System.out.print', 'Math.max', 'Math.min'].map(builtin),
    snippet('main', 'public static void main(String[] args) {\n\t${}\n}', 'vstupný bod programu'),
    snippet('class', 'class ${1:Name} {\n\t${}\n}', 'trieda'),
    snippet('if', 'if (${1:condition}) {\n\t${}\n}', 'podmienka'),
  ],
  rust: [
    ...COMMON,
    ...['as', 'async', 'await', 'const', 'crate', 'enum', 'extern', 'fn', 'impl', 'let', 'match', 'mod', 'move', 'mut', 'pub', 'ref', 'Self', 'self', 'static', 'struct', 'trait', 'unsafe', 'use', 'where'].map(keyword),
    ...['bool', 'char', 'f32', 'f64', 'i32', 'i64', 'String', 'str', 'u32', 'u64', 'usize', 'Vec'].map(type),
    ...['println!', 'print!', 'format!', 'vec!', 'Some', 'None', 'Ok', 'Err'].map(builtin),
    snippet('main', 'fn main() {\n\t${}\n}', 'vstupný bod programu'),
    snippet('fn', 'fn ${1:name}(${2:args}) {\n\t${}\n}', 'funkcia'),
    snippet('match', 'match ${1:value} {\n\t${2:pattern} => ${},\n\t_ => {}\n}', 'vetvenie hodnoty'),
  ],
  go: [
    ...COMMON,
    ...['break', 'case', 'chan', 'const', 'defer', 'fallthrough', 'func', 'go', 'goto', 'interface', 'map', 'package', 'range', 'select', 'struct', 'type', 'var'].map(keyword),
    ...['bool', 'byte', 'error', 'float64', 'int', 'int64', 'rune', 'string', 'uint', 'uintptr'].map(type),
    ...['fmt.Println', 'fmt.Printf', 'len', 'append', 'make', 'new', 'panic', 'recover'].map(builtin),
    snippet('main', 'func main() {\n\t${}\n}', 'vstupný bod programu'),
    snippet('func', 'func ${1:name}(${2:args}) {\n\t${}\n}', 'funkcia'),
    snippet('if', 'if ${1:condition} {\n\t${}\n}', 'podmienka'),
  ],
  asm: [
    ...['.ascii', '.data', '.global', '.intel_syntax', '.section', '.text', '.type', '.zero', 'call', 'cmp', 'je', 'jne', 'jmp', 'lea', 'mov', 'pop', 'push', 'ret', 'syscall', 'xor'].map(keyword),
    snippet('start', '.global _start\n\n.section .text\n_start:\n\t${}', 'vstupný bod Linux x86-64'),
    snippet('label', '${1:label}:\n\t${}', 'náväštie'),
  ],
  bash: [
    ...['case', 'do', 'done', 'elif', 'else', 'esac', 'export', 'fi', 'for', 'function', 'if', 'in', 'local', 'then', 'until', 'while'].map(keyword),
    ...['printf', 'read', 'echo', 'grep', 'sed', 'awk', 'mkdir', 'rm', 'cp', 'mv'].map(builtin),
    snippet('if', 'if ${1:condition}; then\n\t${}\nfi', 'podmienka'),
    snippet('for', 'for ${1:item} in ${2:items}; do\n\t${}\ndone', 'cyklus'),
    snippet('function', '${1:name}() {\n\t${}\n}', 'funkcia'),
  ],
};

function completionEntries(languageId) {
  return COMPLETIONS[languageId] || COMPLETIONS.c;
}

const PREPROCESSOR_WORDS = new Set(['define', 'elif', 'else', 'endif', 'error', 'if', 'ifdef', 'ifndef', 'include', 'line', 'pragma', 'undef']);

function blankMatch(value) {
  return value.replace(/[^\n]/g, ' ');
}

function sourceForSymbolScan(content, languageId = '') {
  const source = String(content || '')
    // Remove string literals first so an URL such as "https://..." is not mistaken for a comment.
    .replace(/'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`/g, blankMatch)
    .replace(/\/\*[\s\S]*?\*\//g, blankMatch)
    .replace(/\/\/[^\n]*/g, '')
    // An #include adds no callable symbol. Keep #define so its macro name stays available.
    .replace(/^\s*#\s*(?!define\b).*$/gm, '');
  return ['python', 'ruby', 'perl', 'php', 'bash'].includes(languageId)
    ? source.replace(/#[^\n]*/g, blankMatch)
    : source;
}

function addSymbol(symbols, label, type, detail, boost, reserved) {
  const name = String(label || '').trim();
  if (!name || PREPROCESSOR_WORDS.has(name) || reserved.has(name)) return null;
  const existing = symbols.get(label);
  if (existing && existing.boost >= boost) return existing;
  const symbol = { label: name, type, detail, boost };
  symbols.set(name, symbol);
  return symbol;
}

function addMatches(source, expression, callback) {
  for (const match of source.matchAll(expression)) callback(match);
}

function parameterNames(parameters, languageId) {
  return String(parameters || '')
    .split(',')
    .map((parameter) => {
      const raw = parameter.trim().replace(/^\.\.\./, '');
      if (!raw || raw === 'void') return '';
      if (['python', 'ruby', 'javascript', 'typescript', 'php', 'bash', 'rust', 'go'].includes(languageId)) {
        const match = raw.replace(/^[$@%]/, '').match(/[A-Za-z_][A-Za-z0-9_]*/);
        return match ? `${raw.match(/^[$@%]/)?.[0] || ''}${match[0]}` : '';
      }
      const names = raw.replace(/=[\s\S]*$/, '').match(/[A-Za-z_][A-Za-z0-9_]*/g) || [];
      return names.at(-1) || '';
    })
    .filter(Boolean);
}

function functionTemplate(name, parameters, languageId) {
  const fields = parameterNames(parameters, languageId)
    .map((parameter, index) => `\${${index + 1}:${parameter}}`)
    .join(', ');
  return `${name}(${fields || '${}'})`;
}

function addFunction(symbols, name, parameters, detail, boost, reserved, languageId) {
  const signature = `${name}(${String(parameters || '').trim()})`;
  const symbol = addSymbol(symbols, name, 'function', `${signature} · ${detail}`, boost + 12, reserved);
  if (symbol?.type === 'function') symbol.template = functionTemplate(name, parameters, languageId);
  parameterNames(parameters, languageId).forEach((parameter) => {
    addSymbol(symbols, parameter, 'variable', detail, boost + 18, reserved);
  });
}

function addCommonDeclarations(symbols, source, detail, boost, reserved) {
  addMatches(source, /^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 14, reserved);
  });
  addMatches(source, /^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|trait|struct|enum|union)\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, (match) => {
    addSymbol(symbols, match[1], 'class', detail, boost + 12, reserved);
  });
  addMatches(source, /^\s*(?:typedef\s+[^;\n]*\s|using\s+|type\s+)([A-Za-z_][A-Za-z0-9_]*)\b/gm, (match) => {
    addSymbol(symbols, match[1], 'type', detail, boost + 12, reserved);
  });
}

function addCStyleDeclarations(symbols, source, detail, boost, reserved, languageId) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(
    source,
    /^\s*(?:(?:export|public|private|protected|internal|static|inline|extern|virtual|constexpr|const|async|unsafe|final|override|unsigned|signed|long|short|volatile)\s+|[A-Za-z_][A-Za-z0-9_:<>]*\s+|[*&]\s*)+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()\n]*)\)\s*(?:const\s*)?(?:\{|;|=>)/gm,
    (match) => addFunction(symbols, match[1], match[2], detail, boost, reserved, languageId)
  );
  addMatches(
    source,
    /^\s*(?:(?:const|static|extern|volatile|unsigned|signed|long|short|auto|final|readonly|public|private|protected|internal)\s+)*(?:[A-Za-z_][A-Za-z0-9_:<>]*(?:\s*<[^;=(){}]+>)?)\s+[*&\s]*([A-Za-z_][A-Za-z0-9_]*)\s*(?=[=;,\[])/gm,
    (match) => addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved)
  );
}

function addJavaScriptDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)/gm, (match) => {
    addFunction(symbols, match[1], match[2], detail, boost, reserved, 'javascript');
  });
  addMatches(source, /^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|([A-Za-z_$][A-Za-z0-9_$]*))\s*=>/gm, (match) => {
    addFunction(symbols, match[1], match[2] || match[3], detail, boost, reserved, 'javascript');
  });
  addMatches(source, /^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\b/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
  addMatches(source, /^\s*import\s+(?:\*\s+as\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s+from\b/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
}

function addPythonDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*:/gm, (match) => {
    addFunction(symbols, match[1], match[2], detail, boost, reserved, 'python');
  });
  addMatches(source, /^\s*(?:from\s+[A-Za-z_.][A-Za-z0-9_.]*\s+import\s+|import\s+)([A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?/gm, (match) => {
    addSymbol(symbols, match[2] || match[1], 'variable', detail, boost + 8, reserved);
  });
  addMatches(source, /^\s*(?:for\s+|with\s+[^\n]*\s+as\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|in\b)/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
}

function addRubyDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /^\s*def\s+([A-Za-z_][A-Za-z0-9_!?=]*)\s*(?:\(([^)]*)\)|\s+([^\n]+))?/gm, (match) => {
    addFunction(symbols, match[1], match[2] || match[3], detail, boost, reserved, 'ruby');
  });
  addMatches(source, /^\s*([a-z_][A-Za-z0-9_]*)\s*=/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
}

function addPerlDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /^\s*sub\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, (match) => {
    addFunction(symbols, match[1], '', detail, boost, reserved, 'perl');
  });
  addMatches(source, /\b(?:my|our|state)\s+([$@%][A-Za-z_][A-Za-z0-9_]*)/g, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 10, reserved);
  });
}

function addPhpDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/g, (match) => {
    addFunction(symbols, match[1], match[2], detail, boost, reserved, 'php');
  });
  addMatches(source, /\$[A-Za-z_][A-Za-z0-9_]*/g, (match) => {
    addSymbol(symbols, match[0], 'variable', detail, boost + 8, reserved);
  });
}

function addRustDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)/gm, (match) => {
    addFunction(symbols, match[1], match[2], detail, boost, reserved, 'rust');
  });
  addMatches(source, /\b(?:let\s+(?:mut\s+)?|const\s+|static\s+)([A-Za-z_][A-Za-z0-9_]*)\b/g, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
}

function addGoDeclarations(symbols, source, detail, boost, reserved) {
  addCommonDeclarations(symbols, source, detail, boost, reserved);
  addMatches(source, /^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/gm, (match) => {
    addFunction(symbols, match[1], match[2], detail, boost, reserved, 'go');
  });
  addMatches(source, /^\s*(?:var|const)\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
  addMatches(source, /\b([A-Za-z_][A-Za-z0-9_]*)\s*:=/g, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
}

function addBashDeclarations(symbols, source, detail, boost, reserved) {
  addMatches(source, /^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\s*\))?\s*\{/gm, (match) => {
    addFunction(symbols, match[1], '', detail, boost, reserved, 'bash');
  });
  addMatches(source, /^\s*(?:local\s+|export\s+)?([A-Za-z_][A-Za-z0-9_]*)=/gm, (match) => {
    addSymbol(symbols, match[1], 'variable', detail, boost + 8, reserved);
  });
}

function addAssemblerDeclarations(symbols, source, detail, boost, reserved) {
  addMatches(source, /^\s*([A-Za-z_.$][A-Za-z0-9_.$]*)\s*:/gm, (match) => {
    addSymbol(symbols, match[1], 'function', `${match[1]}: · ${detail}`, boost + 12, reserved);
  });
}

function addDeclarations(symbols, source, languageId, detail, boost, reserved) {
  if (['c', 'cpp', 'csharp', 'java'].includes(languageId)) {
    addCStyleDeclarations(symbols, source, detail, boost, reserved, languageId);
    return;
  }
  if (['javascript', 'typescript'].includes(languageId)) {
    addJavaScriptDeclarations(symbols, source, detail, boost, reserved);
    return;
  }
  if (languageId === 'python') return addPythonDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'ruby') return addRubyDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'perl') return addPerlDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'php') return addPhpDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'rust') return addRustDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'go') return addGoDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'bash') return addBashDeclarations(symbols, source, detail, boost, reserved);
  if (languageId === 'asm') addAssemblerDeclarations(symbols, source, detail, boost, reserved);
}

function readProjectSymbols(files, languageId) {
  const symbols = new Map();
  const reserved = new Set(completionEntries(languageId).map((entry) => entry.label.replace(/^\$/, '')));
  const activePaths = new Set(
    files.filter((file) => file?.current).map((file) => String(file?.path || file?.title || ''))
  );
  files.forEach((file) => {
    const path = String(file?.path || file?.title || '');
    if (!file?.current && activePaths.has(path)) return;
    const source = sourceForSymbolScan(file?.content, languageId);
    const detail = file?.current ? 'v otvorenom súbore' : file?.title ? `v ${file.title}` : 'v projekte';
    const boost = file?.current ? 180 : 100;
    addDeclarations(symbols, source, languageId, detail, boost, reserved);
  });
  return [...symbols.values()]
    .sort((left, right) => right.boost - left.boost || left.label.localeCompare(right.label, 'sk'))
    .slice(0, MAX_PROJECT_SYMBOLS);
}

export function projectCompletionEntries(languageId, files) {
  const projectSymbols = readProjectSymbols(files, languageId);
  const staticEntries = completionEntries(languageId);
  const seen = new Set(projectSymbols.map((entry) => entry.label));
  return [
    ...projectSymbols,
    ...staticEntries.filter((entry) => !seen.has(entry.label)),
  ];
}

export function projectSnippetEntries(languageId) {
  return completionEntries(languageId)
    .filter((entry) => entry.template)
    .map((entry) => ({
      label: entry.label,
      detail: entry.detail,
      template: entry.template,
    }));
}

export function projectIncludeCompletionEntries(languageId, files, { local = false } = {}) {
  if (!INCLUDE_LANGUAGES.has(languageId)) return [];
  if (!local) {
    return (SYSTEM_HEADERS[languageId] || []).map((label) => ({
      label,
      type: 'file',
      detail: 'systémová hlavička',
      boost: 20,
    }));
  }

  const headers = new Map();
  files.forEach((file) => {
    const path = String(file?.path || file?.title || '').replace(/\\/g, '/');
    if (!/\.(?:h|hh|hpp|hxx|inc)$/i.test(path) || headers.has(path)) return;
    headers.set(path, {
      label: path,
      type: 'file',
      detail: 'hlavička projektu',
      boost: 100,
    });
  });
  return [...headers.values()].sort((left, right) => left.label.localeCompare(right.label, 'sk'));
}
