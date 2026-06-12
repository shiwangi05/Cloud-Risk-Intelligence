"""
routers/chat.py
All AI chatbot logic extracted from main.py.

Endpoints:
  POST /chat        – primary chat endpoint
  POST /api/chat    – alias (kept for backward compatibility)
"""

import ast
import json
import math
import operator
import os
import re
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import graph_engine
import models
import schemas
from database import get_db

router = APIRouter(tags=["AI Chatbot"])


# ── Internal helpers ───────────────────────────────────────────────────────────

def _find_resource_in_message(message: str, resources: list[models.CloudResource]):
    normalized = message.lower()
    tokens = set(re.findall(r"[\w-]+", normalized))
    for resource in resources:
        uid = resource.resource_uid.lower()
        name = resource.name.lower()
        if uid in tokens or uid in normalized or name in normalized:
            return resource
    return None


def _attack_paths_from(db: Session, start_resource: models.CloudResource) -> list[list[int]]:
    graph = graph_engine.build_graph(db)
    paths = []

    def dfs(current_id: int, current_path: list[int]):
        for next_id in graph.successors(current_id):
            if next_id in current_path:
                continue
            next_path = [*current_path, next_id]
            paths.append(next_path)
            dfs(next_id, next_path)

    if start_resource.id in graph:
        dfs(start_resource.id, [start_resource.id])
    return paths


def _project_capabilities_reply() -> str:
    return (
        "Cloud Risk Intelligence Platform overview:\n"
        "- Purpose: model cloud infrastructure as a directed graph and surface risk, blast radius, attack paths, cost impact, and alerts.\n"
        "- Backend: FastAPI, SQLAlchemy, SQLite, NetworkX, ReportLab, python-dotenv.\n"
        "- Frontend: React, Vite, Axios, React Flow, Dagre layout, React Hot Toast.\n"
        "- Core data: cloud resources, directed resource connections, and risk alerts.\n"
        "- Main workflows: add inventory, connect resources, view all data, analyze risk, visualize graph, simulate attacks, chat with the assistant, and download a PDF report."
    )


def _api_reference_reply() -> str:
    return (
        "Important API endpoints:\n"
        "- GET /: health check.\n"
        "- POST /api/resources/: create a cloud resource.\n"
        "- GET /api/resources/: list resources with skip and limit query parameters.\n"
        "- PUT /api/resources/{id}: update a resource and recompute risk.\n"
        "- DELETE /api/resources/{id}: delete a resource.\n"
        "- POST /api/resources/connections/: create a directed connection by resource UID.\n"
        "- GET /api/resources/connections/all: list connections with pagination.\n"
        "- GET /all-data: resources, connections, and totals.\n"
        "- GET /risk-analysis: canonical 0-100 risk scoring for every resource (read-only).\n"
        "- POST /recompute-risk: recompute and persist risk scores to the database.\n"
        "- GET /api/graph/: graph nodes, edges, and stats.\n"
        "- GET /api/risks/alerts: open risk alerts with automatic detection.\n"
        "- POST /chat: this assistant.\n"
        "- GET /generate-report: PDF report.\n"
        "- POST /auth/register: create a user account.\n"
        "- POST /auth/token: login and get a JWT token."
    )


def _data_model_reply() -> str:
    return (
        "Project data model:\n"
        "- CloudResource: resource_uid, name, resource_type, cost, sensitivity, public_access, provider, region, risk_score, status, created_at.\n"
        "- ResourceConnection: from_node, to_node, source_id, target_id, connection_type, risk_weight, created_at.\n"
        "- RiskAlert: resource_id, alert_type, severity, title, description, created_at, resolved.\n"
        "- User: username, hashed_password, is_active, created_at.\n"
        "- Connections are stored by human-friendly UIDs and resolved to integer foreign keys for graph traversal."
    )


def _risk_formula_reply() -> str:
    return (
        "Risk scoring model:\n"
        "- Formula: Score = Sensitivity + Exposure + TypeBonus + CostBonus + min(Connections x PerEdge, Cap).\n"
        
    )


def _format_resource(resource: models.CloudResource) -> str:
    return (
        f"- {resource.resource_uid} ({resource.name}): "
        f"type={resource.resource_type}, provider={resource.provider}, region={resource.region}, "
        f"sensitivity={resource.sensitivity}, public={bool(resource.public_access)}, "
        f"cost=${resource.cost or 0:,.2f}, risk={resource.risk_score or 0:.1f}, status={resource.status}"
    )


def _recommendations(resources: list[models.CloudResource], graph) -> list[str]:
    recommendations = []
    for resource in sorted(resources, key=lambda item: item.risk_score or 0, reverse=True):
        actions = []
        degree = graph.degree(resource.id) if resource.id in graph else 0
        if resource.public_access:
            actions.append("remove public exposure")
        if resource.sensitivity == "High":
            actions.append("tighten IAM and encryption controls")
        if degree >= 3:
            actions.append("segment network paths")
        if (resource.cost or 0) > 500:
            actions.append("confirm backups and recovery priority")
        if actions:
            recommendations.append(f"- {resource.resource_uid} ({resource.name}): {', '.join(actions)}")
    return recommendations


def _live_context(db: Session) -> str:
    resources = db.query(models.CloudResource).all()
    connections = db.query(models.ResourceConnection).all()
    alerts = db.query(models.RiskAlert).filter(models.RiskAlert.resolved == False).all()  # noqa: E712
    total_cost = sum(resource.cost or 0 for resource in resources)
    high_risk = [resource for resource in resources if (resource.risk_score or 0) >= 70]
    return (
        "Project context:\n"
        "Cloud Risk Intelligence Platform using FastAPI, SQLAlchemy, SQLite, NetworkX, React, Vite, and React Flow.\n"
        "It stores cloud resources, directed connections, and risk alerts.\n"
        "Risk score is 0-100 from sensitivity, exposure, type, cost, and connectivity.\n"
        f"Current live data: {len(resources)} resources, {len(connections)} connections, "
        f"{len(high_risk)} high-risk resources, {len(alerts)} open alerts, total monthly cost ${total_cost:,.2f}.\n"
        "When answering, be helpful for both general questions and this platform's cloud-risk domain."
    )


def _call_gemini(message: str, db: Session, history: list | None = None) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    # Build multi-turn contents array from history
    contents = []
    system_text = (
        f"{_live_context(db)}\n\n"
        "Answer the user's question clearly and naturally, like a general AI assistant. "
        "If useful, relate the answer to the cloud risk platform context, but do not mention API keys or setup steps."
    )
    # Prefix the first turn with system context
    for i, turn in enumerate(history or []):
        role = "user" if turn.get("role") == "user" else "model"
        text = turn.get("text", "")
        if i == 0 and role == "user":
            text = f"{system_text}\n\n{text}"
        contents.append({"role": role, "parts": [{"text": text}]})

    # Add the current user message
    current_text = message if contents else f"{system_text}\n\nUser question: {message}"
    contents.append({"role": "user", "parts": [{"text": current_text}]})

    payload = {"contents": contents}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return f"AI provider error:\n- Gemini could not answer right now: {exc}"

    candidates = body.get("candidates", [])
    if not candidates:
        return "AI provider returned no answer."

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    return text or "AI provider returned an empty answer."


# ── Safe math evaluator ────────────────────────────────────────────────────────

_ALLOWED_MATH_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_ALLOWED_MATH_FUNCS = {
    "abs": abs, "round": round, "sqrt": math.sqrt,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10,
    "floor": math.floor, "ceil": math.ceil, "factorial": math.factorial,
}

_ALLOWED_MATH_NAMES = {"pi": math.pi, "e": math.e}


def _eval_math(node):
    if isinstance(node, ast.Expression):
        return _eval_math(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_MATH_OPS:
        return _ALLOWED_MATH_OPS[type(node.op)](_eval_math(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_MATH_OPS:
        left = _eval_math(node.left)
        right = _eval_math(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise ValueError("Exponent too large")
        return _ALLOWED_MATH_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Name) and node.id in _ALLOWED_MATH_NAMES:
        return _ALLOWED_MATH_NAMES[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_MATH_FUNCS:
        args = [_eval_math(arg) for arg in node.args]
        if len(args) > 2:
            raise ValueError("Too many arguments")
        return _ALLOWED_MATH_FUNCS[node.func.id](*args)
    raise ValueError("Unsupported math")


def _try_math_reply(message: str) -> str | None:
    raw = message.strip().lower()

    percent_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:percent|%)\s+of\s+(-?\d+(?:\.\d+)?)", raw)
    if percent_match:
        pct = float(percent_match.group(1))
        base = float(percent_match.group(2))
        result = base * pct / 100
        if result.is_integer():
            result = int(result)
        return f"{message.strip()} = {result}"

    expression = raw
    expression = re.sub(r"^(what is|what's|calculate|compute|solve|answer)\s+", "", expression)
    expression = expression.strip(" ?")
    expression = expression.replace("÷", "/").replace("^", "**")
    expression = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", expression)

    has_math_signal = (
        any(op in expression for op in ["+", "-", "*", "/", "%", "**", "(", ")"])
        or any(func in expression for func in _ALLOWED_MATH_FUNCS)
    )
    if not has_math_signal:
        return None
    if not re.fullmatch(r"[\d\s\.\+\-\*\/\%\(\),a-z_]+", expression):
        return None
    try:
        result = _eval_math(ast.parse(expression, mode="eval"))
    except Exception:
        return None
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"{message.strip()} = {result}"


def _poem_reply(message: str) -> str | None:
    if "poem" not in message.lower() and "poetry" not in message.lower():
        return None
    topic = "clouds and quiet circuits"
    match = re.search(r"(?:about|on)\s+(.+)", message, re.IGNORECASE)
    if match:
        topic = match.group(1).strip(" .?!")[:80]
    return (
        f"Here is a short poem about {topic}:\n"
        "- In silent racks the signals gleam,\n"
        "- Like stars reflected in a stream.\n"
        "- A guarded path, a watchful light,\n"
        "- Keeps fragile systems safe at night."
    )


def _chart_reply(message: str, db: Session) -> tuple[str, dict] | None:
    lowered = message.lower()
    if not any(term in lowered for term in ["chart", "plot", "graph"]):
        return None

    chart_type = "bar"
    if "pie" in lowered:
        chart_type = "pie"
    elif "line" in lowered:
        chart_type = "line"
    elif "area" in lowered:
        chart_type = "area"
    elif "scatter" in lowered:
        chart_type = "scatter"
    elif "bar" in lowered or "column" in lowered:
        chart_type = "bar"

    chart_text = re.sub(r"(?i).*?(?:pie|bar|line|area|scatter|column)?\s*(?:chart|plot|graph)(?:\s+of|\s+for)?", "", message, count=1).strip()
    pairs = re.findall(r"([A-Za-z][\w-]{0,24})\s*[:=]\s*(\d+(?:\.\d+)?)", chart_text)
    labels = []
    values = []
    if pairs:
        for label, value in pairs[:8]:
            labels.append(label.strip())
            values.append(float(value))
    else:
        resources = db.query(models.CloudResource).all()
        counts = {}
        for resource in resources:
            counts[resource.resource_type or "Unknown"] = counts.get(resource.resource_type or "Unknown", 0) + 1
        if counts:
            labels = list(counts.keys())
            values = list(counts.values())
        else:
            labels = ["Example A", "Example B", "Example C"]
            values = [40, 35, 25]

    chart = {"type": chart_type, "labels": labels, "values": values}
    return (f"Generated a {chart_type} chart.", chart)


def _local_general_reply(message: str) -> str:
    lowered = message.lower().strip()
    if any(greeting in lowered for greeting in ["hello", "hi", "hey"]):
        return "Hello! Ask me anything, or ask about your cloud risk graph."
    if "cloud risk" in lowered:
        return (
            "Cloud risk intelligence means understanding which cloud resources are exposed, sensitive, expensive, "
            "highly connected, or likely to create cascading impact. "
            "This platform models those resources as a graph so you can see risk scores, attack paths, blast radius, cost impact, and alerts."
        )
    return (
        "I can help with that. Please ask the question a little more specifically, or ask me to explain, calculate, summarize, write, or create a chart."
    )


# ── Route handlers ─────────────────────────────────────────────────────────────

def _should_run_agent(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in [
        "agent", "agentic", "investigate", "triage", "security review",
        "remediation plan", "analyze everything", "full risk review",
        "autonomous", "root cause", "prioritize risks",
    ])


def _agent_plan(message: str) -> list[dict]:
    lowered = message.lower()
    plan = [
        {"tool": "inventory_summary", "reason": "Establish asset, edge, cost, and exposure context."},
        {"tool": "risk_prioritizer", "reason": "Rank resources by risk score and identify critical items."},
    ]
    if any(term in lowered for term in ["graph", "attack", "blast", "path", "dependency", "everything", "full"]):
        plan.append({"tool": "graph_intelligence", "reason": "Inspect centrality, graph density, and reachable impact paths."})
    if any(term in lowered for term in ["alert", "triage", "finding", "everything", "full"]):
        plan.append({"tool": "alert_triage", "reason": "Review open alerts and severity distribution."})
    if any(term in lowered for term in ["recommend", "remediation", "fix", "secure", "everything", "full"]):
        plan.append({"tool": "remediation_planner", "reason": "Generate prioritized actions that need human approval before execution."})
    return plan


def _run_agent_tool(tool: str, db: Session, resources: list[models.CloudResource], connections: list[models.ResourceConnection], graph) -> dict:
    if tool == "inventory_summary":
        total_cost = sum(resource.cost or 0 for resource in resources)
        public_count = sum(1 for resource in resources if resource.public_access)
        high_sensitivity = sum(1 for resource in resources if resource.sensitivity == "High")
        return {"tool": tool, "status": "completed", "finding": f"Inventory has {len(resources)} resources, {len(connections)} connections, {public_count} public resources, {high_sensitivity} high-sensitivity resources, and ${total_cost:,.2f} monthly cost."}

    if tool == "risk_prioritizer":
        top = sorted(resources, key=lambda item: item.risk_score or 0, reverse=True)[:5]
        finding = "Top risk resources: " + "; ".join(f"{resource.resource_uid} ({resource.name}) risk {resource.risk_score or 0:.1f}" for resource in top) if top else "No resources are available for prioritization."
        return {"tool": tool, "status": "completed", "finding": finding}

    if tool == "graph_intelligence":
        stats = graph_engine.get_graph_stats(graph)
        centrality = graph_engine.compute_centrality(graph)
        finding = f"Graph has {stats['total_nodes']} nodes, {stats['total_edges']} edges, density {stats['density']}, and {stats['connected_components']} connected components."
        if centrality:
            top_id, score = max(centrality.items(), key=lambda item: item[1])
            node = graph.nodes.get(top_id, {})
            finding += f" Most central node is {node.get('resource_uid', top_id)} ({node.get('name', top_id)}) with centrality {score:.4f}."
        return {"tool": tool, "status": "completed", "finding": finding}

    if tool == "alert_triage":
        alerts = db.query(models.RiskAlert).filter(models.RiskAlert.resolved == False).all()  # noqa: E712
        by_severity = {}
        for alert in alerts:
            by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        severity_text = ", ".join(f"{severity}: {count}" for severity, count in sorted(by_severity.items())) or "none"
        return {"tool": tool, "status": "completed", "finding": f"There are {len(alerts)} open alerts. Severity breakdown: {severity_text}."}

    if tool == "remediation_planner":
        recommendations = _recommendations(resources, graph)
        finding = "Recommended actions: " + " ".join(recommendations[:5]) if recommendations else "No automatic remediation candidates were found from current inventory signals."
        return {"tool": tool, "status": "needs_approval", "finding": finding}

    return {"tool": tool, "status": "skipped", "finding": "Unknown tool was skipped."}


def _agent_recommendations(resources: list[models.CloudResource], graph) -> list[str]:
    recommendations = []
    for resource in sorted(resources, key=lambda item: item.risk_score or 0, reverse=True):
        degree = graph.degree(resource.id) if resource.id in graph else 0
        if resource.public_access:
            recommendations.append(f"Require approval to remove public exposure from {resource.resource_uid} ({resource.name}).")
        if resource.sensitivity == "High" and (resource.risk_score or 0) >= 70:
            recommendations.append(f"Prioritize access review and encryption validation for {resource.resource_uid} ({resource.name}).")
        if degree >= 3:
            recommendations.append(f"Review segmentation for highly connected resource {resource.resource_uid} ({resource.name}).")
    return recommendations[:8]


def _handle_agentic_chat(req: schemas.ChatRequest, db: Session) -> schemas.ChatResponse:
    resources = db.query(models.CloudResource).all()
    connections = db.query(models.ResourceConnection).all()
    graph = graph_engine.build_graph(db)
    plan = _agent_plan(req.message)
    steps = [_run_agent_tool(item["tool"], db, resources, connections, graph) for item in plan]
    findings = [step["finding"] for step in steps]
    recommendations = _agent_recommendations(resources, graph)
    approval_required = any(step["status"] == "needs_approval" for step in steps) or bool(recommendations)

    run = models.AgentRun(
        goal=req.message,
        status="completed",
        plan=plan,
        steps=steps,
        findings=findings,
        recommendations=recommendations,
        approval_required=approval_required,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    lines = [
        f"Agentic investigation completed (run #{run.id}):",
        "- Goal interpreted: " + req.message,
        "- Plan selected:",
    ]
    lines += [f"  - {item['tool']}: {item['reason']}" for item in plan]
    lines.append("- Tool results:")
    lines += [f"  - {step['tool']}: {step['finding']}" for step in steps]
    if recommendations:
        lines.append("- Recommended next actions:")
        lines += [f"  - {item}" for item in recommendations]
    lines.append("- Human approval: required before any remediation or infrastructure change.")
    lines.append("- Agent memory: this investigation was saved in /api/agent/runs.")

    return schemas.ChatResponse(
        reply="\n".join(lines),
        agent={
            "run_id": run.id,
            "plan": plan,
            "steps": steps,
            "recommendations": recommendations,
            "approval_required": approval_required,
        },
    )


def _handle_chat(req: schemas.ChatRequest, db: Session) -> schemas.ChatResponse:
    message = req.message.lower()
    resources = db.query(models.CloudResource).all()
    connections = db.query(models.ResourceConnection).all()
    graph = graph_engine.build_graph(db)

    if _should_run_agent(req.message):
        return _handle_agentic_chat(req, db)

    math_reply = _try_math_reply(req.message)
    if math_reply:
        return schemas.ChatResponse(reply=math_reply)

    poem_reply = _poem_reply(req.message)
    if poem_reply:
        return schemas.ChatResponse(reply=poem_reply)

    chart_reply = _chart_reply(req.message, db)
    if chart_reply:
        reply, chart = chart_reply
        return schemas.ChatResponse(reply=reply, chart=chart)

    if any(term in message for term in ["what is this project", "about project", "overview", "capabilities", "features", "help", "what can you do"]):
        return schemas.ChatResponse(reply=_project_capabilities_reply())

    if any(term in message for term in ["api", "endpoint", "route", "swagger", "docs"]):
        return schemas.ChatResponse(reply=_api_reference_reply())

    if any(term in message for term in ["schema", "model", "database", "table", "fields", "data model"]):
        return schemas.ChatResponse(reply=_data_model_reply())

    if any(term in message for term in ["formula", "risk score", "scoring", "how is risk calculated"]):
        return schemas.ChatResponse(reply=_risk_formula_reply())

    if not resources:
        ai_reply = _call_gemini(req.message, db)
        if ai_reply:
            return schemas.ChatResponse(reply=ai_reply)
        return schemas.ChatResponse(reply=_local_general_reply(req.message))

    if any(term in message for term in ["summary", "dashboard", "status", "current state", "inventory"]):
        total_cost = sum(resource.cost or 0 for resource in resources)
        high_risk = sum(1 for resource in resources if (resource.risk_score or 0) >= 70)
        public_count = sum(1 for resource in resources if resource.public_access)
        return schemas.ChatResponse(reply=(
            "Current platform summary:\n"
            f"- Resources: {len(resources)}\n"
            f"- Connections: {len(connections)}\n"
            f"- High-risk resources: {high_risk}\n"
            f"- Publicly exposed resources: {public_count}\n"
            f"- Total monthly cost: ${total_cost:,.2f}\n"
            f"- Graph density: {graph_engine.get_graph_stats(graph)['density']}"
        ))

    if "most risky" in message or "highest risk" in message:
        top_resources = sorted(resources, key=lambda item: item.risk_score or 0, reverse=True)[:3]
        lines = ["Top risky resources:"]
        lines += [
            f"- {resource.resource_uid} ({resource.name}): risk score {resource.risk_score:.1f}"
            for resource in top_resources
        ]
        return schemas.ChatResponse(reply="\n".join(lines))

    if any(term in message for term in ["resources", "list resource", "all resource"]):
        lines = ["Resources in inventory:"]
        lines += [_format_resource(resource) for resource in sorted(resources, key=lambda item: item.resource_uid)[:20]]
        if len(resources) > 20:
            lines.append(f"- Showing 20 of {len(resources)} resources.")
        return schemas.ChatResponse(reply="\n".join(lines))

    if any(term in message for term in ["connections", "edges", "dependencies", "network"]):
        if not connections:
            return schemas.ChatResponse(reply="Connections:\n- No resource connections have been added yet.")
        lines = ["Resource connections:"]
        lines += [
            f"- {connection.from_node} -> {connection.to_node}: type={connection.connection_type}, weight={connection.risk_weight}"
            for connection in connections[:20]
        ]
        if len(connections) > 20:
            lines.append(f"- Showing 20 of {len(connections)} connections.")
        return schemas.ChatResponse(reply="\n".join(lines))

    if any(term in message for term in ["graph", "centrality", "network stats", "visualization"]):
        stats = graph_engine.get_graph_stats(graph)
        centrality = graph_engine.compute_centrality(graph)
        lines = [
            "Graph intelligence:",
            f"- Nodes: {stats['total_nodes']}",
            f"- Edges: {stats['total_edges']}",
            f"- Connected components: {stats['connected_components']}",
            f"- Density: {stats['density']}",
            f"- Average risk score: {stats['avg_risk_score']}",
        ]
        if centrality:
            top_id, score = max(centrality.items(), key=lambda item: item[1])
            node = graph.nodes.get(top_id, {})
            lines.append(f"- Most central node: {node.get('resource_uid', top_id)} ({node.get('name', top_id)}), centrality={score:.4f}")
        return schemas.ChatResponse(reply="\n".join(lines))

    if "blast radius" in message or "what happens if" in message or " fails" in message:
        resource = _find_resource_in_message(message, resources)
        if not resource:
            return schemas.ChatResponse(reply="Please include a resource UID or name for blast radius analysis.\n- Example: What happens if RES-001 fails?")
        blast = graph_engine.get_blast_radius(graph, resource.id)
        lines = [f"Blast radius for {resource.resource_uid} ({resource.name}):"]
        lines.append(f"- Impacted resources: {blast['count']}")
        lines += [f"- {node['name']} ({node['resource_type']}), risk {node['risk_score']}" for node in blast["affected_nodes"]]
        return schemas.ChatResponse(reply="\n".join(lines))

    if "attack path" in message or "simulate attack" in message:
        resource = _find_resource_in_message(message, resources)
        if not resource:
            return schemas.ChatResponse(reply="Please include a starting resource UID or name for attack path analysis.\n- Example: attack path from RES-001")
        id_to_uid = {item.id: item.resource_uid for item in resources}
        paths = _attack_paths_from(db, resource)
        if not paths:
            return schemas.ChatResponse(reply=f"No downstream attack paths start from {resource.resource_uid}.\n- The node has no reachable dependencies.")
        lines = [f"Attack paths from {resource.resource_uid}:"]
        lines += [f"- {' -> '.join(id_to_uid[node_id] for node_id in path)}" for path in paths[:5]]
        return schemas.ChatResponse(reply="\n".join(lines))

    if "total cost" in message or "cost" in message:
        total_cost = sum(resource.cost or 0 for resource in resources)
        return schemas.ChatResponse(reply=f"Total cloud cost:\n- ${total_cost:,.2f} per month across {len(resources)} resources.")

    if "how many" in message or "count" in message:
        return schemas.ChatResponse(reply=f"Inventory count:\n- Resources: {len(resources)}\n- Connections: {len(connections)}")

    if "high risk" in message or "critical" in message:
        high_risk = [resource for resource in resources if (resource.risk_score or 0) >= 70]
        if not high_risk:
            return schemas.ChatResponse(reply="High-risk resources:\n- None found with risk score >= 70.")
        lines = ["High-risk resources:"]
        lines += [f"- {resource.resource_uid} ({resource.name}): {resource.risk_score:.1f}" for resource in high_risk]
        return schemas.ChatResponse(reply="\n".join(lines))

    if any(term in message for term in ["alert", "alerts", "risks detected", "findings"]):
        alerts = db.query(models.RiskAlert).filter(models.RiskAlert.resolved == False).all()  # noqa: E712
        if not alerts:
            return schemas.ChatResponse(reply="Open risk alerts:\n- No open alerts are currently stored.")
        lines = ["Open risk alerts:"]
        lines += [
            f"- {alert.severity.upper()} {alert.alert_type}: {alert.title}"
            for alert in alerts[:20]
        ]
        if len(alerts) > 20:
            lines.append(f"- Showing 20 of {len(alerts)} alerts.")
        return schemas.ChatResponse(reply="\n".join(lines))

    if any(term in message for term in ["recommend", "recommendation", "secure", "fix", "mitigation", "improve security"]):
        recommendations = _recommendations(resources, graph)
        if not recommendations:
            return schemas.ChatResponse(reply="Security recommendations:\n- No major automatic recommendations were found from the current inventory.")
        return schemas.ChatResponse(reply="\n".join(["Security recommendations:", *recommendations[:10]]))

    resource = _find_resource_in_message(message, resources)
    if resource:
        degree = graph.degree(resource.id) if resource.id in graph else 0
        return schemas.ChatResponse(reply="\n".join([
            f"Resource details for {resource.resource_uid}:",
            _format_resource(resource),
            f"- Graph degree: {degree}",
            "- Ask for blast radius, attack path, or recommendations to go deeper."
        ]))

    # Gemini fallback (includes full history)
    ai_reply = _call_gemini(req.message, db, history=req.history)
    if ai_reply:
        return schemas.ChatResponse(reply=ai_reply)

    return schemas.ChatResponse(reply=_local_general_reply(req.message))


@router.post("/api/chat", response_model=schemas.ChatResponse)
@router.post("/chat", response_model=schemas.ChatResponse)
def chat(req: schemas.ChatRequest, db: Session = Depends(get_db)):
    return _handle_chat(req, db)


@router.get("/api/agent/runs", response_model=list[schemas.AgentRunOut])
def list_agent_runs(skip: int = 0, limit: int = 25, db: Session = Depends(get_db)):
    return (
        db.query(models.AgentRun)
        .order_by(models.AgentRun.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
