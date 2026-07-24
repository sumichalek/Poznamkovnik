import { createAppIcon } from './app-icons.js';

export function createLibraryItemIcon(type) {
  return createAppIcon(type, `library-item-icon ${type}-icon`);
}
