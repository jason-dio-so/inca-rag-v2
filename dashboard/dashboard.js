/**
 * INCA RAG V2 - Ops Dashboard
 * V2-9: Operations Dashboard / Visualization
 *
 * This dashboard is READ-ONLY.
 * All data comes from V2-8 metrics files.
 * No calculations are performed here.
 *
 * PROHIBITED:
 * - Recalculating metrics
 * - Modifying engine/golden
 * - Auto-generating "all is well" messages
 * - LLM-based interpretation
 */

const METRICS_BASE = '../metrics';

// Metrics file paths
const METRICS_FILES = {
    opsSummary: `${METRICS_BASE}/ops_summary.json`,
    decisionDist: `${METRICS_BASE}/decision_distribution.json`,
    partialFailure: `${METRICS_BASE}/partial_failure_rate.json`,
    evidenceQuality: `${METRICS_BASE}/evidence_quality.json`,
    sourceBoundary: `${METRICS_BASE}/source_boundary.json`,
    goldenDiff: `${METRICS_BASE}/golden_diff.json`,
};

// Chart colors
const COLORS = {
    determined: '#10b981',      // green
    no_amount: '#ef4444',       // red
    condition_mismatch: '#f59e0b', // yellow
    definition_only: '#3b82f6', // blue
    insufficient_evidence: '#8b5cf6', // purple
};

// State
let metricsData = {};
let charts = {};

/**
 * Fetch JSON file
 */
async function fetchJson(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Failed to fetch ${url}:`, error);
        return null;
    }
}

/**
 * Load all metrics
 */
async function loadMetrics() {
    const results = await Promise.all([
        fetchJson(METRICS_FILES.opsSummary),
        fetchJson(METRICS_FILES.decisionDist),
        fetchJson(METRICS_FILES.partialFailure),
        fetchJson(METRICS_FILES.evidenceQuality),
        fetchJson(METRICS_FILES.sourceBoundary),
        fetchJson(METRICS_FILES.goldenDiff),
    ]);

    metricsData = {
        opsSummary: results[0],
        decisionDist: results[1],
        partialFailure: results[2],
        evidenceQuality: results[3],
        sourceBoundary: results[4],
        goldenDiff: results[5],
    };

    return Object.values(metricsData).some(d => d !== null);
}

/**
 * Get status class from level
 */
function getStatusClass(level) {
    switch (level?.toUpperCase()) {
        case 'ERROR': return 'error';
        case 'WARNING': return 'warning';
        default: return 'ok';
    }
}

/**
 * Get status emoji
 */
function getStatusEmoji(level) {
    switch (level?.toUpperCase()) {
        case 'ERROR': return '❌';
        case 'WARNING': return '⚠️';
        default: return '✅';
    }
}

/**
 * Format percentage
 */
function formatPercent(value) {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(1)}%`;
}

/**
 * Render dashboard
 */
function renderDashboard() {
    const content = document.getElementById('content');
    const timestamp = document.getElementById('timestamp');

    // Check if data loaded
    if (!metricsData.opsSummary) {
        content.innerHTML = `
            <div class="error-state">
                <h2>❌ Metrics Not Found</h2>
                <p>Could not load metrics files from ${METRICS_BASE}/</p>
                <p>Run <code>tools/run_metrics_collect.sh</code> to generate metrics.</p>
            </div>
        `;
        return;
    }

    const summary = metricsData.opsSummary;
    const level = summary.level || 'INFO';
    const statusClass = getStatusClass(level);
    const statusEmoji = getStatusEmoji(level);

    // Update timestamp
    timestamp.textContent = `Last updated: ${summary.collected_at || 'Unknown'}`;

    // Build HTML
    content.innerHTML = `
        <!-- Status Banner -->
        <div class="status-banner ${statusClass}">
            <span class="status-icon">${statusEmoji}</span>
            <div class="status-text">
                <h2>System Status: ${summary.status || 'UNKNOWN'}</h2>
                <p>${summary.action_required ? 'Action Required' : 'No action required'}</p>
            </div>
        </div>

        <!-- Key Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="label">Determined Rate</div>
                <div class="value ${getValueClass(summary.summary?.decision_distribution?.determined_rate, 0.5, 0.3)}">
                    ${formatPercent(summary.summary?.decision_distribution?.determined_rate)}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">Partial Failure Rate</div>
                <div class="value ${getValueClass(1 - (summary.summary?.decision_distribution?.partial_failure_rate || 0), 0.5, 0.3)}">
                    ${formatPercent(summary.summary?.decision_distribution?.partial_failure_rate)}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">PASS1 Success</div>
                <div class="value ${getValueClass(summary.summary?.evidence_quality?.pass1_success_rate, 0.7, 0.5)}">
                    ${formatPercent(summary.summary?.evidence_quality?.pass1_success_rate)}
                </div>
            </div>
            <div class="metric-card">
                <div class="label">Golden Drift</div>
                <div class="value ${summary.summary?.golden_drift?.regressions > 0 ? 'error' : 'ok'}">
                    ${summary.summary?.golden_drift?.regressions || 0} regressions
                </div>
            </div>
        </div>

        <!-- Warnings/Errors -->
        ${renderWarningsErrors(summary)}

        <!-- Golden Drift Panel -->
        ${renderGoldenDriftPanel()}

        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-card">
                <h3>Decision Distribution</h3>
                <div class="chart-container">
                    <canvas id="decisionChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>Partial Failure by Type</h3>
                <div class="chart-container">
                    <canvas id="partialFailureChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>Evidence Quality</h3>
                <div class="chart-container">
                    <canvas id="evidenceChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>Source Boundary</h3>
                <div class="chart-container">
                    <canvas id="sourceBoundaryChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Decision Details Table -->
        ${renderDecisionTable()}
    `;

    // Render charts
    renderCharts();
}

/**
 * Get value class based on thresholds
 */
function getValueClass(value, warningThreshold, errorThreshold) {
    if (value === null || value === undefined) return '';
    if (value < errorThreshold) return 'error';
    if (value < warningThreshold) return 'warning';
    return 'ok';
}

/**
 * Render warnings and errors
 */
function renderWarningsErrors(summary) {
    const warnings = summary.warnings || [];
    const errors = summary.errors || [];

    if (warnings.length === 0 && errors.length === 0) {
        return '';
    }

    let html = '<div class="chart-card" style="margin-bottom: 1.5rem;">';
    html += '<h3>Alerts</h3>';

    if (errors.length > 0) {
        html += '<div style="margin-bottom: 1rem;">';
        errors.forEach(err => {
            html += `<div style="color: var(--color-error); margin-bottom: 0.5rem;">❌ ${err}</div>`;
        });
        html += '</div>';
    }

    if (warnings.length > 0) {
        html += '<div>';
        warnings.forEach(warn => {
            html += `<div style="color: var(--color-warning); margin-bottom: 0.5rem;">⚠️ ${warn}</div>`;
        });
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/**
 * Render Golden Drift Panel
 */
function renderGoldenDriftPanel() {
    const drift = metricsData.goldenDiff;
    if (!drift) {
        return '<div class="drift-panel"><h3>Golden Drift</h3><p>No drift data available</p></div>';
    }

    const diff = drift.diff || {};
    const hasDrift = (diff.regressions?.length > 0) || (diff.total_changed > 0);
    const panelClass = hasDrift ? 'drift-panel has-drift' : 'drift-panel';

    let html = `<div class="${panelClass}">`;
    html += `<h3>${hasDrift ? '🚨' : '✅'} Golden Set Drift Detection</h3>`;
    html += '<div class="drift-stats">';
    html += `
        <div class="drift-stat">
            <div class="number" style="color: ${diff.total_changed > 0 ? 'var(--color-warning)' : 'var(--color-ok)'}">
                ${diff.total_changed || 0}
            </div>
            <div class="label">Decision Changes</div>
        </div>
        <div class="drift-stat">
            <div class="number" style="color: ${diff.regressions?.length > 0 ? 'var(--color-error)' : 'var(--color-ok)'}">
                ${diff.regressions?.length || 0}
            </div>
            <div class="label">Regressions</div>
        </div>
        <div class="drift-stat">
            <div class="number">${diff.rule_changes?.length || 0}</div>
            <div class="label">Rule Changes</div>
        </div>
        <div class="drift-stat">
            <div class="number">${formatPercent(diff.change_rate)}</div>
            <div class="label">Change Rate</div>
        </div>
    `;
    html += '</div>';

    // Show regressions if any
    if (diff.regressions?.length > 0) {
        html += '<div class="table-container" style="margin-top: 1rem;">';
        html += '<table>';
        html += '<thead><tr><th>Case ID</th><th>From</th><th>To</th></tr></thead>';
        html += '<tbody>';
        diff.regressions.forEach(reg => {
            html += `<tr>
                <td>${reg.case_id}</td>
                <td><span class="badge ok">${reg.from}</span></td>
                <td><span class="badge error">${reg.to}</span></td>
            </tr>`;
        });
        html += '</tbody></table></div>';
    }

    html += '</div>';
    return html;
}

/**
 * Render decision details table
 */
function renderDecisionTable() {
    const dist = metricsData.decisionDist;
    if (!dist) return '';

    const metrics = dist.metrics || {};

    let html = '<div class="chart-card">';
    html += '<h3>Decision Details</h3>';
    html += '<div class="table-container">';
    html += '<table>';
    html += '<thead><tr><th>Decision</th><th>Count</th><th>Percentage</th><th>Status</th></tr></thead>';
    html += '<tbody>';

    const decisions = ['determined', 'no_amount', 'condition_mismatch', 'definition_only', 'insufficient_evidence'];
    decisions.forEach(decision => {
        const data = metrics[decision] || {};
        const isPartialFailure = decision !== 'determined';
        const badgeClass = isPartialFailure ? 'warning' : 'ok';

        html += `<tr>
            <td>${decision}</td>
            <td>${data.count || 0}</td>
            <td>${data.percentage?.toFixed(1) || 0}%</td>
            <td><span class="badge ${badgeClass}">${isPartialFailure ? 'Partial Failure' : 'Success'}</span></td>
        </tr>`;
    });

    html += '</tbody></table></div></div>';
    return html;
}

/**
 * Render all charts
 */
function renderCharts() {
    renderDecisionChart();
    renderPartialFailureChart();
    renderEvidenceChart();
    renderSourceBoundaryChart();
}

/**
 * Render Decision Distribution chart
 */
function renderDecisionChart() {
    const ctx = document.getElementById('decisionChart');
    if (!ctx || !metricsData.decisionDist) return;

    const metrics = metricsData.decisionDist.metrics || {};

    charts.decision = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Determined', 'No Amount', 'Condition Mismatch', 'Definition Only', 'Insufficient Evidence'],
            datasets: [{
                data: [
                    metrics.determined?.count || 0,
                    metrics.no_amount?.count || 0,
                    metrics.condition_mismatch?.count || 0,
                    metrics.definition_only?.count || 0,
                    metrics.insufficient_evidence?.count || 0,
                ],
                backgroundColor: [
                    COLORS.determined,
                    COLORS.no_amount,
                    COLORS.condition_mismatch,
                    COLORS.definition_only,
                    COLORS.insufficient_evidence,
                ],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#f1f5f9' },
                },
            },
        },
    });
}

/**
 * Render Partial Failure chart
 */
function renderPartialFailureChart() {
    const ctx = document.getElementById('partialFailureChart');
    if (!ctx || !metricsData.partialFailure) return;

    const byDecision = metricsData.partialFailure.metrics?.by_decision || {};

    charts.partialFailure = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['No Amount', 'Condition Mismatch', 'Definition Only', 'Insufficient Evidence'],
            datasets: [{
                label: 'Count',
                data: [
                    byDecision.no_amount?.count || 0,
                    byDecision.condition_mismatch?.count || 0,
                    byDecision.definition_only?.count || 0,
                    byDecision.insufficient_evidence?.count || 0,
                ],
                backgroundColor: [
                    COLORS.no_amount,
                    COLORS.condition_mismatch,
                    COLORS.definition_only,
                    COLORS.insufficient_evidence,
                ],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' },
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' },
                },
            },
        },
    });
}

/**
 * Render Evidence Quality chart
 */
function renderEvidenceChart() {
    const ctx = document.getElementById('evidenceChart');
    if (!ctx || !metricsData.evidenceQuality) return;

    const metrics = metricsData.evidenceQuality.metrics || {};

    charts.evidence = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['PASS1 Success', 'PASS2 Augmentation'],
            datasets: [{
                label: 'Rate',
                data: [
                    (metrics.pass1_success_rate?.rate || 0) * 100,
                    (metrics.pass2_augmentation_rate?.rate || 0) * 100,
                ],
                backgroundColor: [COLORS.determined, COLORS.definition_only],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: '#334155' },
                    ticks: {
                        color: '#94a3b8',
                        callback: value => `${value}%`,
                    },
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' },
                },
            },
        },
    });
}

/**
 * Render Source Boundary chart
 */
function renderSourceBoundaryChart() {
    const ctx = document.getElementById('sourceBoundaryChart');
    if (!ctx || !metricsData.sourceBoundary) return;

    const byDocType = metricsData.sourceBoundary.metrics?.by_doc_type || {};

    charts.sourceBoundary = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['약관', '사업방법서', '상품요약서', '기타'],
            datasets: [{
                data: [
                    byDocType.yakgwan?.count || 0,
                    byDocType.saeop?.count || 0,
                    byDocType.summary?.count || 0,
                    byDocType.other?.count || 0,
                ],
                backgroundColor: [
                    COLORS.determined,
                    COLORS.definition_only,
                    COLORS.condition_mismatch,
                    '#64748b',
                ],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#f1f5f9' },
                },
            },
        },
    });
}

/**
 * Initialize dashboard
 */
async function init() {
    console.log('INCA RAG V2 - Ops Dashboard initializing...');

    const loaded = await loadMetrics();

    if (loaded) {
        console.log('Metrics loaded successfully');
        renderDashboard();
    } else {
        console.error('Failed to load metrics');
        document.getElementById('content').innerHTML = `
            <div class="error-state">
                <h2>❌ Failed to Load Metrics</h2>
                <p>Could not load metrics files.</p>
                <p>Run <code>tools/run_metrics_collect.sh</code> to generate metrics.</p>
            </div>
        `;
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);
