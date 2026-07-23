export const APP_VERSION = '0.12.1';

export const HORIZONTAL_EDITOR_MIN_WIDTH = 1120;
export const HORIZONTAL_EDITOR_MIN_RATIO = 1.15;

export const storageKeys = {
  theme: 'knowledge-theme',
  libraries: 'knowledge-libraries',
  activeLibrary: 'knowledge-active-library',
  libraryElements: 'knowledge-library-elements',
  workspaceOwner: 'knowledge-workspace-owner',
  editorDockInlineSize: 'knowledge-editor-dock-inline-size',
  editorDockBlockSize: 'knowledge-editor-dock-block-size'
};

export const TOPBAR_REVEAL_DISTANCE = 72;
export const themes = new Set(['focus', 'paper', 'dark', 'contrast']);
export const elementTypes = new Set(['folder', 'note', 'article']);
export const elementTypeLabels = {
  folder: 'Priečinok',
  note: 'Poznámka',
  article: 'Článok'
};
