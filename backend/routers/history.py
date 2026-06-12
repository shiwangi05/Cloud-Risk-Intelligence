"""
routers/history.py
Risk History — daily snapshots, trend analysis, anomaly detection.

Endpoints:
  POST /api/history/snapshot  – capture current risk scores for all resources
  GET  /api/history/summary   – day-by-day avg risk trend (last 30 days)
  GET  /api/history/{resource_id} – per-resource trend (last 30 points)
  GET  /api/history/anomalies – resources where score jumped > 20 pts vs prev snapshot
  GET  /api/audit             – paginated audit log
"""

import json
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

import models
import schemas
import graph_engine
from database import get_db

router = APIRouter(prefix="/api/history", tags=["Risk History"])
audit_router = APIRouter(prefix="/api/audit", tags=["Audit Log"])


def _utcnow():
    return datetime.now(timezone.utc)


def write_audit(db: Session, action: str, entity_type: str,
                entity_id: int | None = None, entity_uid: str | None = None,
                detail: str | None = None):
    """Helper called from other routers to write an audit entry."""
    log = models.AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_uid=entity_uid,
        detail=detail,
    )
    db.add(log)
    # Caller is responsible for commit


# ── Snapshot ───────────────────────────────────────────────────────────────────

@router.post("/snapshot", response_model=schemas.SnapshotResponse)
def take_snapshot(db: Session = Depends(get_db)):
    """
    Capture current risk scores for ALL resources and store as a history point.
    Call this once a day (or manually) to build a trend.
    """
    resources = db.query(models.CloudResource).all()
    count = 0
    for resource in resources:
        level = graph_engine._risk_level(resource.risk_score or 0)
        snap = models.RiskHistory(
            resource_id=resource.id,
            resource_uid=resource.resource_uid,
            risk_score=resource.risk_score or 0.0,
            risk_level=level,
        )
        db.add(snap)
        count += 1
    db.commit()
    return schemas.SnapshotResponse(
        snapshots_taken=count,
        message=f"Snapshot recorded for {count} resources at {_utcnow().isoformat()}",
    )


# ── Summary trend (global) ─────────────────────────────────────────────────────

@router.get("/summary", response_model=List[schemas.RiskHistorySummary])
def history_summary(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """
    Return one data-point per day showing avg risk score + level counts.
    Groups history snapshots by calendar date (UTC).
    """
    since = _utcnow() - timedelta(days=days)
    rows = (
        db.query(models.RiskHistory)
        .filter(models.RiskHistory.recorded_at >= since)
        .order_by(models.RiskHistory.recorded_at)
        .all()
    )

    # Group by date string
    by_day: dict[str, list] = {}
    for row in rows:
        day = row.recorded_at.strftime("%Y-%m-%d")
        by_day.setdefault(day, []).append(row)

    result = []
    for day, pts in sorted(by_day.items()):
        result.append(schemas.RiskHistorySummary(
            date=day,
            avg_risk_score=round(sum(p.risk_score for p in pts) / len(pts), 2),
            high_count=sum(1 for p in pts if p.risk_level == "High"),
            medium_count=sum(1 for p in pts if p.risk_level == "Medium"),
            low_count=sum(1 for p in pts if p.risk_level == "Low"),
        ))
    return result


# ── Per-resource trend ─────────────────────────────────────────────────────────

@router.get("/resource/{resource_id}", response_model=List[schemas.RiskHistoryPoint])
def resource_history(resource_id: int, limit: int = Query(30, ge=1, le=90),
                     db: Session = Depends(get_db)):
    """Return the last N history snapshots for a specific resource."""
    rows = (
        db.query(models.RiskHistory)
        .filter(models.RiskHistory.resource_id == resource_id)
        .order_by(models.RiskHistory.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


# ── Anomaly detection ──────────────────────────────────────────────────────────

@router.get("/anomalies")
def get_anomalies(threshold: float = Query(20.0), db: Session = Depends(get_db)):
    """
    Find resources whose risk score jumped by more than `threshold` points
    between the two most recent snapshots.
    """
    resources = db.query(models.CloudResource).all()
    anomalies = []

    for resource in resources:
        last_two = (
            db.query(models.RiskHistory)
            .filter(models.RiskHistory.resource_id == resource.id)
            .order_by(models.RiskHistory.recorded_at.desc())
            .limit(2)
            .all()
        )
        if len(last_two) < 2:
            continue
        latest, previous = last_two[0], last_two[1]
        delta = latest.risk_score - previous.risk_score
        if abs(delta) >= threshold:
            anomalies.append({
                "resource_uid": resource.resource_uid,
                "resource_name": resource.name,
                "resource_type": resource.resource_type,
                "previous_score": previous.risk_score,
                "current_score": latest.risk_score,
                "delta": round(delta, 2),
                "direction": "up" if delta > 0 else "down",
                "recorded_at": latest.recorded_at.isoformat(),
            })

    anomalies.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return {"threshold": threshold, "count": len(anomalies), "anomalies": anomalies}


# ── Audit log ──────────────────────────────────────────────────────────────────

@audit_router.get("/", response_model=List[schemas.AuditLogOut])
def get_audit_log(
    skip: int = 0,
    limit: int = Query(50, le=200),
    entity_type: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.AuditLog)
    if entity_type:
        q = q.filter(models.AuditLog.entity_type == entity_type)
    return q.order_by(models.AuditLog.created_at.desc()).offset(skip).limit(limit).all()
