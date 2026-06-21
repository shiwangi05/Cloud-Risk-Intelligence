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

from fastapi import APIRouter, Depends, HTTPException
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


def _call_gemini_json(prompt: str, db: Session) -> dict | None:
    """Request a low-temperature structured decision; failures use local policy."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": f"{_live_context(db)}\n\n{prompt}"}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = "".join(
            part.get("text", "")
            for part in body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        ).strip()
        return json.loads(text)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, IndexError):
        return None


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

AGENT_NAME = "ARIA"   # Autonomous Risk Intelligence Agent
AGENT_VERSION = "1.0"

def _should_run_agent(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in [
        "aria", "agent", "agentic", "investigate", "triage", "security review",
        "remediation plan", "analyze everything", "full risk review",
        "autonomous", "root cause", "prioritize risks",
    ])


_AGENT_TOOLS = {
    "inventory_summary": "Summarize assets, exposure, sensitivity, connections, and cost.",
    "risk_prioritizer": "Rank the highest-risk resources.",
    "graph_intelligence": "Inspect graph density, components, and central resources.",
    "alert_triage": "Summarize unresolved alerts by severity.",
    "attack_path_analyzer": "Trace downstream paths from a resource named in the goal.",
    "cost_impact": "Estimate downstream monthly cost impact from a named resource.",
    "remediation_planner": "Create dry-run remediation proposals requiring approval.",
}
_MAX_AGENT_STEPS = 5


def _fallback_agent_plan(message: str) -> list[dict]:
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


def _agent_memory(message: str, db: Session) -> list[dict]:
    """Retrieve a few prior runs with overlapping goal terms."""
    terms = {term for term in re.findall(r"[a-z0-9-]+", message.lower()) if len(term) > 3}
    candidates = db.query(models.AgentRun).order_by(models.AgentRun.created_at.desc()).limit(20).all()
    ranked = []
    for run in candidates:
        overlap = len(terms & set(re.findall(r"[a-z0-9-]+", run.goal.lower())))
        if overlap:
            ranked.append((overlap, run))
    return [
        {
            "run_id": run.id,
            "goal": run.goal,
            "status": run.status,
            "findings": (run.findings or [])[:3],
            "recommendations": (run.recommendations or [])[:3],
        }
        for _, run in sorted(ranked, key=lambda item: (item[0], item[1].id), reverse=True)[:3]
    ]


def _agent_plan(message: str, db: Session, memory: list[dict]) -> list[dict]:
    prompt = (
        "You are planning a cloud-risk investigation. Return JSON with a 'plan' array. "
        "Each item must contain 'tool' and 'reason'. Use only these tools: "
        f"{json.dumps(_AGENT_TOOLS)}. Use no more than {_MAX_AGENT_STEPS} tools. "
        "Prefer the smallest plan that can satisfy the goal. Tools are read-only; remediation_planner only drafts changes.\n"
        f"Goal: {message}\nRelevant prior runs: {json.dumps(memory)}"
    )
    decision = _call_gemini_json(prompt, db)
    raw_plan = decision.get("plan", []) if isinstance(decision, dict) else []
    plan = [
        {"tool": item.get("tool"), "reason": str(item.get("reason", "Selected for the investigation."))[:300]}
        for item in raw_plan
        if isinstance(item, dict) and item.get("tool") in _AGENT_TOOLS
    ][:_MAX_AGENT_STEPS]
    return plan or _fallback_agent_plan(message)[:_MAX_AGENT_STEPS]


def _next_agent_decision(message: str, plan: list[dict], steps: list[dict], db: Session) -> dict:
    remaining = [item for item in plan if item["tool"] not in {step["tool"] for step in steps}]
    prompt = (
        "Act as a bounded cloud-risk agent. Return one JSON object. Choose either "
        "{'action':'tool','tool':'allowed_name','reason':'...'} or "
        "{'action':'finish','reason':'why the goal is satisfied'}. You may revise the original plan by selecting "
        f"another allowed tool, but never repeat a tool. Allowed tools: {json.dumps(_AGENT_TOOLS)}.\n"
        f"Goal: {message}\nOriginal plan: {json.dumps(plan)}\nObservations: {json.dumps(steps)}"
    )
    decision = _call_gemini_json(prompt, db)
    used = {step["tool"] for step in steps}
    if (
        isinstance(decision, dict)
        and decision.get("action") == "tool"
        and decision.get("tool") in _AGENT_TOOLS
        and decision.get("tool") not in used
    ):
        return decision
    if isinstance(decision, dict) and decision.get("action") == "finish" and steps:
        return decision
    if remaining:
        return {"action": "tool", **remaining[0]}
    return {"action": "finish", "reason": "The planned evidence has been collected and the goal can be answered."}


def _run_agent_tool(tool: str, goal: str, db: Session, resources: list[models.CloudResource], connections: list[models.ResourceConnection], graph) -> dict:
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

    if tool in {"attack_path_analyzer", "cost_impact"}:
        resource = _find_resource_in_message(goal, resources)
        if not resource:
            return {"tool": tool, "status": "completed", "finding": "No resource UID or name was present in the goal, so targeted impact analysis could not run."}
        paths = _attack_paths_from(db, resource)
        impacted_ids = {node_id for path in paths for node_id in path[1:]}
        impacted = [item for item in resources if item.id in impacted_ids]
        if tool == "attack_path_analyzer":
            finding = f"{resource.resource_uid} has {len(paths)} downstream attack paths reaching {len(impacted)} unique resources."
        else:
            cost = sum(item.cost or 0 for item in impacted)
            finding = f"Failure of {resource.resource_uid} could affect {len(impacted)} downstream resources with ${cost:,.2f} in monthly cost."
        return {"tool": tool, "status": "completed", "finding": finding}

    if tool == "remediation_planner":
        recommendations = _recommendations(resources, graph)
        finding = "Recommended actions: " + " ".join(recommendations[:5]) if recommendations else "No automatic remediation candidates were found from current inventory signals."
        proposals = [
            {"mode": "dry_run", "proposal": item.lstrip("- "), "requires_approval": True}
            for item in recommendations[:5]
        ]
        return {"tool": tool, "status": "needs_approval", "finding": finding, "proposals": proposals}

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
    memory = _agent_memory(req.message, db)
    plan = _agent_plan(req.message, db, memory)
    steps = []
    completion_reason = "The safety iteration limit was reached."
    while len(steps) < _MAX_AGENT_STEPS:
        decision = _next_agent_decision(req.message, plan, steps, db)
        if decision.get("action") == "finish":
            completion_reason = str(decision.get("reason", "Investigation complete."))[:500]
            break
        tool = decision["tool"]
        if tool not in {item["tool"] for item in plan}:
            plan.append({"tool": tool, "reason": str(decision.get("reason", "Added after observing tool results."))[:300]})
        step = _run_agent_tool(tool, req.message, db, resources, connections, graph)
        step["iteration"] = len(steps) + 1
        steps.append(step)
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
        f"ARIA (Autonomous Risk Intelligence Agent) — Run #{run.id}",
        f"Goal: {req.message}",
        "",
        "Plan:",
    ]
    lines += [f"  [{i+1}] {item['tool']}: {item['reason']}" for i, item in enumerate(plan)]
    lines.append("")
    lines.append("Tool Results:")
    lines += [f"  [{step['iteration']}] {step['tool']} ({step['status']}): {step['finding']}" for step in steps]
    if recommendations:
        lines.append("")
        lines.append("ARIA Recommendations (require human approval):")
        lines += [f"  - {item}" for item in recommendations]
    lines.append("")
    lines.append(f"Completion: {completion_reason}")
    lines.append(f"Memory: Investigation saved as run #{run.id} in /api/agent/runs.")

    return schemas.ChatResponse(
        reply="\n".join(lines),
        agent={
            "name": AGENT_NAME,
            "version": AGENT_VERSION,
            "run_id": run.id,
            "plan": plan,
            "steps": steps,
            "recommendations": recommendations,
            "approval_required": approval_required,
            "completion_reason": completion_reason,
            "iterations": len(steps),
            "memory_used": memory,
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
        # Check if the user is asking about a SPECIFIC resource first
        target = _find_resource_in_message(message, resources)
        if target:
            connections_count = graph.degree(target.id) if target.id in graph else 0
            return schemas.ChatResponse(reply="\n".join([
                f"Cost details for {target.resource_uid} ({target.name}):",
                f"- Monthly cost: ${target.cost or 0:,.2f}",
                f"- Provider: {target.provider} / {target.region}",
                f"- Risk score: {target.risk_score or 0:.1f}",
                f"- Connections: {connections_count}",
            ]))
        # No specific resource mentioned — return total
        total_cost = sum(r.cost or 0 for r in resources)
        breakdown = sorted(resources, key=lambda r: r.cost or 0, reverse=True)[:5]
        lines = [f"Total cloud cost:", f"- ${total_cost:,.2f} per month across {len(resources)} resources.", "", "Top 5 by cost:"]
        lines += [f"- {r.resource_uid} ({r.name}): ${r.cost or 0:,.2f}" for r in breakdown]
        return schemas.ChatResponse(reply="\n".join(lines))

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


@router.post("/api/agent/runs/{run_id}/approval", response_model=schemas.AgentRunOut)
def decide_agent_run(run_id: int, req: schemas.AgentApprovalRequest, db: Session = Depends(get_db)):
    """Record a human decision and, on approval, auto-execute ARIA's recommendations."""
    run = db.query(models.AgentRun).filter(models.AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    if not run.approval_required:
        raise HTTPException(status_code=409, detail="This agent run has no approval-gated proposals")

    executed_actions: list[str] = []

    if req.approved:
        executed_actions = _execute_approved_recommendations(run, db)
        finding = (
            f"Plan approved. {len(executed_actions)} action(s) executed automatically: "
            + "; ".join(executed_actions)
        ) if executed_actions else "Plan approved. No automated changes were applicable."
    else:
        finding = req.note or "Proposals rejected by human reviewer. No changes made."

    steps = list(run.steps or [])
    steps.append({
        "tool": "human_approval",
        "status": "approved" if req.approved else "rejected",
        "finding": finding,
        "executed_actions": executed_actions,
    })
    run.steps = steps
    run.status = "approved" if req.approved else "rejected"
    db.commit()
    db.refresh(run)
    return run


# ── Auto-execution engine ──────────────────────────────────────────────────────

def _execute_approved_recommendations(run: models.AgentRun, db) -> list[str]:
    """
    Parse each ARIA recommendation and apply the matching DB change.

    Supported actions (parsed from recommendation text):
      - "remove public exposure from {uid}"     → resource.public_access = False
      - "tighten IAM"  / "encryption validation" → RiskAlert (encryption_review)
      - "segment" / "segmentation"              → RiskAlert (network_segmentation)
      - "backups" / "recovery"                  → RiskAlert (backup_review)
    After any resource change, risk scores are recomputed and an AuditLog entry written.
    """
    resources = db.query(models.CloudResource).all()
    uid_to_res = {r.resource_uid: r for r in resources}
    executed: list[str] = []

    for rec in (run.recommendations or []):
        lowered = rec.lower()

        # ── Action 1: Remove public exposure ──────────────────────────────
        m = re.search(r'remove public exposure from ([\w-]+)', lowered)
        if m:
            uid = m.group(1).upper().replace("-", "-")
            # Try both original and uppercase match
            resource = uid_to_res.get(m.group(1)) or _fuzzy_uid(uid_to_res, m.group(1))
            if resource and resource.public_access:
                resource.public_access = False
                _write_audit(db, "UPDATE", "CloudResource", resource.id,
                             resource.resource_uid, f"ARIA auto-exec: set public_access=False")
                executed.append(f"Disabled public access on {resource.resource_uid} ({resource.name})")
            continue

        # ── Action 2: Encryption / IAM review alert ───────────────────────
        if any(k in lowered for k in ["encryption", "iam", "access review"]):
            uid_match = re.search(r'for ([\w-]+)', lowered)
            if uid_match:
                resource = _fuzzy_uid(uid_to_res, uid_match.group(1))
                if resource and not _alert_exists(db, resource.id, "encryption_review"):
                    alert = models.RiskAlert(
                        resource_id=resource.id,
                        alert_type="encryption_review",
                        severity="high",
                        title=f"[ARIA] Encryption & IAM Review: {resource.name}",
                        description=f"Auto-created by ARIA on plan approval. Resource {resource.resource_uid} requires encryption validation and IAM tightening.",
                    )
                    db.add(alert)
                    _write_audit(db, "CREATE", "RiskAlert", resource.id,
                                 resource.resource_uid, "ARIA auto-exec: created encryption_review alert")
                    executed.append(f"Created encryption_review alert for {resource.resource_uid} ({resource.name})")
            continue

        # ── Action 3: Network segmentation alert ──────────────────────────
        if any(k in lowered for k in ["segment", "network path"]):
            uid_match = re.search(r'resource ([\w-]+)', lowered)
            if uid_match:
                resource = _fuzzy_uid(uid_to_res, uid_match.group(1))
                if resource and not _alert_exists(db, resource.id, "network_segmentation"):
                    alert = models.RiskAlert(
                        resource_id=resource.id,
                        alert_type="network_segmentation",
                        severity="medium",
                        title=f"[ARIA] Network Segmentation Review: {resource.name}",
                        description=f"Auto-created by ARIA on plan approval. Highly connected resource {resource.resource_uid} needs segmentation review.",
                    )
                    db.add(alert)
                    _write_audit(db, "CREATE", "RiskAlert", resource.id,
                                 resource.resource_uid, "ARIA auto-exec: created network_segmentation alert")
                    executed.append(f"Created network_segmentation alert for {resource.resource_uid} ({resource.name})")
            continue

        # ── Action 4: Backup / recovery review alert ──────────────────────
        if any(k in lowered for k in ["backup", "recovery"]):
            uid_match = re.search(r'([\w-]{3,})', lowered)
            # grab first UID-like token from the recommendation text
            uid_match = re.search(r'\b([A-Z][\w-]{2,})\b', rec)
            if uid_match:
                resource = _fuzzy_uid(uid_to_res, uid_match.group(1))
                if resource and not _alert_exists(db, resource.id, "backup_review"):
                    alert = models.RiskAlert(
                        resource_id=resource.id,
                        alert_type="backup_review",
                        severity="medium",
                        title=f"[ARIA] Backup & Recovery Review: {resource.name}",
                        description=f"Auto-created by ARIA on plan approval. Resource {resource.resource_uid} requires backup and recovery priority confirmation.",
                    )
                    db.add(alert)
                    _write_audit(db, "CREATE", "RiskAlert", resource.id,
                                 resource.resource_uid, "ARIA auto-exec: created backup_review alert")
                    executed.append(f"Created backup_review alert for {resource.resource_uid} ({resource.name})")
            continue

    # Recompute risk scores for all affected resources if any changes made
    if executed:
        graph_engine.compute_risk_analysis(db)  # persists updated scores

    db.commit()
    return executed


def _fuzzy_uid(uid_map: dict, token: str) -> models.CloudResource | None:
    """Case-insensitive resource UID lookup with partial match fallback."""
    token_lower = token.lower()
    # Exact match first
    for uid, res in uid_map.items():
        if uid.lower() == token_lower:
            return res
    # Prefix match
    for uid, res in uid_map.items():
        if uid.lower().startswith(token_lower) or token_lower.startswith(uid.lower()):
            return res
    # Name match
    for uid, res in uid_map.items():
        if token_lower in res.name.lower():
            return res
    return None


def _alert_exists(db, resource_id: int, alert_type: str) -> bool:
    """Return True if an open alert of this type already exists for the resource."""
    return db.query(models.RiskAlert).filter(
        models.RiskAlert.resource_id == resource_id,
        models.RiskAlert.alert_type == alert_type,
        models.RiskAlert.resolved == False,  # noqa: E712
    ).first() is not None


def _write_audit(db, action: str, entity_type: str, entity_id: int, entity_uid: str, detail: str):
    """Write an immutable audit log entry for ARIA-executed actions."""
    import json as _json
    log = models.AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_uid=entity_uid,
        detail=_json.dumps({"source": "ARIA_auto_exec", "detail": detail}),
    )
    db.add(log)
