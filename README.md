# FaultLens: Deterministic Root Cause Analysis (RCA) & Observability Platform

> **Tackling "The Invisible Failure Problem" in Modern Distributed Systems**  
> When a user request ripples through a web of CDNs, API gateways, queues, databases, and 3rd-party APIs, a single point of failure triggers a cascading collapse. Traditional tools tell us where the fire is burning—FaultLens pinpoints **who lit the match**.

---

## Architecture Blueprint

FaultLens connects the 4 pillars of modern observability into a deterministic pipeline:

```
                  ┌───────────────────────────────┐
                  │   Telemetry Streams Ingest    │
                  │ (Metrics, Traces, Logs, Graph)│
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                     ┌─────────────────────────┐
                     │ Telemetry Sanitizer &   │
                     │ Sliding Rate Limiter    │
                     └────────────┬────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │     Time-Chunk Batch Processing Engine       │
           │  (2 to 5-Min Windows + Grace Buffer)         │
           └──────────────────────┬───────────────────────┘
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      │                           │                           │
      ▼                           ▼                           ▼
┌──────────────┐       ┌──────────────────────┐    ┌─────────────────────┐
│1. Metrics    │       │2. Dependency Graph & │    │3. Granular Log      │
│   Radar &    │──────►│   Path Traversal     │───►│   Extraction &      │
│   Anomalies  │       │   (Origin Hop)       │    │   Stack Trace       │
└──────────────┘       └──────────────────────┘    └──────────┬──────────┘
                                                              │
                                                              ▼
                                                   ┌─────────────────────┐
                                                   │4. Quantized Blast   │
                                                   │   Radius & User     │
                                                   │   Impact Counter    │
                                                   └─────────────────────┘
```

### The 4 Observability Pillars in FaultLens Engine:
1. **Service Dependency Mapping (The Map)**: Establishes the static and dynamic microservice directed graph topology (`api-gateway` -> `order-service` -> `payment-gateway` -> `payment-db`).
2. **Metrics Anomaly Detection (The Radar)**: Monitors error rate spikes (> 5%), latency SLA breaches (P95 > 400ms), and resource saturation to flag anomaly timestamps.
3. **Distributed Tracing & Path Traversal (The Trail)**: Traverses W3C parent-child trace spans along the dependency graph down to the deepest leaf failure span to isolate the exact origin node ("who lit the match").
4. **Log Correlation (The Root Cause)**: Correlates Trace ID and timestamp window at the failing node to extract the smoking-gun exception stack trace.
5. **User Impact Quantization (The Blast Radius)**: Aggregates unique affected `user_id`s using time-chunk batch processing (2 to 5-minute configurable windows with grace buffer) to handle out-of-order and network-delayed logs without data loss.

---

##  Security Hardening Matrix

FaultLens implements strict P0 enterprise security defenses:

| Threat Vector | Mitigation Strategy | Implementation Location |
| :--- | :--- | :--- |
| **XSS & Injection (SQLi/NoSQLi/Path Traversal)** | HTML Entity Encoding, regex filters, Pydantic v2 strict schemas | [`security/sanitizer.py`](file:///c:/Users/HP/Desktop/Faultlens/security/sanitizer.py) |
| **Context Header Tampering** | W3C `traceparent` regex validation (`32 hex trace_id`, `16 hex span_id`) | [`security/sanitizer.py`](file:///c:/Users/HP/Desktop/Faultlens/security/sanitizer.py) |
| **Telemetry Flooding (DoS)** | Thread-safe Sliding Window Rate Limiter (HTTP 429 Retry-After) | [`security/rate_limiter.py`](file:///c:/Users/HP/Desktop/Faultlens/security/rate_limiter.py) |
| **Unauthorized RCA & Log Access** | Role-Based Access Control (RBAC: `ADMIN`, `ENGINEER`, `VIEWER`) via JWT Tokens | [`security/rbac.py`](file:///c:/Users/HP/Desktop/Faultlens/security/rbac.py) |
| **Information & Schema Leakage** | Exception masking middleware (returns sanitized error codes externally) | [`security/middleware.py`](file:///c:/Users/HP/Desktop/Faultlens/security/middleware.py) |
| **DOM XSS Vulnerabilities** | Modular Vanilla JS using `textContent` and safe DOM node creation | [`frontend/js/components`](file:///c:/Users/HP/Desktop/Faultlens/frontend/js/components) |

---

##  Repository Structure

```
Faultlens/
├── backend/                  # FastAPI Application Core
│   ├── app.py                # Main FastAPI Server & Router Mounts
│   ├── models.py             # Pydantic v2 Validation Schemas
│   ├── simulation.py         # Telemetry Simulator & Synthetic Fault Scenarios
│   └── routes/
│       ├── auth.py           # Login & JWT RBAC Endpoint
│       ├── telemetry.py      # Rate-Limited Telemetry Ingestion
│       ├── topology.py       # Microservice Dependency Graph API
│       └── rca.py            # RCA Isolation, Blast Radius, Simulation Triggers
├── engine/                   # FaultLens Deterministic RCA Engine
│   ├── dependency_graph.py   # Service Topology & Execution Path Traversal
│   ├── time_chunk_buffer.py  # 2-5 min Time Window Batch Processor with Grace Buffer
│   ├── anomaly_detector.py   # Metrics Anomaly & SLA Breach Detector
│   └── rca_engine.py         # 4-Pillar RCA Pipeline & Origin Isolation
├── security/                 # Hardened Security Infrastructure
│   ├── sanitizer.py          # Input Sanitizer (XSS, SQLi, NoSQLi, W3C Context)
│   ├── rbac.py               # JWT Token Signer & Role Enforcement
│   ├── rate_limiter.py       # Sliding Window DoS Limiter
│   └── middleware.py         # Information Masking & OWASP Headers
├── frontend/                 # Enterprise Dark-Mode Dashboard
│   ├── index.html            # Main Dashboard Page
│   ├── css/
│   │   └── styles.css        # Modern CSS Design Tokens & Glassmorphism Panels
│   └── js/
│       ├── app.js            # Main Controller & Real-Time Polling
│       └── components/       # Secure Modular Frontend Components
│           ├── topology_map.js      # Canvas Interactive Microservice Graph
│           ├── metrics_panel.js     # Metrics Radar & Anomaly Monitor
│           ├── trace_inspector.js   # Distributed Trace Waterfall Inspector
│           ├── blast_radius.js      # User Impact & Token Aggregator
│           ├── log_viewer.js        # Smoking Gun Stack Trace Deep Dive
│           └── simulation_studio.js # Fault Injection Control Deck
├── tests/                    # Comprehensive Test Suite
│   ├── test_rca_engine.py
│   ├── test_security.py
│   └── test_time_chunk_buffer.py
├── pytest.ini
└── README.md
```

---

##  Quickstart Guide

### 1. Prerequisites
- Python 3.10+
- Installed packages: `fastapi`, `uvicorn`, `pyjwt`, `pydantic`, `pytest`

### 2. Running local dev server
Start the FaultLens FastAPI dev server:
```bash
python -m uvicorn backend.app:app --reload --port 8000
```

Open your browser and navigate to:
 **`http://localhost:8000`** — FaultLens Observability Dashboard  
 **`http://localhost:8000/docs`** — Interactive OpenAPI Documentation  
 **`http://localhost:8000/healthz`** — Health Check API  

---

##  Running Unit & Security Test Suite

Run the full automated test suite using `pytest`:
```bash
python -m pytest tests/ -v
```

### Verified Test Coverage:
- `test_rca_cascading_failure_origin_isolation`: Verifies that an anomaly at `api-gateway` caused by a root failure at `payment-db` correctly isolates `payment-db` as the origin match lighter.
- `test_out_of_order_and_late_event_ingestion`: Verifies `TimeChunkBatchBuffer` grace buffer processing out-of-order delayed logs without data loss.
- `test_telemetry_sanitizer_xss_and_sqli`: Verifies neutralisation of script payloads and SQL injections.
- `test_sliding_window_rate_limiter`: Verifies telemetry flood protection blocking excessive requests.

---

##  Interactive Fault Injection Scenarios

Within the dashboard **Fault Injection Studio**, you can trigger synthetic incident scenarios:

1. ** Cascading DB Pool Exhaustion (`payment-db`)**: `payment-db` runs out of slots, returning 500 DB timeout errors, cascading up to `payment-gateway` (500), `order-service` (502), and `api-gateway` (503). FaultLens isolates `payment-db` as the root origin.
2. ** 3rd Party Payment Timeout (`Stripe API`)**: Stripe API endpoint hangs; FaultLens detects external dependency bottleneck.
3. ** Delayed & Out-of-Order Telemetry Stream**: Telemetry arrives 3 minutes late due to network lag; `TimeChunkBatchBuffer` matches events into past grace windows and aggregates blast radius.
4. ** ML Engine Memory Leak & Heap OOM**: `recommendation-engine` heap space exhaustion.
5. ** Telemetry Flooding Attack**: Sends a high-velocity stream to verify HTTP 429 rate limiter protection.
