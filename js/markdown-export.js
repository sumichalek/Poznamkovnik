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

function downloadMarkdown(filename, markdown) {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
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

export function downloadLibraryElementMarkdown(element, library) {
  downloadMarkdown(filenameFor(element?.title), libraryElementMarkdown(element, library));
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

export function downloadTaskMarkdown(task) {
  downloadMarkdown(filenameFor(`${task?.title || 'uloha'}-uloha`), taskMarkdown(task));
}
