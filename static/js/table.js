import { showToast } from './ui.js';

export const debounce = (func, wait) => {
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

export function parseSortableValue(cell) {
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

export function compareSortableValues(aCell, bCell, ascending) {
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

export function initTableSorting() {
    const table = document.getElementById('fundTable');
    if (!table) return;

    const headers = table.querySelectorAll('th.sortable');
    let lastSortedColumn = null;

    const sortTable = debounce(function (header) {
        const column = header.cellIndex;
        const tbody = table.querySelector('tbody');
        const allRows = Array.from(tbody.querySelectorAll('tr'));
        const isAscending = header.classList.contains('asc');

        const mainRows = allRows.filter(row => row.classList.contains('fund-row'));

        headers.forEach(h => {
            h.classList.remove('asc', 'desc');
            const icon = h.querySelector('i');
            if (icon) icon.className = 'bi bi-arrow-down-up';
        });

        header.classList.toggle('asc', !isAscending);
        header.classList.toggle('desc', isAscending);
        const icon = header.querySelector('i');
        if (icon) {
            icon.className = isAscending ? 'bi bi-arrow-down' : 'bi bi-arrow-up';
        }

        const sortedPairs = mainRows.map(mainRow => {
            const nextRow = mainRow.nextElementSibling;
            const accordionRow = (nextRow && nextRow.classList.contains('accordion-collapse')) ? nextRow : null;

            return {
                mainRow: mainRow,
                accordionRow: accordionRow,
                valueCell: mainRow.cells[column]
            };
        }).sort((a, b) => compareSortableValues(a.valueCell, b.valueCell, isAscending));

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

    headers.forEach(header => {
        header.addEventListener('click', () => sortTable(header));
    });
}

export function setupGenericTableSorting(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const headers = table.querySelectorAll('.sortable-header');

    headers.forEach(header => {
        header.addEventListener('click', function () {
            const column = parseInt(this.getAttribute('data-column'));
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isAscending = this.classList.contains('asc');

            headers.forEach(h => {
                h.classList.remove('asc', 'desc');
                const icon = h.querySelector('i');
                if (icon) icon.className = 'bi bi-arrow-down-up';
            });

            this.classList.toggle('asc', !isAscending);
            this.classList.toggle('desc', isAscending);
            const icon = this.querySelector('i');
            if (icon) {
                icon.className = isAscending ? 'bi bi-arrow-down' : 'bi bi-arrow-up';
            }

            const sortedRows = rows.sort((a, b) => {
                const aCell = a.cells[column];
                const bCell = b.cells[column];

                if (!aCell || !bCell) return 0;
                return compareSortableValues(aCell, bCell, isAscending);
            });

            const fragment = document.createDocumentFragment();
            sortedRows.forEach(row => fragment.appendChild(row));
            tbody.appendChild(fragment);
        });
    });
}

function updateCell(cell, value) {
    if (!cell) return;
    const span = cell.querySelector('span') || cell;
    const formattedValue = value.toFixed(2);
    if (span.tagName === 'SPAN') {
        span.textContent = formattedValue + '%';
        span.className = span.className.replace(/text-(success|danger)/, '');
        span.classList.add(value >= 0 ? 'text-success' : 'text-danger');
    } else {
        cell.textContent = formattedValue + '%';
    }
    cell.setAttribute('data-value', value);
}

function updateCellNA(cell) {
    if (!cell) return;
    const span = cell.querySelector('span') || cell;
    if (span.tagName === 'SPAN') {
        span.textContent = 'N/A';
        span.className = span.className.replace(/text-(success|danger|secondary)/, 'text-muted');
    } else {
        cell.textContent = 'N/A';
    }
    cell.setAttribute('data-value', '');
}

export function recalculateReturns() {
    const selectedYears = Array.from(document.querySelectorAll('.year-filter:checked')).map(cb => parseInt(cb.value));

    if (selectedYears.length === 0) {
        showToast('Select at least one year to recalculate returns.', 'error');
        return;
    }

    const summaryTable = document.getElementById('summaryTable');
    if (!summaryTable) return;

    const rows = summaryTable.querySelectorAll('tbody tr');

    rows.forEach(row => {
        const abs2yCell = row.querySelector('.total-abs-2y');
        const cagr2yCell = row.querySelector('.cagr-2y');
        const abs3yCell = row.querySelector('.total-abs-3y');
        const cagr3yCell = row.querySelector('.cagr-3y');
        const abs5yCell = row.querySelector('.total-abs-5y');
        const cagr5yCell = row.querySelector('.cagr-5y');

        if (!abs5yCell) return;

        const yearReturns = {
            1: parseFloat(abs5yCell.getAttribute('data-y1')) || 0,
            2: parseFloat(abs5yCell.getAttribute('data-y2')) || 0,
            3: parseFloat(abs5yCell.getAttribute('data-y3')) || 0,
            4: parseFloat(abs5yCell.getAttribute('data-y4')) || 0,
            5: parseFloat(abs5yCell.getAttribute('data-y5')) || 0
        };

        let totalMultiplier = 1;
        selectedYears.forEach(year => {
            totalMultiplier *= (1 + yearReturns[year] / 100);
        });

        const totalAbsolute = (totalMultiplier - 1) * 100;
        const numYears = selectedYears.length;
        const cagr = numYears > 0 ? (Math.pow(totalMultiplier, 1 / numYears) - 1) * 100 : 0;

        updateCell(abs5yCell, totalAbsolute);
        updateCell(cagr5yCell, cagr);

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

export function initViewControls() {
    const comparisonViewContainer = document.getElementById('comparisonViewContainer');
    const expandCollapseButtons = document.getElementById('expandCollapseButtons');
    const tableViewRadio = document.getElementById('tableView');
    const comparisonViewRadio = document.getElementById('comparisonView');
    const tableViewContainer = document.getElementById('tableViewContainer');

    if (tableViewRadio) {
        tableViewRadio.addEventListener('change', function () {
            if (this.checked) {
                tableViewContainer.style.display = 'block';
                comparisonViewContainer.style.display = 'none';
                expandCollapseButtons.style.display = 'block';
            }
        });
    }

    if (comparisonViewRadio) {
        comparisonViewRadio.addEventListener('change', function () {
            if (this.checked) {
                tableViewContainer.style.display = 'none';
                comparisonViewContainer.style.display = 'block';
                expandCollapseButtons.style.display = 'none';
            }
        });
    }

    const expandAllBtn = document.getElementById('expandAllBtn');
    if (expandAllBtn) {
        expandAllBtn.addEventListener('click', function () {
            const collapseElements = document.querySelectorAll('.accordion-collapse');
            collapseElements.forEach(element => {
                // Using global bootstrap
                const bsCollapse = new bootstrap.Collapse(element, { toggle: false });
                bsCollapse.show();
            });

            const accordionRows = document.querySelectorAll('.accordion-button');
            accordionRows.forEach(row => {
                row.setAttribute('aria-expanded', 'true');
            });
        });
    }

    const collapseAllBtn = document.getElementById('collapseAllBtn');
    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', function () {
            const collapseElements = document.querySelectorAll('.accordion-collapse');
            collapseElements.forEach(element => {
                const bsCollapse = new bootstrap.Collapse(element, { toggle: false });
                bsCollapse.hide();
            });

            const accordionRows = document.querySelectorAll('.accordion-button');
            accordionRows.forEach(row => {
                row.setAttribute('aria-expanded', 'false');
            });
        });
    }

    document.querySelectorAll('.year-filter').forEach(checkbox => {
        checkbox.addEventListener('change', recalculateReturns);
    });

    const resetYearsBtn = document.getElementById('resetYearsBtn');
    if (resetYearsBtn) {
        resetYearsBtn.addEventListener('click', function () {
            document.querySelectorAll('.year-filter').forEach(cb => cb.checked = true);
            recalculateReturns();
        });
    }
}
