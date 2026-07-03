const STORAGE_KEY = 'simple-notes';
const form = document.getElementById('note-form');
const titleInput = document.getElementById('note-title');
const contentInput = document.getElementById('note-content');
const notesList = document.getElementById('notes-list');

let notes = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

function saveNotes() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
}

function renderNotes() {
  if (!notes.length) {
    notesList.innerHTML = '<p>Zatiaľ žiadne poznámky. Pridajte prvú.</p>';
    return;
  }

  notesList.innerHTML = notes
    .slice()
    .reverse()
    .map((note) => `
      <article class="note-card">
        <header>
          <h3>${note.title}</h3>
          <button class="delete-btn" data-id="${note.id}">Zmazať</button>
        </header>
        <div class="note-meta">${new Date(note.createdAt).toLocaleString('sk-SK')}</div>
        <p>${note.content}</p>
      </article>
    `)
    .join('');
}

form.addEventListener('submit', (event) => {
  event.preventDefault();

  const title = titleInput.value.trim();
  const content = contentInput.value.trim();

  if (!title || !content) return;

  notes.push({
    id: crypto.randomUUID(),
    title,
    content,
    createdAt: new Date().toISOString()
  });

  saveNotes();
  renderNotes();
  form.reset();
  titleInput.focus();
});

notesList.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-id]');
  if (!button) return;

  const id = button.getAttribute('data-id');
  notes = notes.filter((note) => note.id !== id);
  saveNotes();
  renderNotes();
});

renderNotes();
