import { apiRequest, uploadMusicTrack } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { storageKeys } from './config.js';
import { dom } from './dom.js';
import { refreshMusicResizeHandle } from './music-resize.js';
import { updateTopbarVisibility } from './topbar.js';

const DEFAULT_VOLUME = 0.7;
const POSITION_SAVE_INTERVAL = 1_000;
const TOPBAR_DOUBLE_CLICK_DELAY = 220;

let library = { tracks: [], playlists: [] };
let loaded = false;
let loading = null;
let activePlaylistId = '';
let targetPlaylistId = '';
let currentTrackId = '';
let dialogTrackId = '';
let playlistEditingId = '';
let shuffle = false;
let repeatMode = 'all';
let resumePosition = 0;
let lastPositionSave = 0;
let uploading = false;
let isSeeking = false;
let draggedTrackId = '';
let sleepTimerEndsAt = 0;
let sleepTimerMinutes = 0;
let sleepTimerHandle = 0;
let musicButtonClickTimer = 0;

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function formatTime(value) {
  const seconds = Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 100 * 1024 * 1024 ? 0 : 1)} MB`;
}

function trackById(trackId) {
  return library.tracks.find((track) => track.id === trackId) || null;
}

function playlistById(playlistId) {
  return library.playlists.find((playlist) => playlist.id === playlistId) || null;
}

function queueTracks() {
  const playlist = playlistById(activePlaylistId);
  if (!playlist) return [...library.tracks];
  const byId = new Map(library.tracks.map((track) => [track.id, track]));
  return playlist.trackIds.map((trackId) => byId.get(trackId)).filter(Boolean);
}

function filteredTracks() {
  const query = dom.musicSearch.value.trim().toLocaleLowerCase('sk');
  return queueTracks().filter((track) => {
    if (!query) return true;
    return `${track.title} ${track.artist} ${track.album} ${track.year} ${track.genre} ${track.originalName}`
      .toLocaleLowerCase('sk')
      .includes(query);
  });
}

function setStatus(message = '', { error = false } = {}) {
  dom.musicStatus.textContent = message;
  dom.musicStatus.classList.toggle('is-error', error);
}

function persistPlaybackState() {
  localStorage.setItem(storageKeys.musicTrackId, currentTrackId);
  localStorage.setItem(storageKeys.musicPosition, String(Math.max(0, dom.musicAudio.currentTime || 0)));
}

function updateTopbarButton() {
  const icon = dom.musicButton.querySelector('.app-icon');
  const playing = !dom.musicAudio.paused && Boolean(currentTrackId);
  setAppIcon(icon, playing ? 'pause' : 'music');
  dom.musicButton.title = playing ? 'Prehráva sa hudba' : 'Prehrávač';
  dom.musicButton.setAttribute('aria-label', playing ? 'Prehráva sa hudba, otvoriť prehrávač' : 'Otvoriť prehrávač');
  dom.musicButton.classList.toggle('is-playing', playing);
}

function updateTransport() {
  const track = trackById(currentTrackId);
  const duration = Number.isFinite(dom.musicAudio.duration) ? dom.musicAudio.duration : track?.durationSeconds || 0;
  const currentTime = Math.min(dom.musicAudio.currentTime || 0, duration || 0);
  dom.musicProgress.max = String(duration || 0);
  dom.musicProgress.disabled = !track || !duration;
  if (!isSeeking) {
    dom.musicProgress.value = String(currentTime);
    updateCurrentTimeOutput(currentTime);
  }
  dom.musicDuration.value = formatTime(duration);
  dom.musicDuration.textContent = formatTime(duration);
  dom.musicPrevious.disabled = !queueTracks().length;
  dom.musicPlay.disabled = !track;
  dom.musicNext.disabled = !queueTracks().length;
  setAppIcon(dom.musicPlay.querySelector('.app-icon'), dom.musicAudio.paused ? 'play' : 'pause');
  dom.musicPlay.title = dom.musicAudio.paused ? 'Prehrať' : 'Pozastaviť';
  dom.musicPlay.setAttribute('aria-label', dom.musicAudio.paused ? 'Prehrať' : 'Pozastaviť');
  dom.musicShuffle.classList.toggle('is-active', shuffle);
  dom.musicShuffle.setAttribute('aria-pressed', String(shuffle));
  dom.musicRepeat.classList.toggle('is-active', repeatMode !== 'off');
  dom.musicRepeat.dataset.mode = repeatMode;
  dom.musicRepeat.title = repeatMode === 'one' ? 'Opakovať jednu skladbu' : repeatMode === 'all' ? 'Opakovať zoznam' : 'Neopakovať';
  dom.musicRepeat.setAttribute('aria-label', dom.musicRepeat.title);
  setAppIcon(dom.musicRepeat.querySelector('.app-icon'), repeatMode === 'one' ? 'repeat-1' : 'repeat');
  updateTopbarButton();
}

function updateCurrentTimeOutput(value) {
  const label = formatTime(value);
  dom.musicCurrentTime.value = label;
  dom.musicCurrentTime.textContent = label;
}

function updateNowPlaying() {
  const track = trackById(currentTrackId);
  dom.musicNowTitle.textContent = track?.title || 'Bez vybranej skladby';
  if (!track) {
    dom.musicNowMeta.textContent = 'Pridaj hudbu do vlastnej knižnice.';
    return;
  }
  const metadata = [track.artist, track.album].filter(Boolean);
  dom.musicNowMeta.textContent = metadata.length ? metadata.join(' / ') : track.originalName;
}

function renderPlaylists() {
  dom.musicAllTracks.classList.toggle('is-active', !activePlaylistId);
  dom.musicAllTracks.setAttribute('aria-pressed', String(!activePlaylistId));
  dom.musicPlaylists.replaceChildren();
  library.playlists.forEach((playlist) => {
    const row = document.createElement('div');
    row.className = 'music-playlist-item';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'music-playlist-button';
    const active = playlist.id === activePlaylistId;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
    button.append(createAppIcon('music'));
    const label = document.createElement('span');
    label.textContent = playlist.title;
    const count = document.createElement('small');
    count.textContent = String(playlist.trackIds.length);
    button.append(label, count);
    button.addEventListener('click', () => selectPlaylist(playlist.id));
    const actions = document.createElement('span');
    actions.className = 'music-playlist-actions';
    const rename = document.createElement('button');
    rename.type = 'button';
    rename.className = 'panel-icon-button';
    rename.title = 'Premenovať playlist';
    rename.setAttribute('aria-label', `Premenovať playlist ${playlist.title}`);
    rename.append(createAppIcon('pencil'));
    rename.addEventListener('click', () => showPlaylistForm(playlist));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'panel-icon-button danger';
    remove.title = 'Zmazať playlist';
    remove.setAttribute('aria-label', `Zmazať playlist ${playlist.title}`);
    remove.append(createAppIcon('trash'));
    remove.addEventListener('click', () => void deletePlaylist(playlist));
    actions.append(rename, remove);
    row.append(button, actions);
    dom.musicPlaylists.append(row);
  });
}

function renderTargetPlaylists() {
  const previous = targetPlaylistId;
  dom.musicTargetPlaylist.replaceChildren();
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = library.playlists.length ? 'Vyber playlist' : 'Najprv vytvor playlist';
  dom.musicTargetPlaylist.append(empty);
  library.playlists.forEach((playlist) => {
    const option = document.createElement('option');
    option.value = playlist.id;
    option.textContent = playlist.title;
    dom.musicTargetPlaylist.append(option);
  });
  if (playlistById(previous)) targetPlaylistId = previous;
  else if (playlistById(activePlaylistId)) targetPlaylistId = activePlaylistId;
  else targetPlaylistId = '';
  dom.musicTargetPlaylist.value = targetPlaylistId;
  dom.musicTargetPlaylist.disabled = !library.playlists.length;
}

function createTrackAction(iconName, label, action, disabled = false) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'panel-icon-button';
  button.title = label;
  button.setAttribute('aria-label', label);
  button.disabled = disabled;
  button.append(createAppIcon(iconName));
  button.addEventListener('click', (event) => {
    event.stopPropagation();
    void action();
  });
  button.addEventListener('dblclick', (event) => event.stopPropagation());
  return button;
}

function trackSummary(track) {
  const credit = [track.artist, track.album].filter(Boolean).join(' / ');
  const fileInfo = [track.durationSeconds ? formatTime(track.durationSeconds) : '', formatBytes(track.sizeBytes)].filter(Boolean).join(' / ');
  return credit || fileInfo;
}

function trackTooltip(track) {
  const details = [
    ['Názov', track.title],
    ['Autor', track.artist],
    ['Album', track.album],
    ['Rok', track.year],
    ['Číslo skladby', track.trackNumber],
    ['Žáner', track.genre],
    ['Dĺžka', track.durationSeconds ? formatTime(track.durationSeconds) : ''],
    ['Súbor', track.originalName],
    ['Veľkosť', formatBytes(track.sizeBytes)]
  ];
  return details.filter(([, value]) => value).map(([label, value]) => `${label}: ${value}`).join('\n');
}

function clearTrackDropIndicators() {
  dom.musicTracks.querySelectorAll('.is-drop-before, .is-drop-after').forEach((row) => {
    row.classList.remove('is-drop-before', 'is-drop-after');
  });
}

function bindPlaylistDragEvents(row, trackId) {
  const updateDropPosition = (event) => {
    if (!draggedTrackId || draggedTrackId === trackId) return;
    event.preventDefault();
    clearTrackDropIndicators();
    const bounds = row.getBoundingClientRect();
    row.classList.add(event.clientY >= bounds.top + bounds.height / 2 ? 'is-drop-after' : 'is-drop-before');
  };

  row.addEventListener('dragover', updateDropPosition);
  row.addEventListener('dragleave', (event) => {
    if (!row.contains(event.relatedTarget)) row.classList.remove('is-drop-before', 'is-drop-after');
  });
  row.addEventListener('drop', (event) => {
    if (!draggedTrackId || draggedTrackId === trackId) return;
    event.preventDefault();
    const placeAfter = row.classList.contains('is-drop-after');
    clearTrackDropIndicators();
    const movedTrackId = draggedTrackId;
    draggedTrackId = '';
    void reorderTrackByDrop(movedTrackId, trackId, placeAfter);
  });
}

function renderTracks() {
  const tracks = filteredTracks();
  const playlist = playlistById(activePlaylistId);
  dom.musicTracks.replaceChildren();
  dom.musicListTitle.textContent = playlist?.title || 'Všetky skladby';
  dom.musicListCount.textContent = `${tracks.length} ${tracks.length === 1 ? 'skladba' : tracks.length < 5 ? 'skladby' : 'skladieb'}`;
  if (!tracks.length) {
    const message = document.createElement('p');
    message.className = 'music-empty';
    message.textContent = library.tracks.length ? 'Tomuto výberu nezodpovedá žiadna skladba.' : 'Hudobná knižnica je zatiaľ prázdna.';
    dom.musicTracks.append(message);
    return;
  }
  tracks.forEach((track) => {
    const row = document.createElement('div');
    row.className = 'music-track-row';
    row.classList.toggle('is-current', track.id === currentTrackId);
    row.title = trackTooltip(track);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'music-track-copy';
    copy.title = trackTooltip(track);
    copy.setAttribute('aria-label', `Prehrať alebo pozastaviť skladbu ${track.title}`);
    copy.addEventListener('dblclick', () => void toggleTrackPlayback(track.id));
    copy.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      void toggleTrackPlayback(track.id);
    });
    const text = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = track.title;
    const details = document.createElement('small');
    details.textContent = trackSummary(track);
    text.append(title, details);
    copy.append(text);
    const actions = document.createElement('div');
    actions.className = 'music-track-actions';
    let dragHandle = null;
    if (playlist) {
      dragHandle = document.createElement('button');
      dragHandle.type = 'button';
      dragHandle.className = 'music-track-drag-handle';
      dragHandle.draggable = true;
      dragHandle.title = 'Potiahnuť skladbu na nové miesto';
      dragHandle.setAttribute('aria-label', `Zmeniť poradie skladby ${track.title}`);
      dragHandle.append(createAppIcon('grip-vertical'));
      dragHandle.addEventListener('click', (event) => event.stopPropagation());
      dragHandle.addEventListener('dragstart', (event) => {
        draggedTrackId = track.id;
        row.classList.add('is-dragging');
        event.dataTransfer?.setData('text/plain', track.id);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
      });
      dragHandle.addEventListener('dragend', () => {
        draggedTrackId = '';
        row.classList.remove('is-dragging');
        clearTrackDropIndicators();
      });
      bindPlaylistDragEvents(row, track.id);
      actions.append(createTrackAction('close', 'Odstrániť z playlistu', () => removeTrackFromPlaylist(track.id)));
    } else if (targetPlaylistId) {
      const target = playlistById(targetPlaylistId);
      const alreadyAdded = target?.trackIds.includes(track.id);
      actions.append(
        createTrackAction(alreadyAdded ? 'check' : 'plus', alreadyAdded ? 'Skladba už je v playliste' : 'Pridať do playlistu', () => addTrackToPlaylist(track.id), Boolean(alreadyAdded))
      );
    }
    actions.append(createTrackAction('pencil', 'Upraviť skladbu', () => openTrackDialog(track.id)));
    if (dragHandle) row.append(dragHandle);
    row.append(copy, actions);
    dom.musicTracks.append(row);
  });
}

function render() {
  renderPlaylists();
  renderTargetPlaylists();
  renderTracks();
  updateNowPlaying();
  updateTransport();
}

function applyLibrary(nextLibrary) {
  library = {
    tracks: Array.isArray(nextLibrary?.tracks) ? nextLibrary.tracks : [],
    playlists: Array.isArray(nextLibrary?.playlists) ? nextLibrary.playlists : []
  };
  if (activePlaylistId && !playlistById(activePlaylistId)) activePlaylistId = '';
  if (currentTrackId && !trackById(currentTrackId)) {
    currentTrackId = '';
    resumePosition = 0;
    dom.musicAudio.pause();
    dom.musicAudio.removeAttribute('src');
    dom.musicAudio.load();
    persistPlaybackState();
  }
  render();
}

async function loadMusic() {
  if (loading) return loading;
  loading = apiRequest('/music')
    .then((result) => {
      applyLibrary(result);
      loaded = true;
      if (currentTrackId && !dom.musicAudio.src) loadCurrentTrack();
    })
    .catch((error) => setStatus(error.message || 'Hudobnú knižnicu sa nepodarilo načítať.', { error: true }))
    .finally(() => {
      loading = null;
    });
  return loading;
}

function setPanelOpen(open) {
  dom.musicDock.classList.toggle('is-open', open);
  dom.musicDock.setAttribute('aria-hidden', String(!open));
  dom.musicButton.setAttribute('aria-expanded', String(open));
  requestAnimationFrame(refreshMusicResizeHandle);
  updateTopbarVisibility();
}

function handleMusicButtonClick() {
  if (musicButtonClickTimer) window.clearTimeout(musicButtonClickTimer);
  musicButtonClickTimer = window.setTimeout(() => {
    musicButtonClickTimer = 0;
    if (isMusicPanelOpen()) closeMusicPanel();
    else void openMusicPanel();
  }, TOPBAR_DOUBLE_CLICK_DELAY);
}

function handleMusicButtonDoubleClick(event) {
  event.preventDefault();
  if (musicButtonClickTimer) window.clearTimeout(musicButtonClickTimer);
  musicButtonClickTimer = 0;
  if (currentTrackId) void togglePlayback();
}

export async function openMusicPanel({ trackId = '', playlistId = '' } = {}) {
  setPanelOpen(true);
  if (!loaded) {
    setStatus('Načítavam hudobnú knižnicu...');
    await loadMusic();
    if (loaded) setStatus('');
  }
  if (playlistId && playlistById(playlistId)) selectPlaylist(playlistId);
  if (trackId && trackById(trackId)) await selectTrack(trackId);
}

export function closeMusicPanel() {
  setPanelOpen(false);
}

export function stopMusicPlayback() {
  clearSleepTimer({ persist: true });
  dom.musicAudio.pause();
  dom.musicAudio.removeAttribute('src');
  dom.musicAudio.load();
  library = { tracks: [], playlists: [] };
  loaded = false;
  loading = null;
  render();
  closeMusicPanel();
}

export function isMusicPanelOpen() {
  return dom.musicDock.classList.contains('is-open');
}

function selectPlaylist(playlistId) {
  activePlaylistId = playlistId;
  targetPlaylistId = playlistId;
  localStorage.setItem(storageKeys.musicPlaylistId, activePlaylistId);
  render();
}

function showPlaylistForm(playlist = null) {
  playlistEditingId = playlist?.id || '';
  dom.musicPlaylistForm.hidden = false;
  dom.musicPlaylistName.value = playlist?.title || '';
  dom.musicPlaylistName.focus();
}

function hidePlaylistForm() {
  playlistEditingId = '';
  dom.musicPlaylistForm.reset();
  dom.musicPlaylistForm.hidden = true;
}

async function savePlaylist() {
  const title = dom.musicPlaylistName.value.trim();
  if (!title) return;
  try {
    const result = playlistEditingId
      ? await apiRequest(`/music/playlists/${encodeURIComponent(playlistEditingId)}`, { method: 'PATCH', body: { title } })
      : await apiRequest('/music/playlists', { method: 'POST', body: { id: crypto.randomUUID(), title } });
    hidePlaylistForm();
    applyLibrary(result);
    setStatus('Playlist je uložený.');
  } catch (error) {
    setStatus(error.message || 'Playlist sa nepodarilo uložiť.', { error: true });
  }
}

async function deletePlaylist(playlist) {
  if (!window.confirm(`Zmazať playlist „${playlist.title}“? Skladby v knižnici zostanú zachované.`)) return;
  try {
    const result = await apiRequest(`/music/playlists/${encodeURIComponent(playlist.id)}`, { method: 'DELETE' });
    if (activePlaylistId === playlist.id) activePlaylistId = '';
    if (targetPlaylistId === playlist.id) targetPlaylistId = '';
    applyLibrary(result);
    setStatus('Playlist je odstránený.');
  } catch (error) {
    setStatus(error.message || 'Playlist sa nepodarilo zmazať.', { error: true });
  }
}

async function addTrackToPlaylist(trackId) {
  if (!targetPlaylistId) return;
  try {
    const result = await apiRequest(
      `/music/playlists/${encodeURIComponent(targetPlaylistId)}/tracks/${encodeURIComponent(trackId)}`,
      { method: 'PUT', body: {} }
    );
    applyLibrary(result);
    setStatus('Skladba je zaradená v playliste.');
  } catch (error) {
    setStatus(error.message || 'Skladbu sa nepodarilo zaradiť.', { error: true });
  }
}

async function removeTrackFromPlaylist(trackId) {
  if (!activePlaylistId) return;
  try {
    const result = await apiRequest(
      `/music/playlists/${encodeURIComponent(activePlaylistId)}/tracks/${encodeURIComponent(trackId)}`,
      { method: 'DELETE' }
    );
    applyLibrary(result);
    setStatus('Skladba je odstránená z playlistu.');
  } catch (error) {
    setStatus(error.message || 'Skladbu sa nepodarilo odstrániť.', { error: true });
  }
}

async function reorderTrackByDrop(trackId, targetTrackId, placeAfter) {
  const playlist = playlistById(activePlaylistId);
  if (!playlist) return;
  if (trackId === targetTrackId) return;
  const trackIds = playlist.trackIds.filter((id) => id !== trackId);
  const targetIndex = trackIds.indexOf(targetTrackId);
  if (targetIndex < 0) return;
  trackIds.splice(targetIndex + (placeAfter ? 1 : 0), 0, trackId);
  try {
    const result = await apiRequest(`/music/playlists/${encodeURIComponent(playlist.id)}/order`, {
      method: 'PUT',
      body: { trackIds }
    });
    applyLibrary(result);
  } catch (error) {
    setStatus(error.message || 'Poradie skladieb sa nepodarilo zmeniť.', { error: true });
  }
}

function loadCurrentTrack() {
  const track = trackById(currentTrackId);
  if (!track) return;
  isSeeking = false;
  dom.musicAudio.src = `/api/music/tracks/${encodeURIComponent(track.id)}/audio`;
  dom.musicAudio.load();
  updateNowPlaying();
  updateTransport();
}

async function selectTrack(trackId, { autoplay = false } = {}) {
  const track = trackById(trackId);
  if (!track) return;
  if (currentTrackId !== trackId) {
    dom.musicAudio.pause();
    currentTrackId = trackId;
    resumePosition = 0;
    persistPlaybackState();
    loadCurrentTrack();
  }
  render();
  if (autoplay) await playCurrentTrack();
}

async function playCurrentTrack() {
  if (!currentTrackId) return;
  try {
    await dom.musicAudio.play();
    setStatus('');
  } catch {
    setStatus('Prehliadač zatiaľ nepovolil prehrávanie. Skús tlačidlo Prehrať.', { error: true });
  }
  updateTransport();
}

async function togglePlayback() {
  if (!currentTrackId) {
    const first = queueTracks()[0];
    if (first) await selectTrack(first.id, { autoplay: true });
    return;
  }
  if (dom.musicAudio.paused) await playCurrentTrack();
  else dom.musicAudio.pause();
}

async function toggleTrackPlayback(trackId) {
  if (trackId !== currentTrackId) {
    await selectTrack(trackId, { autoplay: true });
    return;
  }
  await togglePlayback();
}

function previewProgressSeek() {
  isSeeking = true;
  updateCurrentTimeOutput(Number(dom.musicProgress.value) || 0);
}

function commitProgressSeek() {
  if (!isSeeking) return;
  isSeeking = false;
  dom.musicAudio.currentTime = Number(dom.musicProgress.value) || 0;
  updateTransport();
}

function cancelProgressSeek() {
  if (!isSeeking) return;
  isSeeking = false;
  updateTransport();
}

async function selectAdjacent(direction, { autoplay = true } = {}) {
  const queue = queueTracks();
  if (!queue.length) return;
  const currentIndex = queue.findIndex((track) => track.id === currentTrackId);
  let nextIndex = currentIndex + direction;
  if (shuffle && queue.length > 1) {
    do {
      nextIndex = Math.floor(Math.random() * queue.length);
    } while (nextIndex === currentIndex);
  } else if (nextIndex < 0 || nextIndex >= queue.length) {
    if (repeatMode !== 'all') return;
    nextIndex = direction > 0 ? 0 : queue.length - 1;
  }
  await selectTrack(queue[nextIndex]?.id || queue[0].id, { autoplay });
}

function cycleRepeat() {
  repeatMode = repeatMode === 'all' ? 'one' : repeatMode === 'one' ? 'off' : 'all';
  localStorage.setItem(storageKeys.musicRepeat, repeatMode);
  updateTransport();
}

function toggleShuffle() {
  shuffle = !shuffle;
  localStorage.setItem(storageKeys.musicShuffle, String(shuffle));
  updateTransport();
}

function openTrackDialog(trackId) {
  const track = trackById(trackId);
  if (!track) return;
  dialogTrackId = trackId;
  dom.musicTrackFilename.textContent = track.originalName;
  dom.musicTrackTitle.value = track.title;
  dom.musicTrackArtist.value = track.artist;
  dom.musicTrackAlbum.value = track.album;
  dom.musicTrackYear.value = track.year || '';
  dom.musicTrackNumber.value = track.trackNumber || '';
  dom.musicTrackGenre.value = track.genre || '';
  dom.musicTrackDialog.showModal();
  dom.musicTrackTitle.focus();
}

function closeTrackDialog() {
  dialogTrackId = '';
  if (dom.musicTrackDialog.open) dom.musicTrackDialog.close();
}

async function saveTrackDialog() {
  if (!dialogTrackId) return;
  try {
    const result = await apiRequest(`/music/tracks/${encodeURIComponent(dialogTrackId)}`, {
      method: 'PATCH',
      body: {
        title: dom.musicTrackTitle.value.trim(),
        artist: dom.musicTrackArtist.value.trim(),
        album: dom.musicTrackAlbum.value.trim(),
        year: dom.musicTrackYear.value.trim(),
        trackNumber: dom.musicTrackNumber.value.trim(),
        genre: dom.musicTrackGenre.value.trim()
      }
    });
    applyLibrary(result);
    closeTrackDialog();
    setStatus('Údaje skladby sú uložené.');
  } catch (error) {
    setStatus(error.message || 'Údaje skladby sa nepodarilo uložiť.', { error: true });
  }
}

async function deleteTrackDialog() {
  const track = trackById(dialogTrackId);
  if (!track || !window.confirm(`Natrvalo zmazať skladbu „${track.title}“?`)) return;
  try {
    const result = await apiRequest(`/music/tracks/${encodeURIComponent(track.id)}`, { method: 'DELETE' });
    if (currentTrackId === track.id) {
      currentTrackId = '';
      resumePosition = 0;
      dom.musicAudio.pause();
      dom.musicAudio.removeAttribute('src');
      dom.musicAudio.load();
      persistPlaybackState();
    }
    applyLibrary(result);
    closeTrackDialog();
    setStatus('Skladba je odstránená.');
  } catch (error) {
    setStatus(error.message || 'Skladbu sa nepodarilo zmazať.', { error: true });
  }
}

async function uploadTracks(files) {
  if (uploading || !files.length) return;
  uploading = true;
  dom.musicUpload.disabled = true;
  try {
    for (const [index, file] of Array.from(files).entries()) {
      setStatus(`Nahrávam ${index + 1} z ${files.length}: ${file.name}`);
      const result = await uploadMusicTrack(file);
      applyLibrary(result);
    }
    setStatus(files.length === 1 ? 'Skladba je pridaná.' : 'Skladby sú pridané.');
  } catch (error) {
    setStatus(error.message || 'Skladbu sa nepodarilo nahrať.', { error: true });
  } finally {
    uploading = false;
    dom.musicUpload.disabled = false;
    dom.musicFileInput.value = '';
  }
}

function handleLoadedMetadata() {
  const track = trackById(currentTrackId);
  const duration = Number.isFinite(dom.musicAudio.duration) ? dom.musicAudio.duration : 0;
  if (resumePosition > 0 && duration > 0) {
    dom.musicAudio.currentTime = Math.min(resumePosition, Math.max(0, duration - 0.2));
    resumePosition = 0;
  }
  updateTransport();
  if (track && duration > 0 && Math.abs((track.durationSeconds || 0) - duration) > 0.5) {
    void apiRequest(`/music/tracks/${encodeURIComponent(track.id)}`, {
      method: 'PATCH',
      body: { title: track.title, artist: track.artist, album: track.album, durationSeconds: duration }
    }).then(applyLibrary).catch(() => {});
  }
}

function restorePlayerSettings() {
  const storedVolume = Number(localStorage.getItem(storageKeys.musicVolume));
  const volume = Number.isFinite(storedVolume) ? clamp(storedVolume, 0, 1) : DEFAULT_VOLUME;
  dom.musicAudio.volume = volume;
  dom.musicVolume.value = String(volume);
  currentTrackId = localStorage.getItem(storageKeys.musicTrackId) || '';
  resumePosition = Math.max(0, Number(localStorage.getItem(storageKeys.musicPosition)) || 0);
  activePlaylistId = localStorage.getItem(storageKeys.musicPlaylistId) || '';
  targetPlaylistId = activePlaylistId;
  shuffle = localStorage.getItem(storageKeys.musicShuffle) === 'true';
  const storedRepeat = localStorage.getItem(storageKeys.musicRepeat);
  repeatMode = ['all', 'one', 'off'].includes(storedRepeat) ? storedRepeat : 'all';
  sleepTimerEndsAt = Math.max(0, Number(localStorage.getItem(storageKeys.musicSleepTimerEndsAt)) || 0);
  sleepTimerMinutes = Math.max(0, Number(localStorage.getItem(storageKeys.musicSleepTimerMinutes)) || 0);
  if (sleepTimerEndsAt > Date.now()) {
    syncSleepTimerControl();
    scheduleSleepTimer();
  } else {
    clearSleepTimer({ persist: true });
  }
  updateTransport();
}

function syncSleepTimerControl() {
  const requested = String(sleepTimerMinutes);
  const matchingOption = Array.from(dom.musicSleepTimer.options).some((option) => option.value === requested);
  dom.musicSleepTimer.value = sleepTimerEndsAt > Date.now() && matchingOption ? requested : '0';
}

function clearSleepTimer({ persist = true } = {}) {
  if (sleepTimerHandle) window.clearTimeout(sleepTimerHandle);
  sleepTimerHandle = 0;
  sleepTimerEndsAt = 0;
  sleepTimerMinutes = 0;
  if (persist) {
    localStorage.removeItem(storageKeys.musicSleepTimerEndsAt);
    localStorage.removeItem(storageKeys.musicSleepTimerMinutes);
  }
  syncSleepTimerControl();
}

function scheduleSleepTimer() {
  if (sleepTimerHandle) window.clearTimeout(sleepTimerHandle);
  const delay = sleepTimerEndsAt - Date.now();
  if (delay <= 0) {
    clearSleepTimer({ persist: true });
    dom.musicAudio.pause();
    setStatus('Časovač vypol prehrávanie.');
    return;
  }
  sleepTimerHandle = window.setTimeout(() => {
    sleepTimerHandle = 0;
    clearSleepTimer({ persist: true });
    dom.musicAudio.pause();
    setStatus('Časovač vypol prehrávanie.');
  }, delay);
}

function setSleepTimer(minutes) {
  const safeMinutes = Math.max(0, Number(minutes) || 0);
  if (!safeMinutes) {
    clearSleepTimer({ persist: true });
    setStatus('Časovač vypnutia je zrušený.');
    return;
  }
  sleepTimerMinutes = safeMinutes;
  sleepTimerEndsAt = Date.now() + safeMinutes * 60_000;
  localStorage.setItem(storageKeys.musicSleepTimerMinutes, String(safeMinutes));
  localStorage.setItem(storageKeys.musicSleepTimerEndsAt, String(sleepTimerEndsAt));
  syncSleepTimerControl();
  scheduleSleepTimer();
  setStatus(`Prehrávanie sa zastaví za ${safeMinutes} min.`);
}

export function initializeMusic() {
  restorePlayerSettings();
  dom.musicButton.addEventListener('click', handleMusicButtonClick);
  dom.musicButton.addEventListener('dblclick', handleMusicButtonDoubleClick);
  dom.musicClose.addEventListener('click', closeMusicPanel);
  dom.musicUpload.addEventListener('click', () => dom.musicFileInput.click());
  dom.musicFileInput.addEventListener('change', () => void uploadTracks(dom.musicFileInput.files || []));
  dom.musicPlaylistCreate.addEventListener('click', () => showPlaylistForm());
  dom.musicPlaylistCancel.addEventListener('click', hidePlaylistForm);
  dom.musicPlaylistForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void savePlaylist();
  });
  dom.musicSearch.addEventListener('input', renderTracks);
  dom.musicTargetPlaylist.addEventListener('change', () => {
    targetPlaylistId = dom.musicTargetPlaylist.value;
    renderTracks();
  });
  dom.musicAllTracks.addEventListener('click', () => selectPlaylist(''));
  dom.musicPrevious.addEventListener('click', () => void selectAdjacent(-1));
  dom.musicPlay.addEventListener('click', () => void togglePlayback());
  dom.musicNext.addEventListener('click', () => void selectAdjacent(1));
  dom.musicShuffle.addEventListener('click', toggleShuffle);
  dom.musicRepeat.addEventListener('click', cycleRepeat);
  dom.musicProgress.addEventListener('pointerdown', () => { isSeeking = true; });
  dom.musicProgress.addEventListener('input', previewProgressSeek);
  dom.musicProgress.addEventListener('change', commitProgressSeek);
  dom.musicProgress.addEventListener('pointerup', commitProgressSeek);
  dom.musicProgress.addEventListener('pointercancel', cancelProgressSeek);
  dom.musicVolume.addEventListener('input', () => {
    const volume = clamp(Number(dom.musicVolume.value), 0, 1);
    dom.musicAudio.volume = volume;
    localStorage.setItem(storageKeys.musicVolume, String(volume));
  });
  dom.musicSleepTimer.addEventListener('change', () => setSleepTimer(dom.musicSleepTimer.value));
  dom.musicAudio.addEventListener('loadedmetadata', handleLoadedMetadata);
  dom.musicAudio.addEventListener('timeupdate', () => {
    updateTransport();
    if (Date.now() - lastPositionSave >= POSITION_SAVE_INTERVAL) {
      lastPositionSave = Date.now();
      persistPlaybackState();
    }
  });
  dom.musicAudio.addEventListener('play', () => {
    updateTransport();
    renderTracks();
  });
  dom.musicAudio.addEventListener('pause', () => {
    persistPlaybackState();
    updateTransport();
    renderTracks();
  });
  dom.musicAudio.addEventListener('ended', () => {
    if (repeatMode === 'one') {
      dom.musicAudio.currentTime = 0;
      void playCurrentTrack();
      return;
    }
    void selectAdjacent(1);
  });
  dom.musicAudio.addEventListener('error', () => {
    if (currentTrackId) setStatus('Skladbu sa nepodarilo prehrať. Skontroluj, či súbor stále existuje.', { error: true });
  });
  dom.musicTrackCancel.addEventListener('click', closeTrackDialog);
  dom.musicTrackForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveTrackDialog();
  });
  dom.musicTrackDelete.addEventListener('click', () => void deleteTrackDialog());
  dom.musicTrackDialog.addEventListener('click', (event) => {
    if (event.target === dom.musicTrackDialog) closeTrackDialog();
  });
}
