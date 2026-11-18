// randomUUID() needs a secure context; getRandomValues() also works over LAN HTTP.
export function createId() {
  const random = globalThis.crypto;
  if (typeof random?.randomUUID === 'function') return random.randomUUID();
  if (typeof random?.getRandomValues !== 'function') {
    throw new Error('Prehliadač nepodporuje bezpečné generovanie identifikátorov. Použi aktuálny prehliadač.');
  }

  const bytes = new Uint8Array(16);
  random.getRandomValues(bytes);
  // RFC 9562, UUID v4: version 0100 and variant 10, with 122 random bits.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
