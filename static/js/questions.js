let currentPage = 1;
const pageSize = 10;

function applyQuestionsFilterAndSort(resetPage = true) {
    if (resetPage) {
        currentPage = 1;
    }
    
    const searchInput = document.getElementById('questions-search-input');
    const searchQuery = searchInput ? searchInput.value.trim().toLowerCase() : '';
    
    const statusFilterEl = document.getElementById('questions-status-filter');
    const statusFilter = statusFilterEl ? statusFilterEl.value : 'all';
    
    const diffFilterEl = document.getElementById('questions-difficulty-filter');
    const difficultyFilter = diffFilterEl ? diffFilterEl.value : 'all';
    
    const sortSelectEl = document.getElementById('questions-sort-select');
    const sortValue = sortSelectEl ? sortSelectEl.value : 'id_asc';
    
    const tbody = document.getElementById('questions-tbody');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('.question-item-row'));
    const noMatchesRow = document.getElementById('no-matching-questions-row');
    const noQuestionsRow = document.getElementById('no-questions-row');
    
    if (noQuestionsRow) return;
    
    // 1. Filter rows
    let matchingRows = rows.filter(row => {
        const id = (row.getAttribute('data-id') || '').toLowerCase();
        const title = (row.getAttribute('data-title') || '').toLowerCase();
        const status = row.getAttribute('data-status') || '';
        const difficulty = row.getAttribute('data-difficulty') || '';
        
        const matchSearch = !searchQuery || title.includes(searchQuery) || id.includes(searchQuery) || (`#${id}`).includes(searchQuery);
        const matchStatus = (statusFilter === 'all') || (status === statusFilter);
        const matchDifficulty = (difficultyFilter === 'all') || (difficulty === difficultyFilter);
        
        return matchSearch && matchStatus && matchDifficulty;
    });
    
    // 2. Sort matching rows
    matchingRows.sort((a, b) => {
        const aId = parseInt(a.getAttribute('data-id'), 10) || 0;
        const bId = parseInt(b.getAttribute('data-id'), 10) || 0;
        const aTitle = a.getAttribute('data-title') || '';
        const bTitle = b.getAttribute('data-title') || '';
        const aDiff = parseInt(a.getAttribute('data-difficulty'), 10) || 0;
        const bDiff = parseInt(b.getAttribute('data-difficulty'), 10) || 0;
        const aSolved = parseInt(a.getAttribute('data-solved'), 10) || 0;
        const bSolved = parseInt(b.getAttribute('data-solved'), 10) || 0;
        
        switch(sortValue) {
            case 'id_asc': return aId - bId;
            case 'id_desc': return bId - aId;
            case 'title_asc': return aTitle.localeCompare(bTitle);
            case 'title_desc': return bTitle.localeCompare(aTitle);
            case 'diff_asc': return (aDiff - bDiff) || (aId - bId);
            case 'diff_desc': return (bDiff - aDiff) || (aId - bId);
            case 'solved_desc': return (bSolved - aSolved) || (aId - bId);
            case 'solved_asc': return (aSolved - bSolved) || (aId - bId);
            default: return aId - bId;
        }
    });
    
    // Re-append matching rows to tbody in sorted order
    matchingRows.forEach(row => tbody.appendChild(row));
    if (noMatchesRow) tbody.appendChild(noMatchesRow);
    
    // 3. Paginate
    const totalMatching = matchingRows.length;
    const totalPages = Math.ceil(totalMatching / pageSize) || 1;
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;
    
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    
    // Hide all item rows first
    rows.forEach(row => {
        row.style.display = 'none';
    });
    
    // Display only matching rows for current page
    matchingRows.forEach((row, idx) => {
        if (idx >= startIndex && idx < endIndex) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    // Show/hide no matches notification
    if (noMatchesRow) {
        noMatchesRow.style.display = (totalMatching === 0) ? '' : 'none';
    }
    
    // 4. Update pagination controls
    updatePaginationControls(currentPage, totalPages, totalMatching, startIndex, endIndex);
}

function updatePaginationControls(page, totalPages, totalCount, startIdx, endIdx) {
    const prevBtn = document.getElementById('btn-prev-page');
    const nextBtn = document.getElementById('btn-next-page');
    const pagesContainer = document.getElementById('pagination-pages-list');
    const infoSpan = document.getElementById('pagination-info-text');
    
    if (!prevBtn || !nextBtn || !pagesContainer || !infoSpan) return;
    
    prevBtn.disabled = (page <= 1);
    nextBtn.disabled = (page >= totalPages);
    
    const actualEnd = Math.min(endIdx, totalCount);
    const actualStart = totalCount === 0 ? 0 : startIdx + 1;
    
    const showingTemplate = infoSpan.getAttribute('data-showing-template') || 'Showing {start}-{end} of {total} questions';
    infoSpan.textContent = showingTemplate
        .replace('{start}', actualStart)
        .replace('{end}', actualEnd)
        .replace('{total}', totalCount);
    
    pagesContainer.innerHTML = '';
    
    // Render smart window of page numbers
    let startPage = Math.max(1, page - 2);
    let endPage = Math.min(totalPages, page + 2);
    
    if (startPage > 1) {
        const pBtn = createPageBtn(1, page);
        pagesContainer.appendChild(pBtn);
        if (startPage > 2) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.style.color = 'var(--text-muted)';
            ellipsis.style.alignSelf = 'center';
            ellipsis.style.padding = '0 4px';
            pagesContainer.appendChild(ellipsis);
        }
    }
    
    for (let p = startPage; p <= endPage; p++) {
        const pBtn = createPageBtn(p, page);
        pagesContainer.appendChild(pBtn);
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.style.color = 'var(--text-muted)';
            ellipsis.style.alignSelf = 'center';
            ellipsis.style.padding = '0 4px';
            pagesContainer.appendChild(ellipsis);
        }
        const pBtn = createPageBtn(totalPages, page);
        pagesContainer.appendChild(pBtn);
    }
}

function createPageBtn(p, activePage) {
    const pBtn = document.createElement('button');
    pBtn.type = 'button';
    pBtn.className = `btn btn-sm ${p === activePage ? 'btn-primary' : 'btn-outline'}`;
    pBtn.style.padding = '4px 10px';
    pBtn.style.fontSize = '0.85rem';
    pBtn.textContent = p;
    pBtn.onclick = () => {
        currentPage = p;
        applyQuestionsFilterAndSort(false);
    };
    return pBtn;
}

function changePage(delta) {
    currentPage += delta;
    applyQuestionsFilterAndSort(false);
}

document.addEventListener('DOMContentLoaded', () => {
    applyQuestionsFilterAndSort(true);
});
