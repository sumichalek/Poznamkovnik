import {
  addSourceAssets,
  createAssetCollector,
  downloadMarkdownArchive,
  downloadMarkdownBundle,
  extractEmbeddedAssets,
  loadElementSources,
  loadLibrarySources,
  loadTaskSources,
  rebaseAssetLinks,
  sourceMarkdown
} from './markdown-archive.js';

function inlineMarkdown(node) {
  if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || '';
  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const tag = node.tagName.toLowerCase();
  const content = Array.from(node.childNodes, inlineMarkdown).join('');
  if (tag === 'br') return ' '.repeat(2) + String.fromCharCode(10);
  if (tag === 'strong' || tag === 'b') return `**${content}**`;
  if (tag === 'em' || tag === 'i') return `*${content}*`;
  if (tag === 's' || tag === 'strike' || tag === 'del') return `~~${content}~~`;
  if (tag === 'u') return `<u>${content}</u>`;
  if (tag === 'mark') return `<mark>${content}</mark>`;
  if (tag === 'code') return `\`${content.replace(/`/g, '\\`')}\``;
  if (tag === 'img') return `![${node.getAttribute('alt') || ''}](${node.getAttribute('src') || ''})`;
  if (tag === 'a') {
    const label = content.trim() || node.getAttribute('data-label') || node.getAttribute('href') || 'Odkaz';
    if (node.hasAttribute('data-citation')) return `[${label}]`;
    const href = node.getAttribute('href') || '';
    return href ? `[${label}](${href})` : label;
  }
  if (node.dataset.latex) return `$${node.dataset.latex}$`;
  return content;
}

function blockChildren(node) {
  return Array.from(node.childNodes, blockMarkdown).filter(Boolean).join('\n\n');
}

function listItemText(node) {
  return Array.from(node.childNodes)
    .filter((child) => !['UL', 'OL'].includes(child.nodeName))
    .map(inlineMarkdown)
    .join('')
    .replace(/\s+/g, ' ')
    .trim();
}

function listMarkdown(node, depth = 0) {
  const ordered = node.tagName.toLowerCase() === 'ol';
  const items = Array.from(node.children).filter((child) => child.tagName.toLowerCase() === 'li');
  return items
    .map((item, index) => {
      const checkbox = item.dataset.checked;
      const prefix = checkbox === undefined ? (ordered ? `${index + 1}. ` : '- ') : `- [${checkbox === 'true' ? 'x' : ' '}] `;
      const nested = Array.from(item.children)
        .filter((child) => ['ul', 'ol'].includes(child.tagName.toLowerCase()))
        .map((child) => listMarkdown(child, depth + 1))
        .filter(Boolean);
      const head = `${'  '.repeat(depth)}${prefix}${listItemText(item)}`.trimEnd();
      return nested.length ? `${head}\n${nested.join('\n')}` : head;
    })
    .join('\n');
}

function tableMarkdown(node) {
  const rows = Array.from(node.querySelectorAll('tr'))
    .map((row) => Array.from(row.querySelectorAll(':scope > th, :scope > td')))
    .filter((cells) => cells.length);
  if (!rows.length) return '';

  const width = Math.max(...rows.map((cells) => cells.length));
  const values = rows.map((cells) => Array.from({ length: width }, (_, index) => {
    const cell = cells[index];
    return cell ? inlineMarkdown(cell).replace(/[|\n]+/g, ' ').trim() : '';
  }));
  const header = values[0];
  const body = values.slice(1);
  return [
    `| ${header.join(' | ')} |`,
    `| ${header.map(() => '---').join(' | ')} |`,
    ...body.map((row) => `| ${row.join(' | ')} |`)
  ].join('\n');
}

function blockMarkdown(node) {
  if (node.nodeType === Node.TEXT_NODE) return (node.nodeValue || '').trim();
  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const tag = node.tagName.toLowerCase();
  if (/^h[1-6]$/.test(tag)) return `${'#'.repeat(Number(tag.slice(1)))} ${inlineMarkdown(node).trim()}`;
  if (tag === 'p') return inlineMarkdown(node).trim();
  if (tag === 'ul' || tag === 'ol') return listMarkdown(node);
  if (tag === 'blockquote') {
    return blockChildren(node).split('\n').map((line) => `> ${line}`).join('\n');
  }
  if (tag === 'pre') {
    const code = node.querySelector('code');
    const className = code?.className || '';
    const language = className.match(/language-([\w+-]+)/)?.[1] || '';
    return `\`\`\`${language}\n${(code || node).textContent || ''}\n\`\`\``;
  }
  if (tag === 'hr') return '---';
  if (tag === 'table') return tableMarkdown(node);
  if (tag === 'img') return inlineMarkdown(node);
  if (node.dataset.latex && (tag === 'div' || tag === 'p')) return `$$\n${node.dataset.latex}\n$$`;
  return blockChildren(node) || inlineMarkdown(node).trim();
}

function cleanMarkdown(value) {
  return value
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function yamlString(value) {
  return JSON.stringify(String(value || ''));
}

function filenameFor(title) {
  const safe = String(title || 'poznamka')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
  return `${safe || 'poznamka'}.md`;
}

function archiveSegment(value, fallback = 'polozka') {
  return filenameFor(value || fallback).replace(/\.md$/i, '');
}

function uniqueArchivePath(path, usedPaths) {
  const slash = path.lastIndexOf('/');
  const directory = slash === -1 ? '' : path.slice(0, slash + 1);
  const filename = slash === -1 ? path : path.slice(slash + 1);
  const extensionIndex = filename.lastIndexOf('.');
  const stem = extensionIndex === -1 ? filename : filename.slice(0, extensionIndex);
  const extension = extensionIndex === -1 ? '' : filename.slice(extensionIndex);
  let candidate = path;
  let counter = 2;
  while (usedPaths.has(candidate.toLocaleLowerCase('sk'))) {
    candidate = `${directory}${stem}-${counter}${extension}`;
    counter += 1;
  }
  usedPaths.add(candidate.toLocaleLowerCase('sk'));
  return candidate;
}

function mergeAssetStatus(statuses) {
  return (Array.isArray(statuses) ? statuses : []).reduce(
    (summary, status) => {
      summary.missing.push(...(status?.missing || []));
      summary.skipped.push(...(status?.skipped || []));
      return summary;
    },
    { missing: [], skipped: [] }
  );
}

function manifestText(value, maximum = 2_000) {
  return String(value || '').trim().slice(0, maximum);
}

function sourceLinkManifest(sources) {
  return (Array.isArray(sources) ? sources : [])
    .map((source) => ({
      sourceId: manifestText(source?.id, 160),
      title: manifestText(source?.title, 300),
      sourceFileId: manifestText(source?.sourceFileId, 160),
      relationType: manifestText(source?.relationType, 40) || 'reference',
      locator: manifestText(source?.locator, 300),
      label: manifestText(source?.label, 300),
      note: manifestText(source?.note, 2_000)
    }))
    .filter((source) => source.sourceId);
}

function librarySourceManifest(sources) {
  return (Array.isArray(sources) ? sources : [])
    .map((source) => ({
      sourceId: manifestText(source?.id, 160),
      title: manifestText(source?.title, 300),
      note: manifestText(source?.note, 2_000)
    }))
    .filter((source) => source.sourceId);
}

function libraryFolderDirectories(elements) {
  const foldersById = new Map(elements.filter((item) => item.type === 'folder').map((item) => [item.id, item]));
  const segmentByFolderId = new Map();
  const siblingNames = new Map();
  elements.filter((item) => item.type === 'folder').forEach((folder) => {
    const parentKey = foldersById.has(folder.parentId) ? folder.parentId : '';
    const used = siblingNames.get(parentKey) || new Set();
    const base = archiveSegment(folder.title, 'priecinok');
    let candidate = base;
    let counter = 2;
    while (used.has(candidate.toLocaleLowerCase('sk'))) {
      candidate = `${base}-${counter}`;
      counter += 1;
    }
    used.add(candidate.toLocaleLowerCase('sk'));
    siblingNames.set(parentKey, used);
    segmentByFolderId.set(folder.id, candidate);
  });
  const directories = new Map();
  const resolveDirectory = (folderId, seen = new Set()) => {
    if (!folderId || !foldersById.has(folderId) || seen.has(folderId)) return '';
    if (directories.has(folderId)) return directories.get(folderId);
    const folder = foldersById.get(folderId);
    const parent = resolveDirectory(folder.parentId, new Set([...seen, folderId]));
    const directory = [parent, segmentByFolderId.get(folderId)].filter(Boolean).join('/');
    directories.set(folderId, directory);
    return directory;
  };
  foldersById.forEach((_, folderId) => resolveDirectory(folderId));
  return directories;
}

export function libraryElementMarkdown(element, library) {
  const title = String(element?.title || (element?.type === 'article' ? 'Nový článok' : 'Nová poznámka')).trim();
  const document = new DOMParser().parseFromString(element?.content || '', 'text/html');
  const body = cleanMarkdown(blockChildren(document.body));
  const tags = Array.isArray(element?.tags) ? element.tags.filter(Boolean) : [];
  const metadata = [
    '---',
    `title: ${yamlString(title)}`,
    `type: ${yamlString(element?.type === 'article' ? 'article' : 'note')}`,
    `library: ${yamlString(library?.name || '')}`,
    `created: ${yamlString(String(element?.createdAt || '').slice(0, 10))}`,
    `updated: ${yamlString(String(element?.updatedAt || '').slice(0, 10))}`,
    tags.length ? 'tags:' : 'tags: []',
    ...tags.map((tag) => `  - ${yamlString(tag)}`),
    '---'
  ];
  return `${metadata.join('\n')}\n\n# ${title}\n${body ? `\n${body}` : ''}\n`;
}

function taskLinksMarkdown(links) {
  if (!links.length) return '';
  const labels = {
    library: 'Knižnica',
    element: 'Poznámka alebo článok',
    source: 'Zdroj'
  };
  const rows = links.map((link) => {
    const type = labels[link?.targetType] || 'Prepojený prvok';
    const title = String(link?.title || 'Bez názvu');
    const subtitle = String(link?.subtitle || '').trim();
    return '- **' + type + ':** ' + title + (subtitle ? ' (' + subtitle + ')' : '');
  });
  return '## Prepojenia\n\n' + rows.join('\n');
}

function reportBundleResult(result) {
  if (result?.tooLarge) {
    window.alert('Prílohy presahujú 512 MB. Stiahol sa iba Markdown so zoznamom zdrojov.');
  }
  if (result?.skippedFiles?.length) {
    window.alert('Tieto prílohy neboli pridané, aby export neprekročil 512 MB: ' + result.skippedFiles.join(', ') + '.');
  }
  if (result?.missingFiles?.length) {
    window.alert('Export sa stiahol, ale tieto prílohy sa nepodarilo pridať: ' + result.missingFiles.join(', ') + '.');
  }
}

export async function downloadLibraryElementMarkdown(element, library) {
  const collector = createAssetCollector();
  const content = extractEmbeddedAssets(element?.content || '', collector);
  const sources = await loadElementSources(element?.id);
  const assetStatus = await addSourceAssets(sources, collector);
  const markdown = [libraryElementMarkdown({ ...element, content }, library).trim(), sourceMarkdown(sources)]
    .filter(Boolean)
    .join('\n\n')
    .concat('\n');
  reportBundleResult(await downloadMarkdownBundle(filenameFor(element?.title), markdown, collector, assetStatus));
}

export async function downloadLibraryMarkdownArchive(library, elements) {
  if (!library) return;
  const collector = createAssetCollector();
  const statuses = [];
  const files = [];
  const documentSources = [];
  const usedPaths = new Set(['readme.md']);
  const items = Array.isArray(elements) ? elements.filter((item) => item && ['folder', 'note', 'article'].includes(item.type)) : [];
  const directories = libraryFolderDirectories(items);
  const librarySources = await loadLibrarySources(library.id);
  statuses.push(await addSourceAssets(librarySources, collector));

  for (const element of items) {
    if (element.type === 'folder') continue;
    const folderPath = directories.get(element.parentId) || '';
    const path = uniqueArchivePath([folderPath, filenameFor(element.title)].filter(Boolean).join('/'), usedPaths);
    const content = extractEmbeddedAssets(element.content || '', collector);
    const sources = await loadElementSources(element.id, { preserveLinks: true });
    statuses.push(await addSourceAssets(sources, collector));
    const sourceSection = sourceMarkdown(sources);
    const markdown = [libraryElementMarkdown({ ...element, content }, library).trim(), sourceSection]
      .filter(Boolean)
      .join('\n\n')
      .concat('\n');
    const exportedSourceSection = rebaseAssetLinks(sourceSection, path);
    files.push({ name: path, content: rebaseAssetLinks(markdown, path), title: element.title, type: element.type });
    documentSources.push({ path, sourceSection: exportedSourceSection, links: sourceLinkManifest(sources) });
  }

  const contentList = files.length
    ? files.map((file) => `- [${file.title}](${file.name}) (${file.type === 'article' ? 'článok' : 'poznámka'})`).join('\n')
    : '- Knižnica zatiaľ neobsahuje žiadne poznámky ani články.';
  const readme = [
    `# ${library.name}`,
    '',
    'Export z Poznámkovníka vo formáte Markdown.',
    '',
    '## Obsah',
    '',
    contentList,
    sourceMarkdown(librarySources)
  ].filter(Boolean).join('\n') + '\n';
  const manifest = JSON.stringify({
    format: 'poznamkovnik-markdown-export',
    version: 2,
    folders: items
      .filter((item) => item.type === 'folder')
      .map((folder) => ({ path: directories.get(folder.id), title: String(folder.title || 'Priečinok') }))
      .filter((folder) => folder.path),
    librarySources: librarySourceManifest(librarySources),
    documents: documentSources
  }, null, 2) + '\n';
  const archiveFiles = [
    { name: 'README.md', content: readme },
    { name: '.poznamkovnik-export.json', content: manifest },
    ...files.map(({ name, content }) => ({ name, content }))
  ];
  reportBundleResult(await downloadMarkdownArchive(
    `${archiveSegment(library.name, 'kniznica')}-markdown-export.zip`,
    archiveFiles,
    collector,
    mergeAssetStatus(statuses)
  ));
}

function markdownFence(code, language = '') {
  const fence = String(code || '').includes('```') ? '````' : '```';
  return `${fence}${language}\n${String(code || '')}\n${fence}`;
}

function tutorialPageMarkdown(page, language, examples) {
  const content = page?.content && typeof page.content === 'object' ? page.content : {};
  const metadata = [
    '---',
    `title: ${yamlString(page?.title || 'Časť učebnice')}`,
    'type: "tutorial_page"',
    `language: ${yamlString(language?.title || '')}`,
    `kind: ${yamlString(page?.kind || 'lesson')}`,
    `created: ${yamlString(String(page?.createdAt || '').slice(0, 10))}`,
    `updated: ${yamlString(String(page?.updatedAt || '').slice(0, 10))}`,
    '---'
  ];
  const sections = (content.sections || []).flatMap((section) => {
    const rows = [];
    if (section?.title) rows.push(`## ${section.title}`);
    rows.push(...(Array.isArray(section?.paragraphs) ? section.paragraphs : []).filter(Boolean));
    if (Array.isArray(section?.bullets) && section.bullets.length) rows.push(section.bullets.map((item) => `- ${item}`).join('\n'));
    if (section?.callout) rows.push(`> ${section.callout}`);
    return rows.length ? [rows.join('\n\n')] : [];
  });
  const exampleSection = examples.length
    ? [
        '## Skúšobné príklady',
        ...examples.map((example) => {
          const rows = [`### ${example.title}`];
          if (example.description) rows.push(example.description);
          rows.push(markdownFence(example.draftSource ?? example.source, language?.code || 'text'));
          if (example.draftStdin ?? example.stdin) {
            rows.push('#### Vstup');
            rows.push(markdownFence(example.draftStdin ?? example.stdin, 'text'));
          }
          return rows.join('\n\n');
        })
      ].join('\n\n')
    : '';
  const personalNote = String(page?.note || '').trim()
    ? `## Moje poznámky\n\n${String(page.note).trim()}`
    : '';
  return [
    metadata.join('\n'),
    `# ${page?.title || 'Časť učebnice'}`,
    page?.summary ? `_${page.summary}_` : '',
    content.lead || '',
    ...sections,
    exampleSection,
    personalNote
  ].filter(Boolean).join('\n\n') + '\n';
}

function tutorialArchivePaths(pages) {
  const pagesById = new Map(pages.map((page) => [page.id, page]));
  const children = new Map();
  pages.forEach((page) => {
    const parentId = pagesById.has(page.parentId) ? page.parentId : '';
    if (!children.has(parentId)) children.set(parentId, []);
    children.get(parentId).push(page);
  });
  children.forEach((items) => items.sort((first, second) => Number(first.position) - Number(second.position) || String(first.title).localeCompare(String(second.title), 'sk')));
  const paths = new Map();
  const appendChildren = (parentId, directory) => {
    (children.get(parentId) || []).forEach((page, index) => {
      const ordinal = String(index + 1).padStart(2, '0');
      const base = `${ordinal}-${archiveSegment(page.title, 'cast')}`;
      if (page.kind === 'chapter') {
        const chapterDirectory = [directory, base].filter(Boolean).join('/');
        paths.set(page.id, `${chapterDirectory}/README.md`);
        appendChildren(page.id, chapterDirectory);
        return;
      }
      paths.set(page.id, [directory, `${base}.md`].filter(Boolean).join('/'));
      appendChildren(page.id, directory);
    });
  };
  appendChildren('', '');
  return paths;
}

export async function downloadTutorialMarkdownArchive(tutorial) {
  const language = tutorial?.language;
  const pages = Array.isArray(tutorial?.pages) ? tutorial.pages : [];
  if (!language || !pages.length) return;
  const paths = tutorialArchivePaths(pages);
  const examples = Array.isArray(tutorial.examples) ? tutorial.examples : [];
  const files = pages
    .map((page) => {
      const path = paths.get(page.id);
      if (!path) return null;
      return {
        name: path,
        content: tutorialPageMarkdown(page, language, examples.filter((example) => example.pageId === page.id)),
        title: page.title
      };
    })
    .filter(Boolean);
  const readme = [
    `# ${language.title}`,
    '',
    language.summary || 'Export učebnice z Poznámkovníka vo formáte Markdown.',
    '',
    '## Obsah',
    '',
    ...files.map((file) => `- [${file.title}](${file.name})`)
  ].join('\n') + '\n';
  await downloadMarkdownArchive(
    `${archiveSegment(language.title, 'ucebnica')}-markdown-export.zip`,
    [{ name: 'README.md', content: readme }, ...files],
    createAssetCollector()
  );
}

const taskStatusLabels = {
  open: 'Otvorená',
  in_progress: 'Rozpracovaná',
  done: 'Hotová'
};

const taskPriorityLabels = {
  none: 'Bez priority',
  low: 'Nízka',
  medium: 'Stredná',
  high: 'Vysoká'
};

export function taskMarkdown(task) {
  const title = String(task?.title || 'Nová úloha').trim();
  const status = taskStatusLabels[task?.status] ? task.status : 'open';
  const priority = taskPriorityLabels[task?.priority] ? task.priority : 'none';
  const dueDate = String(task?.dueDate || '').trim();
  const tags = Array.isArray(task?.tags) ? task.tags.filter(Boolean) : [];
  const description = cleanMarkdown(String(task?.description || '').replace(/\r\n?/g, '\n'));
  const metadata = [
    '---',
    `title: ${yamlString(title)}`,
    'type: "task"',
    `status: ${yamlString(status)}`,
    `priority: ${yamlString(priority)}`,
    `due: ${yamlString(dueDate)}`,
    tags.length ? 'tags:' : 'tags: []',
    ...tags.map((tag) => `  - ${yamlString(tag)}`),
    '---'
  ];
  const details = [
    `**Stav:** ${taskStatusLabels[status]}`,
    `**Priorita:** ${taskPriorityLabels[priority]}`,
    dueDate ? `**Termín:** ${dueDate}` : ''
  ].filter(Boolean);
  const checkbox = status === 'done' ? 'x' : ' ';
  const hardBreak = String.fromCharCode(32).repeat(2) + String.fromCharCode(10);
  return `${metadata.join('\n')}\n\n# [${checkbox}] ${title}\n\n${details.join(hardBreak)}${description ? `\n\n${description}` : ''}\n`;
}

export async function downloadTaskMarkdown(task) {
  const links = Array.isArray(task?.links) ? task.links : [];
  const sources = await loadTaskSources(links);
  const collector = createAssetCollector();
  const assetStatus = await addSourceAssets(sources, collector);
  const markdown = [taskMarkdown(task).trim(), taskLinksMarkdown(links), sourceMarkdown(sources)]
    .filter(Boolean)
    .join('\n\n')
    .concat('\n');
  reportBundleResult(await downloadMarkdownBundle(filenameFor(String(task?.title || 'uloha') + '-uloha'), markdown, collector, assetStatus));
}
