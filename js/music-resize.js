import { storageKeys } from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';

const INLINE_MIN_SIZE = 360;
const NARROW_VIEWPORT_MAX = 800;

let activePointerId = null;

function viewportWidth() {
  return window.visualViewport?.width || window.innerWidth;
}

function isResizable() {
  return viewportWidth() > NARROW_VIEWPORT_MAX && document.body.dataset.editorAxis !== 'vertical';
}

function sizeRange() {
  const width = viewportWidth();
  const reservedForWorkspace = Math.max(300, Math.round(width * 0.22));
  const max = Math.max(INLINE_MIN_SIZE, width - reservedForWorkspace);
  return { min: INLINE_MIN_SIZE, max };
}

function clampSize(value) {
  const { min, max } = sizeRange();
  return Math.round(Math.min(max, Math.max(min, value)));
}

function currentSize() {
  if (Number.isFinite(state.musicDockInlineSize) && state.musicDockInlineSize > 0) return state.musicDockInlineSize;
  return Math.round(dom.musicDock.getBoundingClientRect().width);
}

function setSize(value, { persist = true, refresh = true } = {}) {
  const nextSize = clampSize(value);
  state.musicDockInlineSize = nextSize;
  document.documentElement.style.setProperty('--music-dock-inline-size', `${nextSize}px`);
  if (persist) localStorage.setItem(storageKeys.musicDockInlineSize, String(nextSize));
  if (refresh) refreshMusicResizeHandle();
  return nextSize;
}

function updateHandleAccessibility() {
  const open = dom.musicDock.classList.contains('is-open') && isResizable();
  const { min, max } = sizeRange();
  const size = clampSize(currentSize());
  dom.musicResizeHandle.setAttribute('aria-hidden', String(!open));
  dom.musicResizeHandle.tabIndex = open ? 0 : -1;
  dom.musicResizeHandle.setAttribute('aria-valuemin', String(min));
  dom.musicResizeHandle.setAttribute('aria-valuemax', String(max));
  dom.musicResizeHandle.setAttribute('aria-valuenow', String(size));
  dom.musicResizeHandle.setAttribute('aria-valuetext', `${size} px`);
}

function resizeFromPointer(event) {
  setSize(viewportWidth() - event.clientX, { persist: false });
}

function finishResize(event) {
  if (activePointerId === null || event.pointerId !== activePointerId) return;
  if (dom.musicResizeHandle.hasPointerCapture(event.pointerId)) dom.musicResizeHandle.releasePointerCapture(event.pointerId);
  localStorage.setItem(storageKeys.musicDockInlineSize, String(state.musicDockInlineSize));
  activePointerId = null;
  document.body.classList.remove('is-music-resizing');
}

function startResize(event) {
  if (!dom.musicDock.classList.contains('is-open') || !isResizable() || event.button !== 0) return;
  event.preventDefault();
  activePointerId = event.pointerId;
  dom.musicResizeHandle.setPointerCapture(event.pointerId);
  document.body.classList.add('is-music-resizing');
  resizeFromPointer(event);
}

function resizeFromKeyboard(event) {
  if (!dom.musicDock.classList.contains('is-open') || !isResizable()) return;
  const step = event.shiftKey ? 32 : 12;
  let nextSize = currentSize();
  if (event.key === 'Home') nextSize = sizeRange().min;
  else if (event.key === 'End') nextSize = sizeRange().max;
  else if (event.key === 'ArrowLeft') nextSize += step;
  else if (event.key === 'ArrowRight') nextSize -= step;
  else return;
  event.preventDefault();
  setSize(nextSize);
}

export function refreshMusicResizeHandle() {
  if (!dom.musicResizeHandle) return;
  if (Number.isFinite(state.musicDockInlineSize) && state.musicDockInlineSize > 0) {
    setSize(state.musicDockInlineSize, { persist: false, refresh: false });
  }
  updateHandleAccessibility();
}

export function initializeMusicResizing() {
  const stored = Number(localStorage.getItem(storageKeys.musicDockInlineSize));
  if (Number.isFinite(stored) && stored > 0) {
    state.musicDockInlineSize = stored;
    document.documentElement.style.setProperty('--music-dock-inline-size', `${stored}px`);
  }
  dom.musicResizeHandle.addEventListener('pointerdown', startResize);
  dom.musicResizeHandle.addEventListener('pointermove', (event) => {
    if (event.pointerId === activePointerId) resizeFromPointer(event);
  });
  dom.musicResizeHandle.addEventListener('pointerup', finishResize);
  dom.musicResizeHandle.addEventListener('pointercancel', finishResize);
  dom.musicResizeHandle.addEventListener('keydown', resizeFromKeyboard);
  window.addEventListener('resize', refreshMusicResizeHandle);
}
