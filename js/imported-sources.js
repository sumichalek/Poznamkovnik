import { apiRequest, uploadSourceFile } from './api.js';

export function sourceFileMapKey(sourceId, fileId) {
  return `${sourceId}\u0000${fileId}`;
}

export function importedSourceAction(sourceActions, link) {
  const selected = sourceActions?.[link?.sourceId];
  if (['existing', 'copy', 'skip'].includes(selected)) return selected;
  return ['available', 'missing-file'].includes(link?.importAvailability) ? 'existing' : 'skip';
}

export function importedSourceTitle(link, snapshot) {
  return snapshot?.title || link?.title || 'z importu';
}

export function importedSourceFileName(snapshot, fileId) {
  return snapshot?.files?.find((file) => file.id === fileId)?.originalName || 'priloha';
}

export async function copyImportedSources({ links, sourceSnapshots, sourceAssets, sourceActions }) {
  const warnings = [];
  const sourceIds = new Map();
  const sourceFileIds = new Map();
  const snapshots = new Map((Array.isArray(sourceSnapshots) ? sourceSnapshots : [])
    .filter((source) => source?.id)
    .map((source) => [source.id, source]));
  const linkedSources = Array.isArray(links) ? links : [];
  const sourceIdsToCopy = [...new Set(linkedSources
    .filter((link) => importedSourceAction(sourceActions, link) === 'copy')
    .map((link) => link.sourceId)
    .filter(Boolean))];

  for (const originalSourceId of sourceIdsToCopy) {
    const snapshot = snapshots.get(originalSourceId);
    if (!snapshot) {
      const link = linkedSources.find((item) => item.sourceId === originalSourceId);
      warnings.push(`Zdroj „${importedSourceTitle(link, snapshot)}“ nemá v archíve údaje potrebné na vytvorenie kópie.`);
      continue;
    }
    let copiedSource;
    try {
      const result = await apiRequest('/sources', {
        method: 'POST',
        body: {
          title: snapshot.title,
          kind: snapshot.kind || 'source',
          description: snapshot.description || '',
          metadata: snapshot.metadata && typeof snapshot.metadata === 'object' ? snapshot.metadata : {},
          tags: Array.isArray(snapshot.tags) ? snapshot.tags : []
        }
      });
      copiedSource = result.source;
      sourceIds.set(originalSourceId, copiedSource.id);
    } catch {
      warnings.push(`Zdroj „${snapshot.title}“ sa nepodarilo vytvoriť; jeho väzby sa vynechajú.`);
      continue;
    }

    const uploadedFileIds = new Set();
    for (const sourceFile of Array.isArray(snapshot.files) ? snapshot.files : []) {
      const asset = sourceFile.archivePath ? sourceAssets?.get(sourceFile.archivePath) : null;
      if (!(asset?.blob instanceof Blob)) {
        warnings.push(`Súbor „${sourceFile.originalName}“ pre zdroj „${snapshot.title}“ v archíve nie je dostupný.`);
        continue;
      }
      try {
        const file = new File([asset.blob], sourceFile.originalName, { type: sourceFile.mimeType || asset.blob.type });
        const result = await uploadSourceFile(copiedSource.id, file);
        const uploaded = Array.isArray(result?.source?.files)
          ? result.source.files.find((item) => !uploadedFileIds.has(item.id))
          : null;
        if (!uploaded?.id) throw new Error('Server nevrátil vytvorený súbor.');
        uploadedFileIds.add(uploaded.id);
        sourceFileIds.set(sourceFileMapKey(originalSourceId, sourceFile.id), uploaded.id);
      } catch {
        warnings.push(`Súbor „${sourceFile.originalName}“ sa nepodarilo skopírovať do zdroja „${snapshot.title}“.`);
      }
    }
  }
  return { warnings, sourceIds, sourceFileIds, snapshots };
}

export function resolvedImportedSourceId(link, sourceActions, copyResult) {
  const action = importedSourceAction(sourceActions, link);
  if (action === 'skip') return '';
  if (action === 'copy') return copyResult.sourceIds.get(link.sourceId) || '';
  return link.sourceId || '';
}

export function resolvedImportedSourceFileId(link, sourceActions, copyResult) {
  if (!link.sourceFileId) return '';
  if (importedSourceAction(sourceActions, link) !== 'copy') {
    return link.importAvailability === 'missing-file' ? '' : link.sourceFileId;
  }
  return copyResult.sourceFileIds.get(sourceFileMapKey(link.sourceId, link.sourceFileId)) || '';
}
