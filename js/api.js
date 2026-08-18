export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function apiRequest(path, { method = 'GET', body, headers } = {}) {
  const requestHeaders = new Headers(headers);
  const options = { method, credentials: 'same-origin', headers: requestHeaders };

  if (body !== undefined) {
    requestHeaders.set('Content-Type', 'application/json');
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`/api${path}`, options);
  const contentType = response.headers.get('Content-Type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new ApiError(payload?.error || 'Server neodpovedal očakávaným spôsobom.', response.status);
  return payload;
}

export async function uploadSourceFile(sourceId, file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch(`/api/sources/${encodeURIComponent(sourceId)}/files`, {
    method: 'POST',
    credentials: 'same-origin',
    body: form
  });
  const payload = await response.json();
  if (!response.ok) throw new ApiError(payload?.error || 'Súbor sa nepodarilo nahrať.', response.status);
  return payload;
}

export async function uploadMusicTrack(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch('/api/music/tracks', {
    method: 'POST',
    credentials: 'same-origin',
    body: form
  });
  const payload = await response.json();
  if (!response.ok) throw new ApiError(payload?.error || 'Skladbu sa nepodarilo nahrať.', response.status);
  return payload;
}

export async function uploadBackupArchive(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch('/api/backups/restore', {
    method: 'POST',
    credentials: 'same-origin',
    body: form
  });
  const contentType = response.headers.get('Content-Type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new ApiError(payload?.error || 'Zálohu sa nepodarilo obnoviť.', response.status);
  return payload;
}

export async function previewBackupArchive(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await fetch('/api/backups/preview', {
    method: 'POST',
    credentials: 'same-origin',
    body: form
  });
  const contentType = response.headers.get('Content-Type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new ApiError(payload?.error || 'Zálohu sa nepodarilo overiť.', response.status);
  return payload;
}

function backupFilename(response) {
  const disposition = response.headers.get('Content-Disposition') || '';
  const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (utf8Name) {
    try {
      return decodeURIComponent(utf8Name).replace(/[\\/]/g, '_');
    } catch {
      // Fall through to the regular filename variant.
    }
  }
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return filename ? filename.replace(/[\\/]/g, '_') : 'Poznamkovnik-zaloha.zip';
}

export async function downloadBackupArchive(path = '/backups/export') {
  const response = await fetch(`/api${path}`, { credentials: 'same-origin' });
  if (!response.ok) {
    const contentType = response.headers.get('Content-Type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : null;
    throw new ApiError(payload?.error || 'Zálohu sa nepodarilo stiahnuť.', response.status);
  }
  return { blob: await response.blob(), filename: backupFilename(response) };
}
