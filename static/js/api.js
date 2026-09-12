export async function fetchWithTimeout(url, options = {}, timeout = 5000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    const response = await fetch(url, {
        ...options,
        signal: controller.signal
    });
    clearTimeout(id);
    return response;
}

export async function refreshData() {
    return await fetch('/api/refresh', { method: 'POST' });
}

export async function getNotes() {
    return await fetch('/api/notes');
}

export async function addNote(date, text) {
    return await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, text })
    });
}

export async function deleteNoteApi(index) {
    return await fetch(`/api/notes/${index}`, {
        method: 'DELETE'
    });
}

export async function searchFundsApi(query) {
    return await fetch(`/api/funds/search?q=${encodeURIComponent(query)}`);
}

export async function addFundToPortfolio(code, name) {
    return await fetch('/api/funds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, name })
    });
}

export async function addFundToResearch(code, name) {
    return await fetch('/api/research-funds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, name })
    });
}

export async function removePortfolioFundApi(code) {
    return await fetch(`/api/funds/${code}`, {
        method: 'DELETE'
    });
}

export async function getResearchFundsApi() {
    return await fetch('/api/research-funds');
}

export async function removeResearchFundApi(code) {
    return await fetch(`/api/research-funds/${code}`, {
        method: 'DELETE'
    });
}
