/**
 * FaultLens Frontend - Metrics Panel Component
 * Displays service metrics radar and anomaly flags.
 */

window.MetricsPanel = {
    render(containerId, nodes) {
        const container = document.getElementById(containerId);
        if (!container) return;

        // Clear existing children securely
        container.textContent = '';

        (nodes || []).forEach(node => {
            const card = document.createElement('div');
            card.className = `metric-node-card status-${node.health_status || 'HEALTHY'}`;

            const nameEl = document.createElement('div');
            nameEl.className = 'node-card-name';
            nameEl.textContent = node.name || node.id;

            const list = document.createElement('div');
            list.className = 'node-card-metrics-list';

            const errRow = document.createElement('div');
            errRow.textContent = `Error Rate: ${node.error_rate_pct || 0}%`;
            if ((node.error_rate_pct || 0) > 5) errRow.style.color = '#ef4444';

            const latRow = document.createElement('div');
            latRow.textContent = `P95 Latency: ${node.latency_p95_ms || 25}ms`;

            const cpuRow = document.createElement('div');
            cpuRow.textContent = `CPU Usage: ${node.cpu_usage_pct || 15}%`;

            list.appendChild(errRow);
            list.appendChild(latRow);
            list.appendChild(cpuRow);

            card.appendChild(nameEl);
            card.appendChild(list);
            container.appendChild(card);
        });
    }
};
