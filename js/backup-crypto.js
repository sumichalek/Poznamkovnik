const MAGIC_TEXT = 'POZNAMKOVNIK-ENCRYPTED-BACKUP-1\n';
const FORMAT = 'poznamkovnik-encrypted-backup';
const FORMAT_VERSION = 1;
const KDF_ITERATIONS = 600_000;
const SALT_BYTES = 16;
const IV_BYTES = 12;
const MAX_HEADER_BYTES = 64 * 1024;

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();
const magic = textEncoder.encode(MAGIC_TEXT);

function cryptoProvider() {
  if (!globalThis.isSecureContext || !globalThis.crypto?.subtle) {
    throw new Error('Prehliadač nepodporuje bezpečné šifrovanie záloh v tomto prostredí.');
  }
  return globalThis.crypto;
}

function base64FromBytes(bytes) {
  let value = '';
  bytes.forEach((byte) => {
    value += String.fromCharCode(byte);
  });
  return btoa(value);
}

function bytesFromBase64(value, label) {
  if (typeof value !== 'string' || !value) throw new Error(`Šifrovaná záloha nemá platnú hodnotu: ${label}.`);
  try {
    const decoded = atob(value);
    return Uint8Array.from(decoded, (character) => character.charCodeAt(0));
  } catch {
    throw new Error(`Šifrovaná záloha nemá platnú hodnotu: ${label}.`);
  }
}

function normalizeZipFilename(filename) {
  const value = String(filename || '').trim().replace(/[\\/]/g, '_');
  return value.toLowerCase().endsWith('.zip') ? value : 'Poznamkovnik-zaloha.zip';
}

function encryptedFilename(filename) {
  return normalizeZipFilename(filename).replace(/\.zip$/i, '') + '.pznbackup';
}

function sameBytes(first, second) {
  if (first.byteLength !== second.byteLength) return false;
  return first.every((value, index) => value === second[index]);
}

async function deriveKey(password, salt, usage) {
  const crypto = cryptoProvider();
  const passwordKey = await crypto.subtle.importKey('raw', textEncoder.encode(password), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      hash: 'SHA-256',
      salt,
      iterations: KDF_ITERATIONS
    },
    passwordKey,
    { name: 'AES-GCM', length: 256 },
    false,
    [usage]
  );
}

function readHeader(bytes) {
  if (bytes.byteLength < magic.byteLength + 4 || !sameBytes(bytes.slice(0, magic.byteLength), magic)) return null;
  const headerLength = new DataView(bytes.buffer, bytes.byteOffset + magic.byteLength, 4).getUint32(0, false);
  if (!headerLength || headerLength > MAX_HEADER_BYTES || bytes.byteLength < magic.byteLength + 4 + headerLength) {
    throw new Error('Šifrovaná záloha má poškodenú hlavičku.');
  }
  const headerStart = magic.byteLength + 4;
  const headerBytes = bytes.slice(headerStart, headerStart + headerLength);
  try {
    return { header: JSON.parse(textDecoder.decode(headerBytes)), headerBytes, payloadOffset: headerStart + headerLength };
  } catch {
    throw new Error('Šifrovaná záloha má nečitateľnú hlavičku.');
  }
}

function validateHeader(header) {
  if (!header || header.format !== FORMAT || header.version !== FORMAT_VERSION) {
    throw new Error('Tento formát šifrovanej zálohy nie je podporovaný.');
  }
  if (header.cipher !== 'AES-GCM' || header.kdf !== 'PBKDF2-SHA-256' || header.iterations !== KDF_ITERATIONS) {
    throw new Error('Šifrovaná záloha používa nepodporované zabezpečenie.');
  }
  const salt = bytesFromBase64(header.salt, 'soľ');
  const iv = bytesFromBase64(header.iv, 'inicializačný vektor');
  if (salt.byteLength !== SALT_BYTES || iv.byteLength !== IV_BYTES) {
    throw new Error('Šifrovaná záloha má neplatné kryptografické údaje.');
  }
  return { salt, iv };
}

function ensurePassword(password) {
  if (typeof password !== 'string' || password.length < 10) {
    throw new Error('Heslo pre šifrovanú zálohu musí mať aspoň 10 znakov.');
  }
}

export function encryptedBackupSupported() {
  return Boolean(globalThis.isSecureContext && globalThis.crypto?.subtle);
}

export async function isEncryptedBackup(file) {
  if (!(file instanceof Blob) || file.size < magic.byteLength + 4) return false;
  const prefix = new Uint8Array(await file.slice(0, magic.byteLength + 4).arrayBuffer());
  return sameBytes(prefix.slice(0, magic.byteLength), magic);
}

export async function encryptBackupArchive(archive, password, filename) {
  ensurePassword(password);
  const crypto = cryptoProvider();
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const header = {
    format: FORMAT,
    version: FORMAT_VERSION,
    cipher: 'AES-GCM',
    kdf: 'PBKDF2-SHA-256',
    iterations: KDF_ITERATIONS,
    salt: base64FromBytes(salt),
    iv: base64FromBytes(iv)
  };
  const headerBytes = textEncoder.encode(JSON.stringify(header));
  const archiveBytes = await archive.arrayBuffer();
  const key = await deriveKey(password, salt, 'encrypt');
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData: headerBytes, tagLength: 128 },
    key,
    archiveBytes
  );
  const prefix = new Uint8Array(magic.byteLength + 4 + headerBytes.byteLength);
  prefix.set(magic, 0);
  new DataView(prefix.buffer).setUint32(magic.byteLength, headerBytes.byteLength, false);
  prefix.set(headerBytes, magic.byteLength + 4);
  return {
    blob: new Blob([prefix, encrypted], { type: 'application/octet-stream' }),
    filename: encryptedFilename(filename)
  };
}

export async function decryptBackupArchive(file, password) {
  ensurePassword(password);
  const prefixLength = Math.min(file.size, magic.byteLength + 4 + MAX_HEADER_BYTES);
  const prefix = new Uint8Array(await file.slice(0, prefixLength).arrayBuffer());
  const parsed = readHeader(prefix);
  if (!parsed) throw new Error('Vybraný súbor nie je šifrovaná záloha Poznámkovníka.');
  const { salt, iv } = validateHeader(parsed.header);
  if (file.size <= parsed.payloadOffset) throw new Error('Šifrovaná záloha neobsahuje žiadne dáta.');
  const encrypted = await file.slice(parsed.payloadOffset).arrayBuffer();
  const key = await deriveKey(password, salt, 'decrypt');
  try {
    const archive = await cryptoProvider().subtle.decrypt(
      { name: 'AES-GCM', iv, additionalData: parsed.headerBytes, tagLength: 128 },
      key,
      encrypted
    );
    return new File([archive], 'Poznamkovnik-zaloha.zip', { type: 'application/zip' });
  } catch {
    throw new Error('Zálohu sa nepodarilo odomknúť. Over heslo a vybraný súbor.');
  }
}
