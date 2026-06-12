import os
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.dirname(__file__))

from database import Base, get_db
from main import app


TEST_API_KEY = "dev-secret-key"

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def auth_headers():
    return {"X-API-Key": TEST_API_KEY}


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def sample_resource(uid="RES-001", name="App Server"):
    return {
        "resource_uid": uid,
        "name": name,
        "resource_type": "Server",
        "cost": 125.0,
        "sensitivity": "Medium",
        "public_access": False,
        "provider": "AWS",
        "region": "us-east-1",
        "status": "active",
    }


def test_create_resource_returns_201():
    response = client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    assert response.status_code == 201
    assert response.json()["resource_uid"] == "RES-001"


def test_duplicate_resource_uid_returns_400():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    response = client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    assert response.status_code == 400


def test_get_graph_returns_nodes_and_edges_structure():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    response = client.get("/api/graph/", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert "nodes" in body
    assert "edges" in body
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)


def test_chat_total_cost_returns_reply_string():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    response = client.post("/chat", json={"message": "total cost"}, headers=auth_headers())
    assert response.status_code == 200
    assert isinstance(response.json()["reply"], str)
    assert "Total cloud cost" in response.json()["reply"]


def test_chat_answers_simple_math_without_ai_key():
    response = client.post("/api/chat", json={"message": "1+1"}, headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["reply"] == "1+1 = 2"


def test_chat_writes_poem_without_ai_key():
    response = client.post("/api/chat", json={"message": "write a poem about cloud security"}, headers=auth_headers())
    assert response.status_code == 200
    assert "Here is a short poem" in response.json()["reply"]


def test_chat_returns_pie_chart_artifact():
    response = client.post("/api/chat", json={"message": "generate pie chart apples: 2 oranges: 3"}, headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["chart"]["type"] == "pie"
    assert body["chart"]["labels"] == ["apples", "oranges"]
    assert body["chart"]["values"] == [2.0, 3.0]


def test_chat_project_overview_works_without_inventory():
    response = client.post("/chat", json={"message": "What is this project?"}, headers=auth_headers())
    assert response.status_code == 200
    assert "Cloud Risk Intelligence Platform overview" in response.json()["reply"]


def test_chat_api_reference_lists_resource_endpoint():
    response = client.post("/chat", json={"message": "Show API endpoints"}, headers=auth_headers())
    assert response.status_code == 200
    assert "POST /api/resources/" in response.json()["reply"]


def test_api_chat_alias_works():
    response = client.post("/api/chat", json={"message": "What is the risk formula?"}, headers=auth_headers())
    assert response.status_code == 200
    assert "Risk scoring model" in response.json()["reply"]


def test_chat_specific_resource_details():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    response = client.post("/chat", json={"message": "Tell me about RES-001"}, headers=auth_headers())
    assert response.status_code == 200
    assert "Resource details for RES-001" in response.json()["reply"]


def test_document_exports_return_files():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())

    pdf = client.get("/api/documents/pdf", headers=auth_headers())
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    excel = client.get("/api/documents/excel", headers=auth_headers())
    assert excel.status_code == 200
    assert excel.content.startswith(b"PK")

    word = client.get("/api/documents/word", headers=auth_headers())
    assert word.status_code == 200
    assert word.content.startswith(b"PK")


def test_create_connection_missing_node_returns_404():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())
    response = client.post(
        "/api/resources/connections/",
        json={"from_node": "RES-001", "to_node": "MISSING", "connection_type": "network", "risk_weight": 1},
        headers=auth_headers(),
    )
    assert response.status_code == 404


def test_invalid_resource_type_is_rejected():
    payload = sample_resource()
    payload["resource_type"] = "Unknown"
    response = client.post("/api/resources/", json=payload, headers=auth_headers())
    assert response.status_code == 422


def test_auth_register_login_and_me():
    register = client.post(
        "/auth/register",
        json={"username": "analyst", "password": "secret123"},
        headers=auth_headers(),
    )
    assert register.status_code == 201

    login = client.post(
        "/auth/token",
        data={"username": "analyst", "password": "secret123"},
        headers=auth_headers(),
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get(
        "/auth/me",
        headers={**auth_headers(), "Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "analyst"


def test_history_snapshot_and_audit_log_are_wired():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())

    snapshot = client.post("/api/history/snapshot", headers=auth_headers())
    assert snapshot.status_code == 200
    assert snapshot.json()["snapshots_taken"] == 1

    audit = client.get("/api/audit/", headers=auth_headers())
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "CREATE"


def test_pdf_report_is_read_only_for_risk_score():
    client.post("/api/resources/", json=sample_resource(), headers=auth_headers())

    before = client.get("/api/resources/", headers=auth_headers()).json()[0]["risk_score"]
    response = client.get("/generate-report", headers=auth_headers())
    after = client.get("/api/resources/", headers=auth_headers()).json()[0]["risk_score"]

    assert response.status_code == 200
    assert before == after


def test_agentic_investigation_creates_run_log():
    payload = sample_resource()
    payload["sensitivity"] = "High"
    payload["public_access"] = True
    client.post("/api/resources/", json=payload, headers=auth_headers())

    response = client.post(
        "/api/chat",
        json={"message": "Run an agentic full risk review and remediation plan"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert "Agentic investigation completed" in body["reply"]
    assert body["agent"]["approval_required"] is True
    assert len(body["agent"]["plan"]) >= 3

    runs = client.get("/api/agent/runs", headers=auth_headers())
    assert runs.status_code == 200
    assert runs.json()[0]["goal"] == "Run an agentic full risk review and remediation plan"
