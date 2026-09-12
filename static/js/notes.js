import { getNotes, addNote, deleteNoteApi } from './api.js';

let notes = [];

export async function renderNotes() {
    const notesList = document.getElementById('notesList');
    if (!notesList) return;

    try {
        const response = await getNotes();
        if (response.ok) {
            notes = await response.json();
            notesList.innerHTML = '';
            notes.forEach((note, index) => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                <div>
                    <strong></strong>
                    <p class="mb-0"></p>
                </div>
                <button class="btn btn-danger btn-sm delete-note-btn" data-index="${index}">Delete</button>
            `;
                li.querySelector('strong').textContent = note.date;
                li.querySelector('p').textContent = note.text;
                notesList.appendChild(li);
            });

            // Add event listeners for delete buttons
            notesList.querySelectorAll('.delete-note-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const idx = e.target.dataset.index;
                    if (confirm('Are you sure you want to delete this note?')) {
                        try {
                            const delResponse = await deleteNoteApi(idx);
                            if (delResponse.ok) {
                                renderNotes();
                            }
                        } catch (error) {
                            console.error('Error deleting note:', error);
                        }
                    }
                });
            });
        }
    } catch (error) {
        console.error('Error fetching notes:', error);
    }
}

export function initNotes() {
    const noteForm = document.getElementById('noteForm');
    const noteDate = document.getElementById('noteDate');

    if (noteDate) {
        noteDate.valueAsDate = new Date();
    }

    if (noteForm) {
        noteForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const date = document.getElementById('noteDate').value;
            const text = document.getElementById('noteText').value;

            try {
                const response = await addNote(date, text);
                if (response.ok) {
                    renderNotes();
                    noteForm.reset();
                    document.getElementById('noteDate').valueAsDate = new Date();
                }
            } catch (error) {
                console.error('Error saving note:', error);
            }
        });
    }

    renderNotes();
}
