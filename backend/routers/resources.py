from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
import graph_engine
from database import get_db
from routers.history import write_audit

router = APIRouter(prefix="/api/resources", tags=["Resources"])
data_router = APIRouter(tags=["Data Input"])


@router.get("/", response_model=List[schemas.CloudResourceOut])
def list_resources(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.CloudResource).offset(skip).limit(limit).all()


@router.post("/", response_model=schemas.CloudResourceOut, status_code=201)
def create_resource(resource: schemas.CloudResourceCreate, db: Session = Depends(get_db)):
    existing = db.query(models.CloudResource).filter(
        models.CloudResource.resource_uid == resource.resource_uid
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Resource ID '{resource.resource_uid}' already exists.")

    data = resource.model_dump()
    data["risk_score"] = graph_engine.compute_resource_risk_score(resource)
    db_resource = models.CloudResource(**data)
    db.add(db_resource)
    write_audit(db, "CREATE", "CloudResource", entity_uid=resource.resource_uid)
    db.commit()
    db.refresh(db_resource)
    graph_engine.invalidate_graph_cache()
    return db_resource


@router.get("/{resource_id}", response_model=schemas.CloudResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.query(models.CloudResource).filter(models.CloudResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.put("/{resource_id}", response_model=schemas.CloudResourceOut)
def update_resource(resource_id: int, update: schemas.CloudResourceUpdate, db: Session = Depends(get_db)):
    resource = db.query(models.CloudResource).filter(models.CloudResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    for key, value in update.model_dump(exclude_none=True).items():
        setattr(resource, key, value)
    graph_engine.invalidate_graph_cache()
    graph = graph_engine.build_graph(db)
    resource.risk_score = graph_engine.compute_resource_risk_score(
        resource,
        graph.degree(resource.id) if resource.id in graph else 0,
    )
    write_audit(
        db,
        "UPDATE",
        "CloudResource",
        entity_id=resource.id,
        entity_uid=resource.resource_uid,
        detail="Updated resource metadata and recomputed risk score.",
    )
    db.commit()
    db.refresh(resource)
    graph_engine.invalidate_graph_cache()
    return resource


@router.delete("/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.query(models.CloudResource).filter(models.CloudResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    write_audit(db, "DELETE", "CloudResource", entity_id=resource.id, entity_uid=resource.resource_uid)
    db.delete(resource)
    db.commit()
    graph_engine.invalidate_graph_cache()   # Don't recompute; caller can POST /recompute-risk
    return {"message": "Resource deleted successfully"}


# ─── Connections ───────────────────────────────────────────────────────────────

@router.get("/connections/all", response_model=List[schemas.ResourceConnectionOut])
def list_connections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.ResourceConnection).offset(skip).limit(limit).all()


@router.post("/connections/", response_model=schemas.ResourceConnectionOut, status_code=201)
def create_connection(conn: schemas.ResourceConnectionCreate, db: Session = Depends(get_db)):
    source = db.query(models.CloudResource).filter(
        models.CloudResource.resource_uid == conn.from_node
    ).first()
    target = db.query(models.CloudResource).filter(
        models.CloudResource.resource_uid == conn.to_node
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail=f"Source resource '{conn.from_node}' not found.")
    if not target:
        raise HTTPException(status_code=404, detail=f"Target resource '{conn.to_node}' not found.")
    if source.id == target.id:
        raise HTTPException(status_code=400, detail="Source and target cannot be the same resource.")

    existing = db.query(models.ResourceConnection).filter(
        models.ResourceConnection.source_id == source.id,
        models.ResourceConnection.target_id == target.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This connection already exists.")

    db_conn = models.ResourceConnection(
        from_node=conn.from_node,
        to_node=conn.to_node,
        source_id=source.id,
        target_id=target.id,
        connection_type=conn.connection_type,
        risk_weight=conn.risk_weight,
    )
    db.add(db_conn)
    write_audit(
        db,
        "CREATE",
        "Connection",
        entity_uid=f"{conn.from_node}->{conn.to_node}",
    )
    db.commit()
    db.refresh(db_conn)
    graph_engine.invalidate_graph_cache()   # scores updated lazily on next /recompute-risk
    return db_conn


@router.delete("/connections/{conn_id}")
def delete_connection(conn_id: int, db: Session = Depends(get_db)):
    conn = db.query(models.ResourceConnection).filter(models.ResourceConnection.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    write_audit(db, "DELETE", "Connection", entity_id=conn.id, entity_uid=f"{conn.from_node}->{conn.to_node}")
    db.delete(conn)
    db.commit()
    graph_engine.invalidate_graph_cache()   # scores updated lazily on next /recompute-risk
    return {"message": "Connection deleted"}


@data_router.get("/all-data", tags=["Resources"])
def get_all_data(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Paginated list of resources and connections."""
    total_resources = db.query(models.CloudResource).count()
    total_connections = db.query(models.ResourceConnection).count()
    resources = (
        db.query(models.CloudResource)
        .order_by(models.CloudResource.resource_uid)
        .offset(skip)
        .limit(limit)
        .all()
    )
    connections = (
        db.query(models.ResourceConnection)
        .order_by(models.ResourceConnection.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "resources": resources,
        "connections": connections,
        "total_resources": total_resources,
        "total_connections": total_connections,
        "skip": skip,
        "limit": limit,
        "has_more_resources": (skip + limit) < total_resources,
        "has_more_connections": (skip + limit) < total_connections,
    }
