function normalizedLines(markdown) {
  return String(markdown || '').replace(/\r\n?/g, '\n').split('\n');
}

function readablePathSegment(value) {
  const text = decodeURIComponent(String(value || '').replace(/\.[^.]+$/, '').replace(/^\d{2}-/, '').replace(/[-_]+/g, ' '));
  return text.replace(/\s+/g, ' ').trim() || 'Importovaná kapitola';
}

function cleanedParagraphs(lines) {
  const paragraphs = [];
  let buffer = [];
  const flush = () => {
    const text = buffer.join('\n').trim();
    if (text) paragraphs.push(text);
    buffer = [];
  };
  lines.forEach((line) => {
    if (!line.trim()) {
      flush();
      return;
    }
    buffer.push(line);
  });
  flush();
  return paragraphs;
}

function sectionFromMarkdown(title, lines) {
  const paragraphs = [];
  const bullets = [];
  const quote = [];
  let buffer = [];
  const flush = () => {
    const text = buffer.join('\n').trim();
    if (text) paragraphs.push(text);
    buffer = [];
  };
  lines.forEach((line) => {
    const bullet = line.match(/^\s*(?:[-+*]|\d+\.)\s+(.+)$/);
    if (bullet) {
      flush();
      bullets.push(bullet[1].trim());
      return;
    }
    if (line.startsWith('>')) {
      flush();
      quote.push(line.replace(/^>\s?/, '').trim());
      return;
    }
    if (!line.trim()) {
      flush();
      return;
    }
    buffer.push(line);
  });
  flush();
  return {
    title: String(title || '').trim(),
    paragraphs,
    bullets,
    callout: quote.join('\n').trim()
  };
}

function pageContent(markdown) {
  const lines = normalizedLines(markdown);
  let index = 0;
  while (index < lines.length && !lines[index].trim()) index += 1;
  let summary = '';
  const summaryMatch = lines[index]?.trim().match(/^_(.+)_$/);
  if (summaryMatch) {
    summary = summaryMatch[1].trim();
    index += 1;
  }
  const intro = [];
  const sections = [];
  let sectionTitle = '';
  let sectionLines = [];
  const flushSection = () => {
    if (!sectionTitle) return;
    const section = sectionFromMarkdown(sectionTitle, sectionLines);
    if (section.title || section.paragraphs.length || section.bullets.length || section.callout) sections.push(section);
    sectionTitle = '';
    sectionLines = [];
  };
  for (; index < lines.length; index += 1) {
    const heading = lines[index].match(/^##\s+(.+)$/);
    if (heading) {
      flushSection();
      sectionTitle = heading[1].trim();
      continue;
    }
    if (sectionTitle) sectionLines.push(lines[index]);
    else intro.push(lines[index]);
  }
  flushSection();
  const notesIndex = sections.findIndex((section) => section.title.toLocaleLowerCase('sk') === 'moje poznámky');
  const notes = notesIndex === -1
    ? ''
    : [
        ...sections[notesIndex].paragraphs,
        ...sections[notesIndex].bullets.map((item) => `- ${item}`),
        sections[notesIndex].callout ? `> ${sections[notesIndex].callout}` : ''
      ].filter(Boolean).join('\n\n');
  if (notesIndex !== -1) sections.splice(notesIndex, 1);
  return {
    summary,
    content: {
      lead: cleanedParagraphs(intro).join('\n\n'),
      sections
    },
    notes
  };
}

function folderTitleMap(preview) {
  return new Map((preview?.folders || []).map((folder) => [folder.path, folder.title]));
}

function documentKind(document) {
  const kind = String(document?.metadata?.kind || '').toLocaleLowerCase('sk');
  if (['chapter', 'lesson', 'reference'].includes(kind)) return kind;
  return String(document?.path || '').toLocaleLowerCase('sk').endsWith('/readme.md') || String(document?.path || '').toLocaleLowerCase('sk') === 'readme.md'
    ? 'chapter'
    : 'lesson';
}

function sourceChapterTitle(preview) {
  return readablePathSegment(String(preview?.sourceName || 'Importovaná učebnica').replace(/\.zip$/i, ''));
}

function counted(count, one, few, many) {
  return `${count} ${count === 1 ? one : count >= 2 && count <= 4 ? few : many}`;
}

export function tutorialMarkdownImportPlan(preview) {
  const folders = folderTitleMap(preview);
  const specs = new Map();
  const warnings = [...(preview?.warnings || [])];
  const rootKey = '__import_root__';
  const ensureChapter = (directory) => {
    const path = String(directory || '');
    const key = path ? `folder:${path}` : `folder:${rootKey}`;
    if (specs.has(key)) return key;
    const parentPath = path.split('/').slice(0, -1).filter(Boolean).join('/');
    const parentKey = path && parentPath ? ensureChapter(parentPath) : '';
    const segment = path.split('/').at(-1);
    specs.set(key, {
      key,
      parentKey,
      kind: 'chapter',
      title: path ? folders.get(path) || readablePathSegment(segment) : sourceChapterTitle(preview),
      summary: '',
      content: { lead: '', sections: [] },
      notes: '',
      depth: path ? path.split('/').length : 0,
      path: path || String(preview?.sourceName || 'import')
    });
    return key;
  };

  (preview?.documents || []).forEach((document) => {
    const directory = Array.isArray(document.directory) ? document.directory.join('/') : '';
    const kind = documentKind(document);
    const parsed = pageContent(document.markdown);
    if (kind === 'chapter') {
      const chapterKey = ensureChapter(directory);
      specs.set(chapterKey, {
        ...specs.get(chapterKey),
        title: document.title,
        summary: parsed.summary,
        content: parsed.content,
        notes: parsed.notes,
        path: document.path
      });
      return;
    }
    const parentKey = ensureChapter(directory);
    const key = `document:${document.path}`;
    specs.set(key, {
      key,
      parentKey,
      kind,
      title: document.title,
      summary: parsed.summary,
      content: parsed.content,
      notes: parsed.notes,
      depth: directory ? directory.split('/').length + 1 : 1,
      path: document.path
    });
  });

  const pages = [...specs.values()]
    .sort((first, second) => (
      first.depth - second.depth
      || Number(first.kind !== 'chapter') - Number(second.kind !== 'chapter')
      || first.path.localeCompare(second.path, 'sk')
    ));
  const chapterCount = pages.filter((page) => page.kind === 'chapter').length;
  const lessonCount = pages.filter((page) => page.kind === 'lesson').length;
  const referenceCount = pages.filter((page) => page.kind === 'reference').length;
  if (preview?.attachments) warnings.push('Prílohy zo ZIP-u sa do učebnice zatiaľ nevkladajú.');
  if (pages.some((page) => page.content.sections.some((section) => section.title.toLocaleLowerCase('sk') === 'skúšobné príklady'))) {
    warnings.push('Skúšobné príklady sa zatiaľ uložia ako text. Interaktívne príklady doplníme v ďalšom kroku.');
  }
  return {
    pages,
    warnings: [...new Set(warnings)],
    summary: [
      counted(chapterCount, 'kapitola', 'kapitoly', 'kapitol'),
      counted(lessonCount, 'lekcia', 'lekcie', 'lekcií'),
      referenceCount ? counted(referenceCount, 'referencia', 'referencie', 'referencií') : ''
    ].filter(Boolean).join(' · ')
  };
}

export function tutorialMarkdownPreview(preview) {
  const plan = tutorialMarkdownImportPlan(preview);
  return {
    summary: plan.summary,
    warnings: plan.warnings,
    items: plan.pages.map((page) => ({
      type: page.kind === 'chapter' ? 'Kapitola' : page.kind === 'reference' ? 'Referencia' : 'Lekcia',
      title: page.title,
      path: page.path
    }))
  };
}
