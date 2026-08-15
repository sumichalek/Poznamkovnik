export const APP_VERSION = '0.31.2';

export const HORIZONTAL_EDITOR_MIN_WIDTH = 1120;
export const HORIZONTAL_EDITOR_MIN_RATIO = 1.15;

export const storageKeys = {
  theme: 'knowledge-theme',
  libraries: 'knowledge-libraries',
  activeLibrary: 'knowledge-active-library',
  libraryElements: 'knowledge-library-elements',
  workspaceOwner: 'knowledge-workspace-owner',
  editorDockInlineSize: 'knowledge-editor-dock-inline-size',
  editorDockBlockSize: 'knowledge-editor-dock-block-size',
  sourceDetailInlineSize: 'knowledge-source-detail-inline-size',
  sourceDetailBlockSize: 'knowledge-source-detail-block-size',
  sourcePreviewInlineSize: 'knowledge-source-preview-inline-size',
  tutorialPlaygroundInlineSize: 'knowledge-tutorial-playground-inline-size',
  tutorialPlaygroundBlockSize: 'knowledge-tutorial-playground-block-size',
  musicVolume: 'knowledge-music-volume',
  musicTrackId: 'knowledge-music-track-id',
  musicPosition: 'knowledge-music-position',
  musicPlaylistId: 'knowledge-music-playlist-id',
  musicShuffle: 'knowledge-music-shuffle',
  musicRepeat: 'knowledge-music-repeat',
  musicDockInlineSize: 'knowledge-music-dock-inline-size',
  musicSleepTimerMinutes: 'knowledge-music-sleep-timer-minutes',
  musicSleepTimerEndsAt: 'knowledge-music-sleep-timer-ends-at'
};

export const TOPBAR_REVEAL_DISTANCE = 72;
export const LEFT_PANEL_REVEAL_DISTANCE = 18;
export const themes = new Set(['focus', 'paper', 'dark', 'contrast']);
export const elementTypes = new Set(['folder', 'note', 'article']);
export const elementTypeLabels = {
  folder: 'Priečinok',
  note: 'Poznámka',
  article: 'Článok'
};
