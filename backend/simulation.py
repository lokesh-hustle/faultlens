"""
FaultLens Backend - Telemetry Simulator
Generates synthetic distributed tracing, log, and metric streams for incident scenarios.
"""

import time
import random
import uuid
from typing import Dict, List, Any

from engine.dependency_graph import ServiceDependencyGraph, ServiceNode, ServiceDependency
from engine.anomaly_detector import MetricsAnomalyDetector, ServiceMetric
from engine.rca_engine import FaultLensRCAEngine


def build_default_topology() -> ServiceDependencyGraph:
    graph = ServiceDependencyGraph()
    
    # Define microservice nodes
    nodes = [
        ServiceNode(id="api-gateway", name="API Gateway", tier="gateway", sla_latency_ms=100.0),
        ServiceNode(id="auth-service", name="Auth & Session Service", tier="auth", sla_latency_ms=80.0),
        ServiceNode(id="user-db", name="User PostgreSQL DB", tier="database", sla_latency_ms=20.0),
        ServiceNode(id="order-service", name="Order Management Service", tier="app", sla_latency_ms=150.0),
        ServiceNode(id="payment-gateway", name="Payment Gateway Service", tier="app", sla_latency_ms=250.0),
        ServiceNode(id="payment-db", name="Payment DB Cluster", tier="database", sla_latency_ms=30.0),
        ServiceNode(id="inventory-service", name="Inventory Service", tier="app", sla_latency_ms=120.0),
        ServiceNode(id="inventory-db", name="Inventory Redis Cache", tier="database", sla_latency_ms=10.0),
        ServiceNode(id="recommendation-engine", name="ML Recommendation Engine", tier="app", sla_latency_ms=350.0),
        ServiceNode(id="third-party-stripe", name="Stripe API (External)", tier="third_party", sla_latency_ms=400.0)
    ]

    for n in nodes:
        graph.add_node(n)

    # Define service dependencies (directed edges)
    deps = [
        ServiceDependency(source="api-gateway", target="auth-service", protocol="gRPC"),
        ServiceDependency(source="auth-service", target="user-db", protocol="PostgreSQL"),
        ServiceDependency(source="api-gateway", target="order-service", protocol="HTTP/2"),
        ServiceDependency(source="api-gateway", target="recommendation-engine", protocol="gRPC"),
        ServiceDependency(source="order-service", target="payment-gateway", protocol="gRPC"),
        ServiceDependency(source="order-service", target="inventory-service", protocol="HTTP/2"),
        ServiceDependency(source="payment-gateway", target="payment-db", protocol="PostgreSQL"),
        ServiceDependency(source="payment-gateway", target="third-party-stripe", protocol="HTTPS"),
        ServiceDependency(source="inventory-service", target="inventory-db", protocol="Redis")
    ]

    for d in deps:
        graph.add_dependency(d)

    return graph


class TelemetrySimulator:
    def __init__(self, rca_engine: FaultLensRCAEngine):
        self.engine = rca_engine

    def generate_baseline_telemetry(self, num_normal_traces: int = 15):
        """Generates healthy traffic baseline across all services."""
        now = time.time()
        users = [f"usr_{random.randint(1000, 9999)}" for _ in range(30)]
        services = list(self.engine.graph.nodes.keys())

        # Ingest baseline metrics
        for s_id in services:
            metric = ServiceMetric(
                service_id=s_id,
                timestamp=now,
                error_rate_pct=round(random.uniform(0.1, 1.2), 2),
                latency_p95_ms=round(random.uniform(15.0, 90.0), 2),
                throughput_rps=round(random.uniform(80.0, 350.0), 1),
                cpu_usage_pct=round(random.uniform(12.0, 45.0), 1),
                memory_usage_pct=round(random.uniform(20.0, 50.0), 1)
            )
            self.engine.anomaly_detector.ingest_metric(metric)

        # Ingest healthy trace spans
        for i in range(num_normal_traces):
            trace_id = uuid.uuid4().hex
            u_id = random.choice(users)
            t_offset = now - random.uniform(0, 120)

            # Gateway -> Order -> Payment -> Payment DB
            span_gw = {
                "trace_id": trace_id, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "api-gateway", "timestamp": t_offset, "duration_ms": 110.0,
                "status_code": 200, "user_id": u_id
            }
            span_order = {
                "trace_id": trace_id, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_gw["span_id"],
                "service": "order-service", "timestamp": t_offset + 0.01, "duration_ms": 85.0,
                "status_code": 200, "user_id": u_id
            }
            span_pay = {
                "trace_id": trace_id, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_order["span_id"],
                "service": "payment-gateway", "timestamp": t_offset + 0.02, "duration_ms": 45.0,
                "status_code": 200, "user_id": u_id
            }
            span_db = {
                "trace_id": trace_id, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_pay["span_id"],
                "service": "payment-db", "timestamp": t_offset + 0.03, "duration_ms": 12.0,
                "status_code": 200, "user_id": u_id
            }

            for s in [span_gw, span_order, span_pay, span_db]:
                self.engine.store_span(s)

    def trigger_scenario(self, scenario_name: str, affected_user_count: int = 50, delay_seconds: float = 0.0) -> Dict[str, Any]:
        """
        Executes a targeted fault injection scenario.
        Clears old scenario telemetry to prevent user accumulation bugs.
        """
        self.engine.reset_telemetry()
        now = time.time() - delay_seconds
        incident_users = [f"user_{i+1:03d}" for i in range(affected_user_count)]
        
        if scenario_name == "cascading_db_failure":
            return self._scenario_cascading_db_failure(now, incident_users)
        elif scenario_name == "payment_api_timeout":
            return self._scenario_payment_api_timeout(now, incident_users)
        elif scenario_name == "out_of_order_logs":
            return self._scenario_out_of_order_logs(now, incident_users)
        elif scenario_name == "memory_leak":
            return self._scenario_memory_leak(now, incident_users)
        else:
            return self._scenario_cascading_db_failure(now, incident_users)

    def _scenario_cascading_db_failure(self, now: float, users: List[str]) -> Dict[str, Any]:
        """
        Root Cause: payment-db PostgreSQL Connection Pool Exhaustion.
        Cascades: payment-db (500) -> payment-gateway (500) -> order-service (502) -> api-gateway (503).
        """
        # Inject anomalous metrics
        self.engine.anomaly_detector.ingest_metric(ServiceMetric(
            service_id="payment-db", timestamp=now, error_rate_pct=88.5, latency_p95_ms=1850.0,
            throughput_rps=420.0, cpu_usage_pct=98.2, memory_usage_pct=92.0
        ))
        self.engine.anomaly_detector.ingest_metric(ServiceMetric(
            service_id="payment-gateway", timestamp=now, error_rate_pct=65.2, latency_p95_ms=2100.0,
            throughput_rps=380.0, cpu_usage_pct=75.0, memory_usage_pct=60.0
        ))
        self.engine.anomaly_detector.ingest_metric(ServiceMetric(
            service_id="api-gateway", timestamp=now, error_rate_pct=42.0, latency_p95_ms=2300.0,
            throughput_rps=350.0, cpu_usage_pct=50.0, memory_usage_pct=40.0
        ))

        primary_trace_id = uuid.uuid4().hex
        num_failing = max(1, int(len(users) * 0.40))
        failing_users = users[:num_failing]
        healthy_users = users[num_failing:]
        
        # Inject error traces for affected subset of users
        for idx, u_id in enumerate(failing_users):
            tid = primary_trace_id if idx == 0 else uuid.uuid4().hex
            t_time = now - random.uniform(5, 120)

            span_gw = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "api-gateway", "timestamp": t_time, "duration_ms": 2300.0,
                "status_code": 503, "user_id": u_id, "error_message": "HTTP 503 Service Unavailable"
            }
            span_order = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_gw["span_id"],
                "service": "order-service", "timestamp": t_time + 0.01, "duration_ms": 2250.0,
                "status_code": 502, "user_id": u_id, "error_message": "HTTP 502 Bad Gateway from payment-gateway"
            }
            span_pay = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_order["span_id"],
                "service": "payment-gateway", "timestamp": t_time + 0.02, "duration_ms": 2200.0,
                "status_code": 500, "user_id": u_id, "error_message": "DBConnectionTimeout: failed to acquire connection from pool"
            }
            span_db = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_pay["span_id"],
                "service": "payment-db", "timestamp": t_time + 0.03, "duration_ms": 2150.0,
                "status_code": 500, "user_id": u_id, "error_message": "FATAL: remaining connection slots reserved for non-replication superuser connections"
            }

            for s in [span_gw, span_order, span_pay, span_db]:
                self.engine.store_span(s)

        # Inject healthy baseline spans for unaffected users
        for u_id in healthy_users:
            tid = uuid.uuid4().hex
            t_time = now - random.uniform(5, 120)
            span_ok = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "api-gateway", "timestamp": t_time, "duration_ms": 45.0,
                "status_code": 200, "user_id": u_id
            }
            self.engine.store_span(span_ok)

        # Smoking gun log entry
        smoking_gun_log = {
            "log_id": f"log-{uuid.uuid4().hex[:8]}",
            "service": "payment-db",
            "trace_id": primary_trace_id,
            "timestamp": now,
            "level": "CRITICAL",
            "message": "FATAL: remaining connection slots are reserved for non-replication superuser connections. Maxpool 100 reached.",
            "stack_trace": (
                "psycopg2.OperationalError: FATAL: remaining connection slots reserved\n"
                "  File 'payment_db/pool.py', line 142, in getconn\n"
                "    raise PoolExhaustedError('Max DB connections 100/100 reached under heavy checkout surge')\n"
                "  File 'payment_service/repo.py', line 58, in execute_transaction\n"
                "    conn = self.pool.getconn(timeout=2.0)"
            ),
            "user_id": failing_users[0]
        }
        self.engine.store_log(smoking_gun_log)

        # Execute RCA
        rca_res = self.engine.run_rca(trigger_service="api-gateway", timestamp=now, target_trace_id=primary_trace_id)
        return rca_res

    def _scenario_payment_api_timeout(self, now: float, users: List[str]) -> Dict[str, Any]:
        """
        Root Cause: Third-Party Stripe API HTTP 504 Deadline Exceeded.
        """
        self.engine.anomaly_detector.ingest_metric(ServiceMetric(
            service_id="payment-gateway", timestamp=now, error_rate_pct=72.0, latency_p95_ms=5100.0,
            throughput_rps=120.0, cpu_usage_pct=40.0, memory_usage_pct=45.0
        ))

        primary_trace_id = uuid.uuid4().hex
        num_failing = max(1, int(len(users) * 0.40))
        failing_users = users[:num_failing]
        healthy_users = users[num_failing:]

        for u_id in failing_users:
            tid = primary_trace_id if u_id == failing_users[0] else uuid.uuid4().hex
            t_time = now - random.uniform(1, 60)

            span_pay = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "payment-gateway", "timestamp": t_time, "duration_ms": 5000.0,
                "status_code": 504, "user_id": u_id, "error_message": "Gateway Timeout from external provider"
            }
            span_stripe = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": span_pay["span_id"],
                "service": "third-party-stripe", "timestamp": t_time + 0.01, "duration_ms": 4980.0,
                "status_code": 504, "user_id": u_id, "error_message": "HTTPS POST https://api.stripe.com/v1/charges timed out after 5000ms"
            }
            self.engine.store_span(span_pay)
            self.engine.store_span(span_stripe)

        for u_id in healthy_users:
            tid = uuid.uuid4().hex
            t_time = now - random.uniform(1, 60)
            span_ok = {
                "trace_id": tid, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "payment-gateway", "timestamp": t_time, "duration_ms": 110.0,
                "status_code": 200, "user_id": u_id
            }
            self.engine.store_span(span_ok)

        log_stripe = {
            "log_id": f"log-{uuid.uuid4().hex[:8]}",
            "service": "third-party-stripe",
            "trace_id": primary_trace_id,
            "timestamp": now,
            "level": "ERROR",
            "message": "External API Timeout: https://api.stripe.com/v1/charges non-responsive after 5000ms SLA",
            "stack_trace": (
                "httpx.ReadTimeout: HTTPSConnectionPool(host='api.stripe.com', port=443): Read timed out. (read timeout=5.0)\n"
                "  File 'clients/stripe_client.py', line 89, in create_charge\n"
                "    response = await self.client.post('/v1/charges', json=payload)"
            ),
            "user_id": failing_users[0]
        }
        self.engine.store_log(log_stripe)

        return self.engine.run_rca(trigger_service="payment-gateway", timestamp=now, target_trace_id=primary_trace_id)

    def _scenario_out_of_order_logs(self, now: float, users: List[str]) -> Dict[str, Any]:
        """
        Simulates out-of-order network delayed logs arriving 3 minutes after the incident.
        Tests TimeChunkBatchBuffer grace buffer aggregation.
        """
        delayed_timestamp = now - 180  # 3 minutes ago
        primary_trace_id = uuid.uuid4().hex
        num_failing = max(1, int(len(users) * 0.40))
        failing_users = users[:num_failing]
        healthy_users = users[num_failing:]

        # Ingest trace spans with historical timestamp for failing users
        for u_id in failing_users:
            span = {
                "trace_id": primary_trace_id, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "auth-service", "timestamp": delayed_timestamp, "duration_ms": 1200.0,
                "status_code": 500, "user_id": u_id, "error_message": "JWT Key Verification Failed"
            }
            self.engine.store_span(span)

        for u_id in healthy_users:
            span = {
                "trace_id": uuid.uuid4().hex, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "auth-service", "timestamp": delayed_timestamp, "duration_ms": 30.0,
                "status_code": 200, "user_id": u_id
            }
            self.engine.store_span(span)

        # Delayed log ingested NOW but with past timestamp
        delayed_log = {
            "log_id": f"log-{uuid.uuid4().hex[:8]}",
            "service": "auth-service",
            "trace_id": primary_trace_id,
            "timestamp": delayed_timestamp,
            "level": "CRITICAL",
            "message": "KeyRotationException: RSA public key id 'key_2026_09' missing from JWKS cache",
            "stack_trace": (
                "jwt.exceptions.InvalidKeyError: Unable to find key with kid 'key_2026_09'\n"
                "  File 'auth/jwt_verifier.py', line 64, in decode_token\n"
                "    key = self.jwks.get_key(header['kid'])"
            ),
            "user_id": failing_users[0]
        }
        self.engine.store_log(delayed_log)

        return self.engine.run_rca(trigger_service="auth-service", timestamp=delayed_timestamp, target_trace_id=primary_trace_id)

    def _scenario_memory_leak(self, now: float, users: List[str]) -> Dict[str, Any]:
        """
        Root Cause: ML Recommendation Engine Java OOM / Heap Limit Exhaustion.
        """
        self.engine.anomaly_detector.ingest_metric(ServiceMetric(
            service_id="recommendation-engine", timestamp=now, error_rate_pct=95.0, latency_p95_ms=8500.0,
            throughput_rps=10.0, cpu_usage_pct=99.9, memory_usage_pct=99.8
        ))

        primary_trace_id = uuid.uuid4().hex
        num_failing = max(1, int(len(users) * 0.40))
        failing_users = users[:num_failing]
        healthy_users = users[num_failing:]

        for u_id in failing_users:
            span = {
                "trace_id": primary_trace_id, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "recommendation-engine", "timestamp": now, "duration_ms": 8500.0,
                "status_code": 500, "user_id": u_id, "error_message": "java.lang.OutOfMemoryError: Java heap space"
            }
            self.engine.store_span(span)

        for u_id in healthy_users:
            span = {
                "trace_id": uuid.uuid4().hex, "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "service": "recommendation-engine", "timestamp": now, "duration_ms": 120.0,
                "status_code": 200, "user_id": u_id
            }
            self.engine.store_span(span)

        oom_log = {
            "log_id": f"log-{uuid.uuid4().hex[:8]}",
            "service": "recommendation-engine",
            "trace_id": primary_trace_id,
            "timestamp": now,
            "level": "FATAL",
            "message": "java.lang.OutOfMemoryError: Java heap space. Metaspace / GC Overhead Limit Exceeded.",
            "stack_trace": (
                "java.lang.OutOfMemoryError: Java heap space\n"
                "  at com.faultlens.recommendation.TensorMatrix.allocate(TensorMatrix.java:184)\n"
                "  at com.faultlens.recommendation.InferencePipeline.predict(InferencePipeline.java:92)"
            ),
            "user_id": failing_users[0]
        }
        self.engine.store_log(oom_log)

        return self.engine.run_rca(trigger_service="recommendation-engine", timestamp=now, target_trace_id=primary_trace_id)

        return self.engine.run_rca(trigger_service="recommendation-engine", timestamp=now, target_trace_id=primary_trace_id)
