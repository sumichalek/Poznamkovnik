export function normalizedTestOutput(value) {
  return String(value || '').replace(/\r\n/g, '\n').replace(/[ \t]+\n/g, '\n').replace(/\n+$/, '');
}

export function firstOutputDifference(expected, actual) {
  const expectedText = normalizedTestOutput(expected);
  const actualText = normalizedTestOutput(actual);
  if (expectedText === actualText) return null;
  const expectedLines = expectedText ? expectedText.split('\n') : [];
  const actualLines = actualText ? actualText.split('\n') : [];
  const maxLines = Math.max(expectedLines.length, actualLines.length);
  for (let index = 0; index < maxLines; index += 1) {
    if (expectedLines[index] === actualLines[index]) continue;
    return {
      line: index + 1,
      expected: expectedLines[index] ?? null,
      actual: actualLines[index] ?? null,
    };
  }
  return null;
}

export function fullOutputComparison(expected, actual) {
  return `Očakávané:\n${expected || '(prázdny výstup)'}\n\nSkutočné:\n${actual || '(prázdny výstup)'}`;
}
