from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
import graph_engine

router = APIRouter(prefix="/api/risks", tags=["Risks"])


def _auto_detect_risks(db: Session):
    """Scan resources and connections and auto-generate risk alerts."""
    G = graph_engine.build_graph(db)
    new_alerts = []

    def has_open_alert(resource_id: int, alert_type: str) -> bool:
        return db.query(models.RiskAlert).filter(
            models.RiskAlert.resource_id == resource_id,
            models.RiskAlert.alert_type == alert_type,
            models.RiskAlert.resolved == False,  # noqa: E712
        ).first() is not None

    # 1. Flag high risk-score nodes
    for resource in db.query(models.CloudResource).all():
        if resource.risk_score >= 80:
            if not has_open_alert(resource.id, "high_risk"):
                new_alerts.append(models.RiskAlert(
                    resource_id=resource.id,
                    alert_type="high_risk",
                    severity="critical",
                    title=f"Critical Risk: {resource.name}",
                    description=f"{resource.resource_type} resource '{resource.name}' has risk score {resource.risk_score}/100.",
                ))

    # 2. Detect highly connected (hub) nodes
    centrality = graph_engine.compute_centrality(G)
    for nid, score in centrality.items():
        if score > 0.5:
            node = G.nodes.get(nid, {})
            if not has_open_alert(nid, "critical_hub"):
                new_alerts.append(models.RiskAlert(
                    resource_id=nid,
                    alert_type="critical_hub",
                    severity="high",
                    title=f"Critical Hub Detected: {node.get('name', nid)}",
                    description=f"This node has high betweenness centrality ({score:.2f}), making it a single point of failure.",
                ))

    # 3. Check for exposed IAM resources
    for resource in db.query(models.CloudResource).filter(
        models.CloudResource.resource_type == "IAM"
    ).all():
        out_degree = G.out_degree(resource.id) if resource.id in G else 0
        if out_degree >= 3:
            if not has_open_alert(resource.id, "over_privileged"):
                new_alerts.append(models.RiskAlert(
                    resource_id=resource.id,
                    alert_type="over_privileged",
                    severity="high",
                    title=f"Over-Privileged IAM: {resource.name}",
                    description=f"IAM resource '{resource.name}' has {out_degree} outbound permissions. Reduce privilege scope.",
                ))

    for alert in new_alerts:
        db.add(alert)
    db.commit()


@router.get("/alerts", response_model=List[schemas.RiskAlertOut])
def get_alerts(db: Session = Depends(get_db)):
    _auto_detect_risks(db)
    return db.query(models.RiskAlert).filter(models.RiskAlert.resolved == False).all()  # noqa: E712


@router.post("/alerts", response_model=schemas.RiskAlertOut, status_code=201)
def create_alert(alert: schemas.RiskAlertCreate, db: Session = Depends(get_db)):
    db_alert = models.RiskAlert(**alert.model_dump())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(models.RiskAlert).filter(models.RiskAlert.id == alert_id).first()
    if not alert:
        return {"error": "Alert not found"}
    alert.resolved = True  # Fixed: was integer 1, now proper Boolean
    db.commit()
    return {"message": "Alert resolved"}


@router.get("/summary")
def risk_summary(db: Session = Depends(get_db)):
    """High-level risk summary for the dashboard."""
    G = graph_engine.build_graph(db)
    stats = graph_engine.get_graph_stats(G)
    alerts = db.query(models.RiskAlert).filter(models.RiskAlert.resolved == False).all()  # noqa: E712
    critical = sum(1 for a in alerts if a.severity == "critical")
    high = sum(1 for a in alerts if a.severity == "high")
    medium = sum(1 for a in alerts if a.severity == "medium")

    return {
        "graph_stats": stats,
        "open_alerts": len(alerts),
        "critical": critical,
        "high": high,
        "medium": medium,
        "overall_risk_level": (
            "CRITICAL" if critical > 0 else
            "HIGH" if high > 0 else
            "MEDIUM" if medium > 0 else
            "LOW"
        ),
    }
