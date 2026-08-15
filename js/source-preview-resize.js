import { storageKeys } from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';

const INLINE_MIN_SIZE = 440;
const NARROW_VIEWPORT_MAX = 800;

let activePointerId = null;

function viewportWidth() {
  return window.visualViewport?.width || window.innerWidth;
}

function isResizable() {
  return viewportWidth() > NARROW_VIEWPORT_MAX && !dom.sourcePreviewDock.classList.contains('is-fullscreen');
}

function sizeRange() {
  const width = viewportWidth();
  const reservedForSource = Math.max(300, Math.round(width * 0.2));
  const detailIsOpen = state.editorAxis === 'horizontal' && dom.sourceDetailDock.classList.contains('is-open');
  const detailWidth = detailIsOpen ? Math.round(dom.sourceDetailDock.getBoundingClientRect().width) : Number.POSITIVE_INFINITY;
  const max = Math.max(0, Math.min(width - reservedForSource, detailWidth));
  return {
    min: Math.min(INLINE_MIN_SIZE, max),
    max
  };
}

function clampSize(value) {
  const { min, max } = sizeRange();
  return Math.round(Math.min(max, Math.max(min, value)));
}

function currentSize() {
  if (Number.isFinite(state.sourcePreviewInlineSize) && state.sourcePreviewInlineSize > 0) {
    return state.sourcePreviewInlineSize;
  }
  return Math.round(dom.sourcePreviewDock.getBoundingClientRect().width);
}

function setSize(value, { persist = true, refresh = true } = {}) {
  const nextSize = clampSize(value);
  state.sourcePreviewInlineSize = nextSize;
  document.documentElement.style.setProperty('--source-preview-inline-size', `${nextSize}px`);
  if (persist) localStorage.setItem(storageKeys.sourcePreviewInlineSize, String(nextSize));
  if (refresh) refreshSourcePreviewResizeHandle();
  return nextSize;
}

function applySavedSize() {
  const storedValue = Number(localStorage.getItem(storageKeys.sourcePreviewInlineSize));
  if (!Number.isFinite(storedValue) || storedValue <= 0) return;
  state.sourcePreviewInlineSize = storedValue;
  document.documentElement.style.setProperty('--source-preview-inline-size', `${storedValue}px`);
}

function updateHandleAccessibility() {
  const open = dom.sourcePreviewDock.classList.contains('is-open') && isResizable();
  const { min, max } = sizeRange();
  const size = clampSize(currentSize());
  dom.sourcePreviewResizeHandle.setAttribute('aria-hidden', String(!open));
  dom.sourcePreviewResizeHandle.tabIndex = open ? 0 : -1;
  dom.sourcePreviewResizeHandle.setAttribute('aria-valuemin', String(min));
  dom.sourcePreviewResizeHandle.setAttribute('aria-valuemax', String(max));
  dom.sourcePreviewResizeHandle.setAttribute('aria-valuenow', String(size));
  dom.sourcePreviewResizeHandle.setAttribute('aria-valuetext', `${size} px`);
}

function resizeFromPointer(event) {
  setSize(viewportWidth() - event.clientX, { persist: false });
}

function finishResize(event) {
  if (activePointerId === null || event.pointerId !== activePointerId) return;
  if (dom.sourcePreviewResizeHandle.hasPointerCapture(event.pointerId)) {
    dom.sourcePreviewResizeHandle.releasePointerCapture(event.pointerId);
  }
  localStorage.setItem(storageKeys.sourcePreviewInlineSize, String(state.sourcePreviewInlineSize));
  activePointerId = null;
  document.body.classList.remove('is-source-preview-resizing');
}

function startResize(event) {
  if (!dom.sourcePreviewDock.classList.contains('is-open') || !isResizable() || event.button !== 0) return;
  event.preventDefault();
  activePointerId = event.pointerId;
  dom.sourcePreviewResizeHandle.setPointerCapture(event.pointerId);
  document.body.classList.add('is-source-preview-resizing');
  resizeFromPointer(event);
}

function resizeFromKeyboard(event) {
  if (!dom.sourcePreviewDock.classList.contains('is-open') || !isResizable()) return;
  const step = event.shiftKey ? 32 : 12;
  let nextSize = currentSize();
  if (event.key === 'Home') {
    nextSize = sizeRange().min;
  } else if (event.key === 'End') {
    nextSize = sizeRange().max;
  } else if (event.key === 'ArrowLeft') {
    nextSize += step;
  } else if (event.key === 'ArrowRight') {
    nextSize -= step;
  } else {
    return;
  }
  event.preventDefault();
  setSize(nextSize);
}

export function refreshSourcePreviewResizeHandle() {
  if (!dom.sourcePreviewResizeHandle) return;
  if (Number.isFinite(state.sourcePreviewInlineSize) && state.sourcePreviewInlineSize > 0) {
    setSize(state.sourcePreviewInlineSize, { persist: false, refresh: false });
  } else if (dom.sourcePreviewDock.classList.contains('is-open') && !dom.sourcePreviewDock.classList.contains('is-fullscreen')) {
    setSize(currentSize(), { persist: false, refresh: false });
  }
  updateHandleAccessibility();
}

export function initializeSourcePreviewResizing() {
  applySavedSize();
  dom.sourcePreviewResizeHandle.addEventListener('pointerdown', startResize);
  dom.sourcePreviewResizeHandle.addEventListener('pointermove', (event) => {
    if (event.pointerId === activePointerId) resizeFromPointer(event);
  });
  dom.sourcePreviewResizeHandle.addEventListener('pointerup', finishResize);
  dom.sourcePreviewResizeHandle.addEventListener('pointercancel', finishResize);
  dom.sourcePreviewResizeHandle.addEventListener('keydown', resizeFromKeyboard);
}
