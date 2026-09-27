/**
 * FaultLens Frontend - Trace Inspector Component
 * Renders parent-child waterfall trace spans and isolates failure hops.
 */

window.TraceInspector = {
    render(containerId, rcaReport) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.textContent = '';

        const chain = (rcaReport && rcaReport.path_traversal_chain) || [];
        const label = document.getElementById('trace-summary-label');
        if (label) {
            label.textContent = `${chain.length} Hops Traversed | Trace ID: ${rcaReport.primary_trace_id || 'N/A'}`;
        }

        if (chain.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-trace';
            empty.textContent = 'No trace waterfall data available for current selection.';
            container.appendChild(empty);
            return;
        }

        // Calculate max duration for percentage bars
        const maxDuration = Math.max(...chain.map(c => c.duration_ms || 100), 100);

        chain.forEach((hop, idx) => {
            const row = document.createElement('div');
            row.className = `waterfall-row ${hop.is_error ? 'is-failure-span' : ''}`;

            // 1. Service & Hop Indicator
            const svcCol = document.createElement('div');
            svcCol.className = 'span-service-name';

            const bullet = document.createElement('div');
            bullet.className = 'hop-bullet';
            bullet.textContent = String(idx + 1);

            const name = document.createElement('span');
            name.textContent = hop.service;

            svcCol.appendChild(bullet);
            svcCol.appendChild(name);

            // 2. Status Code Pill
            const statusCol = document.createElement('div');
            const statusPill = document.createElement('span');
            statusPill.className = `span-status-pill ${hop.is_error ? 'status-error' : 'status-200'}`;
            statusPill.textContent = `HTTP ${hop.status_code || (hop.is_error ? 500 : 200)}`;
            statusCol.appendChild(statusPill);

            // 3. Span Duration
            const durCol = document.createElement('div');
            durCol.className = 'span-duration';
            durCol.textContent = `${hop.duration_ms ? hop.duration_ms.toFixed(1) : 45.0}ms`;

            // 4. Waterfall Bar Track
            const barCol = document.createElement('div');
            barCol.className = 'waterfall-bar-track';

            const fill = document.createElement('div');
            fill.className = `waterfall-bar-fill ${hop.is_error ? 'fill-error' : ''}`;
            const pct = Math.min(100, Math.max(10, ((hop.duration_ms || 50) / maxDuration) * 100));
            fill.style.width = `${pct}%`;

            barCol.appendChild(fill);

            row.appendChild(svcCol);
            row.appendChild(statusCol);
            row.appendChild(durCol);
            row.appendChild(barCol);

            container.appendChild(row);
        });
    }
};
