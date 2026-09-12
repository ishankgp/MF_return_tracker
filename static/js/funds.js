import { 
    searchFundsApi, 
    addFundToPortfolio, 
    addFundToResearch, 
    removePortfolioFundApi, 
    getResearchFundsApi, 
    removeResearchFundApi 
} from './api.js';
import { showStatus, showToast } from './ui.js';

export function initFundsManagement() {
    const fundSearchInput = document.getElementById('fundSearchInput');
    const fundSearchBtn = document.getElementById('fundSearchBtn');
    const fundSearchResults = document.getElementById('fundSearchResults');
    const refreshAfterManageBtn = document.getElementById('refreshAfterManageBtn');

    if (fundSearchInput) {
        fundSearchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') fundSearchBtn?.click();
        });
    }

    if (fundSearchBtn) {
        fundSearchBtn.addEventListener('click', async () => {
            const query = fundSearchInput.value.trim();
            if (query.length < 3) {
                showStatus('Enter at least 3 characters to search.', 'error');
                return;
            }
            
            fundSearchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
            fundSearchBtn.disabled = true;
            showStatus('Searching AMFI fund universe...', 'info');
            
            try {
                const response = await searchFundsApi(query);
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
                        
                        document.querySelectorAll('.add-portfolio-btn').forEach(btn => {
                            btn.addEventListener('click', (e) => handleAddFund(e, addFundToPortfolio, 'Portfolio'));
                        });
                        document.querySelectorAll('.add-research-btn').forEach(btn => {
                            btn.addEventListener('click', (e) => handleAddFund(e, addFundToResearch, 'Research'));
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
    }

    document.querySelectorAll('.remove-fund-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const code = e.currentTarget.dataset.code;
            const name = e.currentTarget.dataset.name;
            
            if (confirm(`Remove "${name}" from portfolio?`)) {
                const targetBtn = e.currentTarget;
                targetBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                targetBtn.disabled = true;
                
                try {
                    const response = await removePortfolioFundApi(code);
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

    const manageFundsModal = document.getElementById('manageFundsModal');
    if (manageFundsModal) {
        manageFundsModal.addEventListener('shown.bs.modal', loadResearchFundsList);
    }

    if (refreshAfterManageBtn) {
        refreshAfterManageBtn.addEventListener('click', () => {
            window.location.reload();
        });
    }
}

async function handleAddFund(e, apiCall, destination) {
    const btn = e.currentTarget;
    const code = btn.dataset.code;
    const name = btn.dataset.name;
    
    const btnGroup = btn.closest('.btn-group');
    const allBtns = btnGroup ? btnGroup.querySelectorAll('button') : [btn];
    
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    allBtns.forEach(b => b.disabled = true);
    
    try {
        const response = await apiCall(code, name);
        
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

async function loadResearchFundsList() {
    const tbody = document.getElementById('researchFundsList');
    if (!tbody) return;
    
    try {
        const response = await getResearchFundsApi();
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
            const response = await removeResearchFundApi(code);
            if (response.ok) {
                btn.closest('tr').remove();
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
