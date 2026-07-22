import { storageKeys } from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';

const INLINE_MIN_SIZE = 360;
const BLOCK_MIN_SIZE = 200;

let activePointerId = null;

function viewportSize() {
  const viewport = window.visualViewport;
  return {
    width: viewport?.width || window.innerWidth,
    height: viewport?.height || window.innerHeight
  };
}

function sizeRange(axis) {
  const { width, height } = viewportSize();
  if (axis === 'horizontal') {
    const reservedForLibrary = Math.max(260, Math.round(width * 0.18));
    const max = Math.max(INLINE_MIN_SIZE, width - reservedForLibrary);
    return { min: INLINE_MIN_SIZE, max };
  }

  const reservedForLibrary = Math.max(160, Math.round(height * 0.2));
  const max = Math.max(BLOCK_MIN_SIZE, height - reservedForLibrary);
  return { min: BLOCK_MIN_SIZE, max };
}

function stateKey(axis) {
  return axis === 'horizontal' ? 'editorDockInlineSize' : 'editorDockBlockSize';
}

function cssVariable(axis) {
  return axis === 'horizontal' ? '--editor-dock-inline-size' : '--editor-dock-block-size';
}

function storageKey(axis) {
  return axis === 'horizontal' ? storageKeys.editorDockInlineSize : storageKeys.editorDockBlockSize;
}

function clampSize(axis, value) {
  const { min, max } = sizeRange(axis);
  return Math.round(Math.min(max, Math.max(min, value)));
}

function currentSize(axis) {
  const savedSize = state[stateKey(axis)];
  if (Number.isFinite(savedSize) && savedSize > 0) return savedSize;
  const dockRect = dom.libraryEditorDock.getBoundingClientRect();
  return Math.round(axis === 'horizontal' ? dockRect.width : dockRect.height);
}

function setSize(axis, value, { persist = true, refresh = true } = {}) {
  const nextSize = clampSize(axis, value);
  state[stateKey(axis)] = nextSize;
  document.documentElement.style.setProperty(cssVariable(axis), `${nextSize}px`);
  if (persist) localStorage.setItem(storageKey(axis), String(nextSize));
  if (refresh) refreshEditorResizeHandle();
  return nextSize;
}

function applySavedSize(axis) {
  const storedValue = Number(localStorage.getItem(storageKey(axis)));
  if (!Number.isFinite(storedValue) || storedValue <= 0) return;
  state[stateKey(axis)] = storedValue;
  document.documentElement.style.setProperty(cssVariable(axis), `${storedValue}px`);
}

function updateHandleAccessibility() {
  const axis = state.editorAxis;
  const { min, max } = sizeRange(axis);
  const size = clampSize(axis, currentSize(axis));
  const isHorizontal = axis === 'horizontal';
  dom.editorResizeHandle.setAttribute('aria-orientation', isHorizontal ? 'vertical' : 'horizontal');
  dom.editorResizeHandle.setAttribute('aria-label', isHorizontal ? 'Zmeniť šírku editora' : 'Zmeniť výšku editora');
  dom.editorResizeHandle.setAttribute('aria-valuemin', String(min));
  dom.editorResizeHandle.setAttribute('aria-valuemax', String(max));
  dom.editorResizeHandle.setAttribute('aria-valuenow', String(size));
  dom.editorResizeHandle.setAttribute('aria-valuetext', `${size} px`);
}

function resizeFromPointer(event) {
  const { width, height } = viewportSize();
  const size = state.editorAxis === 'horizontal' ? width - event.clientX : height - event.clientY;
  setSize(state.editorAxis, size, { persist: false });
}

function finishResize(event) {
  if (activePointerId === null || event.pointerId !== activePointerId) return;
  if (dom.editorResizeHandle.hasPointerCapture(event.pointerId)) {
    dom.editorResizeHandle.releasePointerCapture(event.pointerId);
  }
  const axis = state.editorAxis;
  localStorage.setItem(storageKey(axis), String(state[stateKey(axis)]));
  activePointerId = null;
  document.body.classList.remove('is-editor-resizing');
}

function startResize(event) {
  if (state.editorLayout !== 'docked' || event.button !== 0) return;
  event.preventDefault();
  activePointerId = event.pointerId;
  dom.editorResizeHandle.setPointerCapture(event.pointerId);
  document.body.classList.add('is-editor-resizing');
  resizeFromPointer(event);
}

function resizeFromKeyboard(event) {
  if (state.editorLayout !== 'docked') return;
  const axis = state.editorAxis;
  const step = event.shiftKey ? 32 : 12;
  let nextSize = currentSize(axis);

  if (event.key === 'Home') {
    nextSize = sizeRange(axis).min;
  } else if (event.key === 'End') {
    nextSize = sizeRange(axis).max;
  } else if (axis === 'horizontal' && event.key === 'ArrowLeft') {
    nextSize += step;
  } else if (axis === 'horizontal' && event.key === 'ArrowRight') {
    nextSize -= step;
  } else if (axis === 'vertical' && event.key === 'ArrowUp') {
    nextSize += step;
  } else if (axis === 'vertical' && event.key === 'ArrowDown') {
    nextSize -= step;
  } else {
    return;
  }

  event.preventDefault();
  setSize(axis, nextSize);
}

export function refreshEditorResizeHandle() {
  if (!dom.editorResizeHandle) return;
  const axis = state.editorAxis;
  const activeSize = state[stateKey(axis)];
  if (Number.isFinite(activeSize) && activeSize > 0) {
    setSize(axis, activeSize, { persist: false, refresh: false });
  }
  updateHandleAccessibility();
}

export function initializeEditorResizing() {
  applySavedSize('horizontal');
  applySavedSize('vertical');
  dom.editorResizeHandle.addEventListener('pointerdown', startResize);
  dom.editorResizeHandle.addEventListener('pointermove', (event) => {
    if (event.pointerId !== activePointerId) return;
    resizeFromPointer(event);
  });
  dom.editorResizeHandle.addEventListener('pointerup', finishResize);
  dom.editorResizeHandle.addEventListener('pointercancel', finishResize);
  dom.editorResizeHandle.addEventListener('keydown', resizeFromKeyboard);
}
