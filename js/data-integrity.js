import { apiRequest } from './api.js';
import { createAppIcon } from './app-icons.js';
import { dom } from './dom.js';

function formatSize(bytes) {
  if (!Number.isFinite(Number(bytes)) || Number(bytes) < 1024) return `${Math.max(0, Number(bytes) || 0)} B`;
  const units = ['KB', 'MB', 'GB'];
  let amount = Number(bytes) / 1024;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(amount >= 10 ? 0 : 1)} ${units[unit]}`;
}

function targetLabel(targetType) {
  if (targetType === 'source') return 'Zdroj';
  if (targetType === 'document_project') return 'Dielňa PDF';
  if (targetType === 'music_track') return 'Hudba';
  return 'Úložisko';
}

function setStatus(message = '', isError = false) {
  dom.dataIntegrityStatus.textContent = message;
  dom.dataIntegrityStatus.classList.toggle('is-error', isError);
}

function openTarget(issue) {
  if (!issue?.targetType || !issue?.targetId) return;
  window.dispatchEvent(
    new CustomEvent('global-search-open', {
      detail: { type: issue.targetType, targetId: issue.targetId }
    })
  );
}

function makeIssueRow(issue) {
  const row = document.createElement('article');
  row.className = `data-integrity-issue is-${issue.severity === 'error' ? 'error' : 'warning'}`;

  const icon = document.createElement('span');
  icon.className = 'data-integrity-issue-icon';
  icon.append(createAppIcon(issue.severity === 'error' ? 'close' : 'info'));

  const copy = document.createElement('div');
  copy.className = 'data-integrity-issue-copy';
  const title = document.createElement('strong');
  title.textContent = `${targetLabel(issue.targetType)}: ${issue.title}`;
  const description = document.createElement('span');
  description.textContent = issue.detail;
  copy.append(title, description);
  if (issue.context) {
    const context = document.createElement('small');
    context.textContent = issue.context;
    copy.append(context);
  }

  row.append(icon, copy);
  if (issue.targetType && issue.targetId) {
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'icon-button data-integrity-open';
    open.title = 'Otvoriť prvok';
    open.setAttribute('aria-label', 'Otvoriť prvok');
    open.append(createAppIcon('external-link'));
    open.addEventListener('click', () => openTarget(issue));
    row.append(open);
  }
  return row;
}

function renderResult(result) {
  const issues = Array.isArray(result?.issues) ? result.issues : [];
  dom.dataIntegritySummary.hidden = false;
  dom.dataIntegritySummary.textContent = `Overené ${result?.checkedFiles || 0} súborov · uložených ${result?.storedFiles || 0} súborov · ${formatSize(result?.storageBytes || 0)}.`;
  dom.dataIntegrityIssues.replaceChildren();
  dom.dataIntegrityIssues.hidden = false;
  if (issues.length === 0) {
    const clean = document.createElement('p');
    clean.className = 'data-integrity-clean';
    clean.textContent = 'Kontrola nenašla žiadny problém.';
    dom.dataIntegrityIssues.append(clean);
    setStatus('Kontrola je hotová.');
    return;
  }
  dom.dataIntegrityIssues.append(...issues.map(makeIssueRow));
  const hasErrors = issues.some((issue) => issue.severity === 'error');
  setStatus(hasErrors ? `Kontrola našla ${issues.length} problémov.` : `Kontrola našla ${issues.length} upozornení.`, hasErrors);
}

async function runIntegrityCheck() {
  dom.dataIntegrityRun.disabled = true;
  setStatus('Kontrolujem uložené súbory…');
  try {
    renderResult(await apiRequest('/integrity'));
  } catch (error) {
    setStatus(error.message || 'Kontrolu integrity sa nepodarilo dokončiť.', true);
  } finally {
    dom.dataIntegrityRun.disabled = false;
  }
}

export function initializeDataIntegrity() {
  dom.dataIntegrityRun.addEventListener('click', () => void runIntegrityCheck());
}
