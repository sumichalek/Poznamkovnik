function text(value, maximum = 2_000) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(0, maximum);
}

function metadataOf(source) {
  return source?.metadata && typeof source.metadata === 'object' ? source.metadata : {};
}

function authorsOf(source) {
  return text(metadataOf(source).author, 1_200)
    .split(';')
    .map((author) => text(author, 240))
    .filter(Boolean);
}

function surname(author) {
  const parts = text(author).split(' ').filter(Boolean);
  return parts.at(-1) || text(author);
}

function yearOf(source) {
  return text(metadataOf(source).year, 24);
}

function escapeBibtex(value) {
  return text(value, 8_000).replace(/([{}\\])/g, '\\$1');
}

function escapeRis(value) {
  return text(value, 8_000).replace(/[\r\n]+/g, ' ');
}

function slug(value, fallback = 'source') {
  return text(value, 160)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '')
    .toLowerCase()
    .slice(0, 32) || fallback;
}

function cslAuthor(author) {
  const clean = text(author, 240);
  const parts = clean.split(' ').filter(Boolean);
  if (parts.length < 2) return { literal: clean };
  return { family: parts.at(-1), given: parts.slice(0, -1).join(' ') };
}

export function shortCitation(source) {
  const authors = authorsOf(source);
  const year = yearOf(source);
  let label = '';
  if (authors.length === 1) label = surname(authors[0]);
  else if (authors.length === 2) label = `${surname(authors[0])} a ${surname(authors[1])}`;
  else if (authors.length > 2) label = `${surname(authors[0])} a kol.`;
  else label = text(source?.title, 90) || 'Zdroj';
  return year ? `${label}, ${year}` : label;
}

export function bibliographicReference(source) {
  const metadata = metadataOf(source);
  const authors = text(metadata.author, 1_200);
  const year = yearOf(source);
  const title = text(source?.title, 240) || 'Bez názvu';
  const publisher = text(metadata.publisher, 240);
  const publication = text(metadata.publicationTitle, 240);
  const volume = text(metadata.volume, 80);
  const issue = text(metadata.issue, 80);
  const pages = text(metadata.pages, 120);
  const doi = text(metadata.doi, 500);
  const isbn = text(metadata.isbn, 32);
  const url = text(metadata.url, 1_600);
  const prefix = [authors, year ? `(${year})` : '', `${title}.`].filter(Boolean).join(' ');
  const publicationDetail = [
    publication,
    volume ? `zv. ${volume}` : '',
    issue ? `č. ${issue}` : '',
    pages ? `s. ${pages}` : ''
  ].filter(Boolean).join(', ');
  const tail = [
    publicationDetail,
    publisher,
    doi ? `DOI: ${doi}` : '',
    !doi && isbn ? `ISBN: ${isbn}` : '',
    url ? `Dostupné na: ${url}` : ''
  ].filter(Boolean);
  return [prefix, ...tail].join(' ');
}

export function bibliographyKey(source) {
  const authors = authorsOf(source);
  return `${slug(authors[0] ? surname(authors[0]) : source?.title)}${yearOf(source) || 'nd'}${slug(source?.title, 'source').slice(0, 18)}`;
}

export function bibliographyBibtex(source) {
  const metadata = metadataOf(source);
  const type = { article: 'article', book: 'book', dataset: 'misc', web: 'misc' }[source?.kind] || 'misc';
  const fields = {
    author: text(metadata.author),
    title: text(source?.title),
    year: yearOf(source),
    publisher: text(metadata.publisher),
    journal: text(metadata.publicationTitle),
    volume: text(metadata.volume),
    number: text(metadata.issue),
    pages: text(metadata.pages),
    doi: text(metadata.doi),
    isbn: text(metadata.isbn),
    url: text(metadata.url),
    language: text(metadata.language)
  };
  const rows = Object.entries(fields)
    .filter(([, value]) => value)
    .map(([key, value]) => `  ${key} = {${escapeBibtex(value)}}`);
  return `@${type}{${bibliographyKey(source)},\n${rows.join(',\n')}\n}\n`;
}

export function bibliographyRis(source) {
  const metadata = metadataOf(source);
  const type = { article: 'JOUR', book: 'BOOK', dataset: 'DATA', web: 'ELEC', attachment: 'GEN' }[source?.kind] || 'GEN';
  const lines = [`TY  - ${type}`];
  authorsOf(source).forEach((author) => lines.push(`AU  - ${escapeRis(author)}`));
  const fields = [
    ['TI', source?.title],
    ['PY', metadata.year],
    ['PB', metadata.publisher],
    ['JO', metadata.publicationTitle],
    ['VL', metadata.volume],
    ['IS', metadata.issue],
    ['SP', metadata.pages],
    ['DO', metadata.doi],
    ['SN', metadata.isbn],
    ['UR', metadata.url],
    ['LA', metadata.language],
    ['N1', source?.description]
  ];
  fields.forEach(([tag, value]) => {
    const clean = escapeRis(value);
    if (clean) lines.push(`${tag}  - ${clean}`);
  });
  lines.push('ER  - ');
  return lines.join('\n').concat('\n');
}

export function bibliographyCslJson(source) {
  const metadata = metadataOf(source);
  const year = Number.parseInt(yearOf(source), 10);
  const type = { article: 'article-journal', book: 'book', dataset: 'dataset', web: 'webpage', attachment: 'document' }[source?.kind] || 'document';
  const result = {
    id: bibliographyKey(source),
    type,
    title: text(source?.title),
    author: authorsOf(source).map(cslAuthor),
    publisher: text(metadata.publisher),
    'container-title': text(metadata.publicationTitle),
    volume: text(metadata.volume),
    issue: text(metadata.issue),
    page: text(metadata.pages),
    DOI: text(metadata.doi),
    ISBN: text(metadata.isbn),
    URL: text(metadata.url),
    language: text(metadata.language),
    note: text(source?.description, 10_000)
  };
  if (Number.isInteger(year) && year > 0) result.issued = { 'date-parts': [[year]] };
  Object.keys(result).forEach((key) => {
    const value = result[key];
    if (value === '' || (Array.isArray(value) && !value.length)) delete result[key];
  });
  return result;
}
