"""
FaultLens Backend - Main FastAPI Application
Production-ready, heavily secured Root Cause Analysis & Observability Platform.
"""
import sys
import os

# Ensure project root directory is in sys.path regardless of CWD or invocation directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from engine.dependency_graph import ServiceDependencyGraph
from engine.time_chunk_buffer import TimeChunkBatchBuffer
from engine.anomaly_detector import MetricsAnomalyDetector
from engine.rca_engine import FaultLensRCAEngine
from backend.simulation import build_default_topology, TelemetrySimulator
from security.middleware import InformationMaskingMiddleware

from backend.routes.auth import router as auth_router
from backend.routes.telemetry import router as telemetry_router
from backend.routes.topology import router as topology_router
from backend.routes.rca import router as rca_router

# Global Singleton Instances
global_dependency_graph: ServiceDependencyGraph = build_default_topology()
global_time_buffer: TimeChunkBatchBuffer = TimeChunkBatchBuffer(window_size_seconds=180, grace_period_seconds=120)
global_anomaly_detector: MetricsAnomalyDetector = MetricsAnomalyDetector(error_threshold_pct=5.0, latency_sla_ms=400.0)

global_rca_engine: FaultLensRCAEngine = FaultLensRCAEngine(
    graph=global_dependency_graph,
    buffer=global_time_buffer,
    anomaly_detector=global_anomaly_detector
)

global_simulator: TelemetrySimulator = TelemetrySimulator(rca_engine=global_rca_engine)
incident_history = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Seed initial baseline telemetry and a default cascading failure incident for immediate UI demo
    global_simulator.generate_baseline_telemetry(num_normal_traces=25)
    default_rca = global_simulator.trigger_scenario("cascading_db_failure", affected_user_count=84)
    incident_history.append(default_rca)
    yield


app = FastAPI(
    title="FaultLens Observability & RCA API",
    description="Deterministic Root Cause Analysis & User Impact Engine for Cloud-Native Architectures",
    version="1.0.0",
    lifespan=lifespan
)

# Apply Security Middleware
app.add_middleware(InformationMaskingMiddleware)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(telemetry_router)
app.include_router(topology_router)
app.include_router(rca_router)

# Mount Static Frontend
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        index_path = os.path.join(frontend_dir, "index.html")
        return FileResponse(index_path)


@app.get("/healthz")
async def health_check():
    return {
        "status": "HEALTHY",
        "service": "FaultLens Core RCA Engine",
        "buffer_windows_active": len(global_time_buffer.batches),
        "topology_nodes_count": len(global_dependency_graph.nodes)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.app:app", host="127.0.0.1", port=port, reload=True)

