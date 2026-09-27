"""
FaultLens Backend - Pydantic Data Models & Validation Schemas
Strict schemas protecting API endpoints against malformed data and injection attacks.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
import time

from security.sanitizer import TelemetrySanitizer


class ServiceNodeModel(BaseModel):
    id: str = Field(..., description="Unique service node identifier", example="payment-gateway")
    name: str = Field(..., example="Payment Gateway Microservice")
    tier: str = Field("app", example="gateway | app | auth | database | third_party")
    sla_latency_ms: float = Field(200.0, ge=1.0, le=60000.0)
    error_threshold_pct: float = Field(2.0, ge=0.0, le=100.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "name", "tier")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        return TelemetrySanitizer.sanitize_string(v)


class ServiceDependencyModel(BaseModel):
    source: str = Field(..., example="order-service")
    target: str = Field(..., example="payment-gateway")
    protocol: str = Field("HTTP", example="HTTP | gRPC | Kafka | PostgreSQL")
    circuit_breaker_enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "target", "protocol")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        return TelemetrySanitizer.sanitize_string(v)


class MetricEntryModel(BaseModel):
    service_id: str
    timestamp: float = Field(default_factory=time.time)
    error_rate_pct: float = Field(0.0, ge=0.0, le=100.0)
    latency_p95_ms: float = Field(10.0, ge=0.0)
    throughput_rps: float = Field(100.0, ge=0.0)
    cpu_usage_pct: float = Field(15.0, ge=0.0, le=100.0)
    memory_usage_pct: float = Field(20.0, ge=0.0, le=100.0)

    @field_validator("service_id")
    @classmethod
    def validate_service(cls, v: str) -> str:
        return TelemetrySanitizer.validate_service_name(v)


class TraceSpanModel(BaseModel):
    trace_id: str = Field(..., description="32-hex character W3C Trace ID")
    span_id: str = Field(..., description="16-hex character W3C Span ID")
    parent_span_id: Optional[str] = None
    service: str
    name: str = "HTTP GET"
    timestamp: float = Field(default_factory=time.time)
    duration_ms: float = Field(15.0, ge=0.0)
    status_code: int = Field(200, ge=100, le=599)
    user_id: Optional[str] = None
    error_message: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("trace_id")
    @classmethod
    def check_trace_id(cls, v: str) -> str:
        return TelemetrySanitizer.validate_trace_id(v)

    @field_validator("span_id", "parent_span_id")
    @classmethod
    def check_span_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return TelemetrySanitizer.validate_span_id(v)

    @field_validator("service", "name", "user_id", "error_message")
    @classmethod
    def sanitize_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return TelemetrySanitizer.sanitize_string(v)


class LogEntryModel(BaseModel):
    log_id: Optional[str] = None
    service: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    level: str = Field("INFO", example="INFO | WARN | ERROR | CRITICAL")
    message: str
    stack_trace: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("service", "level", "message", "stack_trace", "user_id")
    @classmethod
    def sanitize_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return TelemetrySanitizer.sanitize_string(v)


class BatchTelemetryIngestModel(BaseModel):
    spans: List[TraceSpanModel] = Field(default_factory=list)
    logs: List[LogEntryModel] = Field(default_factory=list)
    metrics: List[MetricEntryModel] = Field(default_factory=list)


class RCARequestModel(BaseModel):
    service_id: str
    timestamp: Optional[float] = None
    target_trace_id: Optional[str] = None

    @field_validator("service_id")
    @classmethod
    def check_service(cls, v: str) -> str:
        return TelemetrySanitizer.validate_service_name(v)


class UserLoginModel(BaseModel):
    username: str
    password: str


class TokenResponseModel(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class SimulationTriggerModel(BaseModel):
    scenario: str = Field("cascading_db_failure", example="cascading_db_failure | payment_api_timeout | out_of_order_logs | memory_leak | telemetry_flood")
    user_count: int = Field(50, ge=5, le=1000)
    delay_seconds: float = Field(0.0, ge=0.0, le=300.0)
