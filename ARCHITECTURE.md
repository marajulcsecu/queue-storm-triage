# Architecture Document — QueueStorm CRM Ticket Triage Service

**Version:** 1.0
**Date:** 2026-06-25
**Companion to:** `REQUIREMENTS.md`
**Status:** Approved for implementation

---

## 1. Architectural Goals & Principles

### 1.1 Goals
1. **Fast to build and deploy** — within a 1-hour window for the warmup
2. **Deterministic and testable** — rule-based classification with predictable outputs
3. **Safe by default** — the safety filter is a non-bypassable post-processing step
4. **Cloud-portable** — runs on any free-tier PaaS with a single Dockerfile
5. **Professional quality** — modular code, tests, docs, deployable by anyone with the README

### 1.2 Principles
- **Statelessness** — no DB, no session, no caching. The service is a pure function over input.
- **Defense in depth** — multiple safety checks (input validation, classification order, post-generation filter)
- **Separation of concerns** — routing, validation, classification, summarization, and safety are independent modules
- **Observable without leaking PII** — structured logs include metadata, never message bodies
- **Boring tech** — pick proven, well-documented tools over novelty

---

## 2. System Context (C4 Level 1)

```
┌─────────────────────┐         HTTPS JSON         ┌──────────────────────────┐
│   Test Harness /    │ ───────────────────────▶   │   Triage Service         │
│   Support Tooling   │  POST /sort-ticket         │   (this project)         │
│                     │  GET  /health              │                          │
└─────────────────────┘  ◀───────────────────────  └──────────────────────────┘
                              JSON Response
```

**External actors:**
- **Client** — sends a single ticket, expects a single classification
- **(Optional) LLM Provider** — only used as fallback for low-confidence cases

---

## 3. Container Architecture (C4 Level 2)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Triage Service Container                       │
│                                                                   │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐ │
│  │  API Layer   │───▶│ Validation      │───▶│ Classification   │ │
│  │  (FastAPI)   │    │ Layer           │    │ Engine           │ │
│  │              │    │ (Pydantic)      │    │ (Rule-based)     │ │
│  └──────────────┘    └─────────────────┘    └──────────────────┘ │
│         │                                              │          │
│         │                                              ▼          │
│         │                                   ┌──────────────────┐  │
│         │                                   │ Summary Builder  │  │
│         │                                   │ (Template-based) │  │
│         │                                   └──────────────────┘  │
│         │                                              │          │
│         │                                              ▼          │
│         │                                   ┌──────────────────┐  │
│         │                                   │ Safety Filter    │  │
│         │                                   │ (Regex guard)    │  │
│         │                                   └──────────────────┘  │
│         │                                              │          │
│         ▼                                              ▼          │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                  Response Formatter                           ││
│  └──────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│                    ┌──────────────────┐                           │
│                    │ Structured Logs │                           │
│                    └──────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **API Layer** | HTTP routing, request parsing, error mapping, response serialization |
| **Validation Layer** | Schema enforcement, type coercion, enum validation, field constraints |
| **Classification Engine** | Apply rule-based patterns to determine `case_type` + initial `severity` |
| **Summary Builder** | Generate 1–2 sentence neutral summary from ticket text + classification |
| **Safety Filter** | Scan and rewrite the summary to remove any prompt that asks for credentials |
| **Response Formatter** | Combine all outputs into the final response contract; compute `human_review_required` and `confidence` |
| **Structured Logs** | Emit per-request logs (metadata only, no message body) |

---

## 4. Request Flow (Happy Path)

```
1. Client sends POST /sort-ticket with JSON body
   │
2. API Layer receives request, parses JSON
   │ ── parse error ──▶ HTTP 400
   │
3. Validation Layer validates against Pydantic schema
   │ ── schema error ──▶ HTTP 422 (with field-level errors)
   │
4. Classification Engine runs (priority order):
   a. phishing_check(message)    → if match: case_type = phishing, severity = critical
   b. wrong_transfer_check(msg)  → if match: case_type = wrong_transfer, severity = high
   c. payment_failed_check(msg)  → if match: case_type = payment_failed, severity = high
   d. refund_check(msg)          → if match: case_type = refund_request, severity = low/medium
   e. fallback                   → case_type = other, severity = low
   │
5. Department Routing based on case_type (lookup table)
   │
6. Summary Builder constructs agent_summary from message + classification
   │
7. Safety Filter scans summary for forbidden phrases (PIN, OTP, password, etc.)
   │ ── violation ──▶ rewrite to neutral phrasing OR raise hard error
   │
8. Response Formatter computes:
   - human_review_required = (severity == "critical" OR case_type == "phishing_or_social_engineering")
   - confidence = matched_rules / total_rules_evaluated
   │
9. Return JSON response with HTTP 200
   │
10. Structured log emitted (ticket_id, latency_ms, case_type, confidence, NO message)
```

---

## 5. Technology Stack

### 5.1 Chosen Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Language** | Python 3.11+ | Fast to write, excellent for text processing, team familiarity |
| **Web Framework** | FastAPI | Auto OpenAPI docs, Pydantic-native, async support, fast |
| **Validation** | Pydantic v2 | Type-safe models, automatic 422 errors, enum support |
| **Server** | Uvicorn (ASGI) | Standard FastAPI server, fast and lightweight |
| **Testing** | pytest | De facto Python standard, simple, fast |
| **HTTP Client (tests)** | httpx | Async-friendly, used by FastAPI TestClient |
| **Container** | Docker (python:3.11-slim) | Reproducible, small image, free-tier compatible |
| **Deployment** | Render (free tier) | Auto HTTPS, free, simple git-based deploy |
| **Logging** | structlog (or stdlib `logging` JSON formatter) | Structured logs without heavy deps |
| **LLM (optional)** | None in v1 | Rule-based covers the brief; LLM adds cost + latency + secret risk |

### 5.2 Explicitly NOT chosen

| Rejected | Why |
|----------|-----|
| Flask | Slower validation story, no native async |
| Django | Heavyweight for a 2-endpoint service |
| Node.js/Express | Slightly more boilerplate for schema validation |
| Database (Postgres/SQLite) | Stateless service — no persistence needed |
| Redis / cache | Adds ops complexity; latency is already low |
| LLM in primary path | Cost, latency, determinism, secret-handling risk |
| GPU | Explicitly disallowed by brief |

---

## 6. Module / File Structure

```
mockproject/
├── README.md                   # Runbook, setup, deployment
├── REQUIREMENTS.md             # This document's companion
├── ARCHITECTURE.md             # This document
├── ROADMAP.md                  # Implementation order with milestones
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Optional local dev convenience
├── .dockerignore
├── .gitignore
├── .env.example                # Template for env vars (NO real values)
├── pyproject.toml              # Or requirements.txt
├── requirements.txt            # Pinned dependencies
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, route definitions
│   ├── config.py               # Env var loading, settings
│   ├── logging_config.py       # Structured logging setup
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py          # TicketRequest schema
│   │   ├── response.py         # TicketResponse schema
│   │   └── enums.py            # CaseType, Severity, Department, Channel, Locale
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py       # Main classify() entry point
│   │   ├── rules/
│   │   │   ├── __init__.py
│   │   │   ├── phishing.py     # Phishing detection rules
│   │   │   ├── wrong_transfer.py
│   │   │   ├── payment_failed.py
│   │   │   └── refund.py
│   │   ├── summarizer.py       # agent_summary generator
│   │   ├── safety.py           # Forbidden-phrase filter
│   │   └── router.py           # case_type → department mapping
│   │
│   └── api/
│       ├── __init__.py
│       ├── health.py           # /health handler
│       └── triage.py           # /sort-ticket handler
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures (TestClient)
    ├── test_health.py
    ├── test_triage_brief_cases.py    # The 5 sample cases from brief
    ├── test_classifier.py           # Per-rule unit tests
    ├── test_safety.py               # Safety filter tests
    ├── test_validation.py           # Schema validation tests
    └── fixtures/
        └── tickets.json             # Test data
```

---

## 7. Data Design

### 7.1 Why No Database?
The service is **stateless** — each request is independent, the response is fully derived from the request. There is no:
- User session
- Ticket history
- Aggregated metrics
- Cross-request learning

A database would add operational complexity (connection management, migrations, credentials) for zero functional value.

### 7.2 Request Schema (Pydantic)

```python
class TicketRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    channel: Optional[Channel] = None
    locale: Optional[Locale] = None
    message: str = Field(..., min_length=1)
```

### 7.3 Response Schema (Pydantic)

```python
class TicketResponse(BaseModel):
    ticket_id: str
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    human_review_required: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
```

### 7.4 Enums (Single Source of Truth)

```python
class CaseType(str, Enum):
    WRONG_TRANSFER = "wrong_transfer"
    PAYMENT_FAILED = "payment_failed"
    REFUND_REQUEST = "refund_request"
    PHISHING = "phishing_or_social_engineering"
    OTHER = "other"

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Department(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENTS_OPS = "payments_ops"
    FRAUD_RISK = "fraud_risk"

class Channel(str, Enum):
    APP = "app"
    SMS = "sms"
    CALL_CENTER = "call_center"
    MERCHANT_PORTAL = "merchant_portal"

class Locale(str, Enum):
    BN = "bn"
    EN = "en"
    MIXED = "mixed"
```

### 7.5 Classification Rules (Initial Set — refined during implementation)

Each rule is a small, independently testable function that returns `(matched: bool, confidence_delta: float)`.

**Phishing (highest priority):**
- Mentions of: OTP, PIN, password, CVV, card number
- Phrases: "someone called asking", "SMS asking for", "is that bKash?"
- Impersonation cues: "from Nagad support", "from bank"

**Wrong Transfer:**
- Keywords: wrong number, wrong account, sent to wrong, mistyped, by mistake
- Phrases: "sent 5000 to wrong", "transferred to wrong"

**Payment Failed:**
- Keywords: payment failed, transaction failed, money deducted, balance deducted, pending
- Phrases: "failed but", "deducted but not received"

**Refund Request:**
- Keywords: refund, money back, return my money, cancel transaction
- Phrases: "please refund", "I want my money back"

**Fallback:** none of the above → `other`

### 7.6 Department Routing Table

```python
DEPARTMENT_MAP = {
    CaseType.PHISHING: Department.FRAUD_RISK,
    CaseType.WRONG_TRANSFER: Department.DISPUTE_RESOLUTION,
    CaseType.PAYMENT_FAILED: Department.PAYMENTS_OPS,
    CaseType.REFUND_REQUEST: Department.DISPUTE_RESOLUTION,  # or customer_support if low severity
    CaseType.OTHER: Department.CUSTOMER_SUPPORT,
}
```

### 7.7 Severity Defaults

```python
SEVERITY_DEFAULTS = {
    CaseType.PHISHING: Severity.CRITICAL,
    CaseType.WRONG_TRANSFER: Severity.HIGH,
    CaseType.PAYMENT_FAILED: Severity.HIGH,
    CaseType.REFUND_REQUEST: Severity.LOW,        # bumps to MEDIUM if dispute cues
    CaseType.OTHER: Severity.LOW,
}
```

---

## 8. Safety Filter Design

### 8.1 Threat
The summary generation process might (intentionally or by LLM hallucination) produce text asking the customer to share their credentials. This is a hard fail per the brief.

### 8.2 Defense
A **post-generation regex filter** scans `agent_summary` before returning:

```python
FORBIDDEN_PATTERNS = [
    r"\bshare\s+(?:your\s+)?(?:otp|pin|password|cvv|card\s*number)\b",
    r"\bsend\s+(?:me\s+)?(?:your\s+)?(?:otp|pin|password)\b",
    r"\btell\s+me\s+your\s+(?:otp|pin|password)\b",
    r"\bprovide\s+your\s+(?:otp|pin|password)\b",
    r"\bgive\s+(?:me\s+)?(?:your\s+)?(?:otp|pin|password)\b",
]
```

### 8.3 Response Strategy
- **Approach A (rewrite)**: Replace forbidden phrases with neutral text like "[credential]". Log a warning.
- **Approach B (reject)**: Raise an internal exception, return 500 with a generic safe summary.
- **Chosen approach**: **A** (rewrite) — keeps the API contract stable. Log warning for monitoring.

---

## 9. Deployment Architecture

### 9.1 Target: Render (Free Tier)

```
GitHub Repo (public)
        │
        │  git push (auto-deploy on main)
        ▼
┌────────────────────────────┐
│  Render Web Service        │
│  - Docker runtime          │
│  - Auto HTTPS              │
│  - Free tier               │
│  - Public URL              │
└────────────────────────────┘
        │
        │  HTTPS
        ▼
   End Users / Grader
```

### 9.2 Environment Variables (set in Render dashboard, NEVER in code)

| Var | Purpose | Required |
|-----|---------|----------|
| `LOG_LEVEL` | `INFO` / `DEBUG` | No (default: INFO) |
| `APP_VERSION` | Reported in /health | No (default: 1.0.0) |

(Nothing else is needed for v1 — fully stateless, no API keys.)

### 9.3 Dockerfile (Strategy)
- Base: `python:3.11-slim`
- Install dependencies to `/app`
- Copy app code
- Run with uvicorn on port 8000
- Expose 8000
- Healthcheck pointing at `/health`

---

## 10. Cross-Cutting Concerns

### 10.1 Logging
- JSON-structured logs (one line per event)
- Per-request log includes: `timestamp`, `ticket_id`, `endpoint`, `latency_ms`, `status_code`, `case_type`, `confidence`
- **Never logs the message body** (PII risk)
- Logger name: `triage`

### 10.2 Error Handling
| Scenario | HTTP Status | Body |
|----------|-------------|------|
| Invalid JSON | 400 | `{"error": "invalid_json", "detail": "..."}` |
| Schema violation | 422 | `{"error": "validation_error", "detail": [...]}` |
| Missing `/sort-ticket` field | 422 | Pydantic-standard error |
| Internal error | 500 | `{"error": "internal_error", "ticket_id": "..."}` |
| Safety filter rewrite | 200 | Valid response, log warning |

### 10.3 Performance Budget
- Network round trip (client → Render): ~50ms
- FastAPI overhead: ~5ms
- Validation: ~1ms
- Classification (rule-based): <5ms
- Summary generation: <10ms
- Safety filter: <1ms
- **Total target**: < 100ms p99 (well within 30s limit)

### 10.4 Security Posture
- No authentication (public endpoint per brief)
- No PII in logs
- Input validation as a security boundary
- Safety filter as content security control
- No outbound network calls (no LLM in v1)
- HTTPS enforced by platform (Render)

---

## 11. Future Considerations (Out of Scope for v1)

These are explicitly **NOT** in v1 but worth noting:
- Add an LLM fallback for low-confidence cases
- Add multi-language support (Bangla-aware classification)
- Add request rate limiting
- Add metrics endpoint (Prometheus)
- Add batch endpoint (`POST /sort-tickets` for arrays)
- Add persistent ticket store for audit
- Add admin UI to review misclassified tickets and tune rules

---

## 12. Architecture Decision Records (ADRs)

### ADR-1: Rule-based classification over LLM
- **Decision**: Use rule-based classification in v1
- **Status**: Accepted
- **Context**: Brief allows LLM but doesn't require it
- **Pros**: Deterministic, free, fast, no secret, easy to debug
- **Cons**: May miss novel patterns; needs manual rule expansion
- **Mitigation**: Optional LLM fallback can be added later if real traffic shows gaps

### ADR-2: No database
- **Decision**: Stateless service, no persistence
- **Status**: Accepted
- **Context**: Brief describes one-shot classification, no stateful requirements
- **Pros**: Zero ops, deployable anywhere, no migration story
- **Cons**: No audit trail; can't improve from history
- **Mitigation**: Logs to stdout; can add structured log shipping later

### ADR-3: Python + FastAPI
- **Decision**: Use Python 3.11 + FastAPI
- **Status**: Accepted
- **Context**: Need fast iteration, type safety, free-tier deployability
- **Pros**: Pydantic-native, auto docs, fast, well-known
- **Cons**: None for this scope

### ADR-4: Phishing detection takes priority over other rules
- **Decision**: Run phishing check first; if matched, skip other rules
- **Status**: Accepted
- **Context**: A phishing message may also contain payment-failed cues; routing to fraud_risk is critical
- **Pros**: Correct routing for highest-severity case
- **Cons**: A message that is both phishing AND refund will be classified as phishing (correct)

### ADR-5: Summary safety filter rewrites rather than rejects
- **Decision**: Replace forbidden phrases with neutral tokens, log warning, return 200
- **Status**: Accepted
- **Context**: Brief says the safety violation "will fail that test case automatically" — implies grader checks the final response
- **Pros**: API contract stays stable; grader sees safe output
- **Cons**: Slightly masks the issue if logs aren't reviewed
- **Mitigation**: Emit WARN log every time the filter triggers

---

## 13. Glossary

See `REQUIREMENTS.md` §7 — same glossary applies.