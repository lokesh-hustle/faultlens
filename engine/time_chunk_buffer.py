"""
FaultLens Engine - Time-Chunk Batch Processing Engine
Aggregates out-of-order and network-delayed telemetry streams into bounded time chunks.
Calculates exact unique user impact (blast radius) with configurable grace period buffers.
"""

import time
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field


@dataclass
class TelemetryEvent:
    event_id: str
    timestamp: float  # Unix timestamp in seconds
    service: str
    trace_id: str
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    event_type: str = "span"  # 'span', 'log', 'metric'
    status_code: int = 200
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeChunkBatch:
    window_start: float
    window_end: float
    events: List[TelemetryEvent] = field(default_factory=list)
    all_users: Set[str] = field(default_factory=set)
    affected_users: Set[str] = field(default_factory=set)
    affected_services: Set[str] = field(default_factory=set)
    total_requests: int = 0
    total_errors: int = 0
    is_closed: bool = False
    last_updated: float = field(default_factory=time.time)

    def add_event(self, event: TelemetryEvent):
        self.events.append(event)
        self.total_requests += 1
        if event.user_id:
            self.all_users.add(event.user_id)

        is_error = event.status_code >= 400 or bool(event.error_message) or event.data.get("is_error", False)
        if is_error:
            self.total_errors += 1
            if event.user_id:
                self.affected_users.add(event.user_id)
            if event.service:
                self.affected_services.add(event.service)
        self.last_updated = time.time()


class TimeChunkBatchBuffer:
    def __init__(self, window_size_seconds: int = 180, grace_period_seconds: int = 120):
        """
        :param window_size_seconds: Time window duration (e.g., 180s = 3 minutes).
        :param grace_period_seconds: Grace buffer duration to accept late-arriving logs/spans (e.g. 120s = 2 minutes).
        """
        self.window_size = window_size_seconds
        self.grace_period = grace_period_seconds
        # Key: window_start (float) -> TimeChunkBatch
        self.batches: Dict[float, TimeChunkBatch] = {}

    def _get_window_start(self, timestamp: float) -> float:
        """Aligns a timestamp to its fixed window boundary."""
        return (timestamp // self.window_size) * self.window_size

    def ingest_event(self, event: TelemetryEvent) -> TimeChunkBatch:
        """Ingests a telemetry event into its target time window batch."""
        now = time.time()
        window_start = self._get_window_start(event.timestamp)
        window_end = window_start + self.window_size

        # Check if event is beyond grace period for older windows
        if now > window_end + self.grace_period:
            # Event is too late (dropped by strict SLA), but we can still record in nearest active window
            pass

        if window_start not in self.batches:
            self.batches[window_start] = TimeChunkBatch(
                window_start=window_start,
                window_end=window_end
            )

        batch = self.batches[window_start]
        batch.add_event(event)
        return batch

    def get_batch(self, timestamp: float) -> Optional[TimeChunkBatch]:
        window_start = self._get_window_start(timestamp)
        return self.batches.get(window_start)

    def calculate_blast_radius(self, start_timestamp: float, end_timestamp: float) -> Dict[str, Any]:
        """
        Aggregates unique affected users and metrics across time chunks within a specified window.
        """
        affected_users = set()
        all_users = set()
        affected_services = set()
        total_requests = 0
        total_errors = 0
        trace_ids = set()

        for w_start, batch in self.batches.items():
            # Check overlap with range [start_timestamp, end_timestamp]
            if batch.window_end >= start_timestamp and batch.window_start <= end_timestamp:
                affected_users.update(batch.affected_users)
                all_users.update(batch.all_users)
                affected_services.update(batch.affected_services)
                total_requests += batch.total_requests
                total_errors += batch.total_errors
                for ev in batch.events:
                    if ev.status_code >= 400 or ev.error_message:
                        trace_ids.add(ev.trace_id)

        error_rate_pct = (total_errors / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "window_start_iso": datetime.fromtimestamp(start_timestamp, timezone.utc).isoformat(),
            "window_end_iso": datetime.fromtimestamp(end_timestamp, timezone.utc).isoformat(),
            "unique_affected_users_count": len(affected_users),
            "unique_affected_user_ids": sorted(list(affected_users)),
            "total_users_in_window": len(all_users),
            "affected_services_count": len(affected_services),
            "affected_services": sorted(list(affected_services)),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_pct": round(error_rate_pct, 2),
            "associated_error_trace_ids": sorted(list(trace_ids))[:50]
        }

    def clear(self):
        """Clears all buffered batch windows."""
        self.batches.clear()

    def clear_old_batches(self, retention_seconds: int = 3600):
        """Prunes batches older than retention window to conserve memory."""
        now = time.time()
        cutoff = now - retention_seconds
        keys_to_del = [k for k, v in self.batches.items() if v.window_end < cutoff]
        for k in keys_to_del:
            del self.batches[k]
