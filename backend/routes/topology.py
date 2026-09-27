"""
FaultLens API Router - System Topology Map & Service Graph
Provides real-time microservice dependency graph data and health indicators.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any

router = APIRouter(prefix="/api/v1/topology", tags=["System Topology"])


def get_engine():
    from backend.app import global_rca_engine
    return global_rca_engine


@router.get("")
async def get_system_topology():
    """
    Returns the microservice graph structure enriched with live health metrics and anomaly indicators.
    """
    engine = get_engine()
    graph_dict = engine.graph.to_dict()

    enriched_nodes = []
    for node in graph_dict["nodes"]:
        s_id = node["id"]
        health = engine.anomaly_detector.get_service_health(s_id)
        node_copy = dict(node)
        node_copy["health_status"] = health["status"]
        node_copy["error_rate_pct"] = health["error_rate_pct"]
        node_copy["latency_p95_ms"] = health["latency_p95_ms"]
        node_copy["cpu_usage_pct"] = health["cpu_usage_pct"]
        node_copy["throughput_rps"] = health.get("throughput_rps", 100.0)
        enriched_nodes.append(node_copy)

    return {
        "nodes": enriched_nodes,
        "dependencies": graph_dict["dependencies"]
    }


@router.get("/node/{service_id}")
async def get_node_details(service_id: str):
    engine = get_engine()
    if service_id not in engine.graph.nodes:
        raise HTTPException(status_code=404, detail=f"Service node [{service_id}] not found in topology graph.")

    node = engine.graph.nodes[service_id]
    health = engine.anomaly_detector.get_service_health(service_id)
    upstreams = engine.graph.get_upstream_services(service_id)
    downstreams = engine.graph.get_downstream_services(service_id)

    return {
        "node": {
            "id": node.id,
            "name": node.name,
            "tier": node.tier,
            "sla_latency_ms": node.sla_latency_ms,
            "error_threshold_pct": node.error_threshold_pct
        },
        "health": health,
        "upstream_callers": upstreams,
        "downstream_dependencies": downstreams
    }
