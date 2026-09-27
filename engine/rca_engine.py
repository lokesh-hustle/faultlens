"""
FaultLens Engine - Deterministic RCA Engine
Orchestrates the 4 Pillars of Observability:
1. Metrics Anomaly Detection
2. Trace Path Traversal on Dependency Graph
3. Granular Log Extraction & Stack Trace Isolation
4. Time-Chunk User Impact Quantization (Blast Radius)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import time

from engine.dependency_graph import ServiceDependencyGraph
from engine.time_chunk_buffer import TimeChunkBatchBuffer, TelemetryEvent
from engine.anomaly_detector import MetricsAnomalyDetector, AnomalyTrigger


class FaultLensRCAEngine:
    def __init__(
        self,
        graph: ServiceDependencyGraph,
        buffer: TimeChunkBatchBuffer,
        anomaly_detector: MetricsAnomalyDetector
    ):
        self.graph = graph
        self.buffer = buffer
        self.anomaly_detector = anomaly_detector
        # Store trace spans: trace_id -> List[span_dict]
        self.trace_store: Dict[str, List[Dict[str, Any]]] = {}
        # Store logs: service_id -> List[log_dict]
        self.log_store: Dict[str, List[Dict[str, Any]]] = {}

    def reset_telemetry(self):
        """Resets telemetry stores and time chunk buffer."""
        self.trace_store.clear()
        self.log_store.clear()
        self.buffer.clear()

    def store_span(self, span: Dict[str, Any]):
        trace_id = span.get("trace_id")
        if not trace_id:
            return
        if trace_id not in self.trace_store:
            self.trace_store[trace_id] = []
        self.trace_store[trace_id].append(span)

        # Ingest into batch buffer as well for blast radius calculation
        event = TelemetryEvent(
            event_id=span.get("span_id", f"span-{time.time()}"),
            timestamp=span.get("timestamp", time.time()),
            service=span.get("service", "unknown"),
            trace_id=trace_id,
            span_id=span.get("span_id"),
            user_id=span.get("user_id"),
            event_type="span",
            status_code=int(span.get("status_code", 200)),
            latency_ms=float(span.get("duration_ms", 0.0)),
            error_message=span.get("error_message")
        )
        self.buffer.ingest_event(event)

    def store_log(self, log_entry: Dict[str, Any]):
        service = log_entry.get("service")
        if not service:
            return
        if service not in self.log_store:
            self.log_store[service] = []
        self.log_store[service].append(log_entry)

        # Ingest into batch buffer
        if log_entry.get("level") in ("ERROR", "CRITICAL", "FATAL") or log_entry.get("is_error"):
            event = TelemetryEvent(
                event_id=log_entry.get("log_id", f"log-{time.time()}"),
                timestamp=log_entry.get("timestamp", time.time()),
                service=service,
                trace_id=log_entry.get("trace_id", "unknown"),
                user_id=log_entry.get("user_id"),
                event_type="log",
                status_code=500,
                error_message=log_entry.get("message")
            )
            self.buffer.ingest_event(event)

    def run_rca(self, trigger_service: str, timestamp: Optional[float] = None, target_trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes deterministic root cause analysis for an incident.
        """
        if timestamp is None:
            timestamp = time.time()

        # Step 1: Identify associated failing traces
        associated_traces = []
        if target_trace_id and target_trace_id in self.trace_store:
            associated_traces = [target_trace_id]
        else:
            # Find recent error traces near timestamp
            for tid, spans in self.trace_store.items():
                for s in spans:
                    if abs(s.get("timestamp", 0) - timestamp) < 600:  # 10 minute window
                        if s.get("status_code", 200) >= 400 or s.get("error_message"):
                            associated_traces.append(tid)
                            break

        if not associated_traces:
            # Fallback: scan for any trace involving trigger_service with errors
            for tid, spans in self.trace_store.items():
                if any(s.get("service") == trigger_service and (s.get("status_code", 200) >= 400 or s.get("error_message")) for s in spans):
                    associated_traces.append(tid)

        primary_trace_id = associated_traces[0] if associated_traces else None
        spans_in_trace = self.trace_store.get(primary_trace_id, []) if primary_trace_id else []

        # Step 2: Path Traversal over Service Dependency Graph & Trace Span Tree
        # Walk span hierarchy to find the origin span (deepest failing span or span with explicit failure)
        origin_node = trigger_service
        origin_span = None
        failing_spans = []

        for span in spans_in_trace:
            if span.get("status_code", 200) >= 400 or span.get("error_message") or span.get("is_error"):
                failing_spans.append(span)

        if failing_spans:
            # Sort failing spans by parent-child depth (spans without failing children are leaf root causes)
            # Find the leaf failing span
            span_ids_with_children = set()
            for s in failing_spans:
                parent_id = s.get("parent_span_id")
                if parent_id:
                    span_ids_with_children.add(parent_id)
            
            leaf_failures = [s for s in failing_spans if s.get("span_id") not in span_ids_with_children]
            origin_span = leaf_failures[0] if leaf_failures else failing_spans[-1]
            origin_node = origin_span.get("service", trigger_service)
        else:
            # If trace tree spans are missing, use graph traversal to check downstream dependencies
            downstream = self.graph.get_downstream_services(trigger_service)
            for ds in downstream:
                health = self.anomaly_detector.get_service_health(ds)
                if health.get("status") in ("CRITICAL", "DEGRADED"):
                    origin_node = ds
                    break

        # Step 3: Log Extraction at Failing Node using Trace ID & Timestamp correlation
        smoking_gun_log = None
        logs_for_node = self.log_store.get(origin_node, [])

        if primary_trace_id:
            for l in logs_for_node:
                if l.get("trace_id") == primary_trace_id and l.get("level") in ("ERROR", "CRITICAL", "FATAL"):
                    smoking_gun_log = l
                    break

        if not smoking_gun_log:
            # Match by closest timestamp and error level
            error_logs = [l for l in logs_for_node if l.get("level") in ("ERROR", "CRITICAL", "FATAL")]
            if error_logs:
                error_logs.sort(key=lambda x: abs(x.get("timestamp", 0) - timestamp))
                smoking_gun_log = error_logs[0]

        # Step 4: Blast Radius User Impact Calculation via TimeChunkBatchBuffer
        start_win = timestamp - 300  # 5 min window before
        end_win = timestamp + 300    # 5 min window after
        blast_radius = self.buffer.calculate_blast_radius(start_win, end_win)

        # Synthesize Root Cause Summary
        root_cause_msg = "Unknown anomaly"
        stack_trace = "No stack trace available."

        if smoking_gun_log:
            root_cause_msg = smoking_gun_log.get("message", "Service error detected")
            stack_trace = smoking_gun_log.get("stack_trace", f"Error at {origin_node}: {root_cause_msg}")
        elif origin_span:
            root_cause_msg = origin_span.get("error_message", f"HTTP {origin_span.get('status_code', 500)} failure")
            stack_trace = f"Span failure: {origin_span.get('span_id')} [{origin_node}]\nMessage: {root_cause_msg}"

        path_traversal_chain = self._build_path_chain(trigger_service, origin_node, spans_in_trace)

        return {
            "incident_id": f"RCA-{int(timestamp)}-{origin_node}",
            "timestamp": timestamp,
            "timestamp_iso": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
            "trigger_service": trigger_service,
            "root_cause_service": origin_node,
            "is_cascading_failure": trigger_service != origin_node,
            "root_cause_message": root_cause_msg,
            "stack_trace": stack_trace,
            "primary_trace_id": primary_trace_id,
            "path_traversal_chain": path_traversal_chain,
            "origin_span": origin_span,
            "smoking_gun_log": smoking_gun_log,
            "blast_radius": blast_radius,
            "remediation_recommendation": self._get_remediation_advice(origin_node, root_cause_msg)
        }

    def _build_path_chain(self, start_service: str, end_service: str, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Constructs ordered hops from entry point to origin node."""
        if not spans:
            paths = self.graph.find_execution_paths(start_service, end_service)
            if paths:
                return [{"service": s, "hop": idx} for idx, s in enumerate(paths[0])]
            return [{"service": start_service, "hop": 0}, {"service": end_service, "hop": 1}]

        # Build hop chain from spans
        sorted_spans = sorted(spans, key=lambda x: x.get("timestamp", 0))
        chain = []
        for idx, s in enumerate(sorted_spans):
            chain.append({
                "hop": idx,
                "service": s.get("service"),
                "span_id": s.get("span_id"),
                "parent_span_id": s.get("parent_span_id"),
                "duration_ms": s.get("duration_ms"),
                "status_code": s.get("status_code"),
                "is_error": s.get("status_code", 200) >= 400 or bool(s.get("error_message"))
            })
        return chain

    def _get_remediation_advice(self, service: str, error_msg: str) -> str:
        error_lower = error_msg.lower()
        if "connection pool" in error_lower or "db" in error_lower or "postgres" in error_lower:
            return f"Scale database connection pool for [{service}], verify query timeouts, or restart active connections."
        elif "timeout" in error_lower or "deadline" in error_lower:
            return f"Increase HTTP/gRPC client timeout on upstream callers of [{service}] and check downstream network latency."
        elif "oom" in error_lower or "memory" in error_lower or "heap" in error_lower:
            return f"Restart pod [{service}], increase Kubernetes memory limits, and profile memory allocations."
        elif "auth" in error_lower or "token" in error_lower or "unauthorized" in error_lower:
            return f"Verify JWT secret rotation and auth service key distribution across cluster."
        else:
            return f"Inspect application logs for [{service}], trigger circuit breaker, and rollback recent deployment."
