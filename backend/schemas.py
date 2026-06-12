from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

ResourceType = Literal["Server", "Database", "Storage", "IAM"]
Sensitivity = Literal["High", "Medium", "Low"]
Provider = Literal["AWS", "GCP", "Azure"]
ResourceStatus = Literal["active", "inactive", "deprecated"]
ConnectionType = Literal["network", "iam", "data", "api"]
AlertSeverity = Literal["critical", "high", "medium", "low", "info"]
AlertStatus = Literal["open", "in_progress", "resolved"]


# ─── Cloud Resource Schemas ────────────────────────────────────────────────────

class CloudResourceCreate(BaseModel):
    resource_uid: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$", description="User-defined unique Resource ID (e.g. RES-001)")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable resource name")
    resource_type: ResourceType = Field(..., description="Server | Database | Storage | IAM")
    cost: Optional[float] = Field(0.0, ge=0, le=1_000_000, description="Monthly cost in USD")
    sensitivity: Optional[Sensitivity] = Field("Low", description="High | Medium | Low")
    public_access: Optional[bool] = Field(False, description="Is this resource publicly accessible?")
    provider: Optional[Provider] = "AWS"
    region: Optional[str] = Field("us-east-1", min_length=1, max_length=50)
    risk_score: Optional[float] = Field(0.0, ge=0, le=100)
    status: Optional[ResourceStatus] = "active"


class CloudResourceOut(CloudResourceCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

#------Update schema with all fields optional------------------------------
class CloudResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    resource_type: Optional[ResourceType] = None
    cost: Optional[float] = Field(None, ge=0, le=1_000_000)
    sensitivity: Optional[Sensitivity] = None
    public_access: Optional[bool] = None
    provider: Optional[Provider] = None
    region: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[ResourceStatus] = None


# ─── Connection Schemas ────────────────────────────────────────────────────────

class ResourceConnectionCreate(BaseModel):
    from_node: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$", description="resource_uid of source resource")
    to_node: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$", description="resource_uid of destination resource")
    connection_type: Optional[ConnectionType] = "network"
    risk_weight: Optional[float] = Field(1.0, ge=0, le=10)

    @field_validator("to_node")
    @classmethod
    def target_must_differ(cls, value, info):
        if info.data.get("from_node", "").lower() == value.lower():
            raise ValueError("Source and target cannot be the same resource.")
        return value


class ResourceConnectionOut(ResourceConnectionCreate):
    id: int
    source_id: Optional[int] = None
    target_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── All-Data Response ─────────────────────────────────────────────────────────

class AllDataResponse(BaseModel):
    resources: List[CloudResourceOut]
    connections: List[ResourceConnectionOut]
    total_resources: int
    total_connections: int


# ─── Risk Alert Schemas ────────────────────────────────────────────────────────

class RiskAlertBase(BaseModel):
    resource_id: Optional[int] = None
    alert_type: str
    severity: Optional[AlertSeverity] = "medium"
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class RiskAlertCreate(RiskAlertBase):
    pass


class RiskAlertOut(RiskAlertBase):
    id: int
    created_at: datetime
    resolved: bool
    assignee: Optional[str] = None
    status: str = "open"

    class Config:
        from_attributes = True


class RiskAlertAssign(BaseModel):
    assignee: Optional[str] = None
    status: Optional[AlertStatus] = None


# ─── Graph Schemas ─────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: int
    name: str
    resource_type: str
    provider: str
    region: str
    risk_score: float
    status: str
    sensitivity: str
    public_access: bool
    cost: float


class GraphEdge(BaseModel):
    source: int
    target: int
    connection_type: str
    risk_weight: float


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: dict


class AttackPathResult(BaseModel):
    path: List[int]
    node_names: List[str]
    total_risk: float
    hops: int


# ─── Risk Analysis Schemas ─────────────────────────────────────────────────────

class RiskAnalysisNode(BaseModel):
    id: int
    resource_uid: str
    name: str
    resource_type: str
    provider: str
    region: str
    status: str
    sensitivity: str
    public_access: bool
    cost: float
    # Score breakdown
    connectivity: int
    sensitivity_score: float   # Fixed: was int, float is correct
    exposure_score: float      # Fixed: was int, float is correct
    risk_score: float
    risk_level: str            # Low | Medium | High


class RiskAnalysisResponse(BaseModel):
    nodes: List[RiskAnalysisNode]
    total_nodes: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    formula: str


# ─── Attack Simulation Schemas ─────────────────────────────────────────────────

class SimulateAttackRequest(BaseModel):
    start_node_uid: str


class SimulateAttackResponse(BaseModel):
    steps: List[List[str]]  # Each step contains a list of compromised resource UIDs


# ─── Chatbot Schemas ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []   # last N {role, text} pairs for multi-turn context


class ChatResponse(BaseModel):
    reply: str
    chart: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None


class AttackPathDetail(BaseModel):
    path: List[str]
    description: str


class AttackPathsResponse(BaseModel):
    start_node: str
    paths: List[AttackPathDetail]


# ─── Cost Impact Schemas ───────────────────────────────────────────────────────

class CostImpactRequest(BaseModel):
    start_node_uid: str

class CostImpactResponse(BaseModel):
    total_impacted_nodes: int
    total_cost_loss: float


# ─── Auth Schemas ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, description="Plain-text password (hashed server-side)")


class UserOut(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# ─── Admin / Risk Config Schema ───────────────────────────────────────────────

class RiskConfigOut(BaseModel):
    sensitivity_high: float
    sensitivity_medium: float
    public_access: float
    type_database: float
    type_storage: float
    cost_threshold: float
    cost_bonus: float
    connectivity_per_edge: float
    connectivity_cap: float


# ─── Risk History Schemas ──────────────────────────────────────────────────────

class RiskHistoryPoint(BaseModel):
    resource_id: int
    resource_uid: str
    risk_score: float
    risk_level: str
    recorded_at: datetime

    class Config:
        from_attributes = True


class RiskHistorySummary(BaseModel):
    date: str
    avg_risk_score: float
    high_count: int
    medium_count: int
    low_count: int


class SnapshotResponse(BaseModel):
    snapshots_taken: int
    message: str


# ─── Audit Log Schemas ─────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    entity_uid: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRunOut(BaseModel):
    id: int
    goal: str
    status: str
    plan: Optional[List[Dict[str, Any]]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    findings: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None
    approval_required: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Compliance Schemas ────────────────────────────────────────────────────────

class ComplianceRuleResult(BaseModel):
    rule_id: str
    rule_name: str
    status: str   # PASS | FAIL | WARN
    detail: str


class ComplianceResourceReport(BaseModel):
    resource_id: int
    resource_uid: str
    resource_name: str
    resource_type: str
    provider: str
    results: List[ComplianceRuleResult]
    pass_count: int
    fail_count: int
    warn_count: int
    overall: str  # PASS | FAIL | WARN


class ComplianceReport(BaseModel):
    total_resources: int
    pass_count: int
    fail_count: int
    warn_count: int
    resources: List[ComplianceResourceReport]
    checked_at: datetime


# ─── CVE Schemas ───────────────────────────────────────────────────────────────

class CVEItem(BaseModel):
    cve_id: str
    description: str
    severity: str
    cvss_score: Optional[float] = None
    published: Optional[str] = None
    url: str


class CVEResponse(BaseModel):
    resource_type: str
    query: str
    total: int
    cves: List[CVEItem]


# ─── IAM Analysis Schemas ──────────────────────────────────────────────────────

class IAMFinding(BaseModel):
    severity: str   # critical | high | medium | info
    rule: str
    detail: str


class IAMAnalysisResult(BaseModel):
    total_statements: int
    findings: List[IAMFinding]
    risk_level: str
    summary: str


# ─── Bulk Import Schemas ───────────────────────────────────────────────────────

class BulkImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[str]
    resources: List[CloudResourceOut]


# ─── Cost Optimization Schemas ─────────────────────────────────────────────────

class CostOptimizationItem(BaseModel):
    resource_uid: str
    name: str
    resource_type: str
    provider: str
    region: str
    cost: float
    risk_score: float
    risk_level: str
    reason: str
    suggestion: str


class CostOptimizationReport(BaseModel):
    total_flagged: int
    potential_monthly_savings: float
    items: List[CostOptimizationItem]
