# Cloud Risk Intelligence Backend

## Local API Key

Protected endpoints require this header:

```text
X-API-Key: dev-secret-key
```

The key is read from `API_KEY` in `.env`. The `GET /` health check is public.

## Authentication

User authentication is available at:

```text
POST /auth/register
POST /auth/token
GET /auth/me
```

The API key still protects the API boundary. JWT bearer tokens identify logged-in users for account-aware routes.

## History And Audit

Operational history is exposed at:

```text
POST /api/history/snapshot
GET /api/history/summary
GET /api/history/resource/{resource_id}
GET /api/history/anomalies
GET /api/audit/
```

Resource and connection create/update/delete actions write audit entries automatically.

## Docker

The backend includes a Dockerfile and can run through the root `docker-compose.yml` with Postgres.

## Optional AI Provider

Set `GEMINI_API_KEY` in `.env` to enable general ChatGPT-style answers through Gemini. Without it, the assistant still answers project and live inventory questions.

```text
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-2.5-flash
```

## Agentic Investigations

Ask the chat endpoint to investigate, triage, prioritize risks, or create a remediation plan to start an agent run. The agent uses a bounded plan-act-observe loop with an allowlist of read-only tools and a maximum of five tool calls. Gemini creates and revises structured plans when configured; a deterministic local policy is used when it is unavailable.

Runs and relevant prior-run memory are available from `GET /api/agent/runs`. Remediation output is always a dry run. Record a human decision with `POST /api/agent/runs/{run_id}/approval` and an `{"approved": true|false, "note": "..."}` body. Approval is audited in the run trace but does not execute or mutate infrastructure.
