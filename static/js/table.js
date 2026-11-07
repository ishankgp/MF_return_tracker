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
        return ascending ? a.value - b.value : b.value - a.value;
    }

    return ascending
        ? a.value.toString().localeCompare(b.value.toString())
        : b.value.toString().localeCompare(a.value.toString());
}

const portfolioTableIds = ['fundTable', 'shortTermTable', 'yearlyTable', 'summaryTable'];
const tableSorts = new WeakMap();
const categoryStorageKey = 'portfolioCategory';

function detailRow(row) {
    const target = row.getAttribute('data-bs-target');
    return target ? document.getElementById(target.slice(1)) : null;
}

function sortPortfolioTable(table) {
    const state = tableSorts.get(table);
    if (!state) return;
    const rows = Array.from(table.tBodies[0].children).filter(row => row.hasAttribute('data-portfolio-fund'));
    const visible = rows.filter(row => !row.hidden);
    visible.sort((a, b) => compareSortableValues(a.cells[state.column], b.cells[state.column], state.ascending));
    const fragment = document.createDocumentFragment();
    [...visible, ...rows.filter(row => row.hidden)].forEach(row => {
        fragment.appendChild(row);
        const detail = detailRow(row);
        if (detail) fragment.appendChild(detail);
    });
    // Empty-state rows are never included in sorting.
    table.tBodies[0].prepend(fragment);
}

function installSorting(table, selector) {
    if (!table) return;
    const headers = table.querySelectorAll(selector);
    headers.forEach(header => {
        header.tabIndex = 0;
        header.setAttribute('aria-sort', 'none');
        const sort = () => {
            const previous = tableSorts.get(table);
            const column = Number(header.dataset.column ?? header.cellIndex);
            const ascending = previous?.header === header ? !previous.ascending : false;
            tableSorts.set(table, { header, column, ascending });
            headers.forEach(h => {
                h.classList.remove('asc', 'desc');
                h.setAttribute('aria-sort', 'none');
                const icon = h.querySelector('i');
                if (icon) icon.className = 'bi bi-arrow-down-up';
            });
            header.classList.add(ascending ? 'asc' : 'desc');
            header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
            const icon = header.querySelector('i');
            if (icon) icon.className = ascending ? 'bi bi-arrow-up' : 'bi bi-arrow-down';
            sortPortfolioTable(table);
        };
        header.addEventListener('click', sort);
        header.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                sort();
            }
        });
    });
}

export function initTableSorting() {
    installSorting(document.getElementById('fundTable'), 'th.sortable');
}

export function setupGenericTableSorting(tableId) {
    installSorting(document.getElementById(tableId), '.sortable-header');
}

export function initPortfolioCategoryFilter() {
    const buttons = document.querySelectorAll('[data-portfolio-category]');
    if (!buttons.length) return;
    const tables = portfolioTableIds.map(id => document.getElementById(id)).filter(Boolean);
    const validCategories = ['all', 'midcap', 'smallcap'];
    let selected = 'all';
    try {
        const saved = sessionStorage.getItem(categoryStorageKey);
        if (validCategories.includes(saved)) selected = saved;
    } catch { /* Filtering still works when browser storage is unavailable. */ }

    const apply = category => {
        buttons.forEach(button => {
            const active = button.dataset.portfolioCategory === category;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', String(active));
        });
        tables.forEach(table => {
            const rows = Array.from(table.tBodies[0].children).filter(row => row.hasAttribute('data-portfolio-fund'));
            let count = 0;
            rows.forEach(row => {
                row.hidden = category !== 'all' && row.dataset.category !== category;
                if (!row.hidden) count++;
                const detail = detailRow(row);
                if (detail) {
                    detail.hidden = row.hidden;
                    if (row.hidden) bootstrap.Collapse.getOrCreateInstance(detail, { toggle: false }).hide();
                }
            });
            let empty = table.tBodies[0].querySelector(':scope > .portfolio-empty-row');
            if (!empty) {
                empty = document.createElement('tr');
                empty.className = 'portfolio-empty-row';
                const cell = document.createElement('td');
                cell.colSpan = Math.max(...Array.from(table.tHead.rows, row => Array.from(row.cells).reduce((n, c) => n + c.colSpan, 0)));
                cell.className = 'text-center text-muted py-4';
                cell.textContent = 'No portfolio funds match this category.';
                empty.appendChild(cell);
                table.tBodies[0].appendChild(empty);
            }
            empty.hidden = count !== 0;
            if (table.id === 'fundTable') {
                document.getElementById('portfolioFilterCount').textContent = `${count} of ${rows.length} funds`;
            }
            sortPortfolioTable(table);
        });
    };
    buttons.forEach(button => button.addEventListener('click', () => {
        selected = button.dataset.portfolioCategory;
        try { sessionStorage.setItem(categoryStorageKey, selected); } catch { /* Optional persistence. */ }
        apply(selected);
    }));
    apply(selected);
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
    sortPortfolioTable(summaryTable);
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

    const setDetailsExpanded = expanded => {
        document.querySelectorAll('#fundTable .fund-row').forEach(row => {
            if (expanded && row.hidden) return;
            const detail = detailRow(row);
            if (!detail) return;
            const collapse = bootstrap.Collapse.getOrCreateInstance(detail, { toggle: false });
            if (expanded) collapse.show();
            else collapse.hide();
        });
    };
    document.getElementById('expandAllBtn')?.addEventListener('click', () => setDetailsExpanded(true));
    document.getElementById('collapseAllBtn')?.addEventListener('click', () => setDetailsExpanded(false));

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
