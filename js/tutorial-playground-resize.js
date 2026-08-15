import { storageKeys } from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';

const INLINE_MIN_SIZE = 460;
const BLOCK_MIN_SIZE = 300;

let activePointerId = null;

function viewportSize() {
  const viewport = window.visualViewport;
  return {
    width: viewport?.width || window.innerWidth,
    height: viewport?.height || window.innerHeight
  };
}

function isFullscreen() {
  return dom.tutorialPlaygroundDock.classList.contains('is-fullscreen');
}

function sizeRange(axis) {
  const { width, height } = viewportSize();
  if (axis === 'horizontal') {
    const reservedForReader = Math.max(340, Math.round(width * 0.24));
    return { min: INLINE_MIN_SIZE, max: Math.max(INLINE_MIN_SIZE, width - reservedForReader) };
  }
  const reservedForReader = Math.max(200, Math.round(height * 0.24));
  return { min: BLOCK_MIN_SIZE, max: Math.max(BLOCK_MIN_SIZE, height - reservedForReader) };
}

function stateKey(axis) {
  return axis === 'horizontal' ? 'tutorialPlaygroundInlineSize' : 'tutorialPlaygroundBlockSize';
}

function cssVariable(axis) {
  return axis === 'horizontal' ? '--tutorial-playground-inline-size' : '--tutorial-playground-block-size';
}

function storageKey(axis) {
  return axis === 'horizontal' ? storageKeys.tutorialPlaygroundInlineSize : storageKeys.tutorialPlaygroundBlockSize;
}

function currentSize(axis) {
  const stored = state[stateKey(axis)];
  if (Number.isFinite(stored) && stored > 0) return stored;
  const rect = dom.tutorialPlaygroundDock.getBoundingClientRect();
  return Math.round(axis === 'horizontal' ? rect.width : rect.height);
}

function clampSize(axis, value) {
  const { min, max } = sizeRange(axis);
  return Math.round(Math.min(max, Math.max(min, value)));
}

function setSize(axis, value, { persist = true, refresh = true } = {}) {
  const size = clampSize(axis, value);
  state[stateKey(axis)] = size;
  document.documentElement.style.setProperty(cssVariable(axis), `${size}px`);
  if (persist) localStorage.setItem(storageKey(axis), String(size));
  if (refresh) refreshTutorialPlaygroundResizeHandle();
  return size;
}

function updateHandleAccessibility() {
  const open = dom.tutorialPlaygroundDock.classList.contains('is-open') && !isFullscreen();
  const axis = state.editorAxis;
  const { min, max } = sizeRange(axis);
  const size = clampSize(axis, currentSize(axis));
  const horizontal = axis === 'horizontal';
  dom.tutorialPlaygroundResizeHandle.setAttribute('aria-hidden', String(!open));
  dom.tutorialPlaygroundResizeHandle.tabIndex = open ? 0 : -1;
  dom.tutorialPlaygroundResizeHandle.setAttribute('aria-orientation', horizontal ? 'vertical' : 'horizontal');
  dom.tutorialPlaygroundResizeHandle.setAttribute(
    'aria-label',
    horizontal ? 'Zmeniť šírku skúšobne' : 'Zmeniť výšku skúšobne'
  );
  dom.tutorialPlaygroundResizeHandle.setAttribute('aria-valuemin', String(min));
  dom.tutorialPlaygroundResizeHandle.setAttribute('aria-valuemax', String(max));
  dom.tutorialPlaygroundResizeHandle.setAttribute('aria-valuenow', String(size));
  dom.tutorialPlaygroundResizeHandle.setAttribute('aria-valuetext', `${size} px`);
}

function resizeFromPointer(event) {
  const { width, height } = viewportSize();
  setSize(state.editorAxis, state.editorAxis === 'horizontal' ? width - event.clientX : height - event.clientY, { persist: false });
}

function finishResize(event) {
  if (activePointerId === null || event.pointerId !== activePointerId) return;
  if (dom.tutorialPlaygroundResizeHandle.hasPointerCapture(event.pointerId)) {
    dom.tutorialPlaygroundResizeHandle.releasePointerCapture(event.pointerId);
  }
  const axis = state.editorAxis;
  localStorage.setItem(storageKey(axis), String(state[stateKey(axis)]));
  activePointerId = null;
  document.body.classList.remove('is-tutorial-playground-resizing');
}

function startResize(event) {
  if (!dom.tutorialPlaygroundDock.classList.contains('is-open') || isFullscreen() || event.button !== 0) return;
  event.preventDefault();
  activePointerId = event.pointerId;
  dom.tutorialPlaygroundResizeHandle.setPointerCapture(event.pointerId);
  document.body.classList.add('is-tutorial-playground-resizing');
  resizeFromPointer(event);
}

function resizeFromKeyboard(event) {
  if (!dom.tutorialPlaygroundDock.classList.contains('is-open') || isFullscreen()) return;
  const axis = state.editorAxis;
  const step = event.shiftKey ? 32 : 12;
  let size = currentSize(axis);
  if (event.key === 'Home') size = sizeRange(axis).min;
  else if (event.key === 'End') size = sizeRange(axis).max;
  else if (axis === 'horizontal' && event.key === 'ArrowLeft') size += step;
  else if (axis === 'horizontal' && event.key === 'ArrowRight') size -= step;
  else if (axis === 'vertical' && event.key === 'ArrowUp') size += step;
  else if (axis === 'vertical' && event.key === 'ArrowDown') size -= step;
  else return;
  event.preventDefault();
  setSize(axis, size);
}

export function refreshTutorialPlaygroundResizeHandle() {
  if (!dom.tutorialPlaygroundResizeHandle) return;
  const axis = state.editorAxis;
  const stored = state[stateKey(axis)];
  if (Number.isFinite(stored) && stored > 0) setSize(axis, stored, { persist: false, refresh: false });
  updateHandleAccessibility();
}

export function initializeTutorialPlaygroundResizing() {
  ['horizontal', 'vertical'].forEach((axis) => {
    const saved = Number(localStorage.getItem(storageKey(axis)));
    if (!Number.isFinite(saved) || saved <= 0) return;
    state[stateKey(axis)] = saved;
    document.documentElement.style.setProperty(cssVariable(axis), `${saved}px`);
  });
  dom.tutorialPlaygroundResizeHandle.addEventListener('pointerdown', startResize);
  dom.tutorialPlaygroundResizeHandle.addEventListener('pointermove', (event) => {
    if (event.pointerId === activePointerId) resizeFromPointer(event);
  });
  dom.tutorialPlaygroundResizeHandle.addEventListener('pointerup', finishResize);
  dom.tutorialPlaygroundResizeHandle.addEventListener('pointercancel', finishResize);
  dom.tutorialPlaygroundResizeHandle.addEventListener('keydown', resizeFromKeyboard);
}
