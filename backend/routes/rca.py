"""
FaultLens API Router - Root Cause Analysis (RCA), Blast Radius & Telemetry Simulation
"""

import time
from fastapi import APIRouter, HTTPException, Depends, Request, status
from typing import Dict, List, Any, Optional

from backend.models import RCARequestModel, SimulationTriggerModel
from security.rate_limiter import standard_rate_limiter
from security.rbac import require_role, Role

router = APIRouter(prefix="/api/v1", tags=["Root Cause Analysis & Simulation"])


def get_components():
    from backend.app import global_rca_engine, global_simulator, incident_history
    return global_rca_engine, global_simulator, incident_history


@router.post("/rca/analyze")
async def analyze_root_cause(
    payload: RCARequestModel,
    request: Request,
    current_user=Depends(require_role(Role.VIEWER))
):
    """
    Triggers deterministic 4-pillar Root Cause Analysis.
    """
    standard_rate_limiter.check_request(request)
    engine, simulator, incidents = get_components()

    rca_report = engine.run_rca(
        trigger_service=payload.service_id,
        timestamp=payload.timestamp or time.time(),
        target_trace_id=payload.target_trace_id
    )

    # Save into active incidents store
    incidents.append(rca_report)
    if len(incidents) > 50:
        incidents.pop(0)

    return rca_report


@router.get("/rca/incidents")
async def list_incidents(request: Request):
    standard_rate_limiter.check_request(request)
    _, _, incidents = get_components()
    return {"count": len(incidents), "incidents": list(reversed(incidents))}


@router.get("/blast-radius")
async def calculate_blast_radius(
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    window_minutes: int = 5,
    request: Request = None
):
    if request:
        standard_rate_limiter.check_request(request)
    engine, _, _ = get_components()

    now = time.time()
    if not end_time:
        end_time = now
    if not start_time:
        start_time = end_time - (window_minutes * 60)

    report = engine.buffer.calculate_blast_radius(start_time, end_time)
    return report


@router.post("/simulation/trigger")
async def trigger_simulation_scenario(
    payload: SimulationTriggerModel,
    request: Request,
    current_user=Depends(require_role(Role.ENGINEER))
):
    """
    Injects synthetic fault scenarios to demonstrate real-time RCA isolation.
    """
    standard_rate_limiter.check_request(request)
    engine, simulator, incidents = get_components()

    if payload.scenario == "telemetry_flood":
        # Demonstrate rate limiter blocking
        return {
            "scenario": "telemetry_flood",
            "message": "Telemetry flood simulation launched. Rapid ingestion endpoint requests will trigger HTTP 429 Too Many Requests defense.",
            "status": "SIMULATION_ACTIVE"
        }

    rca_report = simulator.trigger_scenario(
        scenario_name=payload.scenario,
        affected_user_count=payload.user_count,
        delay_seconds=payload.delay_seconds
    )

    incidents.append(rca_report)
    return {
        "status": "SIMULATION_SUCCESS",
        "scenario_triggered": payload.scenario,
        "rca_report": rca_report
    }
