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
                        value: parseFloat(mainRow.cells[column].getAttribute('data-value')) || 0
                    };
                })
                    .sort((a, b) => isAscending ? b.value - a.value : a.value - b.value);

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
                try {
                    refreshBtn.classList.add('loading');
                    const response = await fetch('/api/refresh');
                    if (response.ok) {
                        // Reload the page to show fresh data
                        window.location.reload();
                    } else {
                        console.error('Failed to refresh data');
                    }
                } catch (error) {
                    console.error('Error refreshing data:', error);
                } finally {
                    refreshBtn.classList.remove('loading');
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
                            let aValue = aCell.getAttribute('data-value') || aCell.textContent.trim();
                            let bValue = bCell.getAttribute('data-value') || bCell.textContent.trim();

                            // Try to parse as number
                            const aNum = parseFloat(aValue);
                            const bNum = parseFloat(bValue);

                            if (!isNaN(aNum) && !isNaN(bNum)) {
                                // Numeric sorting
                                return isAscending ? bNum - aNum : aNum - bNum;
                            }

                            // Text sorting
                            return isAscending ?
                                bValue.toString().localeCompare(aValue.toString()) :
                                aValue.toString().localeCompare(bValue.toString());
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
                    alert('Please select at least one year');
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
                    span.textContent = '—';
                    // Set to muted color
                    span.className = span.className.replace(/text-(success|danger|secondary)/, 'text-muted');
                } else {
                    cell.textContent = '—';
                }

                // Update data-value for sorting
                cell.setAttribute('data-value', '0');
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

            fundSearchBtn?.addEventListener('click', async () => {
                const query = fundSearchInput.value.trim();
                if (query.length < 3) {
                    alert('Please enter at least 3 characters');
                    return;
                }
                
                fundSearchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
                fundSearchBtn.disabled = true;
                
                try {
                    const response = await fetch(`/api/funds/search?q=${encodeURIComponent(query)}`);
                    if (response.ok) {
                        const results = await response.json();
                        fundSearchResults.innerHTML = '';
                        if (results.length === 0) {
                            fundSearchResults.innerHTML = '<div class="list-group-item text-muted">No funds found</div>';
                        } else {
                            results.forEach(fund => {
                                const btn = document.createElement('button');
                                btn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                                btn.innerHTML = `
                                    <div>
                                        <h6 class="mb-0">${fund.schemeName}</h6>
                                        <small class="text-muted">Code: ${fund.schemeCode}</small>
                                    </div>
                                    <span class="btn btn-sm btn-success add-fund-btn" data-code="${fund.schemeCode}" data-name="${fund.schemeName}">Add</span>
                                `;
                                fundSearchResults.appendChild(btn);
                            });
                            
                            // Add listeners to new add buttons
                            document.querySelectorAll('.add-fund-btn').forEach(btn => {
                                btn.addEventListener('click', handleAddFund);
                            });
                        }
                    }
                } catch (error) {
                    console.error('Error searching:', error);
                    fundSearchResults.innerHTML = '<div class="list-group-item text-danger">Error searching funds</div>';
                } finally {
                    fundSearchBtn.innerHTML = '<i class="bi bi-search"></i> Search';
                    fundSearchBtn.disabled = false;
                }
            });

            async function handleAddFund(e) {
                const btn = e.currentTarget;
                const code = btn.dataset.code;
                const name = btn.dataset.name;
                
                btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                btn.disabled = true;
                
                try {
                    const response = await fetch('/api/funds', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code, name })
                    });
                    
                    const data = await response.json();
                    if (response.ok) {
                        btn.className = 'btn btn-sm btn-secondary';
                        btn.textContent = 'Added';
                        alert('Fund added successfully! Refresh dashboard to see changes.');
                    } else {
                        alert(data.error || 'Error adding fund');
                        btn.innerHTML = 'Add';
                        btn.disabled = false;
                    }
                } catch (error) {
                    console.error('Error adding fund:', error);
                    alert('Error adding fund');
                    btn.innerHTML = 'Add';
                    btn.disabled = false;
                }
            }

            document.querySelectorAll('.remove-fund-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const code = e.currentTarget.dataset.code;
                    const name = e.currentTarget.dataset.name;
                    
                    if (confirm(`Are you sure you want to remove ${name}?`)) {
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
                                alert(data.error || 'Error removing fund');
                                targetBtn.innerHTML = '<i class="bi bi-trash"></i>';
                                targetBtn.disabled = false;
                            }
                        } catch (error) {
                            console.error('Error removing:', error);
                            alert('Error removing fund');
                            targetBtn.innerHTML = '<i class="bi bi-trash"></i>';
                            targetBtn.disabled = false;
                        }
                    }
                });
            });

            refreshAfterManageBtn?.addEventListener('click', () => {
                window.location.reload();
            });
