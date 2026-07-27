let currentPage = 1;
const pageSize = 10;
let currentSortColumn = 'id';
let currentSortOrder = 'asc';
let currentStatusFilters = new Set();
let currentDifficultyFilters = new Set();
let currentAuthorFilters = new Set();

let allAuthorsData = []; // Array of { value, name, count, isUnassigned } sorted by count desc
let visibleAuthorsCount = 3; // Initially show top 3 authors

function initAuthorFilters() {
    const tbody = document.getElementById('questions-tbody');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('.questions-table-row'));
    const countsMap = new Map();
    let unassignedCount = 0;
    
    rows.forEach(row => {
        const author = (row.getAttribute('data-author') || '').trim();
        if (author) {
            countsMap.set(author, (countsMap.get(author) || 0) + 1);
        } else {
            unassignedCount++;
        }
    });
    
    allAuthorsData = [];
    countsMap.forEach((count, author) => {
        allAuthorsData.push({
            value: author,
            name: author,
            count: count,
            isUnassigned: false
        });
    });
    
    // Sort by count descending, then by name ascending
    allAuthorsData.sort((a, b) => (b.count - a.count) || a.name.localeCompare(b.name));
    
    if (unassignedCount > 0) {
        const container = document.getElementById('author-pills-container');
        const unassignedText = (container && container.getAttribute('data-unassigned-text')) || 'Unassigned';
        allAuthorsData.push({
            value: 'unassigned',
            name: unassignedText,
            count: unassignedCount,
            isUnassigned: true
        });
    }
    
    visibleAuthorsCount = 3;
    renderAuthorPills();
}

function renderAuthorPills() {
    const container = document.getElementById('author-pills-container');
    if (!container) return;
    
    const allText = container.getAttribute('data-all-text') || 'All';
    const showMoreText = container.getAttribute('data-show-more-text') || 'Show More';
    
    container.innerHTML = '';
    
    // 1. All pill
    const allBtn = document.createElement('button');
    allBtn.type = 'button';
    allBtn.className = `filter-pill ${currentAuthorFilters.size === 0 ? 'active' : ''}`;
    allBtn.setAttribute('data-value', 'all');
    allBtn.textContent = allText;
    container.appendChild(allBtn);
    
    // 2. Authors up to visibleAuthorsCount
    const authorsToShow = allAuthorsData.slice(0, visibleAuthorsCount);
    authorsToShow.forEach(auth => {
        const btn = document.createElement('button');
        btn.type = 'button';
        const isActive = currentAuthorFilters.has(auth.value);
        btn.className = `filter-pill ${isActive ? 'active' : ''}`;
        btn.setAttribute('data-value', auth.value);
        
        if (auth.isUnassigned) {
            btn.textContent = `⚪ ${auth.name} (${auth.count})`;
        } else {
            btn.textContent = `👤 ${auth.name} (${auth.count})`;
        }
        container.appendChild(btn);
    });
    
    // 3. Show More button if there are remaining authors
    if (visibleAuthorsCount < allAuthorsData.length) {
        const showMoreBtn = document.createElement('button');
        showMoreBtn.type = 'button';
        showMoreBtn.className = 'filter-pill btn-show-more-authors';
        showMoreBtn.id = 'btn-show-more-authors';
        showMoreBtn.style.background = 'rgba(0, 242, 254, 0.08)';
        showMoreBtn.style.borderColor = 'var(--primary-color)';
        showMoreBtn.style.color = 'var(--primary-color)';
        showMoreBtn.style.fontWeight = '600';
        showMoreBtn.textContent = `+ ${showMoreText}`;
        container.appendChild(showMoreBtn);
    }
}

function showMoreAuthors() {
    visibleAuthorsCount += 3;
    renderAuthorPills();
}

function toggleFiltersPanel() {
    const drawer = document.getElementById('arena-filters-drawer');
    const btn = document.getElementById('btn-toggle-filters');
    if (!drawer) return;
    drawer.classList.toggle('open');
    if (btn) btn.classList.toggle('active');
}

function setStatusFilter(val) {
    if (val === 'all') {
        currentStatusFilters.clear();
    } else {
        if (currentStatusFilters.has(val)) {
            currentStatusFilters.delete(val);
        } else {
            currentStatusFilters.add(val);
        }
    }
    
    // Update status pills UI
    const container = document.getElementById('status-pills-container');
    if (container) {
        const allBtn = container.querySelector('.filter-pill[data-value="all"]');
        const specificBtns = container.querySelectorAll('.filter-pill:not([data-value="all"])');
        
        if (currentStatusFilters.size === 0) {
            allBtn.classList.add('active');
            specificBtns.forEach(btn => btn.classList.remove('active'));
        } else {
            allBtn.classList.remove('active');
            specificBtns.forEach(btn => {
                const bVal = btn.getAttribute('data-value');
                if (currentStatusFilters.has(bVal)) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
    }
    applyQuestionsFilterAndSort(true);
}

function setDifficultyFilter(val) {
    if (val === 'all') {
        currentDifficultyFilters.clear();
    } else {
        if (currentDifficultyFilters.has(val)) {
            currentDifficultyFilters.delete(val);
        } else {
            currentDifficultyFilters.add(val);
        }
    }
    
    // Update difficulty pills UI
    const container = document.getElementById('difficulty-pills-container');
    if (container) {
        const allBtn = container.querySelector('.filter-pill[data-value="all"]');
        const specificBtns = container.querySelectorAll('.filter-pill:not([data-value="all"])');
        
        if (currentDifficultyFilters.size === 0) {
            allBtn.classList.add('active');
            specificBtns.forEach(btn => btn.classList.remove('active'));
        } else {
            allBtn.classList.remove('active');
            specificBtns.forEach(btn => {
                const bVal = btn.getAttribute('data-value');
                if (currentDifficultyFilters.has(bVal)) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
    }
    applyQuestionsFilterAndSort(true);
}

function setAuthorFilter(val) {
    if (val === 'all') {
        currentAuthorFilters.clear();
    } else {
        if (currentAuthorFilters.has(val)) {
            currentAuthorFilters.delete(val);
        } else {
            currentAuthorFilters.add(val);
        }
    }
    
    // Update author pills UI
    const container = document.getElementById('author-pills-container');
    if (container) {
        const allBtn = container.querySelector('.filter-pill[data-value="all"]');
        const specificBtns = container.querySelectorAll('.filter-pill:not([data-value="all"]):not(#btn-show-more-authors)');
        
        if (currentAuthorFilters.size === 0) {
            if (allBtn) allBtn.classList.add('active');
            specificBtns.forEach(btn => btn.classList.remove('active'));
        } else {
            if (allBtn) allBtn.classList.remove('active');
            specificBtns.forEach(btn => {
                const bVal = btn.getAttribute('data-value');
                if (currentAuthorFilters.has(bVal)) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
    }
    applyQuestionsFilterAndSort(true);
}

function resetAllFilters() {
    const searchInput = document.getElementById('questions-search-input');
    if (searchInput) searchInput.value = '';
    
    currentStatusFilters.clear();
    currentDifficultyFilters.clear();
    currentAuthorFilters.clear();
    
    // Reset status pills UI
    const statusContainer = document.getElementById('status-pills-container');
    if (statusContainer) {
        statusContainer.querySelectorAll('.filter-pill').forEach(btn => {
            if (btn.getAttribute('data-value') === 'all') btn.classList.add('active');
            else btn.classList.remove('active');
        });
    }
    
    // Reset difficulty pills UI
    const diffContainer = document.getElementById('difficulty-pills-container');
    if (diffContainer) {
        diffContainer.querySelectorAll('.filter-pill').forEach(btn => {
            if (btn.getAttribute('data-value') === 'all') btn.classList.add('active');
            else btn.classList.remove('active');
        });
    }
    
    // Reset author filters & pills UI
    visibleAuthorsCount = 3;
    renderAuthorPills();
    
    currentSortColumn = 'id';
    currentSortOrder = 'asc';
    updateSortIcons();
    
    applyQuestionsFilterAndSort(true);
}

function sortQuestionsBy(column) {
    if (currentSortColumn === column) {
        currentSortOrder = (currentSortOrder === 'asc') ? 'desc' : 'asc';
    } else {
        currentSortColumn = column;
        if (column === 'solved' || column === 'difficulty') {
            currentSortOrder = 'desc';
        } else {
            currentSortOrder = 'asc';
        }
    }
    updateSortIcons();
    applyQuestionsFilterAndSort(true);
}

function updateSortIcons() {
    const columns = ['status', 'id', 'title', 'difficulty', 'solved'];
    columns.forEach(col => {
        const icon = document.getElementById(`sort-icon-${col}`);
        const th = document.getElementById(`th-${col}`);
        if (!icon || !th) return;
        
        if (col === currentSortColumn) {
            th.classList.add('active-sort');
            icon.classList.add('active');
            icon.textContent = (currentSortOrder === 'asc') ? '▲' : '▼';
        } else {
            th.classList.remove('active-sort');
            icon.classList.remove('active');
            icon.textContent = '↕';
        }
    });
}

function applyQuestionsFilterAndSort(resetPage = true) {
    if (resetPage) {
        currentPage = 1;
    }
    
    const searchInput = document.getElementById('questions-search-input');
    const searchQuery = searchInput ? searchInput.value.trim().toLowerCase() : '';
    
    const tbody = document.getElementById('questions-tbody');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('.questions-table-row'));
    const noMatchesRow = document.getElementById('no-matching-questions-row');
    const noQuestionsRow = document.getElementById('no-questions-row');
    
    if (noQuestionsRow) return;
    
    // Update active filter badge counter
    let activeFilterCount = 0;
    if (searchQuery) activeFilterCount++;
    activeFilterCount += currentStatusFilters.size;
    activeFilterCount += currentDifficultyFilters.size;
    activeFilterCount += currentAuthorFilters.size;
    
    const badge = document.getElementById('active-filters-badge');
    if (badge) {
        if (activeFilterCount > 0) {
            badge.textContent = activeFilterCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }
    
    // 1. Filter rows
    let matchingRows = rows.filter(row => {
        const id = (row.getAttribute('data-id') || '').toLowerCase();
        const title = (row.getAttribute('data-title') || '').toLowerCase();
        const status = row.getAttribute('data-status') || '';
        const difficulty = row.getAttribute('data-difficulty') || '';
        const author = row.getAttribute('data-author') || '';
        
        const matchSearch = !searchQuery || title.includes(searchQuery) || id.includes(searchQuery) || (`#${id}`).includes(searchQuery) || author.toLowerCase().includes(searchQuery);
        const matchStatus = (currentStatusFilters.size === 0) || currentStatusFilters.has(status);
        const matchDifficulty = (currentDifficultyFilters.size === 0) || currentDifficultyFilters.has(difficulty);
        const matchAuthor = (currentAuthorFilters.size === 0) || Array.from(currentAuthorFilters).some(filterVal => {
            if (filterVal === 'unassigned') {
                return !author;
            }
            return author === filterVal;
        });
        
        return matchSearch && matchStatus && matchDifficulty && matchAuthor;
    });
    
    const statusWeight = {
        'Accepted': 3,
        'Attempted': 2,
        'Unattempted': 1
    };
    
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
        const aStatus = a.getAttribute('data-status') || '';
        const bStatus = b.getAttribute('data-status') || '';
        
        let result = 0;
        switch(currentSortColumn) {
            case 'id':
                result = aId - bId;
                break;
            case 'title':
                result = aTitle.localeCompare(bTitle);
                break;
            case 'difficulty':
                result = (aDiff - bDiff) || (aId - bId);
                break;
            case 'solved':
                result = (aSolved - bSolved) || (aId - bId);
                break;
            case 'status':
                result = ((statusWeight[aStatus] || 0) - (statusWeight[bStatus] || 0)) || (aId - bId);
                break;
            default:
                result = aId - bId;
        }
        
        return (currentSortOrder === 'asc') ? result : -result;
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
            row.style.display = 'table-row';
        } else {
            row.style.display = 'none';
        }
    });
    
    // Show/hide no matches notification
    if (noMatchesRow) {
        noMatchesRow.style.display = (totalMatching === 0) ? 'table-row' : 'none';
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
            ellipsis.className = 'pagination-ellipsis';
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
            ellipsis.className = 'pagination-ellipsis';
            pagesContainer.appendChild(ellipsis);
        }
        const pBtn = createPageBtn(totalPages, page);
        pagesContainer.appendChild(pBtn);
    }
}

function createPageBtn(p, activePage) {
    const pBtn = document.createElement('button');
    pBtn.type = 'button';
    pBtn.className = `pagination-num-btn ${p === activePage ? 'active' : ''}`;
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
    updateSortIcons();
    initAuthorFilters();
    applyQuestionsFilterAndSort(true);
    
    const authorContainer = document.getElementById('author-pills-container');
    if (authorContainer) {
        authorContainer.addEventListener('click', (e) => {
            const pill = e.target.closest('.filter-pill');
            if (!pill) return;
            if (pill.id === 'btn-show-more-authors') {
                showMoreAuthors();
                return;
            }
            const val = pill.getAttribute('data-value');
            if (val !== null) {
                setAuthorFilter(val);
            }
        });
    }
});
