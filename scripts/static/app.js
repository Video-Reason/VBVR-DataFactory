// Generator Test Runner - Frontend JavaScript

let generators = [];
let results = [];
let pollInterval = null;
let sortColumn = null;
let sortDirection = 'asc';

// Initialize
document.addEventListener('DOMContentLoaded', loadGenerators);

// ==================== Generator Functions ====================

async function loadGenerators() {
    try {
        const resp = await fetch('/api/generators');
        const data = await resp.json();
        generators = data.generators;
        renderGeneratorList();
    } catch (e) {
        document.getElementById('generatorList').innerHTML =
            '<p class="text-red-500 text-sm">Failed to load generators</p>';
    }
}

function renderGeneratorList() {
    const container = document.getElementById('generatorList');
    if (generators.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No generators found</p>';
        return;
    }

    container.innerHTML = generators.map(g => `
        <label class="checkbox-item flex items-center p-2 rounded cursor-pointer">
            <input type="checkbox" value="${g}" onchange="updateSelectedCount()"
                class="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500">
            <span class="ml-2 text-sm text-gray-700">${g}</span>
        </label>
    `).join('');
}

function getSelectedGenerators() {
    return Array.from(document.querySelectorAll('#generatorList input:checked'))
        .map(cb => cb.value);
}

function updateSelectedCount() {
    const count = getSelectedGenerators().length;
    document.getElementById('selectedCount').textContent =
        `${count} generator${count !== 1 ? 's' : ''} selected`;
}

function selectAll() {
    document.querySelectorAll('#generatorList input').forEach(cb => cb.checked = true);
    updateSelectedCount();
}

function selectNone() {
    document.querySelectorAll('#generatorList input').forEach(cb => cb.checked = false);
    updateSelectedCount();
}

// ==================== Test Functions ====================

async function runTests() {
    const selected = getSelectedGenerators();
    if (selected.length === 0) {
        alert('Please select at least one generator');
        return;
    }

    const numSamples = parseInt(document.getElementById('numSamples').value) || 3;
    const seedInput = document.getElementById('seed').value;
    const seed = seedInput ? parseInt(seedInput) : null;

    document.getElementById('runBtn').disabled = true;
    document.getElementById('progressSection').classList.remove('hidden');
    document.getElementById('resultsSection').classList.remove('hidden');
    document.getElementById('resultsTable').innerHTML = '';
    results = [];

    try {
        const resp = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ generators: selected, num_samples: numSamples, seed })
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert(err.error || 'Failed to start tests');
            document.getElementById('runBtn').disabled = false;
            return;
        }

        // Start polling for progress
        pollInterval = setInterval(pollStatus, 1000);
    } catch (e) {
        alert('Failed to start tests: ' + e.message);
        document.getElementById('runBtn').disabled = false;
    }
}

async function pollStatus() {
    try {
        const [statusResp, resultsResp] = await Promise.all([
            fetch('/api/status'),
            fetch('/api/results')
        ]);

        const status = await statusResp.json();
        const data = await resultsResp.json();

        // Update progress
        const pct = status.total > 0 ? (status.completed / status.total * 100) : 0;
        document.getElementById('progressBar').style.width = `${pct}%`;
        document.getElementById('progressText').textContent =
            `${status.completed}/${status.total} completed`;
        document.getElementById('currentGenerator').textContent =
            status.running ? `Testing: ${status.current_generator}` : 'Done';

        // Update results
        results = data.results;
        renderResults();
        updateSummary(data.summary);

        // Stop polling when done
        if (!status.running) {
            clearInterval(pollInterval);
            pollInterval = null;
            document.getElementById('runBtn').disabled = false;
        }
    } catch (e) {
        console.error('Poll error:', e);
    }
}

// ==================== Results Functions ====================

function renderResults() {
    const tbody = document.getElementById('resultsTable');
    tbody.innerHTML = results.map((r, i) => {
        const hasDetails = r.error || (r.validation && !r.validation.all_valid);
        const expandIcon = hasDetails ? `<span id="icon-${i}" class="text-gray-400">▶</span>` : '';

        return `
            <tr class="border-b hover:bg-gray-50 ${hasDetails ? 'cursor-pointer' : ''}"
                ${hasDetails ? `onclick="toggleDetails(${i})"` : ''}>
                <td class="py-3 px-2 text-center">${expandIcon}</td>
                <td class="py-3 px-4 font-mono text-xs">${r.generator}</td>
                <td class="py-3 px-4">
                    <span class="px-2 py-1 rounded-full text-xs font-medium ${r.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${r.success ? 'PASS' : 'FAIL'}
                    </span>
                </td>
                <td class="py-3 px-4">${r.num_samples_generated}/${r.num_samples_requested}</td>
                <td class="py-3 px-4">${r.duration_seconds.toFixed(2)}s</td>
                <td class="py-3 px-4">${r.seconds_per_sample.toFixed(2)}s</td>
                <td class="py-3 px-4">${r.peak_memory_mb.toFixed(1)} MB</td>
                <td class="py-3 px-4">
                    ${r.error ? `<span class="text-red-600 text-xs">Error</span>` :
                      `<span class="${r.validation.all_valid ? 'text-green-600' : 'text-yellow-600'}">${r.validation.valid_count}/${r.validation.valid_count + r.validation.invalid_count}</span>`}
                </td>
            </tr>
            ${hasDetails ? `
            <tr id="details-${i}" class="hidden bg-gray-50">
                <td colspan="9" class="p-4">
                    ${r.error ? `
                        <div class="mb-2">
                            <span class="font-medium text-red-700">Error:</span>
                            <pre class="mt-1 p-3 bg-red-50 rounded text-red-800 text-xs whitespace-pre-wrap overflow-x-auto">${escapeHtml(r.error)}</pre>
                        </div>
                    ` : ''}
                    ${r.validation && !r.validation.all_valid ? `
                        <div>
                            <span class="font-medium text-yellow-700">Validation Issues:</span>
                            <ul class="mt-1 text-sm text-gray-600">
                                ${r.validation.details.filter(v => !v.valid).map(v => `
                                    <li class="ml-4">Sample ${v.sample_id}: missing ${v.missing_required.join(', ')}</li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </td>
            </tr>
            ` : ''}
        `;
    }).join('');
}

function updateSummary(summary) {
    const el = document.getElementById('summary');
    if (summary.running) {
        el.innerHTML = `<span class="text-blue-600">Running...</span>`;
    } else {
        el.innerHTML = `
            <span class="text-green-600">${summary.passed} passed</span> /
            <span class="text-red-600">${summary.failed} failed</span>
        `;
    }
}

function sortTable(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'asc';
    }

    const getValue = (r) => {
        switch (column) {
            case 'generator': return r.generator;
            case 'status': return r.success ? 1 : 0;
            case 'samples': return r.num_samples_generated;
            case 'duration': return r.duration_seconds;
            case 'per_sample': return r.seconds_per_sample;
            case 'memory': return r.peak_memory_mb;
            default: return 0;
        }
    };

    results.sort((a, b) => {
        const aVal = getValue(a);
        const bVal = getValue(b);
        const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
        return sortDirection === 'asc' ? cmp : -cmp;
    });

    // Update header indicators
    document.querySelectorAll('th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });

    renderResults();
}

function toggleDetails(index) {
    const detailRow = document.getElementById(`details-${index}`);
    const icon = document.getElementById(`icon-${index}`);
    if (detailRow) {
        detailRow.classList.toggle('hidden');
        if (icon) {
            icon.textContent = detailRow.classList.contains('hidden') ? '▶' : '▼';
        }
    }
}

// ==================== Export Functions ====================

function exportJSON() {
    if (results.length === 0) {
        alert('No results to export');
        return;
    }
    const blob = new Blob([JSON.stringify(results, null, 2)], {type: 'application/json'});
    downloadFile(blob, 'test-results.json');
}

function exportCSV() {
    if (results.length === 0) {
        alert('No results to export');
        return;
    }
    const headers = ['Generator', 'Status', 'Samples Generated', 'Samples Requested', 'Duration (s)', 'Per Sample (s)', 'Memory (MB)', 'Error'];
    const rows = results.map(r => [
        r.generator,
        r.success ? 'PASS' : 'FAIL',
        r.num_samples_generated,
        r.num_samples_requested,
        r.duration_seconds.toFixed(2),
        r.seconds_per_sample.toFixed(2),
        r.peak_memory_mb.toFixed(1),
        r.error ? `"${r.error.replace(/"/g, '""')}"` : ''
    ]);
    const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
    const blob = new Blob([csv], {type: 'text/csv'});
    downloadFile(blob, 'test-results.csv');
}

function downloadFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ==================== Utility Functions ====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== Repo Management Functions ====================

let remoteRepos = [];
let downloadPollInterval = null;

async function loadRemoteRepos() {
    const btn = document.getElementById('loadReposBtn');
    btn.disabled = true;
    btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Loading...';

    try {
        const resp = await fetch('/api/remote-repos');
        if (!resp.ok) {
            const err = await resp.json();
            alert(err.error || 'Failed to load repos');
            return;
        }
        const data = await resp.json();
        remoteRepos = data.repos;
        renderRepoList();
    } catch (e) {
        alert('Failed to load repos: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Load from GitHub';
    }
}

function renderRepoList() {
    const container = document.getElementById('repoList');
    const filter = document.getElementById('repoFilter').value.toLowerCase();

    const filtered = remoteRepos.filter(r => r.name.toLowerCase().includes(filter));

    if (filtered.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No repos found</p>';
        return;
    }

    container.innerHTML = filtered.map(r => {
        let badge = '';
        if (!r.downloaded) {
            badge = '<span class="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">Not downloaded</span>';
        } else if (r.up_to_date === false) {
            badge = '<span class="px-2 py-0.5 text-xs rounded-full bg-yellow-100 text-yellow-800">Outdated</span>';
        } else if (r.up_to_date === true) {
            badge = '<span class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800">Up-to-date</span>';
        } else {
            badge = '<span class="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">Downloaded</span>';
        }
        return `
            <label class="checkbox-item flex items-center p-2 rounded cursor-pointer">
                <input type="checkbox" value="${r.name}" onchange="updateRepoSelectedCount()"
                    class="repo-checkbox w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500">
                <span class="ml-2 text-sm text-gray-700 flex-1">${r.name}</span>
                ${badge}
            </label>
        `;
    }).join('');
}

function filterRepos() {
    renderRepoList();
}

function getSelectedRepos() {
    return Array.from(document.querySelectorAll('.repo-checkbox:checked')).map(cb => cb.value);
}

function updateRepoSelectedCount() {
    const count = getSelectedRepos().length;
    document.getElementById('repoSelectedCount').textContent =
        `${count} repo${count !== 1 ? 's' : ''} selected`;
}

function selectAllRepos() {
    document.querySelectorAll('.repo-checkbox').forEach(cb => cb.checked = true);
    updateRepoSelectedCount();
}

function selectNotDownloaded() {
    document.querySelectorAll('.repo-checkbox').forEach(cb => {
        const repo = remoteRepos.find(r => r.name === cb.value);
        cb.checked = repo && !repo.downloaded;
    });
    updateRepoSelectedCount();
}

function selectOutdated() {
    document.querySelectorAll('.repo-checkbox').forEach(cb => {
        const repo = remoteRepos.find(r => r.name === cb.value);
        cb.checked = repo && repo.downloaded && repo.up_to_date === false;
    });
    updateRepoSelectedCount();
}

function selectNoneRepos() {
    document.querySelectorAll('.repo-checkbox').forEach(cb => cb.checked = false);
    updateRepoSelectedCount();
}

async function downloadRepos() {
    const selected = getSelectedRepos();
    if (selected.length === 0) {
        alert('Please select at least one repo to download');
        return;
    }

    document.getElementById('downloadBtn').disabled = true;
    document.getElementById('downloadSection').classList.remove('hidden');
    document.getElementById('downloadResult').classList.add('hidden');
    document.getElementById('downloadProgressBar').style.width = '0%';

    try {
        const resp = await fetch('/api/download-repos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repos: selected })
        });
        if (!resp.ok) {
            const err = await resp.json();
            alert(err.error || 'Failed to start download');
            document.getElementById('downloadBtn').disabled = false;
            return;
        }

        downloadPollInterval = setInterval(pollDownloadStatus, 500);
    } catch (e) {
        alert('Failed to start download: ' + e.message);
        document.getElementById('downloadBtn').disabled = false;
    }
}

async function pollDownloadStatus() {
    try {
        const resp = await fetch('/api/download-status');
        const status = await resp.json();

        const pct = status.total > 0 ? (status.completed / status.total * 100) : 0;
        document.getElementById('downloadProgressBar').style.width = `${pct}%`;
        document.getElementById('downloadProgressText').textContent =
            `${status.completed}/${status.total} repos`;
        document.getElementById('downloadCurrentRepo').textContent =
            status.running ? status.current_repo : 'Done';

        if (!status.running) {
            clearInterval(downloadPollInterval);
            downloadPollInterval = null;
            document.getElementById('downloadBtn').disabled = false;

            // Show result
            const resultEl = document.getElementById('downloadResult');
            resultEl.classList.remove('hidden');
            if (status.error) {
                resultEl.innerHTML = `<span class="text-red-600">Error: ${status.error}</span>`;
            } else {
                resultEl.innerHTML = `
                    <span class="text-green-600">${status.downloaded_count} new repos downloaded</span>,
                    <span class="text-blue-600">${status.updated_count} repos updated</span>
                `;
            }

            // Reload both lists
            loadRemoteRepos();
            loadGenerators();
        }
    } catch (e) {
        console.error('Download poll error:', e);
    }
}
