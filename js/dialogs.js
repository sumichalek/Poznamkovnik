export function hasOpenApplicationDialog() {
  return Boolean(document.querySelector('dialog[open]'));
}

const WINDOW_MARGIN = 12;
const COMPACT_WINDOW_QUERY = '(max-width: 640px)';
const windowControllers = new WeakMap();

function isCompactWindow() {
  return window.matchMedia(COMPACT_WINDOW_QUERY).matches;
}

function windowBounds(dialog) {
  const rect = dialog.getBoundingClientRect();
  return {
    maxLeft: Math.max(WINDOW_MARGIN, window.innerWidth - rect.width - WINDOW_MARGIN),
    maxTop: Math.max(WINDOW_MARGIN, window.innerHeight - rect.height - WINDOW_MARGIN)
  };
}

function clampWindowPosition(dialog) {
  if (!dialog.open || isCompactWindow() || !dialog.dataset.windowPositioned) return;
  const { maxLeft, maxTop } = windowBounds(dialog);
  const left = Number.parseFloat(dialog.style.left);
  const top = Number.parseFloat(dialog.style.top);
  dialog.style.left = `${Math.min(maxLeft, Math.max(WINDOW_MARGIN, Number.isFinite(left) ? left : WINDOW_MARGIN))}px`;
  dialog.style.top = `${Math.min(maxTop, Math.max(WINDOW_MARGIN, Number.isFinite(top) ? top : WINDOW_MARGIN))}px`;
}

function prepareWindow(dialog) {
  if (!dialog.open || isCompactWindow()) return;
  const rect = dialog.getBoundingClientRect();
  if (!dialog.dataset.windowSized) {
    dialog.style.width = `${Math.round(rect.width)}px`;
    dialog.style.height = `${Math.round(rect.height)}px`;
    dialog.dataset.windowSized = 'true';
  }
  if (!dialog.dataset.windowPositioned) {
    dialog.style.left = `${Math.max(WINDOW_MARGIN, Math.round((window.innerWidth - dialog.offsetWidth) / 2))}px`;
    dialog.style.top = `${Math.max(WINDOW_MARGIN, Math.round((window.innerHeight - dialog.offsetHeight) / 2))}px`;
    dialog.dataset.windowPositioned = 'true';
  }
  clampWindowPosition(dialog);
}

function sectionResizeBounds(section) {
  const minimum = Number.parseInt(section.dataset.dialogSectionMinHeight || '96', 10) || 96;
  const configuredMaximum = Number.parseInt(section.dataset.dialogSectionMaxHeight || '520', 10) || 520;
  const dialog = section.closest('dialog');
  const availableHeight = dialog?.clientHeight ? Math.max(minimum, dialog.clientHeight - 180) : configuredMaximum;
  return { minimum, maximum: Math.max(minimum, Math.min(configuredMaximum, availableHeight)) };
}

function setSectionHeight(section, height) {
  const { minimum, maximum } = sectionResizeBounds(section);
  const nextHeight = Math.round(Math.min(maximum, Math.max(minimum, height)));
  section.style.height = `${nextHeight}px`;
  const handle = section.closest('dialog')?.querySelector(`[data-dialog-resize-target="${section.id}"]`);
  if (handle) handle.setAttribute('aria-valuenow', String(nextHeight));
}

function resizeSectionPair(section, peerSection, primaryHeight, peerHeight, delta) {
  if (!peerSection) {
    setSectionHeight(section, primaryHeight + delta);
    return;
  }
  const primaryBounds = sectionResizeBounds(section);
  const peerBounds = sectionResizeBounds(peerSection);
  const minimumDelta = Math.max(primaryBounds.minimum - primaryHeight, peerHeight - peerBounds.maximum);
  const maximumDelta = Math.min(primaryBounds.maximum - primaryHeight, peerHeight - peerBounds.minimum);
  const appliedDelta = Math.min(maximumDelta, Math.max(minimumDelta, delta));
  setSectionHeight(section, primaryHeight + appliedDelta);
  setSectionHeight(peerSection, peerHeight - appliedDelta);
}

export function fitDialogResizableSection(section) {
  if (!section) return;
  requestAnimationFrame(() => {
    const { minimum, maximum } = sectionResizeBounds(section);
    section.style.height = 'auto';
    setSectionHeight(section, Math.min(maximum, Math.max(minimum, section.scrollHeight)));
  });
}

function installDialogSectionResizers(dialog) {
  dialog.querySelectorAll('[data-dialog-resize-target]').forEach((handle) => {
    const targetId = handle.dataset.dialogResizeTarget;
    const section = targetId ? dialog.querySelector(`#${CSS.escape(targetId)}`) : null;
    if (!section) return;
    const peerId = handle.dataset.dialogResizePeer;
    const peerSection = peerId ? dialog.querySelector(`#${CSS.escape(peerId)}`) : null;
    let drag = null;
    handle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || isCompactWindow()) return;
      drag = {
        pointerId: event.pointerId,
        startY: event.clientY,
        startHeight: section.getBoundingClientRect().height,
        peerStartHeight: peerSection?.getBoundingClientRect().height || 0
      };
      handle.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    handle.addEventListener('pointermove', (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      resizeSectionPair(section, peerSection, drag.startHeight, drag.peerStartHeight, event.clientY - drag.startY);
    });
    const stopDragging = (event) => {
      if (!drag || (event && event.pointerId !== drag.pointerId)) return;
      drag = null;
    };
    handle.addEventListener('pointerup', stopDragging);
    handle.addEventListener('pointercancel', stopDragging);
    handle.addEventListener('keydown', (event) => {
      const increment = event.shiftKey ? 48 : 16;
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        resizeSectionPair(section, peerSection, section.getBoundingClientRect().height, peerSection?.getBoundingClientRect().height || 0, -increment);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        resizeSectionPair(section, peerSection, section.getBoundingClientRect().height, peerSection?.getBoundingClientRect().height || 0, increment);
      }
    });
  });
}

export function installDialogWindowBehavior(dialog) {
  if (!dialog || dialog.dataset.windowFixed === 'true' || windowControllers.has(dialog)) return;
  dialog.classList.add('app-window-dialog');
  const content = [...dialog.children].find((child) => child.matches('section, form, div'));
  const handle = dialog.querySelector('[data-dialog-drag-handle]') || content?.querySelector(':scope > header');
  const controller = { drag: null, resizeObserver: null };
  windowControllers.set(dialog, controller);
  installDialogSectionResizers(dialog);

  if (handle) {
    handle.classList.add('dialog-window-drag-handle');
    handle.title ||= 'Potiahni za hlavičku na presunutie okna';
    handle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || isCompactWindow() || event.target.closest('button, a, input, select, textarea, label')) return;
      const rect = dialog.getBoundingClientRect();
      controller.drag = {
        pointerId: event.pointerId,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top
      };
      dialog.dataset.windowPositioned = 'true';
      dialog.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
  }

  dialog.addEventListener('pointermove', (event) => {
    if (!controller.drag || event.pointerId !== controller.drag.pointerId) return;
    const { maxLeft, maxTop } = windowBounds(dialog);
    dialog.style.left = `${Math.min(maxLeft, Math.max(WINDOW_MARGIN, event.clientX - controller.drag.offsetX))}px`;
    dialog.style.top = `${Math.min(maxTop, Math.max(WINDOW_MARGIN, event.clientY - controller.drag.offsetY))}px`;
  });
  const stopDragging = (event) => {
    if (!controller.drag || (event && event.pointerId !== controller.drag.pointerId)) return;
    controller.drag = null;
  };
  dialog.addEventListener('pointerup', stopDragging);
  dialog.addEventListener('pointercancel', stopDragging);
  dialog.addEventListener('toggle', () => {
    if (dialog.open) requestAnimationFrame(() => prepareWindow(dialog));
  });
  dialog.addEventListener('close', () => {
    controller.drag = null;
  });
  window.addEventListener('resize', () => clampWindowPosition(dialog));

  if (typeof ResizeObserver === 'function') {
    controller.resizeObserver = new ResizeObserver(() => clampWindowPosition(dialog));
    controller.resizeObserver.observe(dialog);
  }
}

export function installDialogBackdropClose(dialog, closeDialog) {
  installDialogWindowBehavior(dialog);
  let backdropPointer = null;

  dialog.addEventListener('pointerdown', (event) => {
    backdropPointer = event.target === dialog
      ? { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false }
      : null;
  });
  dialog.addEventListener('pointermove', (event) => {
    if (!backdropPointer || event.pointerId !== backdropPointer.id) return;
    if (Math.hypot(event.clientX - backdropPointer.x, event.clientY - backdropPointer.y) > 6) {
      backdropPointer.moved = true;
    }
  });
  dialog.addEventListener('pointercancel', () => {
    backdropPointer = null;
  });
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    if (!backdropPointer || backdropPointer.moved) {
      backdropPointer = null;
      return;
    }
    backdropPointer = null;
    closeDialog();
  });
  dialog.addEventListener('close', () => {
    backdropPointer = null;
  });
}
