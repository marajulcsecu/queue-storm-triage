# QueueStorm CRM Ticket Triage Service

A small, fast, stateless HTTP API that reads one customer support message and returns a structured classification (case type, severity, department, agent summary, human-review flag, confidence score).

Built for the QueueStorm Warmup Mock Preliminary Task.

---

## What it does

Given a JSON payload describing one support ticket, the service returns a JSON payload classifying it. Example:

**Request:**

```bash
curl -X POST https://YOUR-LIVE-URL/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "T-3",
    "message": "Someone called asking my OTP, is that bKash?"
  }'
```

**Response:**

```json
{
  "ticket_id": "T-3",
  "case_type": "phishing_or_social_engineering",
  "severity": "critical",
  "department": "fraud_risk",
  "agent_summary": "Customer reports a suspicious contact attempting to obtain account credentials; immediate review recommended.",
  "human_review_required": true,
  "confidence": 0.95
}
```

---

## Endpoints

### `GET /health`

Liveness probe. Returns 200 OK with service identity.

```bash
curl https://YOUR-LIVE-URL/health
# {"status":"ok","service":"ticket-triage","version":"1.0.0"}
```

### `POST /sort-ticket`

Classifies one ticket. See the [Request Schema](#request-schema) and [Response Schema](#response-schema) below.

---

## Request Schema

```json
{
  "ticket_id": "T-001",
  "channel":   "app",
  "locale":    "en",
  "message":   "I sent 5000 taka to a wrong number this morning, please help me get it back"
}
```

| Field      | Type   | Required | Allowed values                          |
|------------|--------|----------|-----------------------------------------|
| `ticket_id`| string | Yes      | non-empty (echoed in response)          |
| `message`  | string | Yes      | non-empty, free text                    |
| `channel`  | string | No       | `app`, `sms`, `call_center`, `merchant_portal` |
| `locale`   | string | No       | `bn`, `en`, `mixed`                     |

---

## Response Schema

```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT to a wrong number and requests recovery.",
  "human_review_required": true,
  "confidence": 0.85
}
```

| Field                   | Type    | Notes                                                    |
|-------------------------|---------|----------------------------------------------------------|
| `ticket_id`             | string  | Echoed from request                                      |
| `case_type`             | enum    | One of 5 values — see below                              |
| `severity`              | enum    | `low`, `medium`, `high`, `critical`                      |
| `department`            | enum    | One of 4 values — see below                              |
| `agent_summary`         | string  | 1–2 neutral sentences; **never asks for credentials**    |
| `human_review_required` | boolean | `true` iff severity is `critical` OR case is phishing    |
| `confidence`            | float   | `0.0` – `1.0`                                            |

### `case_type` values

| Value                            | When to use                                  |
|----------------------------------|----------------------------------------------|
| `wrong_transfer`                 | Money sent to wrong recipient                |
| `payment_failed`                 | Transaction failed, balance may be deducted  |
| `refund_request`                 | Customer asking for a refund                 |
| `phishing_or_social_engineering` | Suspicious contact asking for credentials    |
| `other`                          | None of the above match                      |

### `department` values

| Value                 | Routed case types                       |
|-----------------------|-----------------------------------------|
| `customer_support`    | `other`, low-severity `refund_request`  |
| `dispute_resolution`  | `wrong_transfer`, contested refunds     |
| `payments_ops`        | `payment_failed`                        |
| `fraud_risk`          | `phishing_or_social_engineering`        |

---

## Tech Stack

- **Language:** Python 3.12
- **Web framework:** FastAPI 0.138
- **Validation:** Pydantic v2.13
- **Server:** Uvicorn 0.49 (with standard extras: uvloop, httptools)
- **Logging:** structlog (JSON-formatted)
- **Classification:** Rule-based regex (no LLM, deterministic, < 5 ms typical)
- **Container:** python:3.12-slim, ~159 MB
- **Tests:** pytest 9.1, 85 tests, runs in < 0.2 s
- **Deployment:** Docker on Render (free tier)

---

## Run Locally

### Prerequisites

- Python 3.11+ (tested with 3.12.3)
- Git

### Setup

```bash
# 1. Clone (if you haven't already)
git clone https://github.com/marajulcsecu/queue-storm-triage.git
cd queue-storm-triage

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
```

### Run the server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

You should see:

```
INFO:     Started server process [12345]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Test it

In another terminal:

```bash
# Health check
curl http://127.0.0.1:8000/health

# Sort a ticket
curl -X POST http://127.0.0.1:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-1","message":"I sent 3000 to wrong number"}'
```

### Run the test suite

```bash
pytest -v
# Expected: 85 passed in ~0.2s
```

---

## Run with Docker

### Build

```bash
docker build -t triage-service .
```

### Run

```bash
docker run -p 8000:8000 triage-service
```

Then test with the same `curl` commands as above, replacing `127.0.0.1:8000` with `localhost:8000`.

---

## Deploy to Render

This service is designed to deploy on Render's free tier with zero configuration.

### Step 1: Push to GitHub (already done if you're reading this on GitHub)

### Step 2: Create a new Web Service on Render

1. Log in to [dashboard.render.com](https://dashboard.render.com)
2. Click **New +** → **Web Service**
3. Connect your GitHub account if not already connected
4. Select the `queue-storm-triage` repository
5. Use these settings:
   - **Environment:** `Docker`
   - **Region:** Choose closest to your users
   - **Branch:** `main`
   - **Instance Type:** `Free`
   - **Health Check Path:** `/health`

### Step 3: Set environment variables (optional)

In the Render dashboard → **Environment** tab, you can set:

| Variable      | Value     | Purpose                              |
|---------------|-----------|--------------------------------------|
| `LOG_LEVEL`   | `INFO`    | Default logging level                |
| `APP_VERSION` | `1.0.0`   | Reported in `/health` response body  |

These are optional — the service runs with sensible defaults.

### Step 4: Deploy

Click **Create Web Service**. Render will build the Docker image and deploy. After 2-5 minutes, you'll get a URL like:

```
https://queue-storm-triage.onrender.com
```

### Step 5: Smoke test

```bash
curl https://queue-storm-triage.onrender.com/health
curl -X POST https://queue-storm-triage.onrender.com/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-1","message":"I sent 3000 to wrong number"}'
```

---

## Project Structure

```
queue-storm-triage/
├── README.md                  ← You are here
├── REQUIREMENTS.md            ← Functional + non-functional requirements
├── ARCHITECTURE.md            ← System design + ADRs
├── Dockerfile                 ← Container definition
├── docker-compose.yml         ← (optional) local stack
├── .env.example               ← Template for env vars (NO real values)
├── .gitignore
├── .dockerignore
├── requirements.txt           ← Production deps (pinned)
├── requirements-dev.txt       ← Test deps (pinned)
│
├── app/
│   ├── main.py                ← FastAPI app + middleware + exception handlers
│   ├── api/
│   │   ├── health.py          ← GET /health
│   │   └── triage.py          ← POST /sort-ticket
│   ├── models/
│   │   ├── enums.py           ← CaseType, Severity, Department, Channel, Locale
│   │   ├── request.py         ← TicketRequest schema
│   │   └── response.py        ← TicketResponse schema
│   └── services/
│       ├── classifier.py      ← Orchestrates the rules
│       ├── router.py          ← case_type -> department
│       ├── summarizer.py      ← 1-2 sentence neutral summary
│       ├── safety.py          ← Post-generation filter (redacts forbidden phrases)
│       └── rules/
│           ├── phishing.py        ← Highest priority
│           ├── wrong_transfer.py
│           ├── payment_failed.py
│           └── refund.py
│
└── tests/
    ├── conftest.py                  ← Shared fixtures
    ├── test_brief_samples.py        ← 5 sample cases from the brief
    ├── test_validation.py           ← Schema + HTTP error code tests
    ├── test_health.py               ← /health endpoint tests
    ├── test_safety.py               ← Safety filter tests
    └── test_classifier.py           ← Per-rule unit tests
```

---

## Architecture & Design Decisions

For full architectural rationale, see [`ARCHITECTURE.md`](./ARCHITECTURE.md). Key decisions:

- **Rule-based classification, not LLM** — deterministic, free, fast, auditable
- **Stateless service** — no database, no caching, no session
- **Phishing takes priority** — if any rule + phishing both match, phishing wins
- **Safety filter rewrites, doesn't reject** — keeps API contract stable
- **Docker for deployment** — runs anywhere, free tier compatible

---

## Performance

| Metric                 | Target  | Actual (typical) |
|------------------------|---------|------------------|
| `/health` response     | < 10 s  | ~2 ms            |
| `/sort-ticket` response| < 30 s  | ~3 ms (p99 ~15 ms) |
| Image size             | < 500 MB| 159 MB           |
| Cold start             | < 30 s  | ~5 s on Render   |

---

## License

This is a mock-project submission. No license specified.

---

## Submission

For the QueueStorm Warmup submission, the following information is needed:

| Field                | Value                                              |
|----------------------|----------------------------------------------------|
| Team name            | _(your team name)_                                 |
| GitHub repository    | https://github.com/marajulcsecu/queue-storm-triage |
| Live API base URL    | https://queue-storm-triage.onrender.com            |
| Deployment platform  | Render (Docker)                                    |
| LLM used             | No (rule-based classification)                     |
| Known issues         | None                                               |

---

## Contact

Built by **MD. MARAJUL HAQUE** (marajul.cu@gmail.com) for the QueueStorm warmup task.
