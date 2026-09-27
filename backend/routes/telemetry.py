"""
FaultLens API Router - Telemetry Ingestion & Metrics Stream
Hardened with sliding-window rate limiting and input sanitization.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from typing import List, Dict, Any, Optional

from backend.models import BatchTelemetryIngestModel, TraceSpanModel, LogEntryModel, MetricEntryModel
from security.rate_limiter import ingestion_rate_limiter, standard_rate_limiter
from security.rbac import require_role, Role
from engine.anomaly_detector import ServiceMetric

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry Ingestion & Metrics"])


def get_engine_components():
    from backend.app import global_rca_engine
    return global_rca_engine


@router.post("/ingest")
async def ingest_telemetry_batch(
    payload: BatchTelemetryIngestModel,
    request: Request,
    current_user=Depends(require_role(Role.ENGINEER))
):
    """
    Ingests batch telemetry (spans, logs, metrics). Protected by Sliding Window Rate Limiter & RBAC.
    """
    ingestion_rate_limiter.check_request(request)
    engine = get_engine_components()

    ingested_spans_count = 0
    ingested_logs_count = 0
    ingested_metrics_count = 0
    anomalies_triggered = []

    # Ingest Trace Spans
    for span in payload.spans:
        engine.store_span(span.model_dump())
        ingested_spans_count += 1

    # Ingest Logs
    for log in payload.logs:
        engine.store_log(log.model_dump())
        ingested_logs_count += 1

    # Ingest Metrics
    for metric in payload.metrics:
        sm = ServiceMetric(
            service_id=metric.service_id,
            timestamp=metric.timestamp,
            error_rate_pct=metric.error_rate_pct,
            latency_p95_ms=metric.latency_p95_ms,
            throughput_rps=metric.throughput_rps,
            cpu_usage_pct=metric.cpu_usage_pct,
            memory_usage_pct=metric.memory_usage_pct
        )
        trigger = engine.anomaly_detector.ingest_metric(sm)
        if trigger:
            anomalies_triggered.append(trigger)
        ingested_metrics_count += 1

    return {
        "status": "SUCCESS",
        "ingested_spans": ingested_spans_count,
        "ingested_logs": ingested_logs_count,
        "ingested_metrics": ingested_metrics_count,
        "anomalies_detected": [
            {
                "incident_id": a.incident_id,
                "service": a.service_id,
                "type": a.anomaly_type,
                "severity": a.severity,
                "value": a.value,
                "threshold": a.threshold
            }
            for a in anomalies_triggered
        ]
    }


@router.get("/spans")
async def get_recent_spans(service: Optional[str] = None, limit: int = 50, request: Request = None):
    if request:
        standard_rate_limiter.check_request(request)
    engine = get_engine_components()

    spans = []
    for tid, span_list in engine.trace_store.items():
        for s in span_list:
            if not service or s.get("service") == service:
                spans.append(s)
            if len(spans) >= limit:
                break
        if len(spans) >= limit:
            break

    return {"count": len(spans), "spans": spans}


@router.get("/logs")
async def get_recent_logs(service: Optional[str] = None, limit: int = 50, request: Request = None):
    if request:
        standard_rate_limiter.check_request(request)
    engine = get_engine_components()

    logs = []
    if service:
        service_logs = engine.log_store.get(service, [])
        logs = service_logs[-limit:]
    else:
        for s_logs in engine.log_store.values():
            logs.extend(s_logs)
        logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        logs = logs[:limit]

    return {"count": len(logs), "logs": logs}
