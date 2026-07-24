import { storageKeys } from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';

const INLINE_MIN_SIZE = 380;
const BLOCK_MIN_SIZE = 280;

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
    const reservedForBrowser = Math.max(320, Math.round(width * 0.25));
    return { min: INLINE_MIN_SIZE, max: Math.max(INLINE_MIN_SIZE, width - reservedForBrowser) };
  }

  const reservedForBrowser = Math.max(180, Math.round(height * 0.22));
  return { min: BLOCK_MIN_SIZE, max: Math.max(BLOCK_MIN_SIZE, height - reservedForBrowser) };
}

function stateKey(axis) {
  return axis === 'horizontal' ? 'sourceDetailInlineSize' : 'sourceDetailBlockSize';
}

function cssVariable(axis) {
  return axis === 'horizontal' ? '--source-detail-inline-size' : '--source-detail-block-size';
}

function storageKey(axis) {
  return axis === 'horizontal' ? storageKeys.sourceDetailInlineSize : storageKeys.sourceDetailBlockSize;
}

function clampSize(axis, value) {
  const { min, max } = sizeRange(axis);
  return Math.round(Math.min(max, Math.max(min, value)));
}

function currentSize(axis) {
  const savedSize = state[stateKey(axis)];
  if (Number.isFinite(savedSize) && savedSize > 0) return savedSize;
  const dockRect = dom.sourceDetailDock.getBoundingClientRect();
  return Math.round(axis === 'horizontal' ? dockRect.width : dockRect.height);
}

function setSize(axis, value, { persist = true, refresh = true } = {}) {
  const nextSize = clampSize(axis, value);
  state[stateKey(axis)] = nextSize;
  document.documentElement.style.setProperty(cssVariable(axis), `${nextSize}px`);
  if (persist) localStorage.setItem(storageKey(axis), String(nextSize));
  if (refresh) refreshSourceDetailResizeHandle();
  return nextSize;
}

function applySavedSize(axis) {
  const storedValue = Number(localStorage.getItem(storageKey(axis)));
  if (!Number.isFinite(storedValue) || storedValue <= 0) return;
  state[stateKey(axis)] = storedValue;
  document.documentElement.style.setProperty(cssVariable(axis), `${storedValue}px`);
}

function updateHandleAccessibility() {
  const open = dom.sourceDetailDock.classList.contains('is-open') && !dom.sourceDetail.hidden;
  const axis = state.editorAxis;
  const { min, max } = sizeRange(axis);
  const size = clampSize(axis, currentSize(axis));
  const isHorizontal = axis === 'horizontal';
  dom.sourceDetailResizeHandle.setAttribute('aria-hidden', String(!open));
  dom.sourceDetailResizeHandle.tabIndex = open ? 0 : -1;
  dom.sourceDetailResizeHandle.setAttribute('aria-orientation', isHorizontal ? 'vertical' : 'horizontal');
  dom.sourceDetailResizeHandle.setAttribute(
    'aria-label',
    isHorizontal ? 'Zmeniť šírku detailu zdroja' : 'Zmeniť výšku detailu zdroja'
  );
  dom.sourceDetailResizeHandle.setAttribute('aria-valuemin', String(min));
  dom.sourceDetailResizeHandle.setAttribute('aria-valuemax', String(max));
  dom.sourceDetailResizeHandle.setAttribute('aria-valuenow', String(size));
  dom.sourceDetailResizeHandle.setAttribute('aria-valuetext', `${size} px`);
}

function resizeFromPointer(event) {
  const { width, height } = viewportSize();
  const size = state.editorAxis === 'horizontal' ? width - event.clientX : height - event.clientY;
  setSize(state.editorAxis, size, { persist: false });
}

function finishResize(event) {
  if (activePointerId === null || event.pointerId !== activePointerId) return;
  if (dom.sourceDetailResizeHandle.hasPointerCapture(event.pointerId)) {
    dom.sourceDetailResizeHandle.releasePointerCapture(event.pointerId);
  }
  const axis = state.editorAxis;
  localStorage.setItem(storageKey(axis), String(state[stateKey(axis)]));
  activePointerId = null;
  document.body.classList.remove('is-source-detail-resizing');
}

function startResize(event) {
  if (!dom.sourceDetailDock.classList.contains('is-open') || event.button !== 0) return;
  event.preventDefault();
  activePointerId = event.pointerId;
  dom.sourceDetailResizeHandle.setPointerCapture(event.pointerId);
  document.body.classList.add('is-source-detail-resizing');
  resizeFromPointer(event);
}

function resizeFromKeyboard(event) {
  if (!dom.sourceDetailDock.classList.contains('is-open')) return;
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

export function refreshSourceDetailResizeHandle() {
  if (!dom.sourceDetailResizeHandle) return;
  const axis = state.editorAxis;
  const activeSize = state[stateKey(axis)];
  if (Number.isFinite(activeSize) && activeSize > 0) {
    setSize(axis, activeSize, { persist: false, refresh: false });
  }
  updateHandleAccessibility();
}

export function initializeSourceDetailResizing() {
  applySavedSize('horizontal');
  applySavedSize('vertical');
  dom.sourceDetailResizeHandle.addEventListener('pointerdown', startResize);
  dom.sourceDetailResizeHandle.addEventListener('pointermove', (event) => {
    if (event.pointerId !== activePointerId) return;
    resizeFromPointer(event);
  });
  dom.sourceDetailResizeHandle.addEventListener('pointerup', finishResize);
  dom.sourceDetailResizeHandle.addEventListener('pointercancel', finishResize);
  dom.sourceDetailResizeHandle.addEventListener('keydown', resizeFromKeyboard);
}
