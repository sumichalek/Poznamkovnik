export function hasOpenApplicationDialog() {
  return Boolean(document.querySelector('dialog[open]'));
}

export function installDialogBackdropClose(dialog, closeDialog) {
  let startedOnBackdrop = false;

  dialog.addEventListener('pointerdown', (event) => {
    startedOnBackdrop = event.target === dialog;
  });
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    if (!startedOnBackdrop) {
      startedOnBackdrop = false;
      return;
    }
    startedOnBackdrop = false;
    closeDialog();
  });
  dialog.addEventListener('close', () => {
    startedOnBackdrop = false;
  });
}
