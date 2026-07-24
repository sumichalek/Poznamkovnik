import { clearAppliedBackground, initializeBackgroundSettings } from './background.js';
import { dom } from './dom.js';
import { logout } from './login.js';
import { clearWorkspacePreferences, initializeWorkspacePreferences } from './preferences.js';
import { applyTheme, disableWorkspaceSync } from './storage.js';
import { updateTopbarVisibility } from './topbar.js';

let activeSettingsSection = 'appearance';

function selectSettingsSection(sectionName, { focus = false } = {}) {
  const nextSection = Array.from(dom.settingsNavButtons).some((button) => button.dataset.settingsTab === sectionName)
    ? sectionName
    : 'appearance';
  activeSettingsSection = nextSection;

  dom.settingsNavButtons.forEach((button) => {
    const isActive = button.dataset.settingsTab === nextSection;
    button.classList.toggle('is-active', isActive);
    button.setAttribute('aria-selected', String(isActive));
    if (isActive && focus) button.focus();
  });
  dom.settingsSections.forEach((section) => {
    section.hidden = section.dataset.settingsPanel !== nextSection;
  });
}

function moveSettingsTab(currentButton, direction) {
  const buttons = Array.from(dom.settingsNavButtons);
  const currentIndex = buttons.indexOf(currentButton);
  if (currentIndex === -1) return;
  const nextIndex = (currentIndex + direction + buttons.length) % buttons.length;
  selectSettingsSection(buttons[nextIndex].dataset.settingsTab, { focus: true });
}

export function openSettings(sectionName = activeSettingsSection) {
  selectSettingsSection(sectionName);
  if (!dom.settingsDialog.open) dom.settingsDialog.showModal();
  updateTopbarVisibility();
}

export function closeSettings() {
  if (dom.settingsDialog.open) dom.settingsDialog.close();
  updateTopbarVisibility();
}

export function initializeSettings() {
  dom.settingsButton.addEventListener('click', () => openSettings());
  dom.settingsClose.addEventListener('click', closeSettings);
  dom.settingsNavButtons.forEach((button) => {
    button.addEventListener('click', () => selectSettingsSection(button.dataset.settingsTab));
    button.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
        event.preventDefault();
        moveSettingsTab(button, 1);
      }
      if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
        event.preventDefault();
        moveSettingsTab(button, -1);
      }
      if (event.key === 'Home') {
        event.preventDefault();
        selectSettingsSection(dom.settingsNavButtons[0].dataset.settingsTab, { focus: true });
      }
      if (event.key === 'End') {
        event.preventDefault();
        const lastButton = dom.settingsNavButtons[dom.settingsNavButtons.length - 1];
        selectSettingsSection(lastButton.dataset.settingsTab, { focus: true });
      }
    });
  });
  dom.logoutButton.addEventListener('click', async () => {
    disableWorkspaceSync();
    clearAppliedBackground();
    clearWorkspacePreferences();
    closeSettings();
    await logout();
  });
  dom.themeSelect.addEventListener('change', () => applyTheme(dom.themeSelect.value));
  dom.settingsDialog.addEventListener('click', (event) => {
    if (event.target === dom.settingsDialog) closeSettings();
  });
  dom.settingsDialog.addEventListener('close', updateTopbarVisibility);
  initializeBackgroundSettings();
  initializeWorkspacePreferences();
}
