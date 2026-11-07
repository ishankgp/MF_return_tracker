import { showToast } from './ui.js';
import { refreshData } from './api.js';
import { initNotes } from './notes.js';
import { initTableSorting, setupGenericTableSorting, initViewControls, initPortfolioCategoryFilter } from './table.js';
import { initFundsManagement } from './funds.js';

document.addEventListener('DOMContentLoaded', () => {
    initNotes();
    initTableSorting();
    setupGenericTableSorting('shortTermTable');
    setupGenericTableSorting('yearlyTable');
    setupGenericTableSorting('summaryTable');
    initViewControls();
    initPortfolioCategoryFilter();
    initFundsManagement();

    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            const originalHtml = refreshBtn.innerHTML;
            try {
                refreshBtn.classList.add('loading');
                refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span><span class="refresh-label">Refreshing</span>';
                const response = await refreshData();
                if (response.ok) {
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
    }
});
