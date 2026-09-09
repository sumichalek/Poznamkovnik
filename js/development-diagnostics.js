function normalizedFilename(value) {
  return String(value || '')
    .trim()
    .replace(/^\.\//, '')
    .replace(/^\/work\//, '');
}

export function parseDevelopmentDiagnostics(output = '') {
  const text = String(output || '');
  const diagnostics = [];
  const seen = new Set();
  const add = (filename, line, column = 1, severity = 'error', message = '') => {
    const path = normalizedFilename(filename);
    const lineNumber = Number(line);
    const columnNumber = Number(column) || 1;
    if (!path || !Number.isInteger(lineNumber) || lineNumber < 1) return;
    const level = severity === 'warning' ? 'warning' : 'error';
    const key = `${path}:${lineNumber}:${columnNumber}:${level}`;
    if (seen.has(key)) return;
    seen.add(key);
    diagnostics.push({
      filename: path,
      line: lineNumber,
      column: columnNumber,
      severity: level,
      message: String(message || '').trim(),
    });
  };
  const collect = (expression, callback) => {
    for (const match of text.matchAll(expression)) callback(match);
  };

  collect(
    /(?:^|\n)(?:\/work\/)?([^\n:]+(?:\/[^\n:]+)*):(\d+)(?::(\d+))?:\s*(fatal error|error|warning):\s*([^\n]*)/gim,
    (match) => add(match[1], match[2], match[3] || 1, /warning/i.test(match[4]) ? 'warning' : 'error', match[5])
  );
  collect(
    /(?:^|\n)\s*(?:\/work\/)?([^\n:(]+(?:\/[^\n:(]+)*)\((\d+),(\d+)\):\s*(warning|error)\s+[A-Z]+\d+:\s*([^\n]*)/gim,
    (match) => add(match[1], match[2], match[3], /warning/i.test(match[4]) ? 'warning' : 'error', match[5])
  );
  collect(
    /(?:^|\n)(?:\/work\/)?([^\n:]+\.java):(\d+):\s*(error|warning):\s*([^\n]*)/gim,
    (match) => add(match[1], match[2], 1, /warning/i.test(match[3]) ? 'warning' : 'error', match[4])
  );
  collect(
    /(?:^|\n)(?:\.\/|\/work\/)?([^\n:]+\.go):(\d+):(\d+):\s*([^\n]+)/gim,
    (match) => add(match[1], match[2], match[3], /warning/i.test(match[4]) ? 'warning' : 'error', match[4])
  );
  collect(
    /(?:^|\n)\s*-->\s+(?:\/work\/)?([^\n:]+\.rs):(\d+):(\d+)/gim,
    (match) => add(match[1], match[2], match[3], 'error', 'Chyba prekladu Rustu')
  );
  collect(
    /(?:^|\n)\s*File\s+"(?:\/work\/)?([^"\n]+)",\s+line\s+(\d+)/gim,
    (match) => add(match[1], match[2], 1, 'error', 'Chyba interpretácie Pythonu')
  );
  collect(
    /(?:^|\n)(?:[^\n:]+:\s+)?(?:\/work\/)?([^\n:]+\.rb):(\d+):\s*([^\n]+)/gim,
    (match) => add(match[1], match[2], 1, 'error', match[3])
  );
  collect(
    /(?:^|\n)([^\n]*?)\s+at\s+(?:\/work\/)?([^\s\n]+\.pl)\s+line\s+(\d+)(?:,?\s*([^\n]*))?/gim,
    (match) => add(match[2], match[3], 1, 'error', `${match[1]} ${match[4] || ''}`)
  );
  collect(
    /(?:^|\n)(?:PHP\s+)?(?:Parse|Fatal) error:\s*([^\n]*?)\s+in\s+(?:\/work\/)?([^\s\n]+\.php)\s+on\s+line\s+(\d+)/gim,
    (match) => add(match[2], match[3], 1, 'error', match[1])
  );
  collect(
    /(?:^|\n)(?:\/work\/)?([^\n:]+\.(?:sh|bash)):\s*(?:line\s+)?(\d+):\s*([^\n]*)/gim,
    (match) => add(match[1], match[2], 1, 'error', match[3])
  );
  collect(
    /(?:^|\n)(?:\/work\/)?([^\n:]+\.(?:js|mjs)):(\d+)(?::(\d+))?/gim,
    (match) => add(match[1], match[2], match[3] || 1, 'error', 'Chyba interpretácie JavaScriptu')
  );

  return diagnostics;
}

export function firstTestFailureDiagnostic({ compiled = false, compileOutput = '', runOutput = '' } = {}) {
  const compileDiagnostics = parseDevelopmentDiagnostics(compileOutput);
  if (!compiled) return compileDiagnostics.find((diagnostic) => diagnostic.severity !== 'warning') || compileDiagnostics[0] || null;
  const runDiagnostics = parseDevelopmentDiagnostics(runOutput);
  return runDiagnostics.find((diagnostic) => diagnostic.severity !== 'warning') || runDiagnostics[0] || null;
}
