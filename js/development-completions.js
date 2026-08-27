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

function sourceForSymbolScan(content) {
  return String(content || '')
    // Remove string literals first so an URL such as "https://..." is not mistaken for a comment.
    .replace(/'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`/g, blankMatch)
    .replace(/\/\*[\s\S]*?\*\//g, blankMatch)
    .replace(/\/\/[^\n]*/g, '')
    // An #include adds no callable symbol. Keep #define so its macro name stays available.
    .replace(/^\s*#\s*(?!define\b).*$/gm, '');
}

function addSymbol(symbols, label, type, detail, boost) {
  if (!label || PREPROCESSOR_WORDS.has(label)) return;
  const existing = symbols.get(label);
  if (existing && existing.boost >= boost) return;
  symbols.set(label, { label, type, detail, boost });
}

function readProjectSymbols(files, languageId) {
  const symbols = new Map();
  const knownWords = new Set(completionEntries(languageId).map((entry) => entry.label.replace(/^\$/, '')));
  files.forEach((file) => {
    const content = sourceForSymbolScan(file?.content);
    const location = file?.current ? 'v otvorenom súbore' : file?.title ? `v ${file.title}` : 'v projekte';
    const boost = file?.current ? 120 : 90;
    const names = content.match(/\b[A-Za-z_][A-Za-z0-9_]*\b/g) || [];
    names.forEach((name) => {
      if (!knownWords.has(name)) addSymbol(symbols, name, 'variable', location, boost);
    });
    for (const match of content.matchAll(/\b([A-Za-z_][A-Za-z0-9_]*)\s*\(/g)) {
      if (!knownWords.has(match[1])) addSymbol(symbols, match[1], 'function', location, boost);
    }
    for (const match of content.matchAll(/\b(?:class|struct|enum|interface|trait|type)\s+([A-Za-z_][A-Za-z0-9_]*)/g)) {
      addSymbol(symbols, match[1], 'class', location, boost);
    }
    if (languageId === 'php') {
      for (const match of content.matchAll(/\$[A-Za-z_][A-Za-z0-9_]*/g)) {
        addSymbol(symbols, match[0], 'variable', location, boost);
      }
    }
  });
  return [...symbols.values()].slice(0, MAX_PROJECT_SYMBOLS);
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
