"""
FaultLens Engine - Metrics Anomaly Detector
Detects performance spikes, latency breaches, and error rate jumps across service nodes.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time


@dataclass
class ServiceMetric:
    service_id: str
    timestamp: float
    error_rate_pct: float
    latency_p95_ms: float
    throughput_rps: float
    cpu_usage_pct: float
    memory_usage_pct: float


@dataclass
class AnomalyTrigger:
    incident_id: str
    service_id: str
    anomaly_type: str  # 'ERROR_RATE_SPIKE', 'LATENCY_SLA_BREACH', 'CPU_SATURATION'
    severity: str      # 'CRITICAL', 'HIGH', 'WARNING'
    value: float
    threshold: float
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


class MetricsAnomalyDetector:
    def __init__(self, error_threshold_pct: float = 5.0, latency_sla_ms: float = 400.0, cpu_threshold_pct: float = 85.0):
        self.error_threshold_pct = error_threshold_pct
        self.latency_sla_ms = latency_sla_ms
        self.cpu_threshold_pct = cpu_threshold_pct
        self.metric_history: Dict[str, List[ServiceMetric]] = {}

    def ingest_metric(self, metric: ServiceMetric) -> Optional[AnomalyTrigger]:
        if metric.service_id not in self.metric_history:
            self.metric_history[metric.service_id] = []
        
        history = self.metric_history[metric.service_id]
        history.append(metric)
        
        # Keep last 100 data points
        if len(history) > 100:
            history.pop(0)

        # Check for anomalies
        if metric.error_rate_pct >= self.error_threshold_pct:
            return AnomalyTrigger(
                incident_id=f"INC-{int(metric.timestamp)}-{metric.service_id}",
                service_id=metric.service_id,
                anomaly_type="ERROR_RATE_SPIKE",
                severity="CRITICAL" if metric.error_rate_pct > 15.0 else "HIGH",
                value=round(metric.error_rate_pct, 2),
                threshold=self.error_threshold_pct,
                timestamp=metric.timestamp,
                details={"error_rate_pct": metric.error_rate_pct, "rps": metric.throughput_rps}
            )

        if metric.latency_p95_ms >= self.latency_sla_ms:
            return AnomalyTrigger(
                incident_id=f"INC-{int(metric.timestamp)}-{metric.service_id}",
                service_id=metric.service_id,
                anomaly_type="LATENCY_SLA_BREACH",
                severity="HIGH",
                value=round(metric.latency_p95_ms, 2),
                threshold=self.latency_sla_ms,
                timestamp=metric.timestamp,
                details={"latency_p95_ms": metric.latency_p95_ms}
            )

        if metric.cpu_usage_pct >= self.cpu_threshold_pct:
            return AnomalyTrigger(
                incident_id=f"INC-{int(metric.timestamp)}-{metric.service_id}",
                service_id=metric.service_id,
                anomaly_type="CPU_SATURATION",
                severity="WARNING",
                value=round(metric.cpu_usage_pct, 2),
                threshold=self.cpu_threshold_pct,
                timestamp=metric.timestamp,
                details={"cpu_usage_pct": metric.cpu_usage_pct, "memory_usage_pct": metric.memory_usage_pct}
            )

        return None

    def get_service_health(self, service_id: str) -> Dict[str, Any]:
        history = self.metric_history.get(service_id, [])
        if not history:
            return {"status": "HEALTHY", "error_rate_pct": 0.0, "latency_p95_ms": 45.0, "cpu_usage_pct": 25.0}

        latest = history[-1]
        status = "HEALTHY"
        if latest.error_rate_pct >= self.error_threshold_pct or latest.latency_p95_ms >= self.latency_sla_ms * 1.5:
            status = "CRITICAL"
        elif latest.error_rate_pct > 1.0 or latest.latency_p95_ms >= self.latency_sla_ms:
            status = "DEGRADED"

        return {
            "status": status,
            "error_rate_pct": latest.error_rate_pct,
            "latency_p95_ms": latest.latency_p95_ms,
            "throughput_rps": latest.throughput_rps,
            "cpu_usage_pct": latest.cpu_usage_pct,
            "memory_usage_pct": latest.memory_usage_pct,
            "timestamp": latest.timestamp
        }
