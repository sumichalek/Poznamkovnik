import { Editor, Node } from '@tiptap/core';
import Highlight from '@tiptap/extension-highlight';
import Image from '@tiptap/extension-image';
import { BlockMath, InlineMath } from '@tiptap/extension-mathematics';
import { Table } from '@tiptap/extension-table';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import TableRow from '@tiptap/extension-table-row';
import TaskItem from '@tiptap/extension-task-item';
import TaskList from '@tiptap/extension-task-list';
import StarterKit from '@tiptap/starter-kit';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { dom } from './dom.js';

const MAX_EMBEDDED_FILE_SIZE = 1_500_000;
const EMPTY_DOCUMENT = '<p></p>';
const KATEX_OPTIONS = { throwOnError: false, trust: false };
const KATEX_PREVIEW_OPTIONS = { ...KATEX_OPTIONS, throwOnError: true };
const INLINE_KATEX_OPTIONS = { ...KATEX_OPTIONS, displayMode: false };
const BLOCK_KATEX_OPTIONS = { ...KATEX_OPTIONS, displayMode: true };

const Citation = Node.create({
  name: 'citation',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      source: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-source') || ''
      },
      locator: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-locator') || ''
      },
      label: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-label') || ''
      }
    };
  },
  parseHTML() {
    return [{ tag: 'span[data-citation]' }];
  },
  renderHTML({ node }) {
    const label = node.attrs.label || node.attrs.source || 'Zdroj';
    return [
      'span',
      {
        class: 'article-citation',
        'data-citation': '',
        'data-source': node.attrs.source,
        'data-locator': node.attrs.locator,
        'data-label': label,
        contenteditable: 'false',
        title: node.attrs.locator ? `${node.attrs.source}, ${node.attrs.locator}` : node.attrs.source
      },
      `(${label})`
    ];
  }
});

const Attachment = Node.create({
  name: 'attachment',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      href: {
        default: '',
        parseHTML: (element) => element.getAttribute('href') || ''
      },
      name: {
        default: 'Príloha',
        parseHTML: (element) => element.getAttribute('data-attachment-name') || element.textContent || 'Príloha'
      },
      type: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-attachment-type') || ''
      }
    };
  },
  parseHTML() {
    return [{ tag: 'a[data-attachment]' }];
  },
  renderHTML({ node }) {
    return [
      'a',
      {
        class: 'article-attachment',
        'data-attachment': '',
        'data-attachment-name': node.attrs.name,
        'data-attachment-type': node.attrs.type,
        href: node.attrs.href,
        download: node.attrs.name,
        title: node.attrs.name,
        contenteditable: 'false'
      },
      node.attrs.name
    ];
  }
});

let articleEditor = null;
let onEditorUpdate = () => {};
let activeMathDialog = null;

function mathDialogTitle(kind, isEditing) {
  const label = kind === 'block' ? 'Samostatný vzorec' : 'Vzorec v texte';
  return isEditing ? `Upraviť: ${label}` : label;
}

function renderMathPreview() {
  const latex = dom.mathLatex.value.trim();
  dom.mathPreview.replaceChildren();
  dom.mathError.hidden = true;
  dom.mathError.textContent = '';
  dom.mathSubmit.disabled = !latex;
  if (!latex) return false;

  try {
    katex.render(latex, dom.mathPreview, {
      ...KATEX_PREVIEW_OPTIONS,
      displayMode: activeMathDialog?.kind === 'block'
    });
    return true;
  } catch {
    dom.mathPreview.textContent = latex;
    dom.mathError.textContent = 'Zápis vzorca nie je platný.';
    dom.mathError.hidden = false;
    dom.mathSubmit.disabled = true;
    return false;
  }
}

export function openMathDialog({ kind, latex = '', pos = null }) {
  activeMathDialog = { kind, pos };
  dom.mathDialogTitle.textContent = mathDialogTitle(kind, pos !== null);
  dom.mathLatex.value = latex;
  renderMathPreview();
  dom.mathDialog.showModal();
  dom.mathLatex.focus();
  dom.mathLatex.select();
}

export function updateMathPreview() {
  return renderMathPreview();
}

export function closeMathDialog() {
  if (dom.mathDialog.open) dom.mathDialog.close();
}

export function resetMathDialog() {
  activeMathDialog = null;
  dom.mathForm.reset();
  dom.mathPreview.replaceChildren();
  dom.mathError.hidden = true;
  dom.mathError.textContent = '';
  dom.mathSubmit.disabled = false;
}

export function submitMathDialog() {
  if (!articleEditor || !activeMathDialog || !renderMathPreview()) return false;

  const latex = dom.mathLatex.value.trim();
  const { kind, pos } = activeMathDialog;
  const chain = articleEditor.chain().focus();
  const command =
    pos === null
      ? kind === 'block'
        ? chain.insertBlockMath({ latex })
        : chain.insertInlineMath({ latex })
      : kind === 'block'
        ? chain.updateBlockMath({ latex, pos })
        : chain.updateInlineMath({ latex, pos });
  const inserted = command.run();
  if (inserted) closeMathDialog();
  return inserted;
}

function editorAttributes(placeholder) {
  return {
    class: 'article-editor-surface',
    'aria-label': 'Text prvku',
    'data-placeholder': placeholder
  };
}

function documentIsEmpty(editor) {
  const { doc } = editor.state;
  return doc.childCount === 1 && doc.firstChild?.type.name === 'paragraph' && doc.firstChild.content.size === 0;
}

function syncEditorEmptyState(editor) {
  editor.view.dom.classList.toggle('is-editor-empty', documentIsEmpty(editor));
}

function citationLabel(source, locator) {
  return locator ? `${source}, ${locator}` : source;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener('load', () => resolve(String(reader.result || '')));
    reader.addEventListener('error', () => reject(reader.error || new Error('Súbor sa nepodarilo načítať.')));
    reader.readAsDataURL(file);
  });
}

export function initializeArticleEditor({ onUpdate } = {}) {
  if (articleEditor) return articleEditor;
  onEditorUpdate = onUpdate || onEditorUpdate;

  articleEditor = new Editor({
    element: dom.libraryEditorBody,
    content: EMPTY_DOCUMENT,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4, 5, 6] },
        link: {
          autolink: true,
          linkOnPaste: true,
          openOnClick: false,
          defaultProtocol: 'https'
        }
      }),
      Highlight.configure({ multicolor: false }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      Image.configure({ allowBase64: true }),
      InlineMath.configure({
        onClick: (node, pos) => openMathDialog({ kind: 'inline', latex: node.attrs.latex, pos }),
        katexOptions: INLINE_KATEX_OPTIONS
      }),
      BlockMath.configure({
        onClick: (node, pos) => openMathDialog({ kind: 'block', latex: node.attrs.latex, pos }),
        katexOptions: BLOCK_KATEX_OPTIONS
      }),
      Citation,
      Attachment
    ],
    editorProps: {
      attributes: editorAttributes('Píšte poznámku...')
    },
    onCreate: ({ editor }) => syncEditorEmptyState(editor),
    onUpdate: ({ editor }) => {
      syncEditorEmptyState(editor);
      onEditorUpdate();
    }
  });

  return articleEditor;
}

export function setArticleEditorContent(content, placeholder) {
  if (!articleEditor) return;
  articleEditor.commands.setContent(content || EMPTY_DOCUMENT, { emitUpdate: false });
  syncEditorEmptyState(articleEditor);
  articleEditor.setOptions({
    editorProps: {
      attributes: editorAttributes(placeholder)
    }
  });
}

export function clearArticleEditor() {
  if (!articleEditor) return;
  articleEditor.commands.setContent(EMPTY_DOCUMENT, { emitUpdate: false });
  syncEditorEmptyState(articleEditor);
}

export function focusArticleEditor() {
  articleEditor?.commands.focus('end');
}

export function articleEditorContent() {
  if (!articleEditor || documentIsEmpty(articleEditor)) return '';
  return articleEditor.getHTML();
}

export function runArticleEditorAction(action, value = {}) {
  if (!articleEditor) return false;
  const chain = articleEditor.chain().focus();

  switch (action) {
    case 'heading-2':
      return chain.toggleHeading({ level: 2 }).run();
    case 'heading-3':
      return chain.toggleHeading({ level: 3 }).run();
    case 'bold':
      return chain.toggleBold().run();
    case 'italic':
      return chain.toggleItalic().run();
    case 'underline':
      return chain.toggleUnderline().run();
    case 'strike':
      return chain.toggleStrike().run();
    case 'highlight':
      return chain.toggleHighlight().run();
    case 'bullet-list':
      return chain.toggleBulletList().run();
    case 'ordered-list':
      return chain.toggleOrderedList().run();
    case 'task-list':
      return chain.toggleTaskList().run();
    case 'blockquote':
      return chain.toggleBlockquote().run();
    case 'code-block':
      return chain.toggleCodeBlock().run();
    case 'divider':
      return chain.setHorizontalRule().run();
    case 'table':
      return chain.insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
    case 'link': {
      const href = String(value.href || '').trim();
      if (!href) return false;
      if (articleEditor.state.selection.empty) {
        return chain.insertContent({
          type: 'text',
          text: value.label || href,
          marks: [{ type: 'link', attrs: { href } }]
        }).run();
      }
      return chain.extendMarkRange('link').setLink({ href }).run();
    }
    case 'citation': {
      const source = String(value.source || '').trim();
      const locator = String(value.locator || '').trim();
      if (!source) return false;
      return chain
        .insertContent({
          type: 'citation',
          attrs: { source, locator, label: citationLabel(source, locator) }
        })
        .insertContent(' ')
        .run();
    }
    default:
      return false;
  }
}

export async function insertArticleFile(file, kind) {
  if (!articleEditor || !file) return false;
  if (file.size > MAX_EMBEDDED_FILE_SIZE) {
    window.alert('Súbor je príliš veľký na uloženie priamo v článku. Maximálna veľkosť je 1,5 MB.');
    return false;
  }

  try {
    const dataUrl = await readFileAsDataUrl(file);
    const chain = articleEditor.chain().focus();
    if (kind === 'image') {
      return chain.insertContent({
        type: 'image',
        attrs: { src: dataUrl, alt: file.name, title: file.name }
      }).run();
    }
    return chain
      .insertContent({
        type: 'attachment',
        attrs: { href: dataUrl, name: file.name, type: file.type }
      })
      .insertContent(' ')
      .run();
  } catch {
    window.alert('Súbor sa nepodarilo vložiť.');
    return false;
  }
}
