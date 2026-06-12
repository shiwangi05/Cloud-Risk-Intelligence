from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def _utcnow():
    """Timezone-aware UTC datetime — replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


class CloudResource(Base):
    __tablename__ = "cloud_resources"

    id = Column(Integer, primary_key=True, index=True)
    resource_uid = Column(String(50), unique=True, index=True, nullable=False)  # user-defined Resource ID
    name = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)   # Server, Database, Storage
    cost = Column(Float, default=0.0)                    # monthly cost in USD
    sensitivity = Column(String(10), default="Low")      # High, Medium, Low
    public_access = Column(Boolean, default=False)       # True = Yes, False = No

    # Extended / graph fields
    provider = Column(String(30), default="AWS")         # AWS, GCP, Azure
    region = Column(String(50), default="us-east-1")
    risk_score = Column(Float, default=0.0)              # 0-100 (auto-computed)
    status = Column(String(20), default="active")

    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    source_connections = relationship(
        "ResourceConnection",
        foreign_keys="ResourceConnection.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    target_connections = relationship(
        "ResourceConnection",
        foreign_keys="ResourceConnection.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )


class ResourceConnection(Base):
    __tablename__ = "resource_connections"

    id = Column(Integer, primary_key=True, index=True)
    from_node = Column(String(50), nullable=False)   # resource_uid of source
    to_node = Column(String(50), nullable=False)     # resource_uid of target
    source_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    target_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    connection_type = Column(String(50), default="network")
    risk_weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    source = relationship("CloudResource", foreign_keys=[source_id], back_populates="source_connections")
    target = relationship("CloudResource", foreign_keys=[target_id], back_populates="target_connections")


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="medium")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    resolved = Column(Boolean, default=False)
    # Workflow fields
    assignee = Column(String(100), nullable=True)
    status = Column(String(20), default="open")  # open | in_progress | resolved


class RiskHistory(Base):
    """Daily risk score snapshots per resource."""
    __tablename__ = "risk_history"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=False)
    resource_uid = Column(String(50), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)   # Low | Medium | High
    recorded_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class AuditLog(Base):
    """Immutable log of every create/update/delete operation."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(20), nullable=False)        # CREATE | UPDATE | DELETE
    entity_type = Column(String(50), nullable=False)   # CloudResource | Connection | Alert
    entity_id = Column(Integer, nullable=True)
    entity_uid = Column(String(100), nullable=True)
    detail = Column(Text, nullable=True)               # JSON-serialised before/after
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class AgentRun(Base):
    """Agent investigation trace: plan, tool steps, recommendations, and approval notes."""
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    goal = Column(Text, nullable=False)
    status = Column(String(20), default="completed")
    plan = Column(JSON, nullable=True)
    steps = Column(JSON, nullable=True)
    findings = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    approval_required = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class ComplianceResult(Base):
    """CIS Benchmark compliance check results per resource."""
    __tablename__ = "compliance_results"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=False)
    resource_uid = Column(String(50), nullable=False)
    rule_id = Column(String(50), nullable=False)
    rule_name = Column(String(200), nullable=False)
    status = Column(String(10), nullable=False)        # PASS | FAIL | WARN
    detail = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class User(Base):
    """Application user for JWT authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
