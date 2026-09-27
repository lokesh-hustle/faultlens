/**
 * FaultLens Frontend Application Controller
 * Orchestrates API communication, component state updates, and RBAC authorization headers.
 */

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Initialize UI Components
    window.TopologyMap.init('topology-container', 'topology-canvas');

    // State
    let activeRcaReport = null;
    let topologyData = null;

    // RBAC Role Selector Listener
    const roleSelect = document.getElementById('role-selector');
    const roleBadge = document.getElementById('current-role-badge');
    const userName = document.getElementById('current-user-name');

    if (roleSelect) {
        roleSelect.addEventListener('change', (e) => {
            const role = e.target.value;
            if (roleBadge) roleBadge.textContent = role;
            if (userName) {
                if (role === 'ADMIN') userName.textContent = 'Alex Vance (Lead SRE)';
                else if (role === 'ENGINEER') userName.textContent = 'Devon Miller (Reliability Engineer)';
                else userName.textContent = 'Sam Taylor (Product Operations)';
            }
        });
    }

    // Standalone Mock Fallback Data (for file:// or offline preview)
    const fallbackMockTopology = {
        nodes: [
            { id: "api-gateway", name: "API Gateway", tier: "gateway", health_status: "CRITICAL", error_rate_pct: 42.0, latency_p95_ms: 2300, cpu_usage_pct: 50.0 },
            { id: "auth-service", name: "Auth & Session Service", tier: "auth", health_status: "HEALTHY", error_rate_pct: 0.2, latency_p95_ms: 45, cpu_usage_pct: 18.0 },
            { id: "user-db", name: "User PostgreSQL DB", tier: "database", health_status: "HEALTHY", error_rate_pct: 0.0, latency_p95_ms: 12, cpu_usage_pct: 22.0 },
            { id: "order-service", name: "Order Management Service", tier: "app", health_status: "DEGRADED", error_rate_pct: 18.4, latency_p95_ms: 2250, cpu_usage_pct: 48.0 },
            { id: "payment-gateway", name: "Payment Gateway Service", tier: "app", health_status: "CRITICAL", error_rate_pct: 65.2, latency_p95_ms: 2200, cpu_usage_pct: 75.0 },
            { id: "payment-db", name: "Payment DB Cluster", tier: "database", health_status: "CRITICAL", error_rate_pct: 88.5, latency_p95_ms: 1850, cpu_usage_pct: 98.2 },
            { id: "inventory-service", name: "Inventory Service", tier: "app", health_status: "HEALTHY", error_rate_pct: 0.5, latency_p95_ms: 85, cpu_usage_pct: 30.0 },
            { id: "inventory-db", name: "Inventory Redis Cache", tier: "database", health_status: "HEALTHY", error_rate_pct: 0.1, latency_p95_ms: 8, cpu_usage_pct: 15.0 },
            { id: "recommendation-engine", name: "ML Recommendation Engine", tier: "app", health_status: "HEALTHY", error_rate_pct: 0.8, latency_p95_ms: 110, cpu_usage_pct: 42.0 },
            { id: "third-party-stripe", name: "Stripe API (External)", tier: "third_party", health_status: "HEALTHY", error_rate_pct: 0.0, latency_p95_ms: 140, cpu_usage_pct: 0.0 }
        ],
        dependencies: [
            { source: "api-gateway", target: "auth-service", protocol: "gRPC" },
            { source: "auth-service", target: "user-db", protocol: "PostgreSQL" },
            { source: "api-gateway", target: "order-service", protocol: "HTTP/2" },
            { source: "api-gateway", target: "recommendation-engine", protocol: "gRPC" },
            { source: "order-service", target: "payment-gateway", protocol: "gRPC" },
            { source: "order-service", target: "inventory-service", protocol: "HTTP/2" },
            { source: "payment-gateway", target: "payment-db", protocol: "PostgreSQL" },
            { source: "payment-gateway", target: "third-party-stripe", protocol: "HTTPS" },
            { source: "inventory-service", target: "inventory-db", protocol: "Redis" }
        ]
    };

    const fallbackMockRca = {
        incident_id: "RCA-17746123-payment-db",
        trigger_service: "api-gateway",
        root_cause_service: "payment-db",
        is_cascading_failure: true,
        primary_trace_id: "00f067aa0ba902b7da737809db0107d0",
        root_cause_message: "FATAL: remaining connection slots are reserved for non-replication superuser connections. Maxpool 100 reached.",
        stack_trace: "psycopg2.OperationalError: FATAL: remaining connection slots reserved\n  File 'payment_db/pool.py', line 142, in getconn\n    raise PoolExhaustedError('Max DB connections 100/100 reached under heavy checkout surge')\n  File 'payment_service/repo.py', line 58, in execute_transaction\n    conn = self.pool.getconn(timeout=2.0)",
        remediation_recommendation: "Scale database connection pool for [payment-db], verify query timeouts, or restart active connections.",
        path_traversal_chain: [
            { hop: 0, service: "api-gateway", status_code: 503, duration_ms: 2300.0, is_error: true },
            { hop: 1, service: "order-service", status_code: 502, duration_ms: 2250.0, is_error: true },
            { hop: 2, service: "payment-gateway", status_code: 500, duration_ms: 2200.0, is_error: true },
            { hop: 3, service: "payment-db", status_code: 500, duration_ms: 2150.0, is_error: true }
        ],
        blast_radius: {
            unique_affected_users_count: 34,
            total_users_in_window: 84,
            unique_affected_user_ids: Array.from({length: 34}, (_, i) => `user_${(i+1).toString().padStart(3, '0')}`),
            affected_services_count: 4,
            affected_services: ["api-gateway", "order-service", "payment-gateway", "payment-db"],
            total_requests: 84,
            total_errors: 34,
            error_rate_pct: 40.5,
            associated_error_trace_ids: ["00f067aa0ba902b7da737809db0107d0"]
        }
    };

    // Refresh Telemetry Data
    async function loadDashboardData() {
        try {
            // Fetch System Topology
            const topoRes = await fetch('/api/v1/topology');
            if (topoRes.ok) {
                topologyData = await topoRes.json();
            } else {
                topologyData = fallbackMockTopology;
            }

            window.TopologyMap.setData(topologyData.nodes, topologyData.dependencies);
            window.MetricsPanel.render('metrics-cards-grid', topologyData.nodes);

            const svcCountEl = document.getElementById('header-services-count');
            if (svcCountEl) svcCountEl.textContent = (topologyData.nodes || []).length;

            // Fetch Active Incident / Latest RCA Report
            const incRes = await fetch('/api/v1/rca/incidents');
            if (incRes.ok) {
                const incData = await incRes.json();
                if (incData.incidents && incData.incidents.length > 0) {
                    updateRcaViews(incData.incidents[0]);
                } else {
                    updateRcaViews(fallbackMockRca);
                }
            } else {
                updateRcaViews(fallbackMockRca);
            }
        } catch (err) {
            console.log('API offline or standalone preview - loading fallback dashboard data:', err);
            topologyData = fallbackMockTopology;
            window.TopologyMap.setData(topologyData.nodes, topologyData.dependencies);
            window.MetricsPanel.render('metrics-cards-grid', topologyData.nodes);
            const svcCountEl = document.getElementById('header-services-count');
            if (svcCountEl) svcCountEl.textContent = topologyData.nodes.length;
            updateRcaViews(fallbackMockRca);
        }
    }

    function updateRcaViews(report) {
        activeRcaReport = report;
        window.LogViewer.render(report);
        window.TraceInspector.render('trace-waterfall', report);
        window.BlastRadius.render(report);
    }

    // Initialize Simulation Studio Trigger Callbacks
    window.SimulationStudio.init((newReport) => {
        updateRcaViews(newReport);
        loadDashboardData();
    });

    // Refresh Button Event Listener
    const btnRefresh = document.getElementById('btn-refresh-telemetry');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => {
            loadDashboardData();
        });
    }

    // Initial Load
    await loadDashboardData();

    // Auto-refresh poll every 10 seconds for real-time monitoring
    setInterval(() => {
        loadDashboardData();
    }, 10000);
});
