const SVG_NAMESPACE = 'http://www.w3.org/2000/svg';

const iconPaths = {
  folder: ['M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9l-.81-1.2A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z'],
  'folder-plus': ['M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9l-.81-1.2A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z', 'M12 10v6', 'M9 13h6'],
  note: ['M5 3h10a2 2 0 0 1 2 2v5', 'M5 3v18h12', 'M9 3v12', 'M5 7h4', 'M5 11h4', 'm13 17 4-4 2 2-4 4-3 1Z', 'm16 14 2 2'],
  article: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6', 'M8 13h8', 'M8 17h6'],
  plus: ['M12 5v14', 'M5 12h14'],
  close: ['m18 6-12 12', 'm6 6 12 12'],
  check: ['m5 12 4 4L19 6'],
  pencil: ['M12 20h9', 'M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z'],
  trash: ['M3 6h18', 'M8 6V4h8v2', 'M19 6l-1 14H6L5 6', 'M10 11v5', 'M14 11v5'],
  home: ['m3 11 9-8 9 8', 'M5 10v10h14V10', 'M9 20v-6h6v6'],
  'arrow-up': ['M12 19V5', 'm5 12 7-7 7 7'],
  'arrow-left': ['M19 12H5', 'm12 19-7-7 7-7'],
  maximize: ['M15 3h6v6', 'M9 21H3v-6', 'm21 3-7 7', 'm3 21 7-7'],
  minimize: ['M8 3v5H3', 'M21 16v5h-5', 'm3 8 5-5', 'm21 16-5 5'],
  settings: ['M20 7h-9', 'M14 17H5', 'M17 20a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z', 'M7 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z'],
  palette: ['M12 22a10 10 0 1 1 0-20 5 5 0 0 0 0 10h1.5a2.5 2.5 0 0 1 0 5Z', 'M7.5 10.5h.01', 'M11.5 7.5h.01', 'M16.5 10.5h.01', 'M9 15.5h.01'],
  keyboard: ['M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z', 'M7 9h.01', 'M10 9h.01', 'M13 9h.01', 'M16 9h.01', 'M7 13h.01', 'M10 13h.01', 'M13 13h.01', 'M16 13h.01', 'M8 17h8'],
  user: ['M20 21a8 8 0 0 0-16 0', 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z'],
  'external-link': ['M15 3h6v6', 'm10 14 11-11', 'M21 14v7H3V3h7'],
  download: ['M12 3v12', 'm7 10 5 5 5-5', 'M5 21h14'],
  upload: ['M12 21V9', 'm7 14 5-5 5 5', 'M5 3h14'],
  'list-bullets': ['M8 6h13', 'M8 12h13', 'M8 18h13', 'M3 6h.01', 'M3 12h.01', 'M3 18h.01'],
  'list-check': ['m3 6 2 2 3-3', 'M11 6h10', 'm-18 6 2 2 3-3', 'M11 12h10', 'm-18 6 2 2 3-3', 'M11 18h10'],
  link: ['M10 13a5 5 0 0 0 7.07.07l2-2a5 5 0 0 0-7.07-7.07l-1.15 1.15', 'M14 11a5 5 0 0 0-7.07-.07l-2 2a5 5 0 0 0 7.07 7.07l1.15-1.15'],
  paperclip: ['m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48'],
  quote: ['M3 21c3 0 5-2 5-5V8H3v8h3c0 1.7-1.3 3-3 3v2Z', 'M14 21c3 0 5-2 5-5V8h-5v8h3c0 1.7-1.3 3-3 3v2Z'],
  code: ['m16 18 6-6-6-6', 'm8 6-6 6 6 6', 'm14.5 4-5 16'],
  divider: ['M4 12h16', 'M12 8v8'],
  image: ['M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z', 'm3 16 5-5 4 4 3-3 6 6', 'M14 8h.01'],
  table: ['M3 3h18v18H3Z', 'M3 9h18', 'M3 15h18', 'M9 3v18', 'M15 3v18'],
  'book-open': ['M2 4.5A2.5 2.5 0 0 1 4.5 2H8a4 4 0 0 1 4 4v15a3 3 0 0 0-3-3H4.5A2.5 2.5 0 0 0 2 20.5Z', 'M22 4.5A2.5 2.5 0 0 0 19.5 2H16a4 4 0 0 0-4 4v15a3 3 0 0 1 3-3h4.5a2.5 2.5 0 0 1 2 1.5Z'],
  globe: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M3.6 9h16.8', 'M3.6 15h16.8', 'M12 3a13.8 13.8 0 0 1 0 18', 'M12 3a13.8 13.8 0 0 0 0 18'],
  database: ['M12 3c5 0 9 1.8 9 4s-4 4-9 4-9-1.8-9-4 4-4 9-4Z', 'M3 7v5c0 2.2 4 4 9 4s9-1.8 9-4V7', 'M3 12v5c0 2.2 4 4 9 4s9-1.8 9-4v-5'],
  file: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6']
};

const sourceKindIcons = {
  source: 'quote',
  article: 'article',
  book: 'book-open',
  web: 'globe',
  dataset: 'database',
  attachment: 'paperclip'
};

function makePath(pathData) {
  const path = document.createElementNS(SVG_NAMESPACE, 'path');
  path.setAttribute('d', pathData);
  return path;
}

export function createAppIcon(name, className = '') {
  const icon = document.createElementNS(SVG_NAMESPACE, 'svg');
  icon.classList.add('app-icon');
  for (const classPart of className.split(' ').filter(Boolean)) icon.classList.add(classPart);
  icon.dataset.icon = name;
  icon.setAttribute('viewBox', '0 0 24 24');
  icon.setAttribute('fill', 'none');
  icon.setAttribute('stroke', 'currentColor');
  icon.setAttribute('stroke-width', '1.75');
  icon.setAttribute('stroke-linecap', 'round');
  icon.setAttribute('stroke-linejoin', 'round');
  icon.setAttribute('aria-hidden', 'true');
  icon.setAttribute('focusable', 'false');
  (iconPaths[name] || iconPaths.file).forEach((pathData) => icon.append(makePath(pathData)));
  return icon;
}

export function setAppIcon(icon, name) {
  if (!icon) return;
  icon.dataset.icon = name;
  icon.replaceChildren(...(iconPaths[name] || iconPaths.file).map(makePath));
}

export function hydrateAppIcons(root = document) {
  root.querySelectorAll('[data-app-icon]').forEach((placeholder) => {
    const icon = createAppIcon(placeholder.dataset.appIcon, placeholder.className);
    placeholder.replaceWith(icon);
  });
}

export function sourceKindIcon(kind) {
  return sourceKindIcons[kind] || 'quote';
}

export function sourceFileIcon(file) {
  const name = file?.originalName?.toLowerCase() || '';
  const mimeType = file?.mimeType?.toLowerCase() || '';
  if (name.endsWith('.epub')) return 'book-open';
  if (name.endsWith('.xls') || name.endsWith('.xlsx') || name.endsWith('.csv') || mimeType.includes('spreadsheet')) return 'table';
  if (mimeType.startsWith('image/')) return 'image';
  if (name.endsWith('.pdf') || name.endsWith('.doc') || name.endsWith('.docx') || mimeType.startsWith('text/')) return 'article';
  return 'file';
}
