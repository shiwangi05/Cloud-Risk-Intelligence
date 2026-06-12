"""
graph_engine.py
Risk scoring engine with env-configurable weights.
"""

import os
from typing import Dict, List, Optional, Tuple

import networkx as nx
from sqlalchemy.orm import Session

import models

_GRAPH_CACHE: Dict[Tuple[int, int, int], nx.DiGraph] = {}
_GRAPH_CACHE_VERSION = 0


def _load_weights() -> Dict:
    """Read risk scoring weights from environment variables."""
    return {
        "sensitivity_high":          float(os.getenv("RISK_WEIGHT_HIGH", "40")),
        "sensitivity_medium":        float(os.getenv("RISK_WEIGHT_MEDIUM", "20")),
        "public_access":             float(os.getenv("RISK_WEIGHT_PUBLIC", "35")),
        "type_database":             float(os.getenv("RISK_WEIGHT_DATABASE", "10")),
        "type_storage":              float(os.getenv("RISK_WEIGHT_STORAGE", "5")),
        "cost_threshold":            float(os.getenv("RISK_WEIGHT_COST_THRESHOLD", "500")),
        "cost_bonus":                float(os.getenv("RISK_WEIGHT_COST_BONUS", "15")),
        "connectivity_per_edge":     float(os.getenv("RISK_WEIGHT_CONNECTIVITY_PER_EDGE", "5")),
        "connectivity_cap":          float(os.getenv("RISK_WEIGHT_CONNECTIVITY_CAP", "20")),
    }


# Build lookups from current env at import time; updated dynamically by admin endpoint
def _rebuild_maps(w: Dict):
    global SENSITIVITY_MAP, EXPOSURE_MAP, _WEIGHTS
    _WEIGHTS = w
    SENSITIVITY_MAP = {"High": w["sensitivity_high"], "Medium": w["sensitivity_medium"], "Low": 0.0}
    EXPOSURE_MAP = {True: w["public_access"], False: 0.0}


_WEIGHTS: Dict = {}
SENSITIVITY_MAP: Dict = {}
EXPOSURE_MAP: Dict = {}
_rebuild_maps(_load_weights())


def get_weights() -> Dict:
    """Return a copy of the current risk scoring weights."""
    return dict(_WEIGHTS)


def update_weights(new_weights: Dict) -> None:
    """Update weights in memory and persist to .env file."""
    import re
    from pathlib import Path

    env_keys = {
        "sensitivity_high":      "RISK_WEIGHT_HIGH",
        "sensitivity_medium":    "RISK_WEIGHT_MEDIUM",
        "public_access":         "RISK_WEIGHT_PUBLIC",
        "type_database":         "RISK_WEIGHT_DATABASE",
        "type_storage":          "RISK_WEIGHT_STORAGE",
        "cost_threshold":        "RISK_WEIGHT_COST_THRESHOLD",
        "cost_bonus":            "RISK_WEIGHT_COST_BONUS",
        "connectivity_per_edge": "RISK_WEIGHT_CONNECTIVITY_PER_EDGE",
        "connectivity_cap":      "RISK_WEIGHT_CONNECTIVITY_CAP",
    }

    env_path = Path(__file__).parent / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    merged = dict(_WEIGHTS)
    merged.update({k: float(v) for k, v in new_weights.items() if k in env_keys})

    for key, env_var in env_keys.items():
        if key not in merged:
            continue
        val = str(merged[key])
        pattern = rf"^{env_var}=.*$"
        replacement = f"{env_var}={val}"
        if re.search(pattern, text, re.MULTILINE):
            text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
        else:
            text = text.rstrip("\n") + f"\n{replacement}\n"

    env_path.write_text(text, encoding="utf-8")
    _rebuild_maps(merged)
    invalidate_graph_cache()


def invalidate_graph_cache() -> None:
    global _GRAPH_CACHE_VERSION
    _GRAPH_CACHE_VERSION += 1
    _GRAPH_CACHE.clear()


def compute_resource_risk_score(resource, connectivity: int = 0) -> float:
    """Compute the canonical 0-100 risk score using current weights."""
    w = _WEIGHTS
    score = 0.0
    score += SENSITIVITY_MAP.get(resource.sensitivity or "Low", 0)
    score += EXPOSURE_MAP.get(bool(resource.public_access), 0)

    if resource.resource_type == "Database":
        score += w["type_database"]
    elif resource.resource_type == "Storage":
        score += w["type_storage"]

    if resource.cost and resource.cost > w["cost_threshold"]:
        score += w["cost_bonus"]

    score += min(connectivity * w["connectivity_per_edge"], w["connectivity_cap"])
    return min(score, 100.0)


def _risk_level(score: float) -> str:
    if score < 40:
        return "Low"
    if score < 70:
        return "Medium"
    return "High"


def _graph_cache_key(db: Session) -> Tuple[int, int, int]:
    return (
        _GRAPH_CACHE_VERSION,
        db.query(models.CloudResource).count(),
        db.query(models.ResourceConnection).count(),
    )


def build_graph(db: Session) -> nx.DiGraph:
    """Build a directed graph from database resources and connections."""
    cache_key = _graph_cache_key(db)
    if cache_key in _GRAPH_CACHE:
        return _GRAPH_CACHE[cache_key].copy()

    graph = nx.DiGraph()
    resources = db.query(models.CloudResource).all()
    for resource in resources:
        graph.add_node(
            resource.id,
            name=resource.name,
            resource_uid=resource.resource_uid,
            resource_type=resource.resource_type,
            provider=resource.provider,
            region=resource.region,
            risk_score=resource.risk_score or 0,
            status=resource.status,
            sensitivity=resource.sensitivity or "Low",
            public_access=bool(resource.public_access),
            cost=resource.cost or 0.0,
        )

    connections = db.query(models.ResourceConnection).all()
    for connection in connections:
        if connection.source_id and connection.target_id:
            graph.add_edge(
                connection.source_id,
                connection.target_id,
                connection_type=connection.connection_type,
                risk_weight=connection.risk_weight,
            )

    _GRAPH_CACHE.clear()
    _GRAPH_CACHE[cache_key] = graph.copy()
    return graph


def get_graph_stats(graph: nx.DiGraph) -> Dict:
    if graph.number_of_nodes() == 0:
        return {
            "total_nodes": 0, "total_edges": 0, "avg_risk_score": 0,
            "high_risk_nodes": 0, "connected_components": 0, "density": 0,
        }
    risk_scores = [graph.nodes[node].get("risk_score", 0) for node in graph.nodes]
    undirected = graph.to_undirected()
    return {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "avg_risk_score": round(sum(risk_scores) / len(risk_scores), 2),
        "high_risk_nodes": sum(1 for s in risk_scores if s >= 70),
        "connected_components": nx.number_connected_components(undirected) if undirected.number_of_nodes() > 0 else 0,
        "density": round(nx.density(graph), 4),
    }


def find_attack_paths(graph: nx.DiGraph, source_id: int, target_id: int) -> List[List[int]]:
    try:
        return list(nx.all_simple_paths(graph, source=source_id, target=target_id, cutoff=8))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def find_highest_risk_path(graph: nx.DiGraph) -> Optional[Dict]:
    if graph.number_of_nodes() < 2:
        return None
    import itertools
    best_path = None
    best_risk = -1
    pairs = list(itertools.combinations(list(graph.nodes), 2))[:50]
    for source, target in pairs:
        try:
            path = nx.shortest_path(graph, source=source, target=target)
        except nx.NetworkXNoPath:
            continue
        if len(path) < 2:
            continue
        total_risk = sum(graph.nodes[node].get("risk_score", 0) for node in path)
        if total_risk > best_risk:
            best_risk = total_risk
            best_path = path
    if best_path is None:
        return None
    return {
        "path": best_path,
        "node_names": [graph.nodes[node].get("name", str(node)) for node in best_path],
        "total_risk": round(best_risk, 2),
        "hops": len(best_path) - 1,
    }


def get_blast_radius(graph: nx.DiGraph, resource_id: int) -> Dict:
    if resource_id not in graph:
        return {"affected_nodes": [], "count": 0}
    affected = []
    for node_id in nx.descendants(graph, resource_id):
        node = graph.nodes[node_id]
        affected.append({
            "id": node_id,
            "name": node.get("name", str(node_id)),
            "resource_type": node.get("resource_type", "unknown"),
            "risk_score": node.get("risk_score", 0),
        })
    return {
        "source_id": resource_id,
        "source_name": graph.nodes[resource_id].get("name", str(resource_id)),
        "affected_nodes": affected,
        "count": len(affected),
        "total_cascading_risk": round(sum(n["risk_score"] for n in affected), 2),
    }


def compute_centrality(graph: nx.DiGraph) -> Dict[int, float]:
    if graph.number_of_nodes() < 2:
        return {}
    try:
        return nx.betweenness_centrality(graph, weight="risk_weight")
    except Exception:
        return {}


def detect_risk_communities(graph: nx.DiGraph) -> List[List[int]]:
    return [list(c) for c in nx.connected_components(graph.to_undirected())]


def compute_risk_analysis(db: Session) -> List[Dict]:
    """Score every resource and persist to DB."""
    graph = nx.DiGraph()
    resources = db.query(models.CloudResource).all()
    resource_map = {r.id: r for r in resources}

    for resource in resources:
        graph.add_node(
            resource.id,
            name=resource.name, resource_type=resource.resource_type,
            sensitivity=resource.sensitivity or "Low",
            public_access=bool(resource.public_access),
            provider=resource.provider, region=resource.region,
            status=resource.status, cost=resource.cost or 0.0,
        )
    for connection in db.query(models.ResourceConnection).all():
        if connection.source_id and connection.target_id:
            graph.add_edge(connection.source_id, connection.target_id,
                           connection_type=connection.connection_type,
                           risk_weight=connection.risk_weight)

    results = []
    for node_id in graph.nodes:
        attrs = graph.nodes[node_id]
        resource = resource_map.get(node_id)
        connectivity = graph.degree(node_id)
        sensitivity = attrs.get("sensitivity", "Low")
        public_access = attrs.get("public_access", False)
        risk_score = compute_resource_risk_score(resource, connectivity)
        resource.risk_score = risk_score
        results.append({
            "id": node_id,
            "resource_uid": resource.resource_uid,
            "name": attrs.get("name", ""),
            "resource_type": attrs.get("resource_type", ""),
            "provider": attrs.get("provider", "AWS"),
            "region": attrs.get("region", ""),
            "status": attrs.get("status", "active"),
            "sensitivity": sensitivity,
            "public_access": public_access,
            "cost": attrs.get("cost", 0.0),
            "connectivity": connectivity,
            "sensitivity_score": SENSITIVITY_MAP.get(sensitivity, 0),
            "exposure_score": EXPOSURE_MAP.get(public_access, 0),
            "risk_score": risk_score,
            "risk_level": _risk_level(risk_score),
        })

    db.commit()
    invalidate_graph_cache()
    results.sort(key=lambda item: item["risk_score"], reverse=True)
    return results
