from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import graph_engine
import schemas

router = APIRouter(prefix="/api/graph", tags=["Graph"])


@router.get("/", response_model=schemas.GraphData)
def get_graph(db: Session = Depends(get_db)):
    """Return the full graph with nodes, edges, and stats."""
    G = graph_engine.build_graph(db)
    stats = graph_engine.get_graph_stats(G)

    nodes = [
        schemas.GraphNode(
            id=nid,
            name=G.nodes[nid].get("name", ""),
            resource_type=G.nodes[nid].get("resource_type", ""),
            provider=G.nodes[nid].get("provider", "AWS"),
            region=G.nodes[nid].get("region", ""),
            risk_score=G.nodes[nid].get("risk_score", 0),
            status=G.nodes[nid].get("status", "active"),
            sensitivity=G.nodes[nid].get("sensitivity", "Low"),
            public_access=G.nodes[nid].get("public_access", False),
            cost=G.nodes[nid].get("cost", 0.0),
        )
        for nid in G.nodes
    ]

    edges = [
        schemas.GraphEdge(
            source=u,
            target=v,
            connection_type=G.edges[u, v].get("connection_type", "network"),
            risk_weight=G.edges[u, v].get("risk_weight", 1.0),
        )
        for u, v in G.edges
    ]

    return schemas.GraphData(nodes=nodes, edges=edges, stats=stats)


@router.get("/attack-path")
def get_attack_path(source_id: int, target_id: int, db: Session = Depends(get_db)):
    """Find attack paths between two nodes."""
    G = graph_engine.build_graph(db)
    paths = graph_engine.find_attack_paths(G, source_id, target_id)
    result = []
    for path in paths[:5]:  # limit to top 5 paths
        node_names = [G.nodes[n].get("name", str(n)) for n in path]
        total_risk = sum(G.nodes[n].get("risk_score", 0) for n in path)
        result.append({
            "path": path,
            "node_names": node_names,
            "total_risk": round(total_risk, 2),
            "hops": len(path) - 1,
        })
    return {"paths": result, "count": len(result)}


@router.get("/highest-risk-path")
def highest_risk_path(db: Session = Depends(get_db)):
    """Find the highest cumulative risk attack path in the graph."""
    G = graph_engine.build_graph(db)
    result = graph_engine.find_highest_risk_path(G)
    if result is None:
        return {"message": "No paths found. Add more resources and connections."}
    return result


@router.get("/blast-radius/{resource_id}")
def blast_radius(resource_id: int, db: Session = Depends(get_db)):
    """Simulate blast radius from a compromised resource."""
    G = graph_engine.build_graph(db)
    return graph_engine.get_blast_radius(G, resource_id)


@router.get("/centrality")
def centrality(db: Session = Depends(get_db)):
    """Return betweenness centrality scores for all nodes."""
    G = graph_engine.build_graph(db)
    scores = graph_engine.compute_centrality(G)
    # Enrich with name
    result = []
    for nid, score in sorted(scores.items(), key=lambda x: -x[1])[:20]:
        node = G.nodes.get(nid, {})
        result.append({
            "id": nid,
            "name": node.get("name", str(nid)),
            "resource_type": node.get("resource_type", ""),
            "centrality_score": round(score, 4),
            "risk_score": node.get("risk_score", 0),
        })
    return {"centrality": result}
