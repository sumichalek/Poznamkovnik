import { Compartment, EditorState, Prec, RangeSetBuilder, StateEffect, StateField } from '@codemirror/state';
import {
  Decoration,
  EditorView,
  GutterMarker,
  drawSelection,
  gutter,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import {
  bracketMatching,
  defaultHighlightStyle,
  indentOnInput,
  StreamLanguage,
  syntaxHighlighting,
} from '@codemirror/language';
import {
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  closeCompletion,
  completionKeymap,
  completionStatus,
  ifNotIn,
  pickedCompletion,
  snippetCompletion,
} from '@codemirror/autocomplete';
import { cpp } from '@codemirror/lang-cpp';
import { go } from '@codemirror/lang-go';
import { java } from '@codemirror/lang-java';
import { javascript } from '@codemirror/lang-javascript';
import { php } from '@codemirror/lang-php';
import { python } from '@codemirror/lang-python';
import { rust } from '@codemirror/lang-rust';
import { gas } from '@codemirror/legacy-modes/mode/gas';
import { shell } from '@codemirror/legacy-modes/mode/shell';
import { projectCompletionEntries, projectIncludeCompletionEntries } from './development-completions.js';

const languageCompartment = new Compartment();
const setDiagnosticsEffect = StateEffect.define();
let editorView = null;
let suppressChange = false;
let currentLanguageId = 'c';
let projectFiles = [];

class DiagnosticMarker extends GutterMarker {
  constructor(severity) {
    super();
    this.severity = severity;
  }

  toDOM() {
    const marker = document.createElement('span');
    marker.className = `cm-development-diagnostic-marker is-${this.severity}`;
    marker.textContent = '!';
    marker.title = this.severity === 'warning' ? 'Varovanie prekladu' : 'Chyba prekladu';
    marker.setAttribute('aria-label', marker.title);
    marker.setAttribute('role', 'img');
    return marker;
  }
}

function normalizedDiagnostics(diagnostics) {
  const byLine = new Map();
  diagnostics.forEach((diagnostic) => {
    const line = Number(diagnostic?.line || 0);
    if (!Number.isFinite(line) || line < 1) return;
    const severity = diagnostic?.severity === 'warning' ? 'warning' : 'error';
    if (byLine.get(line) !== 'error') byLine.set(line, severity);
  });
  return [...byLine.entries()].sort(([left], [right]) => left - right);
}

function diagnosticRanges(doc, diagnostics) {
  const markers = new RangeSetBuilder();
  const decorations = new RangeSetBuilder();
  normalizedDiagnostics(diagnostics).forEach(([lineNumber, severity]) => {
    const line = doc.line(Math.min(lineNumber, doc.lines));
    markers.add(line.from, line.from, new DiagnosticMarker(severity));
    decorations.add(
      line.from,
      line.from,
      Decoration.line({ class: `cm-development-diagnostic-${severity}` })
    );
  });
  return { markers: markers.finish(), decorations: decorations.finish() };
}

const diagnosticsField = StateField.define({
  create(state) {
    return diagnosticRanges(state.doc, []);
  },
  update(value, transaction) {
    for (const effect of transaction.effects) {
      if (effect.is(setDiagnosticsEffect)) return diagnosticRanges(transaction.state.doc, effect.value);
    }
    if (!transaction.docChanged) return value;
    return {
      markers: value.markers.map(transaction.changes),
      decorations: value.decorations.map(transaction.changes),
    };
  },
  provide(field) {
    return [
      gutter({
        class: 'cm-development-diagnostics-gutter',
        markers: (view) => view.state.field(field).markers,
      }),
      EditorView.decorations.from(field, (value) => value.decorations),
    ];
  },
});

function languageExtension(languageId) {
  switch (languageId) {
    case 'cpp':
    case 'c':
      return cpp();
    case 'csharp':
      // C# shares the familiar C-like structure until we add its dedicated mode.
      return cpp();
    case 'python':
      return python();
    case 'javascript':
      return javascript();
    case 'php':
      return php();
    case 'java':
      return java();
    case 'rust':
      return rust();
    case 'go':
      return go();
    case 'asm':
      return StreamLanguage.define(gas);
    case 'bash':
      return StreamLanguage.define(shell);
    default:
      return cpp();
  }
}

const editorTheme = EditorView.theme({
  '&': {
    height: '100%',
    backgroundColor: 'transparent',
    color: 'var(--text)',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    fontSize: '0.76rem',
  },
  '.cm-scroller': {
    overflow: 'auto',
    fontFamily: 'inherit',
    lineHeight: '1.55',
  },
  '.cm-content': {
    minHeight: '100%',
    padding: 'var(--space-4)',
    caretColor: 'var(--accent)',
    fontFamily: 'inherit',
  },
  '.cm-line': {
    padding: '0',
  },
  '.cm-gutters': {
    minHeight: '100%',
    border: '0',
    borderRight: '1px solid var(--line)',
    backgroundColor: 'color-mix(in srgb, var(--panel-muted) 58%, transparent)',
    color: 'var(--text-muted)',
    fontFamily: 'inherit',
    fontSize: '0.72rem',
    fontWeight: '700',
  },
  '.cm-activeLine': {
    backgroundColor: 'color-mix(in srgb, var(--accent) 8%, transparent)',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'color-mix(in srgb, var(--accent) 14%, transparent)',
    color: 'var(--text)',
  },
  '.cm-line.cm-development-diagnostic-error': {
    backgroundColor: 'color-mix(in srgb, var(--danger) 13%, transparent)',
  },
  '.cm-line.cm-development-diagnostic-warning': {
    backgroundColor: 'color-mix(in srgb, var(--warning) 12%, transparent)',
  },
  '.cm-development-diagnostics-gutter': {
    width: '16px',
    borderRight: '1px solid var(--line)',
    backgroundColor: 'color-mix(in srgb, var(--panel-muted) 58%, transparent)',
  },
  '.cm-development-diagnostic-marker': {
    display: 'grid',
    placeItems: 'center',
    width: '14px',
    height: '14px',
    margin: '2px 1px',
    borderRadius: '50%',
    color: 'var(--button-text)',
    fontFamily: 'ui-sans-serif, system-ui, sans-serif',
    fontSize: '0.62rem',
    fontWeight: '900',
    lineHeight: '1',
  },
  '.cm-development-diagnostic-marker.is-error': {
    backgroundColor: 'var(--danger)',
  },
  '.cm-development-diagnostic-marker.is-warning': {
    backgroundColor: 'var(--warning)',
    color: 'var(--app-bg)',
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: 'color-mix(in srgb, var(--accent) 34%, transparent)',
  },
  '.cm-cursor, .cm-dropCursor': {
    borderLeftColor: 'var(--accent)',
  },
  '.cm-matchingBracket': {
    borderBottom: '1px solid var(--accent)',
    color: 'var(--accent)',
  },
  '.cm-tooltip-autocomplete': {
    overflow: 'hidden',
    border: '1px solid var(--line)',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--panel)',
    boxShadow: 'var(--shadow)',
    color: 'var(--text)',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  },
  '.cm-tooltip-autocomplete > ul': {
    maxHeight: 'min(248px, 42vh)',
    padding: 'var(--space-1)',
  },
  '.cm-tooltip-autocomplete > ul > li': {
    display: 'flex',
    alignItems: 'center',
    minHeight: '26px',
    borderRadius: 'var(--radius-xs)',
    color: 'var(--text)',
    fontSize: '0.72rem',
  },
  '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
    backgroundColor: 'color-mix(in srgb, var(--accent) 18%, transparent)',
    color: 'var(--text)',
  },
  '.cm-completionDetail': {
    marginLeft: 'var(--space-3)',
    color: 'var(--text-muted)',
    fontStyle: 'normal',
  },
}, { dark: true });

function completionSource(context) {
  const word = context.matchBefore(/[A-Za-z_$][A-Za-z0-9_$]*/);
  if (!word && !context.explicit) return null;
  const options = projectCompletionEntries(currentLanguageId, [
    ...projectFiles,
    { title: 'aktuálny súbor', content: context.state.doc.toString() },
  ]).map((entry) => entry.template
    ? snippetCompletion(entry.template, { label: entry.label, type: entry.type, detail: entry.detail })
    : entry);
  if (!options.length) return null;
  return {
    from: word ? word.from : context.pos,
    options,
    validFor: /^[A-Za-z_$][A-Za-z0-9_$]*$/,
  };
}

const genericCompletionSource = ifNotIn(['Comment', 'String'], completionSource);

function includeCompletionSource(context) {
  if (!['c', 'cpp'].includes(currentLanguageId)) return null;
  const line = context.state.doc.lineAt(context.pos);
  const beforeCursor = line.text.slice(0, context.pos - line.from);
  const include = beforeCursor.match(/^\s*#\s*include\s*([<"])([^">]*)$/);
  if (!include) return null;
  const entries = projectIncludeCompletionEntries(currentLanguageId, projectFiles, {
    local: include[1] === '"',
  });
  if (!entries.length) return null;
  const closingCharacter = include[1] === '"' ? '"' : '>';
  return {
    from: context.pos - include[2].length,
    options: entries.map((entry) => ({
      ...entry,
      apply(view, completion, from, to) {
        const closingIsPresent = view.state.sliceDoc(to, to + 1) === closingCharacter;
        const inserted = `${completion.label}${closingIsPresent ? '' : closingCharacter}`;
        view.dispatch({
          changes: { from, to, insert: inserted },
          selection: { anchor: from + inserted.length },
          annotations: pickedCompletion.of(completion),
        });
      },
    })),
    validFor: /^[^">]*$/,
  };
}

function developmentCompletionSource(context) {
  return includeCompletionSource(context) || genericCompletionSource(context);
}

export function initializeDevelopmentEditor({ mount, onChange, onFind, onReplace, onSave, onRun }) {
  if (!mount || editorView) return;
  editorView = new EditorView({
    state: EditorState.create({
      doc: '',
      extensions: [
        lineNumbers(),
        diagnosticsField,
        highlightActiveLineGutter(),
        history(),
        drawSelection(),
        highlightActiveLine(),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        autocompletion({
          activateOnTyping: true,
          aboveCursor: true,
          defaultKeymap: false,
          interactionDelay: 0,
          selectOnOpen: true,
          override: [developmentCompletionSource],
        }),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        languageCompartment.of(languageExtension('c')),
        keymap.of([
          { key: 'Mod-f', run: () => { onFind?.(); return true; } },
          { key: 'Mod-h', run: () => { onReplace?.(); return true; } },
          { key: 'Mod-s', run: () => { onSave?.(); return true; } },
          { key: 'Mod-Enter', run: () => { onRun?.(); return true; } },
          indentWithTab,
          ...closeBracketsKeymap,
          ...defaultKeymap,
          ...historyKeymap,
        ]),
        Prec.highest(keymap.of(completionKeymap)),
        EditorView.domEventHandlers({
          keydown(event, view) {
            if (event.key !== 'Escape' || completionStatus(view.state) !== 'active') return false;
            closeCompletion(view);
            event.preventDefault();
            event.stopPropagation();
            return true;
          },
        }),
        EditorView.contentAttributes.of({ 'aria-label': 'Zdrojový kód' }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged && !suppressChange) onChange?.(update.state.doc.toString());
        }),
        editorTheme,
      ],
    }),
    parent: mount,
  });
}

export function developmentEditorValue() {
  return editorView?.state.doc.toString() || '';
}

export function developmentEditorSelection() {
  const selection = editorView?.state.selection.main;
  return { from: selection?.from || 0, to: selection?.to || 0 };
}

export function setDevelopmentEditorDocument(value, languageId = 'c') {
  if (!editorView) return;
  const content = String(value || '');
  const documentChanged = editorView.state.doc.toString() !== content;
  const languageChanged = currentLanguageId !== languageId;
  if (!documentChanged && !languageChanged) return;
  suppressChange = true;
  try {
    const transaction = {};
    if (documentChanged) {
      transaction.changes = { from: 0, to: editorView.state.doc.length, insert: content };
      transaction.selection = { anchor: 0 };
    }
    if (languageChanged) transaction.effects = languageCompartment.reconfigure(languageExtension(languageId));
    editorView.dispatch(transaction);
    currentLanguageId = languageId;
  } finally {
    suppressChange = false;
  }
}

export function setDevelopmentEditorLanguage(languageId) {
  if (!editorView || currentLanguageId === languageId) return;
  editorView.dispatch({ effects: languageCompartment.reconfigure(languageExtension(languageId)) });
  currentLanguageId = languageId;
}

export function setDevelopmentEditorProjectFiles(files = []) {
  projectFiles = Array.isArray(files)
    ? files.map((file) => ({
      title: String(file?.title || ''),
      path: String(file?.path || file?.title || ''),
      content: String(file?.content || ''),
    }))
    : [];
}

export function setDevelopmentEditorDiagnostics(diagnostics = []) {
  if (!editorView) return;
  editorView.dispatch({
    effects: setDiagnosticsEffect.of(Array.isArray(diagnostics) ? diagnostics : []),
  });
}

export function focusDevelopmentEditor() {
  editorView?.focus();
}

export function selectDevelopmentEditorRange(from, to = from) {
  if (!editorView) return;
  const length = editorView.state.doc.length;
  const start = Math.min(Math.max(0, from), length);
  const end = Math.min(Math.max(start, to), length);
  editorView.dispatch({ selection: { anchor: start, head: end }, scrollIntoView: true });
  editorView.focus();
}

export function replaceDevelopmentEditorRange(from, to, replacement) {
  if (!editorView) return;
  const length = editorView.state.doc.length;
  const start = Math.min(Math.max(0, from), length);
  const end = Math.min(Math.max(start, to), length);
  const text = String(replacement || '');
  editorView.dispatch({
    changes: { from: start, to: end, insert: text },
    selection: { anchor: start + text.length },
    scrollIntoView: true,
  });
  editorView.focus();
}
