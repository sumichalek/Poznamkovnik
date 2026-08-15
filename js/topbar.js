import { dom } from './dom.js';
import { state } from './state.js';

function topbarShouldStayVisible() {
  return (
    state.pointerNearTop ||
    dom.settingsDialog.open ||
    dom.librariesPanel.classList.contains('is-open') ||
    dom.libraryDetailPanel.classList.contains('is-open') ||
    dom.sourcesPanel.classList.contains('is-open') ||
    dom.sourcePreviewDock.classList.contains('is-open') ||
    dom.tasksPanel.classList.contains('is-open') ||
    dom.taskDetailDock.classList.contains('is-open') ||
    dom.calendarPanel.classList.contains('is-open') ||
    dom.calendarEventDock.classList.contains('is-open') ||
    dom.tutorialPanel.classList.contains('is-open') ||
    dom.tutorialPlaygroundDock.classList.contains('is-open') ||
    dom.musicDock.classList.contains('is-open') ||
    dom.topbar.matches(':hover') ||
    dom.topbar.contains(document.activeElement)
  );
}

export function updateTopbarVisibility() {
  window.clearTimeout(state.hideTimer);
  if (topbarShouldStayVisible()) {
    dom.topbar.classList.remove('is-hidden');
    return;
  }

  state.hideTimer = window.setTimeout(() => {
    if (!topbarShouldStayVisible()) dom.topbar.classList.add('is-hidden');
  }, 240);
}

export function hideTopbarImmediately() {
  window.clearTimeout(state.hideTimer);
  state.pointerNearTop = false;
  if (dom.topbar.contains(document.activeElement) && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
  dom.topbar.classList.add('is-hidden');
}
