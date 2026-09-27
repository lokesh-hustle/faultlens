/**
 * FaultLens Frontend - Log Viewer Component
 * Displays the smoking gun error stack trace and automated remediation summary.
 */

window.LogViewer = {
    render(rcaReport) {
        if (!rcaReport) return;

        // Incident ID & Severity Badge
        const incIdEl = document.getElementById('rca-incident-id');
        if (incIdEl) incIdEl.textContent = rcaReport.incident_id || 'RCA-ACTIVE';

        const trigSvcEl = document.getElementById('rca-trigger-service');
        if (trigSvcEl) trigSvcEl.textContent = rcaReport.trigger_service || 'unknown';

        const rootSvcEl = document.getElementById('rca-root-service');
        if (rootSvcEl) rootSvcEl.textContent = rcaReport.root_cause_service || 'unknown';

        const cascadingEl = document.getElementById('rca-is-cascading');
        if (cascadingEl) {
            cascadingEl.textContent = rcaReport.is_cascading_failure ? 'YES (Cascading Propagation)' : 'NO (Direct Failure)';
            cascadingEl.className = rcaReport.is_cascading_failure ? 'meta-val highlight-amber' : 'meta-val';
        }

        const traceIdEl = document.getElementById('rca-trace-id');
        if (traceIdEl) traceIdEl.textContent = rcaReport.primary_trace_id || 'N/A';

        const rootMsgEl = document.getElementById('rca-root-message');
        if (rootMsgEl) rootMsgEl.textContent = rcaReport.root_cause_message || 'Anomaly isolated';

        const remEl = document.getElementById('rca-remediation-text');
        if (remEl) remEl.textContent = rcaReport.remediation_recommendation || 'Inspect logs for service node.';

        // Stack trace
        const stackNodeTag = document.getElementById('stack-node-tag');
        if (stackNodeTag) stackNodeTag.textContent = `Node: ${rcaReport.root_cause_service}`;

        const stackTraceCode = document.getElementById('rca-stack-trace');
        if (stackTraceCode) stackTraceCode.textContent = rcaReport.stack_trace || 'No stack trace details available.';
    }
};
