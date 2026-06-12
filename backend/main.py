"""
main.py  —  Cloud Risk Intelligence API
Entry point: app creation, middleware, router registration.

Routers:
  resources   → /api/resources, /all-data
  graph       → /api/graph
  risks       → /api/risks
  chat        → /chat, /api/chat
  reports     → /generate-report, /api/documents/*
"""

import os
import re

import networkx as nx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session

import graph_engine
import models
import schemas
from database import Base, engine, get_db
from routers import graph as graph_router
from routers import auth as auth_router
from routers import history as history_router
from routers import resources as resources_router
from routers import risks as risks_router
from routers.chat import router as chat_router
from routers.reports import router as reports_router

from dotenv import load_dotenv
load_dotenv()

# ── Rate limiter ──────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# ── Database init ──────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)


def _ensure_sqlite_schema():
    """Patch old local SQLite DBs that predate newer demo columns."""
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        alert_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(risk_alerts)")).fetchall()
        }
        if "assignee" not in alert_columns:
            conn.execute(text("ALTER TABLE risk_alerts ADD COLUMN assignee VARCHAR(100)"))
        if "status" not in alert_columns:
            conn.execute(text("ALTER TABLE risk_alerts ADD COLUMN status VARCHAR(20) DEFAULT 'open'"))


_ensure_sqlite_schema()

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cloud Risk Intelligence API",
    description="AI-Based Cloud Risk Intelligence Platform — Backend API",
    version="2.0.0",
)

# Attach rate limiter state and 429 handler
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda req, exc: JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please wait a moment before sending another message."},
    )
)

# ── CORS ───────────────────────────────────────────────────────────────────────
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API-key middleware ─────────────────────────────────────────────────────────
_PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
}

@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    expected_key = os.getenv("API_KEY", "dev-secret-key")
    if request.headers.get("X-API-Key") != expected_key:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(resources_router.router)
app.include_router(resources_router.data_router)
app.include_router(graph_router.router)
app.include_router(risks_router.router)
app.include_router(chat_router)
app.include_router(reports_router)
app.include_router(auth_router.router)
app.include_router(history_router.router)
app.include_router(history_router.audit_router)


# ── Risk analysis ──────────────────────────────────────────────────────────────

@app.get("/risk-analysis", response_model=schemas.RiskAnalysisResponse, tags=["Risk Analysis"])
def risk_analysis(db: Session = Depends(get_db)):
    """
    Read-only risk analysis — computes and RETURNS scores but does NOT write to DB.

    Use POST /recompute-risk to persist updated scores.
    """
    graph = graph_engine.build_graph(db)
    resources = db.query(models.CloudResource).all()
    resource_map = {r.id: r for r in resources}

    nodes_data = []
    for node_id in graph.nodes:
        attrs = graph.nodes[node_id]
        resource = resource_map.get(node_id)
        if resource is None:
            continue
        connectivity = graph.degree(node_id)
        sensitivity = attrs.get("sensitivity", "Low")
        public_access = attrs.get("public_access", False)
        sensitivity_score = graph_engine.SENSITIVITY_MAP.get(sensitivity, 0)
        exposure_score = graph_engine.EXPOSURE_MAP.get(public_access, 0)
        risk_score = graph_engine.compute_resource_risk_score(resource, connectivity)

        nodes_data.append({
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
            "sensitivity_score": sensitivity_score,
            "exposure_score": exposure_score,
            "risk_score": risk_score,
            "risk_level": graph_engine._risk_level(risk_score),
        })

    # Resources not yet in the graph (no connections) are included with base scores
    graph_ids = set(graph.nodes)
    for resource in resources:
        if resource.id in graph_ids:
            continue
        risk_score = graph_engine.compute_resource_risk_score(resource, 0)
        nodes_data.append({
            "id": resource.id,
            "resource_uid": resource.resource_uid,
            "name": resource.name,
            "resource_type": resource.resource_type,
            "provider": resource.provider or "AWS",
            "region": resource.region or "",
            "status": resource.status or "active",
            "sensitivity": resource.sensitivity or "Low",
            "public_access": bool(resource.public_access),
            "cost": resource.cost or 0.0,
            "connectivity": 0,
            "sensitivity_score": graph_engine.SENSITIVITY_MAP.get(resource.sensitivity or "Low", 0),
            "exposure_score": graph_engine.EXPOSURE_MAP.get(bool(resource.public_access), 0),
            "risk_score": risk_score,
            "risk_level": graph_engine._risk_level(risk_score),
        })

    nodes_data.sort(key=lambda item: item["risk_score"], reverse=True)
    nodes = [schemas.RiskAnalysisNode(**node) for node in nodes_data]
    return schemas.RiskAnalysisResponse(
        nodes=nodes,
        total_nodes=len(nodes),
        high_risk_count=sum(1 for n in nodes if n.risk_level == "High"),
        medium_risk_count=sum(1 for n in nodes if n.risk_level == "Medium"),
        low_risk_count=sum(1 for n in nodes if n.risk_level == "Low"),
        formula="Risk Score = Sensitivity + Exposure + Type + Cost + Connectivity",
    )


@app.post("/recompute-risk", response_model=schemas.RiskAnalysisResponse, tags=["Risk Analysis"])
def recompute_risk(db: Session = Depends(get_db)):
    """
    Recompute risk scores for ALL resources and PERSIST them to the database.

    This is the only endpoint that writes risk scores back. Use this after
    bulk-importing resources or when you want to force a full recalculation.
    """
    nodes_data = graph_engine.compute_risk_analysis(db)   # writes + commits
    nodes = [schemas.RiskAnalysisNode(**node) for node in nodes_data]
    return schemas.RiskAnalysisResponse(
        nodes=nodes,
        total_nodes=len(nodes),
        high_risk_count=sum(1 for n in nodes if n.risk_level == "High"),
        medium_risk_count=sum(1 for n in nodes if n.risk_level == "Medium"),
        low_risk_count=sum(1 for n in nodes if n.risk_level == "Low"),
        formula="Risk Score = Sensitivity + Exposure + Type + Cost + Connectivity",
    )


# ── Attack simulation ──────────────────────────────────────────────────────────

@app.post("/simulate-attack", response_model=schemas.SimulateAttackResponse, tags=["Attack Simulation"])
def simulate_attack(req: schemas.SimulateAttackRequest, db: Session = Depends(get_db)):
    resources = db.query(models.CloudResource).all()
    uid_to_id = {r.resource_uid: r.id for r in resources}
    id_to_uid = {r.id: r.resource_uid for r in resources}
    start_id = uid_to_id.get(req.start_node_uid)
    if not start_id:
        raise HTTPException(status_code=404, detail=f"Node {req.start_node_uid} not found.")

    graph = graph_engine.build_graph(db)
    steps = [[req.start_node_uid]]
    visited = {start_id}
    queue = [start_id]

    while queue:
        next_queue = []
        for current_id in queue:
            for neighbor_id in graph.successors(current_id):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    next_queue.append(neighbor_id)
        if next_queue:
            steps.append([id_to_uid[node_id] for node_id in next_queue])
        queue = next_queue

    return schemas.SimulateAttackResponse(steps=steps)


@app.get("/attack-path", response_model=schemas.AttackPathsResponse, tags=["Attack Simulation"])
def get_attack_paths(start: str, db: Session = Depends(get_db)):
    resources = db.query(models.CloudResource).all()
    start_resource = next((r for r in resources if r.resource_uid == start), None)
    if not start_resource:
        raise HTTPException(status_code=404, detail=f"Start node '{start}' not found.")

    graph = graph_engine.build_graph(db)
    id_to_uid = {r.id: r.resource_uid for r in resources}
    id_to_name = {r.id: r.name for r in resources}

    raw_paths = []

    def dfs(current_id: int, current_path: list[int]):
        for next_id in graph.successors(current_id):
            if next_id in current_path:
                continue
            next_path = [*current_path, next_id]
            raw_paths.append(next_path)
            dfs(next_id, next_path)

    if start_resource.id in graph:
        dfs(start_resource.id, [start_resource.id])

    paths = []
    for path in raw_paths:
        names = [id_to_name[node_id] for node_id in path]
        paths.append(schemas.AttackPathDetail(
            path=[id_to_uid[node_id] for node_id in path],
            description=f"Attacker compromises '{names[0]}' and can reach '{names[-1]}'.",
        ))
    return schemas.AttackPathsResponse(start_node=start, paths=paths)


# ── Cost impact ────────────────────────────────────────────────────────────────

@app.post("/cost-impact", response_model=schemas.CostImpactResponse, tags=["Cost Impact"])
def cost_impact(req: schemas.CostImpactRequest, db: Session = Depends(get_db)):
    resources = db.query(models.CloudResource).all()
    start_resource = next((r for r in resources if r.resource_uid == req.start_node_uid), None)
    if not start_resource:
        raise HTTPException(status_code=404, detail="Start node not found")

    graph = graph_engine.build_graph(db)
    reachable = set()
    if start_resource.id in graph:
        reachable = set(nx.descendants(graph, start_resource.id))
    reachable.add(start_resource.id)

    id_to_cost = {r.id: r.cost or 0 for r in resources}
    total_cost = sum(id_to_cost.get(node_id, 0) for node_id in reachable)
    return schemas.CostImpactResponse(total_impacted_nodes=len(reachable), total_cost_loss=total_cost)



# ── Admin: Risk formula config ─────────────────────────────────────────────────

@app.get("/admin/risk-config", response_model=schemas.RiskConfigOut, tags=["Admin"])
def get_risk_config():
    """Return current risk scoring weights."""
    return schemas.RiskConfigOut(**graph_engine.get_weights())


@app.put("/admin/risk-config", response_model=schemas.RiskConfigOut, tags=["Admin"])
def update_risk_config(config: schemas.RiskConfigOut):
    """
    Update risk scoring weights live.
    Changes are persisted to the .env file and take effect immediately.
    """
    graph_engine.update_weights(config.model_dump())
    return schemas.RiskConfigOut(**graph_engine.get_weights())


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Cloud Risk Intelligence API",
        "status": "running",
        "version": "2.0.0",
        "docs": "/docs",
    }
