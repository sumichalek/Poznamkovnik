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
