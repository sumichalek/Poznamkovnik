import { apiRequest, uploadMusicTrack } from './api.js';
import { createAppIcon, setAppIcon } from './app-icons.js';
import { storageKeys } from './config.js';
import { installDialogBackdropClose } from './dialogs.js';
import { dom } from './dom.js';
import { refreshMusicResizeHandle } from './music-resize.js';
import { updateTopbarVisibility } from './topbar.js';

const DEFAULT_VOLUME = 0.7;
const POSITION_SAVE_INTERVAL = 1_000;
const TOPBAR_DOUBLE_CLICK_DELAY = 220;
const WEEKDAY_LABELS = ['Po', 'Ut', 'St', 'Št', 'Pi', 'So', 'Ne'];

let library = {
  tracks: [], playlists: [], radioStations: [], radioRecordings: [], radioRecordingSchedules: [], podcasts: [], podcastEpisodes: []
};
let loaded = false;
let loading = null;
let mediaView = 'tracks';
let activePlaylistId = '';
let targetPlaylistId = '';
let currentTrackId = '';
let currentRadioStationId = '';
let currentRadioRecordingId = '';
let currentPodcastEpisodeId = '';
let dialogTrackId = '';
let dialogRadioStationId = '';
let dialogRadioScheduleStationId = '';
let playlistEditingId = '';
let activePodcastId = '';
let shuffle = false;
let repeatMode = 'all';
let resumePosition = 0;
let lastPositionSave = 0;
let uploading = false;
let isSeeking = false;
let draggedTrackId = '';
let selectedTrackIds = new Set();
let sleepTimerEndsAt = 0;
let sleepTimerMinutes = 0;
let sleepTimerHandle = 0;
let sleepTimerTicker = 0;
let musicButtonClickTimer = 0;
let statusClearHandle = 0;
let recordingPollHandle = 0;
let panelPinned = false;
let panelMinimized = false;
let musicSearchResultClickTimer = 0;
let searchDescriptionsEnabled = false;

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

function radioStationById(stationId) {
  return library.radioStations.find((station) => station.id === stationId) || null;
}

function radioRecordingById(recordingId) {
  return library.radioRecordings.find((recording) => recording.id === recordingId) || null;
}

function podcastById(podcastId) {
  return library.podcasts.find((podcast) => podcast.id === podcastId) || null;
}

function podcastEpisodeById(episodeId) {
  return library.podcastEpisodes.find((episode) => episode.id === episodeId) || null;
}

function activeRadioRecording() {
  return library.radioRecordings.find((recording) => ['recording', 'stopping'].includes(recording.status)) || null;
}

function activeRadioSchedules() {
  return library.radioRecordingSchedules.filter((schedule) => ['scheduled', 'running'].includes(schedule.status));
}

function isRadioPlaying() {
  return Boolean(currentRadioStationId);
}

function hasCurrentMedia() {
  return Boolean(currentTrackId || currentRadioStationId || currentRadioRecordingId || currentPodcastEpisodeId);
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

function filteredRadioStations() {
  const query = dom.musicSearch.value.trim().toLocaleLowerCase('sk');
  return library.radioStations.filter((station) => {
    if (!query) return true;
    return `${station.title} ${station.streamUrl} ${station.websiteUrl} ${station.note}`
      .toLocaleLowerCase('sk')
      .includes(query);
  });
}

function filteredPodcastEpisodes() {
  const query = dom.musicSearch.value.trim().toLocaleLowerCase('sk');
  return library.podcastEpisodes.filter((episode) => {
    if (activePodcastId && episode.feedId !== activePodcastId) return false;
    if (!query) return true;
    return `${episode.title} ${episode.feedTitle} ${episode.description} ${episode.publishedAt}`
      .toLocaleLowerCase('sk')
      .includes(query);
  });
}

function normalizeMusicSearchText(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLocaleLowerCase('sk');
}

function musicSearchQuery() {
  return normalizeMusicSearchText(dom.musicSearch.value).trim();
}

function isGlobalMusicSearchActive() {
  return Boolean(musicSearchQuery());
}

function escapeMusicSearchRegExp(value) {
  return value.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&');
}

function musicSearchGlobPattern(pattern) {
  let expression = '';
  let hasWildcard = false;
  const characters = [...pattern];
  for (let index = 0; index < characters.length; index += 1) {
    const character = characters[index];
    if (character === '*') {
      expression += '[^\\s]*';
      hasWildcard = true;
      continue;
    }
    if (character === '?') {
      expression += '[^\\s]';
      hasWildcard = true;
      continue;
    }
    if (character === '[') {
      const end = characters.indexOf(']', index + 1);
      if (end > index + 1) {
        let content = characters.slice(index + 1, end).join('');
        const negated = content.startsWith('!');
        if (negated) content = content.slice(1);
        if (content) {
          expression += `[${negated ? '^' : ''}${content.replace(/\\/g, '\\\\')}]`;
          hasWildcard = true;
          index = end;
          continue;
        }
      }
    }
    expression += escapeMusicSearchRegExp(character);
  }
  if (!hasWildcard) return null;
  try {
    return new RegExp(`(?:^|\\s)${expression}(?=\\s|$)`, 'u');
  } catch {
    return null;
  }
}

function matchesMusicSearch(query, ...values) {
  const patterns = query.match(/\S+/gu) || [];
  const text = normalizeMusicSearchText(values.join(' '));
  const words = text.match(/[\p{L}\p{N}]+/gu) || [];
  if (!patterns.length || !words.length) return false;
  return patterns.every((pattern) => {
    const expression = musicSearchGlobPattern(pattern);
    return expression ? expression.test(text) : words.some((word) => word.includes(pattern));
  });
}

function searchMusicValues(query, primaryValues, description = '') {
  const values = searchDescriptionsEnabled && description
    ? [...primaryValues, description]
    : primaryValues;
  return matchesMusicSearch(query, ...values);
}

function syncMusicSearchDescriptionsToggle() {
  const button = dom.musicSearchDescriptions;
  const label = searchDescriptionsEnabled ? 'Nehľadať v opisoch' : 'Hľadať aj v opisoch';
  button.classList.toggle('is-active', searchDescriptionsEnabled);
  button.setAttribute('aria-pressed', String(searchDescriptionsEnabled));
  button.setAttribute('aria-label', label);
  button.title = label;
  setAppIcon(button.querySelector('.app-icon'), searchDescriptionsEnabled ? 'article-check' : 'article');
}

function setStatus(message = '', { error = false, persistent = false } = {}) {
  if (statusClearHandle) window.clearTimeout(statusClearHandle);
  statusClearHandle = 0;
  dom.musicStatus.textContent = message;
  dom.musicStatus.classList.toggle('is-error', Boolean(message) && error);
  dom.musicStatus.classList.toggle('is-visible', Boolean(message));
  if (message && !error && !persistent) {
    statusClearHandle = window.setTimeout(() => setStatus(''), 3_800);
  }
}

function persistPlaybackState() {
  const position = String(Math.max(0, dom.musicAudio.currentTime || 0));
  if (currentTrackId) {
    localStorage.setItem(storageKeys.musicTrackId, currentTrackId);
    localStorage.setItem(storageKeys.musicPosition, position);
  }
  if (currentPodcastEpisodeId) {
    localStorage.setItem(storageKeys.musicPodcastEpisodeId, currentPodcastEpisodeId);
    localStorage.setItem(storageKeys.musicPodcastPosition, position);
  }
}

function clearPersistedPlaybackState() {
  localStorage.removeItem(storageKeys.musicTrackId);
  localStorage.removeItem(storageKeys.musicPosition);
  localStorage.removeItem(storageKeys.musicPodcastEpisodeId);
  localStorage.removeItem(storageKeys.musicPodcastPosition);
}

function updateTopbarButton() {
  const icon = dom.musicButton.querySelector('.app-icon');
  const playing = !dom.musicAudio.paused && hasCurrentMedia();
  setAppIcon(icon, playing ? 'pause' : 'music');
  const panelLabel = panelPinned && panelMinimized ? 'Obnoviť pripnutý prehrávač' : 'Prehrávač';
  dom.musicButton.title = playing ? `Prehráva sa hudba · ${panelLabel}` : panelLabel;
  dom.musicButton.setAttribute('aria-label', playing ? `Prehráva sa hudba, ${panelLabel.toLocaleLowerCase('sk')}` : panelLabel);
  dom.musicButton.classList.toggle('is-playing', playing);
  dom.musicButton.classList.toggle('is-pinned', panelPinned);
}

function updateTransport() {
  const track = trackById(currentTrackId);
  const station = radioStationById(currentRadioStationId);
  const recording = radioRecordingById(currentRadioRecordingId);
  const episode = podcastEpisodeById(currentPodcastEpisodeId);
  const isLive = Boolean(station);
  const isTrackView = mediaView === 'tracks';
  const isPodcastView = mediaView === 'podcasts';
  const canNavigate = isTrackView || isPodcastView;
  const currentViewHasMedia = isTrackView ? Boolean(track || recording) : isPodcastView ? Boolean(episode) : Boolean(station);
  const duration = Number.isFinite(dom.musicAudio.duration)
    ? dom.musicAudio.duration
    : track?.durationSeconds || recording?.durationSeconds || episode?.durationSeconds || 0;
  const currentTime = Math.min(dom.musicAudio.currentTime || 0, duration || 0);
  dom.musicProgressRow.classList.toggle('is-live', isLive);
  dom.musicCurrentTime.hidden = isLive;
  dom.musicProgress.hidden = isLive;
  dom.musicDuration.hidden = isLive;
  dom.musicLiveStatus.hidden = !isLive;
  dom.musicProgress.max = String(duration || 0);
  dom.musicProgress.disabled = isLive || (!track && !recording && !episode) || !duration;
  if (isLive) {
    dom.musicProgress.value = '0';
    updateCurrentTimeOutput('Naživo');
    dom.musicDuration.value = 'Naživo';
    dom.musicDuration.textContent = 'Naživo';
  } else if (!isSeeking) {
    dom.musicProgress.value = String(currentTime);
    updateCurrentTimeOutput(currentTime);
    dom.musicDuration.value = formatTime(duration);
    dom.musicDuration.textContent = formatTime(duration);
  }
  dom.musicPrevious.disabled = !canNavigate || isLive || !(track || episode) || !(isPodcastView ? filteredPodcastEpisodes().length : queueTracks().length);
  const canPlayCurrentView = mediaView === 'radio'
    ? Boolean(currentRadioStationId || filteredRadioStations().length)
    : isPodcastView
      ? Boolean(currentPodcastEpisodeId || filteredPodcastEpisodes().length)
      : Boolean(currentTrackId || queueTracks().length);
  dom.musicPlay.disabled = !canPlayCurrentView;
  dom.musicNext.disabled = !canNavigate || isLive || !(track || episode) || !(isPodcastView ? filteredPodcastEpisodes().length : queueTracks().length);
  const isCurrentViewPlaying = currentViewHasMedia && !dom.musicAudio.paused;
  setAppIcon(dom.musicPlay.querySelector('.app-icon'), isCurrentViewPlaying ? 'pause' : 'play');
  dom.musicPlay.title = isCurrentViewPlaying ? 'Pozastaviť' : 'Prehrať';
  dom.musicPlay.setAttribute('aria-label', isCurrentViewPlaying ? 'Pozastaviť' : 'Prehrať');
  dom.musicShuffle.disabled = !canNavigate || isLive || !(track || episode);
  dom.musicRepeat.disabled = !canNavigate || isLive || !(track || episode);
  dom.musicShuffle.classList.toggle('is-active', canNavigate && !isLive && Boolean(track || episode) && shuffle);
  dom.musicShuffle.setAttribute('aria-pressed', String(shuffle));
  dom.musicRepeat.classList.toggle('is-active', repeatMode !== 'off');
  dom.musicRepeat.dataset.mode = repeatMode;
  dom.musicRepeat.title = repeatMode === 'one' ? 'Opakovať jednu skladbu' : repeatMode === 'all' ? 'Opakovať zoznam' : 'Neopakovať';
  dom.musicRepeat.setAttribute('aria-label', dom.musicRepeat.title);
  setAppIcon(dom.musicRepeat.querySelector('.app-icon'), repeatMode === 'one' ? 'repeat-1' : 'repeat');
  updateRecordButton();
  updateTopbarButton();
}

function updateRecordButton() {
  const station = radioStationById(currentRadioStationId);
  const recording = activeRadioRecording();
  const visible = Boolean(station || recording);
  dom.musicRecord.hidden = !visible;
  dom.musicRecord.disabled = !visible || recording?.status === 'stopping';
  dom.musicRecord.classList.toggle('is-recording', Boolean(recording));
  setAppIcon(dom.musicRecord.querySelector('.app-icon'), recording ? 'stop' : 'record');
  if (!visible) return;
  if (recording?.status === 'stopping') {
    dom.musicRecord.title = 'Nahrávanie sa zastavuje';
    dom.musicRecord.setAttribute('aria-label', dom.musicRecord.title);
    return;
  }
  if (recording) {
    dom.musicRecord.title = `Zastaviť nahrávanie: ${recording.stationTitle}`;
    dom.musicRecord.setAttribute('aria-label', dom.musicRecord.title);
    return;
  }
  dom.musicRecord.title = 'Nahrať vysielanie';
  dom.musicRecord.setAttribute('aria-label', dom.musicRecord.title);
}

function updateCurrentTimeOutput(value) {
  const label = typeof value === 'string' ? value : formatTime(value);
  dom.musicCurrentTime.value = label;
  dom.musicCurrentTime.textContent = label;
}

function nowPlayingInfo() {
  const track = trackById(currentTrackId);
  const station = radioStationById(currentRadioStationId);
  const recording = radioRecordingById(currentRadioRecordingId);
  const episode = podcastEpisodeById(currentPodcastEpisodeId);
  const activeRecording = activeRadioRecording();
  if (station) {
    const host = safeUrlHost(station.streamUrl);
    return {
      title: station.title,
      tooltip: [`Stanica: ${station.title}`, host ? `Stream: ${host}` : 'Živé internetové vysielanie'].join('\n'),
      icon: 'radio'
    };
  }
  if (recording) {
    const details = [
      'Nahrávka rádia',
      recording.durationSeconds ? formatTime(recording.durationSeconds) : '',
      recording.sizeBytes ? formatBytes(recording.sizeBytes) : ''
    ].filter(Boolean);
    return {
      title: recording.stationTitle,
      tooltip: [details.join(' / '), recording.filename ? `Súbor: ${recording.filename}` : ''].filter(Boolean).join('\n'),
      icon: 'radio'
    };
  }
  if (episode) {
    return {
      title: episode.title,
      tooltip: [
        `Podcast: ${episode.feedTitle}`,
        episode.publishedAt ? `Vydané: ${formatPodcastDate(episode.publishedAt)}` : '',
        episode.durationSeconds ? `Dĺžka: ${formatTime(episode.durationSeconds)}` : ''
      ].filter(Boolean).join('\n'),
      icon: 'podcast'
    };
  }
  if (activeRecording && !track) {
    return {
      title: activeRecording.stationTitle,
      tooltip: activeRecording.status === 'stopping'
        ? 'Nahrávanie rádia sa ukončuje na serveri.'
        : 'Nahrávanie rádia beží na serveri.',
      icon: 'radio'
    };
  }
  if (!track) {
    return { title: 'Bez vybranej skladby', tooltip: 'Pridaj hudbu do vlastnej knižnice.', icon: 'music' };
  }
  return {
    title: track.title,
    tooltip: [
      `Skladba: ${track.title}`,
      track.artist ? `Autor: ${track.artist}` : '',
      track.album ? `Album: ${track.album}` : '',
      track.originalName ? `Súbor: ${track.originalName}` : ''
    ].filter(Boolean).join('\n'),
    icon: 'music'
  };
}

function updateMiniPlayer(info) {
  const visible = panelPinned && panelMinimized;
  dom.musicMiniPlayer.hidden = !visible;
  dom.musicMiniPlayer.classList.toggle('is-playing', !dom.musicAudio.paused && hasCurrentMedia());
  dom.musicMiniPlayer.classList.toggle('is-recording', Boolean(activeRadioRecording()));
  dom.musicMiniPlayerTitle.textContent = info.title;
  dom.musicMiniPlayerOpen.title = `Obnoviť prehrávač: ${info.title}`;
  dom.musicMiniPlayerOpen.setAttribute('aria-label', dom.musicMiniPlayerOpen.title);
  dom.musicMiniPlayerOpen.setAttribute('title', info.tooltip || dom.musicMiniPlayerOpen.title);
  setAppIcon(dom.musicMiniPlayerOpen.querySelector('.app-icon'), info.icon);
}

function updateMusicPanelChrome() {
  dom.musicDock.classList.toggle('is-pinned', panelPinned);
  dom.musicPanelPin.classList.toggle('is-active', panelPinned);
  dom.musicPanelPin.setAttribute('aria-pressed', String(panelPinned));
  dom.musicPanelPin.title = panelPinned ? 'Odopnúť prehrávač' : 'Pripnúť prehrávač';
  dom.musicPanelPin.setAttribute('aria-label', dom.musicPanelPin.title);
  setAppIcon(dom.musicPanelPin.querySelector('.app-icon'), panelPinned ? 'pin-off' : 'pin');
  dom.musicPanelMinimize.hidden = !panelPinned;
  dom.musicClose.title = panelPinned ? 'Odopnúť a zavrieť prehrávač' : 'Zavrieť prehrávač';
  dom.musicClose.setAttribute('aria-label', dom.musicClose.title);
  updateNowPlaying();
  updateTopbarButton();
}

function updateNowPlaying() {
  const info = nowPlayingInfo();
  dom.musicNowTitle.textContent = info.title;
  dom.musicNowTitle.title = info.tooltip;
  updateMiniPlayer(info);
}

function safeUrlHost(url) {
  try {
    return new URL(url).host;
  } catch {
    return '';
  }
}

function renderPlaylists() {
  dom.musicAllTracks.querySelector('span').textContent = 'Všetky skladby';
  dom.musicAllTracks.setAttribute('aria-label', 'Zobraziť všetky skladby');
  dom.musicAllTracks.classList.toggle('is-active', !activePlaylistId);
  dom.musicAllTracks.setAttribute('aria-pressed', String(!activePlaylistId));
  dom.musicAllTracksCount.textContent = String(library.tracks.length);
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
  updateSelectionControls();
}

function selectionLabel(count) {
  return `${count} ${count === 1 ? 'označená skladba' : count < 5 ? 'označené skladby' : 'označených skladieb'}`;
}

function updateSelectionControls() {
  const count = selectedTrackIds.size;
  dom.musicSelectionBar.hidden = !count;
  dom.musicSelectionCount.textContent = selectionLabel(count);
  dom.musicAddSelected.disabled = !count || !targetPlaylistId || !library.playlists.length;
}

function setTrackSelected(trackId, selected) {
  if (selected) selectedTrackIds.add(trackId);
  else selectedTrackIds.delete(trackId);
  updateSelectionControls();
}

function clearTrackSelection() {
  if (!selectedTrackIds.size) return;
  selectedTrackIds.clear();
  render();
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
    row.classList.toggle('is-selected', selectedTrackIds.has(track.id));
    row.title = trackTooltip(track);
    const select = document.createElement('label');
    select.className = 'music-track-select';
    select.title = `Označiť skladbu ${track.title}`;
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = selectedTrackIds.has(track.id);
    checkbox.setAttribute('aria-label', `Označiť skladbu ${track.title}`);
    checkbox.addEventListener('change', () => {
      setTrackSelected(track.id, checkbox.checked);
      row.classList.toggle('is-selected', checkbox.checked);
    });
    select.append(checkbox);
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
    }
    actions.append(createTrackAction('pencil', 'Upraviť skladbu', () => openTrackDialog(track.id)));
    if (dragHandle) row.append(dragHandle);
    row.append(select, copy, actions);
    dom.musicTracks.append(row);
  });
  updateSelectionControls();
}

function radioStationSummary(station) {
  const host = safeUrlHost(station.streamUrl);
  return station.note || host || 'Živé vysielanie';
}

function radioStationTooltip(station) {
  return [
    ['Stanica', station.title],
    ['Stream', station.streamUrl],
    ['Web', station.websiteUrl],
    ['Poznámka', station.note]
  ].filter(([, value]) => value).map(([label, value]) => `${label}: ${value}`).join('\n');
}

function radioRecordingStatus(recording) {
  const labels = {
    recording: 'Nahráva sa',
    stopping: 'Ukončuje sa',
    completed: 'Dokončená',
    stopped: 'Zastavená',
    failed: 'Nepodarila sa'
  };
  return labels[recording.status] || 'Neznámy stav';
}

function radioRecordingSummary(recording) {
  const details = [radioRecordingStatus(recording)];
  if (recording.durationSeconds) details.push(formatTime(recording.durationSeconds));
  if (recording.sizeBytes) details.push(formatBytes(recording.sizeBytes));
  return details.join(' / ');
}

function radioRecordingTooltip(recording) {
  const details = [
    ['Stanica', recording.stationTitle],
    ['Stav', radioRecordingStatus(recording)],
    ['Dĺžka', recording.durationSeconds ? formatTime(recording.durationSeconds) : ''],
    ['Veľkosť', recording.sizeBytes ? formatBytes(recording.sizeBytes) : ''],
    ['Chyba', recording.error]
  ];
  return details.filter(([, value]) => value).map(([label, value]) => `${label}: ${value}`).join('\n');
}

function radioScheduleStatus(schedule) {
  const labels = {
    scheduled: 'Naplánované',
    running: 'Spúšťa sa',
    paused: 'Pozastavené',
    completed: 'Dokončené',
    failed: 'Nepodarilo sa',
    cancelled: 'Zrušené',
    missed: 'Zmeškané'
  };
  return labels[schedule.status] || 'Neznámy stav';
}

function radioScheduleWeekdays(schedule) {
  return Array.isArray(schedule.recurrenceWeekdays)
    ? schedule.recurrenceWeekdays.filter((weekday) => Number.isInteger(weekday) && weekday >= 0 && weekday <= 6)
    : [];
}

function radioScheduleRepeatLabel(schedule) {
  const labels = radioScheduleWeekdays(schedule).map((weekday) => WEEKDAY_LABELS[weekday]);
  return labels.length ? `Opakuje sa: ${labels.join(', ')}` : '';
}

function formatScheduleDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return 'Neznámy termín';
  return new Intl.DateTimeFormat('sk-SK', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
}

function radioScheduleSummary(schedule) {
  return [
    formatScheduleDateTime(schedule.startAt),
    radioScheduleRepeatLabel(schedule),
    formatTime(schedule.durationSeconds),
    radioScheduleStatus(schedule)
  ].filter(Boolean).join(' / ');
}

function radioScheduleTooltip(schedule) {
  return [
    ['Stanica', schedule.stationTitle],
    ['Začiatok', formatScheduleDateTime(schedule.startAt)],
    ['Opakovanie', radioScheduleRepeatLabel(schedule)],
    ['Dĺžka', formatTime(schedule.durationSeconds)],
    ['Stav', radioScheduleStatus(schedule)],
    ['Chyba', schedule.error]
  ].filter(([, value]) => value).map(([label, value]) => `${label}: ${value}`).join('\n');
}

function filteredRadioRecordings() {
  const query = dom.musicSearch.value.trim().toLocaleLowerCase('sk');
  return library.radioRecordings.filter((recording) => {
    if (!query) return true;
    return `${recording.stationTitle} ${recording.status}`.toLocaleLowerCase('sk').includes(query);
  });
}

function filteredRadioSchedules() {
  const query = dom.musicSearch.value.trim().toLocaleLowerCase('sk');
  return library.radioRecordingSchedules.filter((schedule) => {
    if (!query) return true;
    return `${schedule.stationTitle} ${schedule.status} ${schedule.error}`.toLocaleLowerCase('sk').includes(query);
  });
}

function downloadRadioRecording(recording) {
  const link = document.createElement('a');
  link.href = `/api/music/recordings/${encodeURIComponent(recording.id)}/file?download=1`;
  link.download = `${recording.stationTitle || 'nahrávka-rádia'}.mp3`;
  document.body.append(link);
  link.click();
  link.remove();
}

function renderRadioRecordings() {
  const recordings = filteredRadioRecordings();
  if (!recordings.length && !library.radioRecordings.length) return;
  const section = document.createElement('section');
  section.className = 'music-recording-section';
  const heading = document.createElement('h4');
  heading.textContent = 'Dočasné nahrávky';
  section.append(heading);
  if (!recordings.length) {
    const message = document.createElement('p');
    message.className = 'music-empty';
    message.textContent = 'Tomuto vyhľadávaniu nezodpovedá žiadna nahrávka.';
    section.append(message);
    dom.musicTracks.append(section);
    return;
  }
  recordings.forEach((recording) => {
    const isReady = ['completed', 'stopped'].includes(recording.status);
    const row = document.createElement('div');
    row.className = 'music-track-row music-recording-row';
    row.classList.toggle('is-current', recording.id === currentRadioRecordingId);
    row.classList.toggle('is-error', recording.status === 'failed');
    row.title = radioRecordingTooltip(recording);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'music-track-copy';
    copy.disabled = !isReady;
    copy.title = isReady ? radioRecordingTooltip(recording) : `${radioRecordingTooltip(recording)}\nNahrávka zatiaľ nie je pripravená na prehratie.`;
    copy.setAttribute('aria-label', `${isReady ? 'Prehrať alebo pozastaviť' : 'Nedá sa prehrať'} nahrávku ${recording.stationTitle}`);
    copy.addEventListener('dblclick', () => void toggleRadioRecordingPlayback(recording.id));
    copy.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      void toggleRadioRecordingPlayback(recording.id);
    });
    const text = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = recording.stationTitle;
    const details = document.createElement('small');
    details.textContent = radioRecordingSummary(recording);
    text.append(title, details);
    copy.append(text);
    const actions = document.createElement('div');
    actions.className = 'music-track-actions';
    if (isReady) actions.append(createTrackAction('download', 'Stiahnuť nahrávku', () => downloadRadioRecording(recording)));
    actions.append(createTrackAction('trash', 'Zmazať nahrávku', () => deleteRadioRecording(recording)));
    row.append(copy, actions);
    section.append(row);
  });
  dom.musicTracks.append(section);
}

function renderRadioSchedules() {
  const schedules = filteredRadioSchedules();
  if (!schedules.length && !library.radioRecordingSchedules.length) return;
  const section = document.createElement('section');
  section.className = 'music-recording-section music-schedule-section';
  const heading = document.createElement('h4');
  heading.textContent = 'Termíny nahrávania';
  section.append(heading);
  if (!schedules.length) {
    const message = document.createElement('p');
    message.className = 'music-empty';
    message.textContent = 'Tomuto vyhľadávaniu nezodpovedá žiadny termín.';
    section.append(message);
    dom.musicTracks.append(section);
    return;
  }
  schedules.forEach((schedule) => {
    const row = document.createElement('div');
    row.className = 'music-track-row music-recording-row music-schedule-row';
    row.classList.toggle('is-error', ['failed', 'missed'].includes(schedule.status));
    row.title = radioScheduleTooltip(schedule);
    const copy = document.createElement('span');
    copy.className = 'music-track-copy';
    const text = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = schedule.stationTitle;
    const details = document.createElement('small');
    details.textContent = radioScheduleSummary(schedule);
    text.append(title, details);
    copy.append(text);
    const actions = document.createElement('div');
    actions.className = 'music-track-actions';
    if (schedule.status === 'scheduled') {
      if (radioScheduleWeekdays(schedule).length) {
        actions.append(createTrackAction('pause', 'Pozastaviť opakovaný plán', () => void pauseRadioSchedule(schedule)));
      }
      actions.append(createTrackAction('close', 'Zrušiť termín nahrávania', () => void cancelRadioSchedule(schedule)));
    } else if (schedule.status === 'paused') {
      actions.append(
        createTrackAction('play', 'Obnoviť opakovaný plán', () => void resumeRadioSchedule(schedule)),
        createTrackAction('trash', 'Odstrániť záznam termínu', () => void deleteRadioSchedule(schedule))
      );
    } else if (schedule.status !== 'running') {
      actions.append(createTrackAction('trash', 'Odstrániť záznam termínu', () => void deleteRadioSchedule(schedule)));
    }
    row.append(copy, actions);
    section.append(row);
  });
  dom.musicTracks.append(section);
}

function renderRadioStations() {
  const stations = filteredRadioStations();
  dom.musicTracks.replaceChildren();
  if (!stations.length) {
    const message = document.createElement('p');
    message.className = 'music-empty';
    message.textContent = library.radioStations.length
      ? 'Tomuto vyhľadávaniu nezodpovedá žiadna stanica.'
      : 'Zatiaľ nemáš uloženú žiadnu stanicu.';
    dom.musicTracks.append(message);
  } else stations.forEach((station) => {
    const row = document.createElement('div');
    row.className = 'music-track-row music-radio-row';
    row.classList.toggle('is-current', station.id === currentRadioStationId);
    row.title = radioStationTooltip(station);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'music-track-copy';
    copy.title = radioStationTooltip(station);
    copy.setAttribute('aria-label', `Prehrať alebo pozastaviť stanicu ${station.title}`);
    copy.addEventListener('dblclick', () => void toggleRadioStationPlayback(station.id));
    copy.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      void toggleRadioStationPlayback(station.id);
    });
    const text = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = station.title;
    const details = document.createElement('small');
    details.textContent = radioStationSummary(station);
    text.append(title, details);
    copy.append(text);
    const actions = document.createElement('div');
    actions.className = 'music-track-actions';
    actions.append(
      createTrackAction('calendar', 'Naplánovať nahrávanie', () => openRadioScheduleDialog(station.id)),
      createTrackAction('pencil', 'Upraviť stanicu', () => openRadioStationDialog(station.id)),
      createTrackAction('trash', 'Zmazať stanicu', () => deleteRadioStation(station))
    );
    row.append(copy, actions);
    dom.musicTracks.append(row);
  });
  renderRadioSchedules();
  renderRadioRecordings();
}

function formatPodcastDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value || '';
  return new Intl.DateTimeFormat('sk-SK', { dateStyle: 'medium' }).format(date);
}

function podcastEpisodeSummary(episode) {
  return [episode.feedTitle, formatPodcastDate(episode.publishedAt), episode.durationSeconds ? formatTime(episode.durationSeconds) : '']
    .filter(Boolean)
    .join(' / ');
}

function podcastEpisodeTooltip(episode) {
  return [
    ['Podcast', episode.feedTitle],
    ['Epizóda', episode.title],
    ['Vydané', formatPodcastDate(episode.publishedAt)],
    ['Dĺžka', episode.durationSeconds ? formatTime(episode.durationSeconds) : ''],
    ['Adresa zvuku', episode.mediaUrl]
  ].filter(([, value]) => value).map(([label, value]) => `${label}: ${value}`).join('\n');
}

function selectPodcast(podcastId) {
  activePodcastId = podcastId;
  localStorage.setItem(storageKeys.musicPodcastId, podcastId);
  render();
}

function renderPodcastFeeds() {
  dom.musicAllTracks.querySelector('span').textContent = 'Všetky epizódy';
  dom.musicAllTracks.setAttribute('aria-label', 'Zobraziť epizódy všetkých podcastov');
  dom.musicAllTracks.classList.toggle('is-active', !activePodcastId);
  dom.musicAllTracks.setAttribute('aria-pressed', String(!activePodcastId));
  dom.musicAllTracksCount.textContent = String(library.podcastEpisodes.length);
  dom.musicPlaylists.replaceChildren();
  library.podcasts.forEach((podcast) => {
    const row = document.createElement('div');
    row.className = 'music-playlist-item';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'music-playlist-button';
    const active = podcast.id === activePodcastId;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
    button.title = podcast.description || podcast.title;
    const label = document.createElement('span');
    label.textContent = podcast.title;
    const count = document.createElement('small');
    count.textContent = String(podcast.episodeCount);
    button.append(label, count);
    button.addEventListener('click', () => selectPodcast(podcast.id));
    const actions = document.createElement('span');
    actions.className = 'music-playlist-actions';
    actions.append(
      createTrackAction('rotate-ccw', `Obnoviť podcast ${podcast.title}`, () => refreshPodcast(podcast.id)),
      createTrackAction('trash', `Odstrániť podcast ${podcast.title}`, () => deletePodcast(podcast))
    );
    row.append(button, actions);
    dom.musicPlaylists.append(row);
  });
}

function renderPodcastEpisodes() {
  const episodes = filteredPodcastEpisodes();
  dom.musicTracks.replaceChildren();
  if (!episodes.length) {
    const message = document.createElement('p');
    message.className = 'music-empty';
    message.textContent = library.podcastEpisodes.length
      ? 'Tomuto výberu nezodpovedá žiadna epizóda.'
      : 'Zatiaľ nemáš pridaný žiadny podcast.';
    dom.musicTracks.append(message);
    return;
  }
  episodes.forEach((episode) => {
    const row = document.createElement('div');
    row.className = 'music-track-row music-podcast-row';
    row.classList.toggle('is-current', episode.id === currentPodcastEpisodeId);
    row.title = podcastEpisodeTooltip(episode);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'music-track-copy';
    copy.title = podcastEpisodeTooltip(episode);
    copy.setAttribute('aria-label', `Prehrať alebo pozastaviť epizódu ${episode.title}`);
    copy.addEventListener('dblclick', () => void togglePodcastEpisodePlayback(episode.id));
    copy.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      void togglePodcastEpisodePlayback(episode.id);
    });
    const text = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = episode.title;
    const details = document.createElement('small');
    details.textContent = podcastEpisodeSummary(episode);
    text.append(title, details);
    copy.append(text);
    row.append(copy);
    dom.musicTracks.append(row);
  });
}

function musicSearchResultMeta(label, details = []) {
  return [label, ...details.filter(Boolean)].join(' / ');
}

function cancelMusicSearch({ focusToggle = false, renderResults = true } = {}) {
  if (musicSearchResultClickTimer) window.clearTimeout(musicSearchResultClickTimer);
  musicSearchResultClickTimer = 0;
  dom.musicSearch.value = '';
  dom.musicSearchClear.hidden = true;
  setMusicSearchOpen(false);
  if (renderResults) render();
  if (focusToggle) requestAnimationFrame(() => dom.musicSearchToggle.focus());
}

function clearMusicSearchForResult() {
  cancelMusicSearch({ renderResults: false });
}

async function openMusicSearchResult(result, { autoplay = false } = {}) {
  clearMusicSearchForResult();
  if (result.type === 'track') {
    setMediaView('tracks');
    await selectTrack(result.id, { autoplay });
    return;
  }
  if (result.type === 'playlist') {
    setMediaView('tracks');
    selectPlaylist(result.id);
    return;
  }
  if (result.type === 'radio') {
    setMediaView('radio');
    await selectRadioStation(result.id, { autoplay });
    return;
  }
  if (result.type === 'podcast') {
    setMediaView('podcasts');
    selectPodcast(result.id);
    return;
  }
  if (result.type === 'episode') {
    setMediaView('podcasts');
    await selectPodcastEpisode(result.id, { autoplay });
  }
}

function addMusicSearchResult(container, result) {
  const row = document.createElement('div');
  row.className = 'music-track-row music-global-search-row';
  row.title = result.tooltip || `${result.label}: ${result.title}`;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'music-track-copy';
  button.setAttribute('aria-label', `Otvoriť ${result.label.toLocaleLowerCase('sk')} ${result.title}`);
  button.append(createAppIcon(result.icon));
  const copy = document.createElement('span');
  const title = document.createElement('strong');
  title.textContent = result.title;
  const details = document.createElement('small');
  details.textContent = result.details;
  copy.append(title, details);
  button.append(copy);
  button.addEventListener('click', () => {
    if (musicSearchResultClickTimer) window.clearTimeout(musicSearchResultClickTimer);
    musicSearchResultClickTimer = window.setTimeout(() => {
      musicSearchResultClickTimer = 0;
      void openMusicSearchResult(result);
    }, TOPBAR_DOUBLE_CLICK_DELAY);
  });
  button.addEventListener('dblclick', (event) => {
    event.preventDefault();
    if (musicSearchResultClickTimer) window.clearTimeout(musicSearchResultClickTimer);
    musicSearchResultClickTimer = 0;
    void openMusicSearchResult(result, { autoplay: result.type !== 'playlist' && result.type !== 'podcast' });
  });
  button.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    if (musicSearchResultClickTimer) window.clearTimeout(musicSearchResultClickTimer);
    musicSearchResultClickTimer = 0;
    void openMusicSearchResult(result);
  });
  row.append(button);
  container.append(row);
}

function addMusicSearchGroup(container, title, results) {
  if (!results.length) return;
  const section = document.createElement('section');
  section.className = 'music-global-search-group';
  const heading = document.createElement('h4');
  heading.textContent = title;
  section.append(heading);
  results.forEach((result) => addMusicSearchResult(section, result));
  container.append(section);
}

function renderGlobalMusicSearch() {
  const query = musicSearchQuery();
  dom.musicTracks.replaceChildren();
  dom.musicTracks.classList.add('is-global-search');

  const tracks = library.tracks
    .filter((track) => matchesMusicSearch(query, track.title, track.artist, track.album, track.year, track.genre))
    .map((track) => ({
      type: 'track',
      id: track.id,
      label: 'Skladba',
      icon: 'music',
      title: track.title,
      details: musicSearchResultMeta('Skladba', [trackSummary(track)]),
      tooltip: trackTooltip(track)
    }));
  const playlists = library.playlists
    .filter((playlist) => matchesMusicSearch(query, playlist.title))
    .map((playlist) => ({
      type: 'playlist',
      id: playlist.id,
      label: 'Playlist',
      icon: 'playlist-plus',
      title: playlist.title,
      details: musicSearchResultMeta('Playlist', [`${playlist.trackIds.length} skladieb`]),
      tooltip: `Playlist: ${playlist.title}\nSkladieb: ${playlist.trackIds.length}`
    }));
  const stations = library.radioStations
    .filter((station) => searchMusicValues(query, [station.title], station.note))
    .map((station) => ({
      type: 'radio',
      id: station.id,
      label: 'Stanica',
      icon: 'radio',
      title: station.title,
      details: musicSearchResultMeta('Rádio', [radioStationSummary(station)]),
      tooltip: radioStationTooltip(station)
    }));
  const podcasts = library.podcasts
    .filter((podcast) => searchMusicValues(query, [podcast.title], podcast.description))
    .map((podcast) => ({
      type: 'podcast',
      id: podcast.id,
      label: 'Podcast',
      icon: 'podcast',
      title: podcast.title,
      details: musicSearchResultMeta('Podcast', [`${podcast.episodeCount} epizód`]),
      tooltip: [podcast.title, podcast.description, podcast.feedUrl].filter(Boolean).join('\n')
    }));
  const episodes = library.podcastEpisodes
    .filter((episode) => searchMusicValues(query, [episode.title, episode.feedTitle, episode.publishedAt], episode.description))
    .map((episode) => ({
      type: 'episode',
      id: episode.id,
      label: 'Epizóda',
      icon: 'podcast',
      title: episode.title,
      details: musicSearchResultMeta('Epizóda', [podcastEpisodeSummary(episode)]),
      tooltip: podcastEpisodeTooltip(episode)
    }));

  const results = document.createElement('div');
  results.className = 'music-global-search-results';
  addMusicSearchGroup(results, 'Skladby', [...playlists, ...tracks]);
  addMusicSearchGroup(results, 'Rádio', stations);
  addMusicSearchGroup(results, 'Podcasty', [...podcasts, ...episodes]);
  if (!results.childElementCount) {
    const message = document.createElement('p');
    message.className = 'music-empty';
    message.textContent = 'Nenašla sa žiadna skladba, stanica ani epizóda podcastu.';
    results.append(message);
  }
  dom.musicTracks.append(results);
}

function updateLibraryChrome() {
  const isRadio = mediaView === 'radio';
  const isPodcast = mediaView === 'podcasts';
  const isSearching = isGlobalMusicSearchActive();
  dom.musicModeTracks.classList.toggle('is-active', !isRadio && !isPodcast);
  dom.musicModeTracks.setAttribute('aria-selected', String(!isRadio && !isPodcast));
  dom.musicModeRadio.classList.toggle('is-active', isRadio);
  dom.musicModeRadio.setAttribute('aria-selected', String(isRadio));
  dom.musicModePodcasts.classList.toggle('is-active', isPodcast);
  dom.musicModePodcasts.setAttribute('aria-selected', String(isPodcast));
  dom.musicUpload.hidden = isRadio || isPodcast;
  dom.musicPlaylistCreate.hidden = isRadio || isPodcast;
  dom.musicRadioCreate.hidden = !isRadio;
  dom.musicPodcastCreate.hidden = !isPodcast;
  dom.musicPodcastRefresh.hidden = !isPodcast;
  dom.musicPodcastRefresh.disabled = !activePodcastId;
  dom.musicPlaylistStrip.hidden = isRadio || isSearching;
  dom.musicPlaylistStrip.setAttribute('aria-label', isPodcast ? 'Podcasty' : 'Playlisty');
  dom.musicSelectionBar.hidden = isRadio || isPodcast || isSearching || !selectedTrackIds.size;
  dom.musicSearch.placeholder = 'Hľadať skladby, rádiá a podcasty';
}

function render() {
  const isSearching = isGlobalMusicSearchActive();
  dom.musicTracks.classList.toggle('is-global-search', isSearching);
  updateLibraryChrome();
  if (isSearching) renderGlobalMusicSearch();
  else if (mediaView === 'radio') renderRadioStations();
  else if (mediaView === 'podcasts') {
    renderPodcastFeeds();
    renderPodcastEpisodes();
  }
  else {
    renderPlaylists();
    renderTargetPlaylists();
    renderTracks();
  }
  updateNowPlaying();
  updateTransport();
}

function applyLibrary(nextLibrary) {
  library = {
    tracks: Array.isArray(nextLibrary?.tracks) ? nextLibrary.tracks : [],
    playlists: Array.isArray(nextLibrary?.playlists) ? nextLibrary.playlists : [],
    radioStations: Array.isArray(nextLibrary?.radioStations) ? nextLibrary.radioStations : [],
    radioRecordings: Array.isArray(nextLibrary?.radioRecordings) ? nextLibrary.radioRecordings : [],
    radioRecordingSchedules: Array.isArray(nextLibrary?.radioRecordingSchedules) ? nextLibrary.radioRecordingSchedules : [],
    podcasts: Array.isArray(nextLibrary?.podcasts) ? nextLibrary.podcasts : [],
    podcastEpisodes: Array.isArray(nextLibrary?.podcastEpisodes) ? nextLibrary.podcastEpisodes : []
  };
  selectedTrackIds = new Set([...selectedTrackIds].filter((trackId) => trackById(trackId)));
  if (activePlaylistId && !playlistById(activePlaylistId)) activePlaylistId = '';
  if (activePodcastId && !podcastById(activePodcastId)) activePodcastId = '';
  if (currentTrackId && !trackById(currentTrackId)) {
    currentTrackId = '';
    resumePosition = 0;
    dom.musicAudio.pause();
    dom.musicAudio.removeAttribute('src');
    dom.musicAudio.load();
    clearPersistedPlaybackState();
  }
  if (currentRadioStationId && !radioStationById(currentRadioStationId)) {
    currentRadioStationId = '';
    dom.musicAudio.pause();
    dom.musicAudio.removeAttribute('src');
    dom.musicAudio.load();
  }
  if (currentRadioRecordingId && !radioRecordingById(currentRadioRecordingId)) {
    currentRadioRecordingId = '';
    dom.musicAudio.pause();
    dom.musicAudio.removeAttribute('src');
    dom.musicAudio.load();
  }
  if (currentPodcastEpisodeId && !podcastEpisodeById(currentPodcastEpisodeId)) {
    currentPodcastEpisodeId = '';
    resumePosition = 0;
    dom.musicAudio.pause();
    dom.musicAudio.removeAttribute('src');
    dom.musicAudio.load();
    localStorage.removeItem(storageKeys.musicPodcastEpisodeId);
    localStorage.removeItem(storageKeys.musicPodcastPosition);
  }
  syncRadioRecordingPolling();
  render();
}

function syncRadioRecordingPolling() {
  const shouldPoll = loaded && Boolean(activeRadioRecording() || activeRadioSchedules().length);
  if (shouldPoll && !recordingPollHandle) {
    recordingPollHandle = window.setInterval(() => void loadMusic(), 3_000);
  } else if (!shouldPoll && recordingPollHandle) {
    window.clearInterval(recordingPollHandle);
    recordingPollHandle = 0;
  }
}

async function loadMusic() {
  if (loading) return loading;
  loading = apiRequest('/music')
    .then((result) => {
      applyLibrary(result);
      loaded = true;
      syncRadioRecordingPolling();
      if (currentTrackId && !dom.musicAudio.src) loadCurrentTrack();
      else if (currentPodcastEpisodeId && !dom.musicAudio.src) loadCurrentPodcastEpisode();
    })
    .catch((error) => setStatus(error.message || 'Hudobnú knižnicu sa nepodarilo načítať.', { error: true }))
    .finally(() => {
      loading = null;
    });
  return loading;
}

function setPanelOpen(open) {
  if (open) panelMinimized = false;
  dom.musicDock.classList.toggle('is-open', open);
  dom.musicDock.setAttribute('aria-hidden', String(!open));
  dom.musicButton.setAttribute('aria-expanded', String(open));
  updateMusicPanelChrome();
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
  if (hasCurrentMedia()) void togglePlayback();
}

function hasOpenMusicOwnedDialog() {
  return Boolean(document.querySelector('dialog[data-music-owned-dialog][open]'));
}

function closeMusicOnOutsidePointerDown(event) {
  if (!isMusicPanelOpen() || panelPinned) return;
  if (dom.musicDock.contains(event.target)) {
    if (!dom.musicSleepControl.contains(event.target)) setSleepTimerPopoverOpen(false);
    if (!dom.musicPanelTransparencyControl.contains(event.target)) setMusicPanelTransparencyPopoverOpen(false);
    return;
  }
  if (dom.musicButton.contains(event.target) || hasOpenMusicOwnedDialog()) return;
  closeMusicPanel();
}

function minimizeMusicPanel() {
  if (!panelPinned) return;
  setSleepTimerPopoverOpen(false);
  setMusicPanelTransparencyPopoverOpen(false);
  panelMinimized = true;
  setPanelOpen(false);
}

function setMusicPanelPinned(pinned) {
  panelPinned = Boolean(pinned);
  if (!panelPinned) panelMinimized = false;
  updateMusicPanelChrome();
  updateTopbarVisibility();
}

function toggleMusicPanelPinned() {
  setMusicPanelPinned(!panelPinned);
}

function unpinMinimizedMusicPanel() {
  if (!panelPinned || !panelMinimized) return;
  setMusicPanelPinned(false);
  setPanelOpen(false);
}

export async function openMusicPanel({ trackId = '', playlistId = '', stationId = '', podcastId = '', podcastEpisodeId = '' } = {}) {
  setPanelOpen(true);
  if (!loaded) {
    setStatus('Načítavam hudobnú knižnicu...');
    await loadMusic();
    if (loaded) setStatus('');
  }
  if (stationId && radioStationById(stationId)) {
    setMediaView('radio');
    await selectRadioStation(stationId);
    return;
  }
  if (podcastId && podcastById(podcastId)) {
    setMediaView('podcasts');
    selectPodcast(podcastId);
    return;
  }
  if (podcastEpisodeId && podcastEpisodeById(podcastEpisodeId)) {
    setMediaView('podcasts');
    await selectPodcastEpisode(podcastEpisodeId);
    return;
  }
  if (playlistId && playlistById(playlistId)) selectPlaylist(playlistId);
  if (trackId && trackById(trackId)) await selectTrack(trackId);
}

export function closeMusicPanel({ unpin = false } = {}) {
  setSleepTimerPopoverOpen(false);
  setMusicPanelTransparencyPopoverOpen(false);
  if (panelPinned && !unpin) {
    minimizeMusicPanel();
    return;
  }
  if (unpin) setMusicPanelPinned(false);
  setPanelOpen(false);
}

export function stopMusicPlayback() {
  clearSleepTimer({ persist: true });
  dom.musicAudio.pause();
  dom.musicAudio.removeAttribute('src');
  dom.musicAudio.load();
  currentTrackId = '';
  currentRadioStationId = '';
  currentRadioRecordingId = '';
  currentPodcastEpisodeId = '';
  library = {
    tracks: [], playlists: [], radioStations: [], radioRecordings: [], radioRecordingSchedules: [], podcasts: [], podcastEpisodes: []
  };
  loaded = false;
  loading = null;
  syncRadioRecordingPolling();
  render();
  closeMusicPanel({ unpin: true });
}

export function isMusicPanelOpen() {
  return dom.musicDock.classList.contains('is-open');
}

function selectPlaylist(playlistId) {
  activePlaylistId = playlistId;
  targetPlaylistId = playlistId;
  selectedTrackIds.clear();
  localStorage.setItem(storageKeys.musicPlaylistId, activePlaylistId);
  render();
}

function setMediaView(view) {
  mediaView = ['tracks', 'radio', 'podcasts'].includes(view) ? view : 'tracks';
  localStorage.setItem(storageKeys.musicMediaView, mediaView);
  selectedTrackIds.clear();
  hidePlaylistForm();
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

async function addSelectedTracksToPlaylist() {
  const playlist = playlistById(targetPlaylistId);
  const trackIds = [...selectedTrackIds].filter((trackId) => trackById(trackId));
  if (!playlist || !trackIds.length) return;
  const newTrackIds = trackIds.filter((trackId) => !playlist.trackIds.includes(trackId));
  if (!newTrackIds.length) {
    setStatus('Označené skladby už v tomto playliste sú.');
    return;
  }
  try {
    let result = null;
    for (const trackId of newTrackIds) {
      result = await apiRequest(
        `/music/playlists/${encodeURIComponent(targetPlaylistId)}/tracks/${encodeURIComponent(trackId)}`,
        { method: 'PUT', body: {} }
      );
    }
    if (result) applyLibrary(result);
    selectedTrackIds.clear();
    renderTracks();
    setStatus(newTrackIds.length === 1 ? 'Skladba je zaradená v playliste.' : 'Skladby sú zaradené v playliste.');
  } catch (error) {
    setStatus(error.message || 'Skladby sa nepodarilo zaradiť do playlistu.', { error: true, persistent: true });
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
  currentRadioStationId = '';
  currentRadioRecordingId = '';
  currentPodcastEpisodeId = '';
  dom.musicAudio.src = `/api/music/tracks/${encodeURIComponent(track.id)}/audio`;
  dom.musicAudio.load();
  updateNowPlaying();
  updateTransport();
}

async function selectTrack(trackId, { autoplay = false } = {}) {
  const track = trackById(trackId);
  if (!track) return;
  if (currentTrackId !== trackId || currentRadioStationId || currentRadioRecordingId || currentPodcastEpisodeId) {
    dom.musicAudio.pause();
    currentTrackId = trackId;
    currentRadioStationId = '';
    currentRadioRecordingId = '';
    currentPodcastEpisodeId = '';
    resumePosition = 0;
    persistPlaybackState();
    loadCurrentTrack();
  }
  render();
  if (autoplay) await playCurrentTrack();
}

function loadCurrentRadioStation() {
  const station = radioStationById(currentRadioStationId);
  if (!station) return;
  isSeeking = false;
  currentTrackId = '';
  currentRadioRecordingId = '';
  currentPodcastEpisodeId = '';
  dom.musicAudio.src = `/api/music/stations/${encodeURIComponent(station.id)}/stream`;
  dom.musicAudio.load();
  updateNowPlaying();
  updateTransport();
}

async function selectRadioStation(stationId, { autoplay = false } = {}) {
  const station = radioStationById(stationId);
  if (!station) return;
  if (currentRadioStationId !== stationId || currentTrackId || currentRadioRecordingId || currentPodcastEpisodeId) {
    dom.musicAudio.pause();
    currentTrackId = '';
    currentRadioStationId = stationId;
    currentRadioRecordingId = '';
    currentPodcastEpisodeId = '';
    resumePosition = 0;
    loadCurrentRadioStation();
  }
  render();
  if (autoplay) await playCurrentRadioStation();
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

async function playCurrentRadioStation() {
  if (!currentRadioStationId) return;
  try {
    await dom.musicAudio.play();
    setStatus('');
  } catch {
    setStatus('Prehliadač alebo stanica nepovolili prehrávanie. Skontroluj adresu streamu.', { error: true });
  }
  updateTransport();
}

function loadCurrentRadioRecording() {
  const recording = radioRecordingById(currentRadioRecordingId);
  if (!recording || !['completed', 'stopped'].includes(recording.status)) return;
  isSeeking = false;
  currentTrackId = '';
  currentRadioStationId = '';
  currentPodcastEpisodeId = '';
  dom.musicAudio.src = `/api/music/recordings/${encodeURIComponent(recording.id)}/file`;
  dom.musicAudio.load();
  updateNowPlaying();
  updateTransport();
}

async function selectRadioRecording(recordingId, { autoplay = false } = {}) {
  const recording = radioRecordingById(recordingId);
  if (!recording || !['completed', 'stopped'].includes(recording.status)) return;
  if (currentRadioRecordingId !== recordingId || currentTrackId || currentRadioStationId || currentPodcastEpisodeId) {
    dom.musicAudio.pause();
    currentTrackId = '';
    currentRadioStationId = '';
    currentRadioRecordingId = recordingId;
    currentPodcastEpisodeId = '';
    resumePosition = 0;
    loadCurrentRadioRecording();
  }
  render();
  if (autoplay) await playCurrentRadioRecording();
}

async function playCurrentRadioRecording() {
  if (!currentRadioRecordingId) return;
  try {
    await dom.musicAudio.play();
    setStatus('');
  } catch {
    setStatus('Nahrávku sa nepodarilo prehrať. Skontroluj, či ešte existuje.', { error: true });
  }
  updateTransport();
}

function loadCurrentPodcastEpisode() {
  const episode = podcastEpisodeById(currentPodcastEpisodeId);
  if (!episode) return;
  isSeeking = false;
  currentTrackId = '';
  currentRadioStationId = '';
  currentRadioRecordingId = '';
  dom.musicAudio.src = episode.mediaUrl;
  dom.musicAudio.load();
  updateNowPlaying();
  updateTransport();
}

async function selectPodcastEpisode(episodeId, { autoplay = false } = {}) {
  const episode = podcastEpisodeById(episodeId);
  if (!episode) return;
  if (currentPodcastEpisodeId !== episodeId || currentTrackId || currentRadioStationId || currentRadioRecordingId) {
    dom.musicAudio.pause();
    currentTrackId = '';
    currentRadioStationId = '';
    currentRadioRecordingId = '';
    currentPodcastEpisodeId = episodeId;
    activePodcastId = episode.feedId;
    localStorage.setItem(storageKeys.musicPodcastId, activePodcastId);
    resumePosition = 0;
    persistPlaybackState();
    loadCurrentPodcastEpisode();
  }
  render();
  if (autoplay) await playCurrentPodcastEpisode();
}

async function playCurrentPodcastEpisode() {
  if (!currentPodcastEpisodeId) return;
  try {
    await dom.musicAudio.play();
    setStatus('');
  } catch {
    setStatus('Prehliadač alebo podcast zatiaľ nepovolil prehrávanie epizódy.', { error: true });
  }
  updateTransport();
}

async function togglePlayback() {
  if (mediaView === 'radio') {
    if (currentRadioStationId) {
      if (dom.musicAudio.paused) await playCurrentRadioStation();
      else dom.musicAudio.pause();
      return;
    }
    const first = filteredRadioStations()[0];
    if (first) await selectRadioStation(first.id, { autoplay: true });
    return;
  }
  if (mediaView === 'podcasts') {
    if (currentPodcastEpisodeId) {
      if (dom.musicAudio.paused) await playCurrentPodcastEpisode();
      else dom.musicAudio.pause();
      return;
    }
    const first = filteredPodcastEpisodes()[0];
    if (first) await selectPodcastEpisode(first.id, { autoplay: true });
    return;
  }
  if (currentRadioRecordingId) {
    if (dom.musicAudio.paused) await playCurrentRadioRecording();
    else dom.musicAudio.pause();
    return;
  }
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

async function toggleRadioStationPlayback(stationId) {
  if (stationId !== currentRadioStationId) {
    await selectRadioStation(stationId, { autoplay: true });
    return;
  }
  await togglePlayback();
}

async function toggleRadioRecordingPlayback(recordingId) {
  if (recordingId !== currentRadioRecordingId) {
    await selectRadioRecording(recordingId, { autoplay: true });
    return;
  }
  await togglePlayback();
}

async function togglePodcastEpisodePlayback(episodeId) {
  if (episodeId !== currentPodcastEpisodeId) {
    await selectPodcastEpisode(episodeId, { autoplay: true });
    return;
  }
  await togglePlayback();
}

async function toggleRadioRecording() {
  const active = activeRadioRecording();
  if (active) {
    if (active.status === 'stopping') return;
    try {
      const result = await apiRequest(`/music/recordings/${encodeURIComponent(active.id)}/stop`, {
        method: 'POST',
        body: {}
      });
      applyLibrary(result);
      setStatus('Nahrávanie sa ukončuje.');
    } catch (error) {
      setStatus(error.message || 'Nahrávanie sa nepodarilo zastaviť.', { error: true, persistent: true });
    }
    return;
  }
  if (!currentRadioStationId) return;
  try {
    const result = await apiRequest(`/music/stations/${encodeURIComponent(currentRadioStationId)}/recordings`, {
      method: 'POST',
      body: {}
    });
    applyLibrary(result);
    setStatus('Nahrávanie vysielania začalo.', { persistent: true });
  } catch (error) {
    setStatus(error.message || 'Nahrávanie sa nepodarilo spustiť.', { error: true, persistent: true });
  }
}

async function deleteRadioRecording(recording) {
  if (!recording || !window.confirm(`Natrvalo zmazať nahrávku stanice „${recording.stationTitle}“?`)) return;
  try {
    const result = await apiRequest(`/music/recordings/${encodeURIComponent(recording.id)}`, { method: 'DELETE' });
    if (currentRadioRecordingId === recording.id) {
      currentRadioRecordingId = '';
      dom.musicAudio.pause();
      dom.musicAudio.removeAttribute('src');
      dom.musicAudio.load();
    }
    applyLibrary(result);
    setStatus('Nahrávka je odstránená.');
  } catch (error) {
    setStatus(error.message || 'Nahrávku sa nepodarilo odstrániť.', { error: true });
  }
}

function openRadioScheduleDialog(stationId) {
  const station = radioStationById(stationId);
  if (!station) return;
  dialogRadioScheduleStationId = station.id;
  const minimum = new Date(Date.now() + 5 * 60_000);
  const local = new Date(minimum.getTime() - minimum.getTimezoneOffset() * 60_000).toISOString();
  dom.radioScheduleStation.textContent = station.title;
  dom.radioScheduleDate.value = local.slice(0, 10);
  dom.radioScheduleTime.value = local.slice(11, 16);
  dom.radioScheduleWeekdays.forEach((input) => { input.checked = false; });
  dom.radioScheduleDuration.max = String(Math.max(1, Number(dom.radioRecordingLimitMinutes.value) || 720));
  dom.radioScheduleDuration.value = String(Math.min(30, Number(dom.radioScheduleDuration.max)));
  dom.radioScheduleDialog.showModal();
  dom.radioScheduleDate.focus();
}

function closeRadioScheduleDialog() {
  dialogRadioScheduleStationId = '';
  if (dom.radioScheduleDialog.open) dom.radioScheduleDialog.close();
}

async function saveRadioScheduleDialog() {
  const stationId = dialogRadioScheduleStationId;
  if (!stationId) return;
  const date = dom.radioScheduleDate.value;
  const time = dom.radioScheduleTime.value;
  const durationMinutes = Number(dom.radioScheduleDuration.value);
  const recurrenceWeekdays = [...dom.radioScheduleWeekdays]
    .filter((input) => input.checked)
    .map((input) => Number(input.value));
  const starts = new Date(`${date}T${time}`);
  if (!date || !time || Number.isNaN(starts.valueOf())) {
    setStatus('Vyber platný dátum a čas nahrávania.', { error: true });
    return;
  }
  try {
    const result = await apiRequest(`/music/stations/${encodeURIComponent(stationId)}/recording-schedules`, {
      method: 'POST',
      body: {
        startAt: starts.toISOString(),
        startDate: date,
        localTime: time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
        recurrenceWeekdays,
        durationSeconds: Math.round(durationMinutes * 60)
      }
    });
    applyLibrary(result);
    closeRadioScheduleDialog();
    setStatus('Nahrávanie je naplánované.', { persistent: true });
  } catch (error) {
    setStatus(error.message || 'Nahrávanie sa nepodarilo naplánovať.', { error: true, persistent: true });
  }
}

async function cancelRadioSchedule(schedule) {
  if (!window.confirm(`Zrušiť nahrávanie stanice „${schedule.stationTitle}“?`)) return;
  try {
    const result = await apiRequest(`/music/recording-schedules/${encodeURIComponent(schedule.id)}/cancel`, {
      method: 'POST',
      body: {}
    });
    applyLibrary(result);
    setStatus('Termín nahrávania je zrušený.');
  } catch (error) {
    setStatus(error.message || 'Termín sa nepodarilo zrušiť.', { error: true });
  }
}

async function deleteRadioSchedule(schedule) {
  if (!window.confirm(`Odstrániť záznam termínu stanice „${schedule.stationTitle}“? Zvuková nahrávka zostane zachovaná.`)) return;
  try {
    const result = await apiRequest(`/music/recording-schedules/${encodeURIComponent(schedule.id)}`, { method: 'DELETE' });
    applyLibrary(result);
    setStatus('Záznam termínu je odstránený.');
  } catch (error) {
    setStatus(error.message || 'Záznam termínu sa nepodarilo odstrániť.', { error: true });
  }
}

async function pauseRadioSchedule(schedule) {
  try {
    const result = await apiRequest(`/music/recording-schedules/${encodeURIComponent(schedule.id)}/pause`, {
      method: 'POST',
      body: {}
    });
    applyLibrary(result);
    setStatus('Opakovaný plán je pozastavený.');
  } catch (error) {
    setStatus(error.message || 'Plán sa nepodarilo pozastaviť.', { error: true });
  }
}

async function resumeRadioSchedule(schedule) {
  try {
    const result = await apiRequest(`/music/recording-schedules/${encodeURIComponent(schedule.id)}/resume`, {
      method: 'POST',
      body: {}
    });
    applyLibrary(result);
    setStatus('Opakovaný plán je obnovený.');
  } catch (error) {
    setStatus(error.message || 'Plán sa nepodarilo obnoviť.', { error: true });
  }
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
  if (currentRadioStationId || currentRadioRecordingId) return;
  if (mediaView === 'podcasts') {
    const queue = filteredPodcastEpisodes();
    if (!queue.length) return;
    const currentIndex = queue.findIndex((episode) => episode.id === currentPodcastEpisodeId);
    let nextIndex = currentIndex + direction;
    if (shuffle && queue.length > 1) {
      do {
        nextIndex = Math.floor(Math.random() * queue.length);
      } while (nextIndex === currentIndex);
    } else if (nextIndex < 0 || nextIndex >= queue.length) {
      if (repeatMode !== 'all') return;
      nextIndex = direction > 0 ? 0 : queue.length - 1;
    }
    await selectPodcastEpisode(queue[nextIndex]?.id || queue[0].id, { autoplay });
    return;
  }
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
      clearPersistedPlaybackState();
    }
    applyLibrary(result);
    closeTrackDialog();
    setStatus('Skladba je odstránená.');
  } catch (error) {
    setStatus(error.message || 'Skladbu sa nepodarilo zmazať.', { error: true });
  }
}

function openRadioStationDialog(stationId = '') {
  const station = stationId ? radioStationById(stationId) : null;
  if (stationId && !station) return;
  dialogRadioStationId = station?.id || '';
  dom.radioStationDialogTitle.textContent = station ? 'Upraviť stanicu' : 'Pridať stanicu';
  dom.radioStationTitle.value = station?.title || '';
  dom.radioStationStreamUrl.value = station?.streamUrl || '';
  dom.radioStationWebsiteUrl.value = station?.websiteUrl || '';
  dom.radioStationNote.value = station?.note || '';
  dom.radioStationDelete.hidden = !station;
  dom.radioStationDialog.showModal();
  dom.radioStationTitle.focus();
}

function closeRadioStationDialog() {
  dialogRadioStationId = '';
  if (dom.radioStationDialog.open) dom.radioStationDialog.close();
}

async function saveRadioStationDialog() {
  const editing = Boolean(dialogRadioStationId);
  const body = {
    title: dom.radioStationTitle.value.trim(),
    streamUrl: dom.radioStationStreamUrl.value.trim(),
    websiteUrl: dom.radioStationWebsiteUrl.value.trim(),
    note: dom.radioStationNote.value.trim()
  };
  try {
    const result = editing
      ? await apiRequest(`/music/stations/${encodeURIComponent(dialogRadioStationId)}`, { method: 'PATCH', body })
      : await apiRequest('/music/stations', { method: 'POST', body: { id: crypto.randomUUID(), ...body } });
    applyLibrary(result);
    setMediaView('radio');
    closeRadioStationDialog();
    setStatus(editing ? 'Stanica je upravená.' : 'Stanica je uložená.');
  } catch (error) {
    setStatus(error.message || 'Stanicu sa nepodarilo uložiť.', { error: true, persistent: true });
  }
}

async function deleteRadioStation(station) {
  if (activeRadioRecording()?.stationId === station?.id) {
    setStatus('Najprv zastav nahrávanie tejto stanice.', { error: true });
    return;
  }
  if (!station || !window.confirm(`Zmazať stanicu „${station.title}“?`)) return;
  try {
    const result = await apiRequest(`/music/stations/${encodeURIComponent(station.id)}`, { method: 'DELETE' });
    if (currentRadioStationId === station.id) {
      currentRadioStationId = '';
      dom.musicAudio.pause();
      dom.musicAudio.removeAttribute('src');
      dom.musicAudio.load();
    }
    applyLibrary(result);
    closeRadioStationDialog();
    setStatus('Stanica je odstránená.');
  } catch (error) {
    setStatus(error.message || 'Stanicu sa nepodarilo odstrániť.', { error: true });
  }
}

async function deleteRadioStationDialog() {
  const station = radioStationById(dialogRadioStationId);
  await deleteRadioStation(station);
}

function openPodcastDialog() {
  dom.podcastForm.reset();
  dom.podcastDialog.showModal();
  dom.podcastFeedUrl.focus();
}

function closePodcastDialog() {
  if (dom.podcastDialog.open) dom.podcastDialog.close();
}

async function savePodcastDialog() {
  const feedUrl = dom.podcastFeedUrl.value.trim();
  if (!feedUrl) return;
  try {
    setStatus('Načítavam podcastový feed...', { persistent: true });
    const result = await apiRequest('/music/podcasts', { method: 'POST', body: { feedUrl } });
    applyLibrary(result);
    const podcast = library.podcasts.find((item) => item.feedUrl === feedUrl);
    setMediaView('podcasts');
    if (podcast) selectPodcast(podcast.id);
    closePodcastDialog();
    setStatus('Podcast je pridaný.');
  } catch (error) {
    setStatus(error.message || 'Podcast sa nepodarilo pridať.', { error: true, persistent: true });
  }
}

async function refreshPodcast(podcastId = activePodcastId) {
  const podcast = podcastById(podcastId);
  if (!podcast) return;
  try {
    setStatus(`Obnovujem podcast „${podcast.title}“...`, { persistent: true });
    const result = await apiRequest(`/music/podcasts/${encodeURIComponent(podcast.id)}/refresh`, { method: 'POST', body: {} });
    applyLibrary(result);
    setStatus('Podcast je obnovený.');
  } catch (error) {
    setStatus(error.message || 'Podcast sa nepodarilo obnoviť.', { error: true, persistent: true });
  }
}

async function deletePodcast(podcast) {
  if (!podcast || !window.confirm(`Odstrániť podcast „${podcast.title}“ aj jeho načítané epizódy?`)) return;
  try {
    const result = await apiRequest(`/music/podcasts/${encodeURIComponent(podcast.id)}`, { method: 'DELETE' });
    if (currentPodcastEpisodeId && podcastEpisodeById(currentPodcastEpisodeId)?.feedId === podcast.id) {
      currentPodcastEpisodeId = '';
      dom.musicAudio.pause();
      dom.musicAudio.removeAttribute('src');
      dom.musicAudio.load();
      localStorage.removeItem(storageKeys.musicPodcastEpisodeId);
      localStorage.removeItem(storageKeys.musicPodcastPosition);
    }
    if (activePodcastId === podcast.id) activePodcastId = '';
    applyLibrary(result);
    setStatus('Podcast je odstránený.');
  } catch (error) {
    setStatus(error.message || 'Podcast sa nepodarilo odstrániť.', { error: true });
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
  if (currentRadioStationId) {
    updateTransport();
    return;
  }
  const track = trackById(currentTrackId);
  const episode = podcastEpisodeById(currentPodcastEpisodeId);
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
  if (episode && duration > 0 && !episode.durationSeconds) updateTransport();
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
  activePodcastId = localStorage.getItem(storageKeys.musicPodcastId) || '';
  searchDescriptionsEnabled = localStorage.getItem(storageKeys.musicSearchDescriptions) === 'true';
  syncMusicSearchDescriptionsToggle();
  const storedView = localStorage.getItem(storageKeys.musicMediaView);
  mediaView = ['tracks', 'radio', 'podcasts'].includes(storedView) ? storedView : 'tracks';
  if (mediaView === 'podcasts') {
    currentPodcastEpisodeId = localStorage.getItem(storageKeys.musicPodcastEpisodeId) || '';
    resumePosition = Math.max(0, Number(localStorage.getItem(storageKeys.musicPodcastPosition)) || 0);
  }
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

function formatSleepCountdown(milliseconds) {
  const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1_000));
  const hours = Math.floor(totalSeconds / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function isSleepTimerActive() {
  return sleepTimerEndsAt > Date.now();
}

function setSleepTimerPopoverOpen(open) {
  const shouldOpen = Boolean(open);
  dom.musicSleepPopover.hidden = !shouldOpen;
  dom.musicSleepToggle.setAttribute('aria-expanded', String(shouldOpen));
  dom.musicSleepControl.classList.toggle('is-open', shouldOpen);
}

function setMusicPanelTransparencyPopoverOpen(open) {
  const shouldOpen = Boolean(open);
  dom.musicPanelTransparencyPopover.hidden = !shouldOpen;
  dom.musicPanelTransparencyToggle.setAttribute('aria-expanded', String(shouldOpen));
  dom.musicPanelTransparencyToggle.classList.toggle('is-active', shouldOpen);
}

function syncSleepTimerControl() {
  const active = isSleepTimerActive();
  const remaining = active ? sleepTimerEndsAt - Date.now() : 0;
  const label = active ? formatSleepCountdown(remaining) : 'Vypnutie';
  dom.musicSleepLabel.textContent = label;
  dom.musicSleepToggle.classList.toggle('is-active', active);
  dom.musicSleepToggle.title = active ? `Prehrávanie sa zastaví za ${label}` : 'Časovač vypnutia prehrávania';
  dom.musicSleepToggle.setAttribute('aria-label', dom.musicSleepToggle.title);
  dom.musicSleepPresetButtons.forEach((button) => {
    const selected = active && Number(button.dataset.musicSleepMinutes) === sleepTimerMinutes;
    button.classList.toggle('is-active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  dom.musicSleepCancel.disabled = !active;
}

function clearSleepTimer({ persist = true } = {}) {
  if (sleepTimerHandle) window.clearTimeout(sleepTimerHandle);
  if (sleepTimerTicker) window.clearInterval(sleepTimerTicker);
  sleepTimerHandle = 0;
  sleepTimerTicker = 0;
  sleepTimerEndsAt = 0;
  sleepTimerMinutes = 0;
  if (persist) {
    localStorage.removeItem(storageKeys.musicSleepTimerEndsAt);
    localStorage.removeItem(storageKeys.musicSleepTimerMinutes);
  }
  syncSleepTimerControl();
}

function completeSleepTimer() {
  clearSleepTimer({ persist: true });
  dom.musicAudio.pause();
  setStatus('Časovač vypol prehrávanie.');
}

function scheduleSleepTimer() {
  if (sleepTimerHandle) window.clearTimeout(sleepTimerHandle);
  if (sleepTimerTicker) window.clearInterval(sleepTimerTicker);
  const delay = sleepTimerEndsAt - Date.now();
  if (delay <= 0) {
    completeSleepTimer();
    return;
  }
  sleepTimerHandle = window.setTimeout(() => {
    sleepTimerHandle = 0;
    completeSleepTimer();
  }, delay);
  sleepTimerTicker = window.setInterval(() => {
    if (!isSleepTimerActive()) {
      completeSleepTimer();
      return;
    }
    syncSleepTimerControl();
  }, 1_000);
  syncSleepTimerControl();
}

function setSleepTimer(minutes) {
  const safeMinutes = clamp(Math.round(Number(minutes) || 0), 0, 480);
  if (!safeMinutes) {
    clearSleepTimer({ persist: true });
    setSleepTimerPopoverOpen(false);
    setStatus('Časovač vypnutia je zrušený.');
    return;
  }
  sleepTimerMinutes = safeMinutes;
  sleepTimerEndsAt = Date.now() + safeMinutes * 60_000;
  localStorage.setItem(storageKeys.musicSleepTimerMinutes, String(safeMinutes));
  localStorage.setItem(storageKeys.musicSleepTimerEndsAt, String(sleepTimerEndsAt));
  scheduleSleepTimer();
  setSleepTimerPopoverOpen(false);
  setStatus(`Prehrávanie sa zastaví za ${safeMinutes} min.`);
}

function handleSleepCustomSubmit(event) {
  event.preventDefault();
  const requested = Number(dom.musicSleepCustomMinutes.value);
  if (!Number.isFinite(requested) || requested < 1) {
    setStatus('Zadaj čas od 1 do 480 minút.', { error: true, persistent: true });
    dom.musicSleepCustomMinutes.focus();
    return;
  }
  const minutes = clamp(Math.round(requested), 1, 480);
  dom.musicSleepCustomMinutes.value = String(minutes);
  setSleepTimer(minutes);
}

function handleMusicSearchInput() {
  dom.musicSearchClear.hidden = !dom.musicSearch.value;
  render();
}

function setMusicSearchOpen(open, { focus = false } = {}) {
  const shouldOpen = Boolean(open);
  const label = shouldOpen ? 'Zrušiť vyhľadávanie' : 'Hľadať v prehrávači';
  dom.musicSearchRow.classList.toggle('is-open', shouldOpen);
  dom.musicSearchToggle.classList.toggle('is-active', shouldOpen);
  dom.musicSearchToggle.setAttribute('aria-expanded', String(shouldOpen));
  dom.musicSearchToggle.setAttribute('aria-label', label);
  dom.musicSearchToggle.title = label;
  setAppIcon(dom.musicSearchToggle.querySelector('.app-icon'), shouldOpen ? 'close' : 'search');
  if (focus && shouldOpen) requestAnimationFrame(() => dom.musicSearch.focus());
}

export function initializeMusic() {
  restorePlayerSettings();
  setMusicSearchOpen(false);
  updateMusicPanelChrome();
  dom.musicButton.addEventListener('click', handleMusicButtonClick);
  dom.musicButton.addEventListener('dblclick', handleMusicButtonDoubleClick);
  document.addEventListener('pointerdown', closeMusicOnOutsidePointerDown);
  dom.musicMiniPlayerOpen.addEventListener('click', () => void openMusicPanel());
  dom.musicMiniPlayerUnpin.addEventListener('click', unpinMinimizedMusicPanel);
  dom.musicPanelPin.addEventListener('click', toggleMusicPanelPinned);
  dom.musicPanelMinimize.addEventListener('click', minimizeMusicPanel);
  dom.musicClose.addEventListener('click', () => closeMusicPanel({ unpin: true }));
  dom.musicPanelTransparencyToggle.addEventListener('click', () => {
    setMusicPanelTransparencyPopoverOpen(dom.musicPanelTransparencyPopover.hidden);
  });
  dom.musicPanelTransparencyControl.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || dom.musicPanelTransparencyPopover.hidden) return;
    event.stopPropagation();
    setMusicPanelTransparencyPopoverOpen(false);
    dom.musicPanelTransparencyToggle.focus();
  });
  dom.musicModeTracks.addEventListener('click', () => setMediaView('tracks'));
  dom.musicModeRadio.addEventListener('click', () => setMediaView('radio'));
  dom.musicModePodcasts.addEventListener('click', () => setMediaView('podcasts'));
  dom.musicUpload.addEventListener('click', () => dom.musicFileInput.click());
  dom.musicFileInput.addEventListener('change', () => void uploadTracks(dom.musicFileInput.files || []));
  dom.musicPlaylistCreate.addEventListener('click', () => showPlaylistForm());
  dom.musicRadioCreate.addEventListener('click', () => openRadioStationDialog());
  dom.musicPodcastCreate.addEventListener('click', openPodcastDialog);
  dom.musicPodcastRefresh.addEventListener('click', () => void refreshPodcast());
  dom.musicPlaylistCancel.addEventListener('click', hidePlaylistForm);
  dom.musicPlaylistForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void savePlaylist();
  });
  dom.musicSearchToggle.addEventListener('click', () => {
    const isOpen = dom.musicSearchRow.classList.contains('is-open');
    if (isOpen) {
      cancelMusicSearch({ focusToggle: true });
      return;
    }
    setMusicSearchOpen(true, { focus: true });
  });
  dom.musicSearch.addEventListener('input', handleMusicSearchInput);
  dom.musicSearchDescriptions.addEventListener('click', () => {
    searchDescriptionsEnabled = !searchDescriptionsEnabled;
    localStorage.setItem(storageKeys.musicSearchDescriptions, String(searchDescriptionsEnabled));
    syncMusicSearchDescriptionsToggle();
    render();
  });
  dom.musicSearch.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    cancelMusicSearch({ focusToggle: true });
  });
  dom.musicSearchClear.addEventListener('click', () => {
    dom.musicSearch.value = '';
    setMusicSearchOpen(true, { focus: true });
    handleMusicSearchInput();
  });
  dom.musicTargetPlaylist.addEventListener('change', () => {
    targetPlaylistId = dom.musicTargetPlaylist.value;
    updateSelectionControls();
  });
  dom.musicAddSelected.addEventListener('click', () => void addSelectedTracksToPlaylist());
  dom.musicSelectionClear.addEventListener('click', clearTrackSelection);
  dom.musicAllTracks.addEventListener('click', () => {
    if (mediaView === 'podcasts') selectPodcast('');
    else selectPlaylist('');
  });
  dom.musicPrevious.addEventListener('click', () => void selectAdjacent(-1));
  dom.musicPlay.addEventListener('click', () => void togglePlayback());
  dom.musicNext.addEventListener('click', () => void selectAdjacent(1));
  dom.musicShuffle.addEventListener('click', toggleShuffle);
  dom.musicRepeat.addEventListener('click', cycleRepeat);
  dom.musicRecord.addEventListener('click', () => void toggleRadioRecording());
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
  dom.musicSleepToggle.addEventListener('click', () => setSleepTimerPopoverOpen(dom.musicSleepPopover.hidden));
  dom.musicSleepPresetButtons.forEach((button) => {
    button.addEventListener('click', () => setSleepTimer(button.dataset.musicSleepMinutes));
  });
  dom.musicSleepCustomForm.addEventListener('submit', handleSleepCustomSubmit);
  dom.musicSleepCancel.addEventListener('click', () => setSleepTimer(0));
  dom.musicSleepControl.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || dom.musicSleepPopover.hidden) return;
    event.stopPropagation();
    setSleepTimerPopoverOpen(false);
    dom.musicSleepToggle.focus();
  });
  dom.musicAudio.addEventListener('loadedmetadata', handleLoadedMetadata);
  dom.musicAudio.addEventListener('timeupdate', () => {
    updateTransport();
    if ((currentTrackId || currentPodcastEpisodeId) && Date.now() - lastPositionSave >= POSITION_SAVE_INTERVAL) {
      lastPositionSave = Date.now();
      persistPlaybackState();
    }
  });
  dom.musicAudio.addEventListener('play', () => {
    updateTransport();
    render();
  });
  dom.musicAudio.addEventListener('pause', () => {
    persistPlaybackState();
    updateTransport();
    render();
  });
  dom.musicAudio.addEventListener('ended', () => {
    if (currentRadioStationId) {
      setStatus('Vysielanie stanice sa skončilo.');
      return;
    }
    if (currentRadioRecordingId) {
      updateTransport();
      return;
    }
    if (repeatMode === 'one') {
      dom.musicAudio.currentTime = 0;
      if (currentPodcastEpisodeId) void playCurrentPodcastEpisode();
      else void playCurrentTrack();
      return;
    }
    void selectAdjacent(1);
  });
  dom.musicAudio.addEventListener('error', () => {
    if (currentRadioStationId) {
      setStatus('Stanica sa nedá prehrať. Skontroluj priamu adresu streamu.', { error: true, persistent: true });
      return;
    }
    if (currentRadioRecordingId) {
      setStatus('Nahrávku sa nepodarilo prehrať. Možno už bola odstránená.', { error: true });
      return;
    }
    if (currentPodcastEpisodeId) {
      setStatus('Epizódu sa nepodarilo prehrať. Skontroluj, či je jej adresa stále dostupná.', { error: true });
      return;
    }
    if (currentTrackId) setStatus('Skladbu sa nepodarilo prehrať. Skontroluj, či súbor stále existuje.', { error: true });
  });
  dom.musicTrackCancel.addEventListener('click', closeTrackDialog);
  dom.musicTrackForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveTrackDialog();
  });
  dom.musicTrackDelete.addEventListener('click', () => void deleteTrackDialog());
  installDialogBackdropClose(dom.musicTrackDialog, closeTrackDialog);
  dom.radioStationCancel.addEventListener('click', closeRadioStationDialog);
  dom.radioStationForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveRadioStationDialog();
  });
  dom.radioStationDelete.addEventListener('click', () => void deleteRadioStationDialog());
  installDialogBackdropClose(dom.radioStationDialog, closeRadioStationDialog);
  dom.radioScheduleCancel.addEventListener('click', closeRadioScheduleDialog);
  dom.radioScheduleForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveRadioScheduleDialog();
  });
  installDialogBackdropClose(dom.radioScheduleDialog, closeRadioScheduleDialog);
  dom.podcastCancel.addEventListener('click', closePodcastDialog);
  dom.podcastForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void savePodcastDialog();
  });
  installDialogBackdropClose(dom.podcastDialog, closePodcastDialog);
}
