            // Performance optimizations
            const debounce = (func, wait) => {
                let timeout;
                return function executedFunction(...args) {
                    const later = () => {
                        clearTimeout(timeout);
                        func(...args);
                    };
                    clearTimeout(timeout);
                    timeout = setTimeout(later, wait);
                };
            };

            // Cache DOM elements
            const table = document.getElementById('fundTable');
            const headers = table.querySelectorAll('th.sortable');
            const refreshBtn = document.getElementById('refreshBtn');
            const noteForm = document.getElementById('noteForm');
            const notesList = document.getElementById('notesList');

            let lastSortedColumn = null;
            let notes = [];

            function parseSortableValue(cell) {
                const raw = cell?.getAttribute('data-value') ?? cell?.textContent?.trim() ?? '';
                if (raw === '' || raw === 'N/A' || raw === 'Data not available') {
                    return { missing: true, value: 0 };
                }
                const numericValue = parseFloat(raw);
                if (!Number.isNaN(numericValue)) {
                    return { missing: false, value: numericValue };
                }
                return { missing: false, value: raw.toString().toLowerCase() };
            }

            function compareSortableValues(aCell, bCell, ascending) {
                const a = parseSortableValue(aCell);
                const b = parseSortableValue(bCell);

                if (a.missing && b.missing) return 0;
                if (a.missing) return 1;
                if (b.missing) return -1;

                if (typeof a.value === 'number' && typeof b.value === 'number') {
                    return ascending ? b.value - a.value : a.value - b.value;
                }

                return ascending
                    ? b.value.toString().localeCompare(a.value.toString())
                    : a.value.toString().localeCompare(b.value.toString());
            }

            function showStatus(message, type = 'info') {
                const status = document.getElementById('fundActionStatus');
                if (status) {
                    status.textContent = message;
                    status.className = `action-status is-${type}`;
                }
            }

            function showToast(message, type = 'info') {
                let container = document.getElementById('toastContainer');
                if (!container) {
                    container = document.createElement('div');
                    container.id = 'toastContainer';
                    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                    document.body.appendChild(container);
                }

                const toastEl = document.createElement('div');
                toastEl.className = `toast align-items-center border-0 text-bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'primary'}`;
                toastEl.setAttribute('role', 'status');
                toastEl.setAttribute('aria-live', 'polite');
                toastEl.setAttribute('aria-atomic', 'true');
                toastEl.innerHTML = `
                    <div class="d-flex">
                        <div class="toast-body"></div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                `;
                toastEl.querySelector('.toast-body').textContent = message;
                container.appendChild(toastEl);

                const toast = new bootstrap.Toast(toastEl, { delay: 3500 });
                toast.show();
                toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
            }

            // Optimized sort function (handles accordion rows)
            const sortTable = debounce(function (header) {
                const column = header.cellIndex;
                const tbody = table.querySelector('tbody');
                const allRows = Array.from(tbody.querySelectorAll('tr'));
                const isAscending = header.classList.contains('asc');

                // Filter only main rows (not accordion collapse rows)
                const mainRows = allRows.filter(row => row.classList.contains('fund-row'));

                // Reset all headers
                headers.forEach(h => {
                    h.classList.remove('asc', 'desc');
                    h.querySelector('i').className = 'bi bi-arrow-down-up';
                });

                // Update current header
                header.classList.toggle('asc', !isAscending);
                header.classList.toggle('desc', isAscending);
                header.querySelector('i').className = isAscending ? 'bi bi-arrow-down' : 'bi bi-arrow-up';

                // Sort main rows with their associated accordion rows
                const sortedPairs = mainRows.map(mainRow => {
                    const nextRow = mainRow.nextElementSibling;
                    const accordionRow = (nextRow && nextRow.classList.contains('accordion-collapse')) ? nextRow : null;

                    return {
                        mainRow: mainRow,
                        accordionRow: accordionRow,
                        valueCell: mainRow.cells[column]
                    };
                })
                    .sort((a, b) => compareSortableValues(a.valueCell, b.valueCell, isAscending));

                // Use DocumentFragment for better performance
                const fragment = document.createDocumentFragment();
                sortedPairs.forEach(pair => {
                    fragment.appendChild(pair.mainRow);
                    if (pair.accordionRow) {
                        fragment.appendChild(pair.accordionRow);
                    }
                });
                tbody.appendChild(fragment);

                lastSortedColumn = header;
            }, 200);

            // Add click handlers
            headers.forEach(header => {
                header.addEventListener('click', () => sortTable(header));
            });

            // Refresh functionality
            refreshBtn.addEventListener('click', async () => {
                const originalHtml = refreshBtn.innerHTML;
                try {
                    refreshBtn.classList.add('loading');
                    refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span><span class="refresh-label">Refreshing</span>';
                    const response = await fetch('/api/refresh', { method: 'POST' });
                    if (response.ok) {
                        // Reload the page to show fresh data
                        window.location.reload();
                    } else {
                        console.error('Failed to refresh data');
                        showToast('Refresh failed. Please try again.', 'error');
                    }
                } catch (error) {
                    console.error('Error refreshing data:', error);
                    showToast('Refresh failed. Please check your connection.', 'error');
                } finally {
                    refreshBtn.classList.remove('loading');
                    refreshBtn.innerHTML = originalHtml;
                }
            });

            // Notes functionality
            async function renderNotes() {
                try {
                    const response = await fetch('/api/notes');
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
                            <button class="btn btn-danger btn-sm" onclick="deleteNote(${index})">Delete</button>
                        `;
                            li.querySelector('strong').textContent = note.date;
                            li.querySelector('p').textContent = note.text;
                            notesList.appendChild(li);
                        });
                    }
                } catch (error) {
                    console.error('Error fetching notes:', error);
                }
            }

            window.deleteNote = async function (index) {
                if (confirm('Are you sure you want to delete this note?')) {
                    try {
                        const response = await fetch(`/api/notes/${index}`, {
                            method: 'DELETE'
                        });
                        if (response.ok) {
                            renderNotes();
                        }
                    } catch (error) {
                        console.error('Error deleting note:', error);
                    }
                }
            };

            noteForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                const date = document.getElementById('noteDate').value;
                const text = document.getElementById('noteText').value;

                try {
                    const response = await fetch('/api/notes', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ date, text })
                    });

                    if (response.ok) {
                        renderNotes();
                        noteForm.reset();
                        // Reset date to today
                        document.getElementById('noteDate').valueAsDate = new Date();
                    }
                } catch (error) {
                    console.error('Error saving note:', error);
                }
            });

            // Initialize notes
            renderNotes();
            document.getElementById('noteDate').valueAsDate = new Date();

            // View mode switching
            const comparisonViewContainer = document.getElementById('comparisonViewContainer');
            const expandCollapseButtons = document.getElementById('expandCollapseButtons');
            const tableViewRadio = document.getElementById('tableView');
            const comparisonViewRadio = document.getElementById('comparisonView');
            const tableViewContainer = document.getElementById('tableViewContainer');

            tableViewRadio.addEventListener('change', function () {
                if (this.checked) {
                    tableViewContainer.style.display = 'block';
                    comparisonViewContainer.style.display = 'none';
                    expandCollapseButtons.style.display = 'block';
                }
            });

            comparisonViewRadio.addEventListener('change', function () {
                if (this.checked) {
                    tableViewContainer.style.display = 'none';
                    comparisonViewContainer.style.display = 'block';
                    expandCollapseButtons.style.display = 'none';
                }
            });

            // Expand All functionality
            document.getElementById('expandAllBtn').addEventListener('click', function () {
                const collapseElements = document.querySelectorAll('.accordion-collapse');
                collapseElements.forEach(element => {
                    const bsCollapse = new bootstrap.Collapse(element, { toggle: false });
                    bsCollapse.show();
                });

                // Update all accordion icons
                const accordionRows = document.querySelectorAll('.accordion-button');
                accordionRows.forEach(row => {
                    row.setAttribute('aria-expanded', 'true');
                });
            });

            // Collapse All functionality
            document.getElementById('collapseAllBtn').addEventListener('click', function () {
                const collapseElements = document.querySelectorAll('.accordion-collapse');
                collapseElements.forEach(element => {
                    const bsCollapse = new bootstrap.Collapse(element, { toggle: false });
                    bsCollapse.hide();
                });

                // Update all accordion icons
                const accordionRows = document.querySelectorAll('.accordion-button');
                accordionRows.forEach(row => {
                    row.setAttribute('aria-expanded', 'false');
                });
            });

            // Generic table sorting function
            function setupTableSorting(tableId) {
                const table = document.getElementById(tableId);
                if (!table) return;

                const headers = table.querySelectorAll('.sortable-header');

                headers.forEach(header => {
                    header.addEventListener('click', function () {
                        const column = parseInt(this.getAttribute('data-column'));
                        const tbody = table.querySelector('tbody');
                        const rows = Array.from(tbody.querySelectorAll('tr'));
                        const isAscending = this.classList.contains('asc');

                        // Reset all headers
                        headers.forEach(h => {
                            h.classList.remove('asc', 'desc');
                            const icon = h.querySelector('i');
                            if (icon) icon.className = 'bi bi-arrow-down-up';
                        });

                        // Update current header
                        this.classList.toggle('asc', !isAscending);
                        this.classList.toggle('desc', isAscending);
                        const icon = this.querySelector('i');
                        if (icon) {
                            icon.className = isAscending ? 'bi bi-arrow-down' : 'bi bi-arrow-up';
                        }

                        // Sort rows
                        const sortedRows = rows.sort((a, b) => {
                            const aCell = a.cells[column];
                            const bCell = b.cells[column];

                            if (!aCell || !bCell) return 0;

                            // Use data-value attribute if available, otherwise use text content
                            return compareSortableValues(aCell, bCell, isAscending);
                        });

                        // Re-append sorted rows
                        const fragment = document.createDocumentFragment();
                        sortedRows.forEach(row => fragment.appendChild(row));
                        tbody.appendChild(fragment);
                    });
                });
            }

            // Setup sorting for all comparison tables
            setupTableSorting('shortTermTable');
            setupTableSorting('yearlyTable');
            setupTableSorting('summaryTable');

            // Dynamic year filtering and recalculation
            function recalculateReturns() {
                const selectedYears = Array.from(document.querySelectorAll('.year-filter:checked')).map(cb => parseInt(cb.value));

                if (selectedYears.length === 0) {
                    showToast('Select at least one year to recalculate returns.', 'error');
                    return;
                }

                // Recalculate for each fund row
                const summaryTable = document.getElementById('summaryTable');
                if (!summaryTable) return;

                const rows = summaryTable.querySelectorAll('tbody tr');

                rows.forEach(row => {
                    // Get all cells with year data
                    const abs2yCell = row.querySelector('.total-abs-2y');
                    const cagr2yCell = row.querySelector('.cagr-2y');
                    const abs3yCell = row.querySelector('.total-abs-3y');
                    const cagr3yCell = row.querySelector('.cagr-3y');
                    const abs5yCell = row.querySelector('.total-abs-5y');
                    const cagr5yCell = row.querySelector('.cagr-5y');

                    if (!abs5yCell) return;

                    // Get individual year returns
                    const yearReturns = {
                        1: parseFloat(abs5yCell.getAttribute('data-y1')) || 0,
                        2: parseFloat(abs5yCell.getAttribute('data-y2')) || 0,
                        3: parseFloat(abs5yCell.getAttribute('data-y3')) || 0,
                        4: parseFloat(abs5yCell.getAttribute('data-y4')) || 0,
                        5: parseFloat(abs5yCell.getAttribute('data-y5')) || 0
                    };

                    // Calculate based on selected years
                    let totalMultiplier = 1;
                    selectedYears.forEach(year => {
                        totalMultiplier *= (1 + yearReturns[year] / 100);
                    });

                    const totalAbsolute = (totalMultiplier - 1) * 100;
                    const numYears = selectedYears.length;
                    const cagr = numYears > 0 ? (Math.pow(totalMultiplier, 1 / numYears) - 1) * 100 : 0;

                    // Update 5-year cells
                    updateCell(abs5yCell, totalAbsolute);
                    updateCell(cagr5yCell, cagr);

                    // Calculate for 3-year period (Years 3, 4, 5)
                    const years3 = selectedYears.filter(y => y >= 3);
                    if (years3.length > 0) {
                        let mult3 = 1;
                        years3.forEach(y => mult3 *= (1 + yearReturns[y] / 100));
                        const abs3 = (mult3 - 1) * 100;
                        const cagr3 = Math.pow(mult3, 1 / years3.length) - 1;
                        updateCell(abs3yCell, abs3);
                        updateCell(cagr3yCell, cagr3 * 100);
                    } else {
                        updateCellNA(abs3yCell);
                        updateCellNA(cagr3yCell);
                    }

                    // Calculate for 2-year period (Years 4, 5)
                    const years2 = selectedYears.filter(y => y >= 4);
                    if (years2.length > 0) {
                        let mult2 = 1;
                        years2.forEach(y => mult2 *= (1 + yearReturns[y] / 100));
                        const abs2 = (mult2 - 1) * 100;
                        const cagr2 = Math.pow(mult2, 1 / years2.length) - 1;
                        updateCell(abs2yCell, abs2);
                        updateCell(cagr2yCell, cagr2 * 100);
                    } else {
                        updateCellNA(abs2yCell);
                        updateCellNA(cagr2yCell);
                    }
                });
            }

            function updateCell(cell, value) {
                if (!cell) return;

                const span = cell.querySelector('span') || cell;
                const formattedValue = value.toFixed(2);

                // Update text
                if (span.tagName === 'SPAN') {
                    span.textContent = formattedValue + '%';
                    // Update color
                    span.className = span.className.replace(/text-(success|danger)/, '');
                    span.classList.add(value >= 0 ? 'text-success' : 'text-danger');
                } else {
                    cell.textContent = formattedValue + '%';
                }

                // Update data-value for sorting
                cell.setAttribute('data-value', value);
            }

            function updateCellNA(cell) {
                if (!cell) return;

                const span = cell.querySelector('span') || cell;

                // Update text to N/A
                if (span.tagName === 'SPAN') {
                    span.textContent = 'N/A';
                    // Set to muted color
                    span.className = span.className.replace(/text-(success|danger|secondary)/, 'text-muted');
                } else {
                    cell.textContent = 'N/A';
                }

                // Update data-value for sorting
                cell.setAttribute('data-value', '');
            }

            // Event listeners for year filters
            document.querySelectorAll('.year-filter').forEach(checkbox => {
                checkbox.addEventListener('change', recalculateReturns);
            });

            // Reset all years
            document.getElementById('resetYearsBtn').addEventListener('click', function () {
                document.querySelectorAll('.year-filter').forEach(cb => cb.checked = true);
                recalculateReturns();
            });

            // --- Funds Management ---
            const fundSearchInput = document.getElementById('fundSearchInput');
            const fundSearchBtn = document.getElementById('fundSearchBtn');
            const fundSearchResults = document.getElementById('fundSearchResults');
            const refreshAfterManageBtn = document.getElementById('refreshAfterManageBtn');

            // Allow Enter key to trigger search
            fundSearchInput?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') fundSearchBtn?.click();
            });

            fundSearchBtn?.addEventListener('click', async () => {
                const query = fundSearchInput.value.trim();
                if (query.length < 3) {
                    showStatus('Enter at least 3 characters to search.', 'error');
                    return;
                }
                
                fundSearchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
                fundSearchBtn.disabled = true;
                showStatus('Searching AMFI fund universe...', 'info');
                
                try {
                    const response = await fetch(`/api/funds/search?q=${encodeURIComponent(query)}`);
                    if (response.ok) {
                        const results = await response.json();
                        fundSearchResults.innerHTML = '';
                        if (results.length === 0) {
                            fundSearchResults.innerHTML = '<div class="list-group-item text-muted">No funds found</div>';
                            showStatus('No funds found. Try a shorter scheme name.', 'error');
                        } else {
                            showStatus(`${results.length} matching funds found. Choose a destination.`, 'success');
                            results.forEach(fund => {
                                const div = document.createElement('div');
                                div.className = 'list-group-item d-flex justify-content-between align-items-center';
                                const safeName = fund.schemeName.replace(/"/g, '&quot;');
                                div.innerHTML = `
                                    <div class="flex-grow-1 me-2" style="min-width:0;">
                                        <h6 class="mb-0 text-truncate">${fund.schemeName}</h6>
                                        <small class="text-muted">Code: ${fund.schemeCode}</small>
                                    </div>
                                    <div class="btn-group btn-group-sm flex-shrink-0" role="group">
                                        <button class="btn btn-success add-portfolio-btn" 
                                                data-code="${fund.schemeCode}" 
                                                data-name="${safeName}"
                                                title="Add to Core Portfolio">
                                            <i class="bi bi-briefcase me-1"></i>Portfolio
                                        </button>
                                        <button class="btn btn-info text-white add-research-btn" 
                                                data-code="${fund.schemeCode}" 
                                                data-name="${safeName}"
                                                title="Add to Research Universe">
                                            <i class="bi bi-search me-1"></i>Research
                                        </button>
                                    </div>
                                `;
                                fundSearchResults.appendChild(div);
                            });
                            
                            // Add listeners for portfolio add buttons
                            document.querySelectorAll('.add-portfolio-btn').forEach(btn => {
                                btn.addEventListener('click', (e) => handleAddFund(e, '/api/funds', 'Portfolio'));
                            });
                            // Add listeners for research add buttons
                            document.querySelectorAll('.add-research-btn').forEach(btn => {
                                btn.addEventListener('click', (e) => handleAddFund(e, '/api/research-funds', 'Research'));
                            });
                        }
                    }
                } catch (error) {
                    console.error('Error searching:', error);
                    fundSearchResults.innerHTML = '<div class="list-group-item text-danger">Error searching funds</div>';
                    showStatus('Search failed. Please try again.', 'error');
                } finally {
                    fundSearchBtn.innerHTML = '<i class="bi bi-search"></i> Search';
                    fundSearchBtn.disabled = false;
                }
            });

            async function handleAddFund(e, apiUrl, destination) {
                const btn = e.currentTarget;
                const code = btn.dataset.code;
                const name = btn.dataset.name;
                
                // Disable both sibling buttons
                const btnGroup = btn.closest('.btn-group');
                const allBtns = btnGroup ? btnGroup.querySelectorAll('button') : [btn];
                
                btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                allBtns.forEach(b => b.disabled = true);
                
                try {
                    const response = await fetch(apiUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code, name })
                    });
                    
                    let data;
                    const contentType = response.headers.get("content-type");
                    if (contentType && contentType.indexOf("application/json") !== -1) {
                        data = await response.json();
                    } else {
                        data = { error: 'Server returned non-JSON response' };
                    }
                    if (response.ok) {
                        btn.className = 'btn btn-sm btn-secondary';
                        btn.innerHTML = `<i class="bi bi-check-lg"></i> Added to ${destination}`;
                        showStatus(`Added ${name} to ${destination}. Refresh dashboard when done.`, 'success');
                        // Re-enable the other button
                        allBtns.forEach(b => { if (b !== btn) b.disabled = false; });
                    } else {
                        showStatus(data.error || `Error adding fund to ${destination}`, 'error');
                        btn.innerHTML = destination === 'Portfolio' 
                            ? '<i class="bi bi-briefcase me-1"></i>Portfolio' 
                            : '<i class="bi bi-search me-1"></i>Research';
                        allBtns.forEach(b => b.disabled = false);
                    }
                } catch (error) {
                    console.error('Error adding fund:', error);
                    showStatus(`Error adding fund to ${destination}`, 'error');
                    btn.innerHTML = destination === 'Portfolio' 
                        ? '<i class="bi bi-briefcase me-1"></i>Portfolio' 
                        : '<i class="bi bi-search me-1"></i>Research';
                    allBtns.forEach(b => b.disabled = false);
                }
            }

            // Remove portfolio fund handler
            document.querySelectorAll('.remove-fund-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const code = e.currentTarget.dataset.code;
                    const name = e.currentTarget.dataset.name;
                    
                    if (confirm(`Remove "${name}" from portfolio?`)) {
                        const targetBtn = e.currentTarget;
                        targetBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                        targetBtn.disabled = true;
                        
                        try {
                            const response = await fetch(`/api/funds/${code}`, {
                                method: 'DELETE'
                            });
                            
                            if (response.ok) {
                                targetBtn.closest('tr').remove();
                            } else {
                                const data = await response.json();
                                showToast(data.error || 'Error removing fund', 'error');
                                targetBtn.innerHTML = '<i class="bi bi-trash"></i>';
                                targetBtn.disabled = false;
                            }
                        } catch (error) {
                            console.error('Error removing:', error);
                            showToast('Error removing fund', 'error');
                            targetBtn.innerHTML = '<i class="bi bi-trash"></i>';
                            targetBtn.disabled = false;
                        }
                    }
                });
            });

            // --- Research Funds Tab in Modal ---
            async function loadResearchFundsList() {
                const tbody = document.getElementById('researchFundsList');
                if (!tbody) return;
                
                try {
                    const response = await fetch('/api/research-funds');
                    if (response.ok) {
                        const funds = await response.json();
                        const countBadge = document.getElementById('researchFundCount');
                        if (countBadge) countBadge.textContent = funds.length;
                        
                        tbody.innerHTML = '';
                        if (funds.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-3">No research funds configured</td></tr>';
                            return;
                        }
                        
                        funds.forEach(fund => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td>${fund.name}</td>
                                <td>${fund.code}</td>
                                <td class="text-end">
                                    <button class="btn btn-sm btn-outline-danger remove-research-fund-btn" data-code="${fund.code}" data-name="${fund.name.replace(/"/g, '&quot;')}">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </td>
                            `;
                            tbody.appendChild(tr);
                        });
                        
                        // Attach remove handlers
                        tbody.querySelectorAll('.remove-research-fund-btn').forEach(btn => {
                            btn.addEventListener('click', handleRemoveResearchFund);
                        });
                    }
                } catch (error) {
                    console.error('Error loading research funds:', error);
                            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Error loading research funds</td></tr>';
                            showToast('Error loading research funds', 'error');
                }
            }

            async function handleRemoveResearchFund(e) {
                const btn = e.currentTarget;
                const code = btn.dataset.code;
                const name = btn.dataset.name;
                
                if (confirm(`Remove "${name}" from research universe?`)) {
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                    btn.disabled = true;
                    
                    try {
                        const response = await fetch(`/api/research-funds/${code}`, {
                            method: 'DELETE'
                        });
                        
                        if (response.ok) {
                            btn.closest('tr').remove();
                            // Update count badge
                            const countBadge = document.getElementById('researchFundCount');
                            if (countBadge) countBadge.textContent = parseInt(countBadge.textContent) - 1;
                        } else {
                            const data = await response.json();
                            showToast(data.error || 'Error removing fund', 'error');
                            btn.innerHTML = '<i class="bi bi-trash"></i>';
                            btn.disabled = false;
                        }
                    } catch (error) {
                        console.error('Error removing research fund:', error);
                        showToast('Error removing fund', 'error');
                        btn.innerHTML = '<i class="bi bi-trash"></i>';
                        btn.disabled = false;
                    }
                }
            }

            // Load research funds when modal opens or research tab is clicked
            const manageFundsModal = document.getElementById('manageFundsModal');
            manageFundsModal?.addEventListener('shown.bs.modal', loadResearchFundsList);

            refreshAfterManageBtn?.addEventListener('click', () => {
                window.location.reload();
            });
