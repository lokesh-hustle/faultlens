"""
FaultLens Security - Sliding-Window Rate Limiter & DoS Protection
Defends ingestion streams and query endpoints against telemetry flooding attacks.
"""

import time
from typing import Dict, List, Tuple
from collections import defaultdict
from fastapi import HTTPException, Request, status
import threading


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 120, burst_limit: int = 200):
        self.rate_limit = requests_per_minute
        self.burst_limit = burst_limit
        self.window_size = 60.0  # seconds
        # Storage: client_identifier -> list of timestamps
        self.history: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def is_rate_limited(self, identifier: str) -> Tuple[bool, int, float]:
        """
        Returns (is_limited, current_count, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - self.window_size

        with self.lock:
            timestamps = self.history[identifier]
            # Prune timestamps older than window
            self.history[identifier] = [t for t in timestamps if t > cutoff]
            current_timestamps = self.history[identifier]
            count = len(current_timestamps)

            if count >= self.rate_limit:
                oldest = current_timestamps[0]
                retry_after = round(self.window_size - (now - oldest), 2)
                return True, count, max(0.1, retry_after)

            self.history[identifier].append(now)
            return False, count + 1, 0.0

    def check_request(self, request: Request, custom_identifier: str = None):
        client_ip = custom_identifier or request.client.host if request.client else "127.0.0.1"
        is_limited, count, retry_after = self.is_rate_limited(client_ip)

        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate Limit Exceeded: Telemetry flooding detected ({count} req/min). Retry after {retry_after}s.",
                headers={"Retry-After": str(int(retry_after))}
            )


# Global instances for ingestion and standard API calls
ingestion_rate_limiter = SlidingWindowRateLimiter(requests_per_minute=600, burst_limit=1000)
standard_rate_limiter = SlidingWindowRateLimiter(requests_per_minute=180, burst_limit=300)
