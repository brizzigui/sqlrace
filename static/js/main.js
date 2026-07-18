// ==========================================================================
// SQL Race Main Javascript Controller
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    initTimers();
    initCodeEditor();
    initSubmissionHandler();
});

/* --------------------------------------------------------------------------
   1. Timers Handler
   -------------------------------------------------------------------------- */
function initTimers() {
    const timerElements = document.querySelectorAll('.contest-timer');
    if (timerElements.length === 0) return;

    function updateTimers() {
        const now = new Date();

        timerElements.forEach(el => {
            const startTimeStr = el.getAttribute('data-starttime');
            const endTimeStr = el.getAttribute('data-endtime');
            
            const start = startTimeStr ? new Date(startTimeStr) : null;
            const end = new Date(endTimeStr);

            if (start && now < start) {
                // Upcoming Contest
                const diffMs = start - now;
                el.textContent = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.starts_in : 'Starts in: ') + formatTimeDelta(diffMs);
            } else if (now >= start && now <= end) {
                // Active Contest
                const diffMs = end - now;
                el.textContent = formatTimeDelta(diffMs);
            } else {
                // Ended Contest
                el.textContent = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.ended : 'Ended');
                el.style.color = 'var(--text-muted)';
            }
        });
    }

    updateTimers();
    setInterval(updateTimers, 1000);
}

function formatTimeDelta(ms) {
    if (ms < 0) return "00:00:00";
    
    let seconds = Math.floor(ms / 1000);
    let minutes = Math.floor(seconds / 60);
    let hours = Math.floor(minutes / 60);
    let days = Math.floor(hours / 24);

    hours = hours % 24;
    minutes = minutes % 60;
    seconds = seconds % 60;

    let timeString = "";
    if (days > 0) {
        timeString += days + "d ";
    }
    
    timeString += String(hours).padStart(2, '0') + ":" + 
                  String(minutes).padStart(2, '0') + ":" + 
                  String(seconds).padStart(2, '0');
                  
    return timeString;
}

/* --------------------------------------------------------------------------
   2. Code Editor (Tab Handling)
   -------------------------------------------------------------------------- */
function initCodeEditor() {
    const editor = document.getElementById('sql-code-editor');
    if (!editor) return;

    editor.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = editor.selectionStart;
            const end = editor.selectionEnd;

            // Insert 4 spaces for tab
            const tabSpaces = "    ";
            editor.value = editor.value.substring(0, start) + tabSpaces + editor.value.substring(end);
            
            // Put caret at right position
            editor.selectionStart = editor.selectionEnd = start + tabSpaces.length;
        }
    });
}

/* --------------------------------------------------------------------------
   3. Async Submissions and Console Console Output
   -------------------------------------------------------------------------- */
function initSubmissionHandler() {
    const form = document.getElementById('submission-form');
    if (!form) return;

    const editor = document.getElementById('sql-code-editor');
    const runBtn = document.getElementById('run-btn');
    const spinner = document.getElementById('loading-spinner');
    
    // Output DOM elements
    const emptyState = document.getElementById('empty-console-state');
    const statusBanner = document.getElementById('result-status-banner');
    const statusText = document.getElementById('result-status-text');
    const errorContainer = document.getElementById('result-error-container');
    const errorText = document.getElementById('result-error-text');
    const tableContainer = document.getElementById('result-table-container');
    const tableHeader = document.getElementById('result-table-header');
    const tableBody = document.getElementById('result-table-body');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const queryValue = editor.value.trim();
        if (!queryValue) return;

        // Visual state updates (Disable buttons, show loader)
        runBtn.disabled = true;
        spinner.classList.remove('hidden');

        // Clean output console
        emptyState.classList.add('hidden');
        statusBanner.className = 'status-banner hidden';
        errorContainer.classList.add('hidden');
        tableContainer.classList.add('hidden');
        tableHeader.innerHTML = '';
        tableBody.innerHTML = '';

        const submitUrl = form.getAttribute('data-submiturl');

        try {
            const response = await fetch(submitUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: queryValue })
            });

            const result = await response.json();
            
            // Re-enable runner
            runBtn.disabled = false;
            spinner.classList.add('hidden');

            // Render Output Status
            statusBanner.classList.remove('hidden');
            
            if (result.status === 'Accepted') {
                statusBanner.classList.add('status-banner-accepted');
                statusText.innerHTML = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.accepted : '🟢 Accepted (AC)');
                triggerConfetti();
            } else if (result.status === 'Wrong Answer') {
                statusBanner.classList.add('status-banner-wrong');
                statusText.innerHTML = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.wrong_answer : '🔴 Wrong Answer (WA)');
                
                // Show assertion warning
                errorContainer.classList.remove('hidden');
                errorText.textContent = result.error_message || (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.empty_answer_mismatch : 'The outputs of your query do not match the expected answer.');
            } else {
                statusBanner.classList.add('status-banner-runtime');
                statusText.innerHTML = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.runtime_error : '⚠️ Runtime Error (RE)');
                
                // Show syntax error
                errorContainer.classList.remove('hidden');
                errorText.textContent = result.error_message;
            }

            // Render Table (for AC / WA)
            if (result.columns && result.columns.length > 0 && result.rows) {
                tableContainer.classList.remove('hidden');
                
                // Headers
                result.columns.forEach(col => {
                    const th = document.createElement('th');
                    th.textContent = col;
                    tableHeader.appendChild(th);
                });

                // Rows
                if (result.rows.length === 0) {
                    const tr = document.createElement('tr');
                    const td = document.createElement('td');
                    td.setAttribute('colspan', result.columns.length);
                    td.className = 'text-center text-muted';
                    td.textContent = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.query_empty_set : 'Empty set (0 rows returned).');
                    tr.appendChild(td);
                    tableBody.appendChild(tr);
                } else {
                    result.rows.forEach(rowData => {
                        const tr = document.createElement('tr');
                        rowData.forEach(cellValue => {
                            const td = document.createElement('td');
                            td.textContent = cellValue === null ? 'NULL' : cellValue;
                            tr.appendChild(td);
                        });
                        tableBody.appendChild(tr);
                    });
                }
            }

            // Append to History Log
            prependToHistory(queryValue, result.status, result.error_message, result.submitted_at);

        } catch (err) {
            runBtn.disabled = false;
            spinner.classList.add('hidden');
            statusBanner.className = 'status-banner status-banner-runtime';
            statusText.innerHTML = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.system_issue : '⚠️ System Connection Issue');
            errorContainer.classList.remove('hidden');
            errorText.textContent = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.failed_communicate : 'Failed to communicate with the judge endpoint: ') + err.message;
        }
    });
}

function prependToHistory(query, status, errorMessage, timeStr) {
    const historyContainer = document.querySelector('.history-list');
    if (!historyContainer) return;

    // Remove empty list state message if it exists
    const emptyMsg = historyContainer.querySelector('.console-message');
    if (emptyMsg) {
        emptyMsg.remove();
    }

    const item = document.createElement('div');
    item.className = 'history-item fade-in';

    const header = document.createElement('div');
    header.className = 'history-item-header';
    header.innerHTML = `
        <span class="status-badge badge-${status.toLowerCase().replace(' ', '')}">${status}</span>
        <span class="history-time">${timeStr}</span>
    `;

    const queryBox = document.createElement('div');
    queryBox.className = 'history-query-box';
    queryBox.innerHTML = `<pre><code class="language-sql">${escapeHtml(query)}</code></pre>`;

    item.appendChild(header);
    item.appendChild(queryBox);

    if (errorMessage) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'history-error';
        errorDiv.innerHTML = `<small>Error: ${escapeHtml(errorMessage)}</small>`;
        item.appendChild(errorDiv);
    }

    historyContainer.insertBefore(item, historyContainer.firstChild);

    // Update history tab badge counter
    const historyTabBtn = document.querySelectorAll('.console-tab-btn')[1];
    if (historyTabBtn) {
        const currentCount = historyContainer.querySelectorAll('.history-item').length;
        historyTabBtn.textContent = `Submission History (${currentCount})`;
    }
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/* --------------------------------------------------------------------------
   4. Console Window Tab Switching
   -------------------------------------------------------------------------- */
window.switchConsoleTab = function(tabName) {
    // Buttons toggle
    const buttons = document.querySelectorAll('.console-tab-btn');
    buttons[0].classList.toggle('active', tabName === 'result');
    buttons[1].classList.toggle('active', tabName === 'history');

    // Panes toggle
    document.getElementById('console-tab-result').classList.toggle('active', tabName === 'result');
    document.getElementById('console-tab-history').classList.toggle('active', tabName === 'history');
};

/* --------------------------------------------------------------------------
   5. Dynamic Scoreboard Refreshes
   -------------------------------------------------------------------------- */
window.refreshLeaderboard = async function(contestId) {
    const btn = document.getElementById('refresh-board-btn');
    const tableBody = document.getElementById('leaderboard-body-el');
    if (!btn || !tableBody) return;

    btn.disabled = true;
    btn.textContent = (window.JS_TRANSLATIONS ? '🔄 ' + window.JS_TRANSLATIONS.loading : '🔄 Loading...');

    try {
        const res = await fetch(`/contest/${contestId}/leaderboard/data`);
        if (!res.ok) throw new Error('Contest status error');
        
        const data = await res.json();
        
        // Render updated body
        tableBody.innerHTML = '';
        
        if (data.leaderboard.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="${4 + data.questions.length}" class="text-muted text-center" style="padding: 40px;">
                        ${window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.no_teams_registered : 'No teams have registered or submitted queries yet.'}
                    </td>
                </tr>
            `;
        } else {
            data.leaderboard.forEach(row => {
                const tr = document.createElement('tr');
                tr.className = 'leaderboard-row';
                
                // My team class identifier check
                // We fetch the team indicator from DOM or session username
                const activeUserEl = document.querySelector('.nav-user strong');
                const isMyTeam = activeUserEl && activeUserEl.textContent.trim() === row.username;
                if (isMyTeam) {
                    tr.classList.add('current-team-row');
                }

                // Rank
                let rankVal = row.rank;
                if (row.rank === 1) rankVal = '🥇';
                else if (row.rank === 2) rankVal = '🥈';
                else if (row.rank === 3) rankVal = '🥉';

                let rankCell = `<td class="rank-col">${rankVal}</td>`;
                let nameCell = `<td class="team-name-col">
                                    <strong>${escapeHtml(row.username)}</strong>
                                    ${isMyTeam ? `<span class="my-team-label">(${window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.you : 'You'})</span>` : ''}
                                </td>`;
                let solvedCell = `<td class="solved-col">${row.solved_count}</td>`;
                let penaltyCell = `<td class="penalty-col">${row.total_penalty}</td>`;

                tr.innerHTML += rankCell + nameCell + solvedCell + penaltyCell;

                // Problem cells
                data.questions.forEach(q => {
                    const cellData = row.problems[q.id];
                    const td = document.createElement('td');
                    
                    if (cellData.solved) {
                        td.className = 'cell-problem cell-accepted';
                        td.innerHTML = `
                            <div class="cell-tries">+${cellData.attempts - 1}</div>
                            <div class="cell-min">${cellData.penalty}</div>
                        `;
                    } else if (cellData.attempts > 0) {
                        td.className = 'cell-problem cell-failed';
                        td.innerHTML = `
                            <div class="cell-tries">-${cellData.attempts}</div>
                            <div class="cell-min">--</div>
                        `;
                    } else {
                        td.className = 'cell-problem cell-empty';
                        td.innerHTML = `<span class="cell-dot">&middot;</span>`;
                    }
                    tr.appendChild(td);
                });

                tableBody.appendChild(tr);
            });
        }

        btn.disabled = false;
        btn.textContent = (window.JS_TRANSLATIONS ? '🔄 ' + window.JS_TRANSLATIONS.live_refresh : '🔄 Live Refresh');
    } catch (err) {
        console.error(err);
        btn.disabled = false;
        btn.textContent = (window.JS_TRANSLATIONS ? window.JS_TRANSLATIONS.refresh_failed : '⚠️ Refresh Failed');
        setTimeout(() => {
            btn.textContent = (window.JS_TRANSLATIONS ? '🔄 ' + window.JS_TRANSLATIONS.live_refresh : '🔄 Live Refresh');
        }, 3000);
    }
};

/* Confetti Effect */
function triggerConfetti() {
    if (!document.getElementById('confetti-style')) {
        const style = document.createElement('style');
        style.id = 'confetti-style';
        style.textContent = `
            @keyframes confetti-fall {
                0% {
                    transform: translateY(0) rotate(0deg);
                    opacity: 1;
                }
                100% {
                    transform: translateY(105vh) rotate(720deg);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }

    const colors = ['#00f2fe', '#4facfe', '#10b981', '#3b82f6', '#f43f5e', '#fbbf24', '#a78bfa'];
    const container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.top = '0';
    container.style.left = '0';
    container.style.width = '100vw';
    container.style.height = '100vh';
    container.style.pointerEvents = 'none';
    container.style.zIndex = '9999';
    container.style.overflow = 'hidden';
    document.body.appendChild(container);

    const count = 120;
    for (let i = 0; i < count; i++) {
        const confetti = document.createElement('div');
        const color = colors[Math.floor(Math.random() * colors.length)];
        const left = Math.random() * 100 + 'vw';
        const size = Math.random() * 10 + 6 + 'px';
        const delay = Math.random() * 1.5;
        const duration = Math.random() * 2.5 + 2.5;
        
        confetti.style.position = 'absolute';
        confetti.style.top = '-20px';
        confetti.style.left = left;
        confetti.style.width = size;
        confetti.style.height = size;
        confetti.style.backgroundColor = color;
        confetti.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
        confetti.style.opacity = Math.random() * 0.4 + 0.6;
        confetti.style.transform = `rotate(${Math.random() * 360}deg)`;
        confetti.style.animation = `confetti-fall ${duration}s linear ${delay}s forwards`;
        
        container.appendChild(confetti);
    }
    
    setTimeout(() => {
        container.remove();
    }, 6000);
}
