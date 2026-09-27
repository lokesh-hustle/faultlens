/**
 * FaultLens Frontend - Blast Radius & User Impact Component
 * Quantizes unique affected users across time chunks with grace buffers.
 */

window.BlastRadius = {
    render(rcaReport) {
        if (!rcaReport) return;

        const blast = rcaReport.blast_radius || {};

        // Update Unique Users Counter
        const uUsersEl = document.getElementById('blast-unique-users');
        if (uUsersEl) uUsersEl.textContent = blast.unique_affected_users_count || 0;

        const subUsersEl = document.getElementById('blast-users-sub');
        if (subUsersEl) subUsersEl.textContent = `Out of ${blast.total_users_in_window || (blast.unique_affected_users_count || 0)} active users`;

        // Update Total Errors & Error Rate
        const totalErrEl = document.getElementById('blast-total-errors');
        if (totalErrEl) totalErrEl.textContent = blast.total_errors || 0;

        const errRateEl = document.getElementById('blast-error-rate');
        if (errRateEl) errRateEl.textContent = `Error Rate: ${blast.error_rate_pct || 0}%`;

        // Update Affected Services
        const svcCountEl = document.getElementById('blast-affected-services-count');
        if (svcCountEl) svcCountEl.textContent = blast.affected_services_count || 0;

        const svcListEl = document.getElementById('blast-services-list');
        if (svcListEl) svcListEl.textContent = (blast.affected_services || []).join(', ') || 'None';

        // Update Correlated Trace IDs count
        const traceCountEl = document.getElementById('blast-trace-count');
        if (traceCountEl) traceCountEl.textContent = (blast.associated_error_trace_ids || []).length;

        // Render User ID Chips securely
        const userContainer = document.getElementById('affected-users-container');
        if (userContainer) {
            userContainer.textContent = '';
            const userIds = blast.unique_affected_user_ids || [];
            
            userIds.forEach(uid => {
                const chip = document.createElement('span');
                chip.className = 'user-chip';
                chip.textContent = uid;
                userContainer.appendChild(chip);
            });
        }

        // Setup User ID list toggle button
        const btnToggle = document.getElementById('btn-toggle-users-list');
        if (btnToggle) {
            btnToggle.onclick = () => {
                if (userContainer) userContainer.classList.toggle('hidden');
            };
        }
    }
};
