# Requirements Document — QueueStorm CRM Ticket Triage Service

**Version:** 1.0
**Date:** 2026-06-25
**Source Brief:** `Mock_Project.docx`
**Status:** Approved for implementation

---

## 1. Project Overview

### 1.1 Purpose
Build a small stateless web service that reads a single customer support message (in English or Bangla) and returns a structured classification. The service acts as a first-pass triage layer for a busy digital finance company's CRM, helping human agents prioritize and route tickets faster.

### 1.2 Scope
**In Scope:**
- A single HTTP service exposing two endpoints
- Rule-based classification of one ticket at a time (no batch processing)
- JSON request/response contract strictly per the brief
- Safety guardrails on the generated summary
- Public HTTPS deployment

**Out of Scope (v1):**
- Persistent storage of tickets
- User authentication / authorization (public endpoint per brief)
- Multi-ticket batch processing
- Real CRM integration
- Web UI
- Authentication of the customer
- Ticket state tracking over time

### 1.3 Target Users
- Internal human support agents (consumers of the structured output)
- The grader / automated test harness (consumers of the API contract)

---

## 2. Functional Requirements

### 2.1 Endpoints

| ID | Method | Path | Purpose |
|----|--------|------|---------|
| FR-1 | GET | `/health` | Return service health status |
| FR-2 | POST | `/sort-ticket` | Classify one ticket and return structured response |

### 2.2 FR-1: Health Endpoint
- **FR-1.1** Must return HTTP 200 with a JSON body indicating the service is alive
- **FR-1.2** Response time must be under 10 seconds (per brief)
- **FR-1.3** Body must include at minimum a `status` field with value `"ok"`

**Proposed response shape (illustrative):**
```json
{
  "status": "ok",
  "service": "ticket-triage",
  "version": "1.0.0"
}
```

### 2.3 FR-2: Sort Ticket Endpoint

#### 2.3.1 Request
- **FR-2.1** Content-Type must be `application/json`
- **FR-2.2** Required fields: `ticket_id` (string), `message` (string)
- **FR-2.3** Optional fields: `channel` (string), `locale` (string)
- **FR-2.4** Reject malformed JSON with HTTP 400
- **FR-2.5** Reject schema-invalid bodies with HTTP 422 (Pydantic validation)

**Field constraints:**
| Field | Required | Allowed Values |
|-------|----------|----------------|
| `ticket_id` | Yes | non-empty string |
| `message` | Yes | non-empty string |
| `channel` | No | `app`, `sms`, `call_center`, `merchant_portal` |
| `locale` | No | `bn`, `en`, `mixed` |

#### 2.3.2 Response
- **FR-2.6** Must return HTTP 200 with a JSON body
- **FR-2.7** `ticket_id` must echo the request value
- **FR-2.8** `case_type` must be one of the 5 enum values
- **FR-2.9** `severity` must be one of: `low`, `medium`, `high`, `critical`
- **FR-2.10** `department` must be one of the 4 enum values
- **FR-2.11** `agent_summary` must be 1–2 neutral sentences
- **FR-2.12** `human_review_required` must be `true` when severity is `critical` OR `case_type` is `phishing_or_social_engineering`
- **FR-2.13** `confidence` must be a float between 0.0 and 1.0

#### 2.3.3 Case Type Classification Rules
| Case Type | Trigger |
|-----------|---------|
| `wrong_transfer` | Customer reports money sent to wrong recipient/account/number |
| `payment_failed` | Transaction failed but balance was deducted / pending |
| `refund_request` | Customer explicitly asks for refund / reversal of completed payment |
| `phishing_or_social_engineering` | Someone asking for OTP, PIN, password, or card details — suspicious contact |
| `other` | None of the above match (fallback) |

#### 2.3.4 Severity Rules
| Severity | Default Triggers |
|----------|------------------|
| `critical` | `phishing_or_social_engineering` (always); large value + urgency cues |
| `high` | `wrong_transfer`, `payment_failed` (default) |
| `medium` | `refund_request` with dispute cues |
| `low` | `other`, simple `refund_request` |

#### 2.3.5 Department Routing
| Department | Default Case Types |
|------------|--------------------|
| `fraud_risk` | `phishing_or_social_engineering` |
| `dispute_resolution` | `wrong_transfer`, contested refunds |
| `payments_ops` | `payment_failed` |
| `customer_support` | `other`, simple refunds |

#### 2.3.6 Safety Rule (HARD CONSTRAINT)
- **FR-2.14 (Safety)** The `agent_summary` field MUST NEVER ask the customer to share their PIN, OTP, password, full card number, CVV, or any credential. Any response violating this rule causes automatic test failure.
- **FR-2.15** A post-generation filter MUST scan and rewrite/reject the summary if it contains any of the forbidden phrases.

---

## 3. Non-Functional Requirements

### 3.1 Performance
| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | `/health` response time | < 10 seconds |
| NFR-2 | `/sort-ticket` response time | < 30 seconds |
| NFR-3 | Cold start acceptable | Yes (no warmup requirement) |

### 3.2 Availability & Deployment
| ID | Requirement |
|----|-------------|
| NFR-4 | Public HTTPS endpoint required |
| NFR-5 | Must run on free-tier platforms (Render, Railway, Fly, Vercel, Poridhi Lab, EC2) |
| NFR-6 | No GPU dependency |
| NFR-7 | Dockerfile provided for reproducible local runs |

### 3.3 Security
| ID | Requirement |
|----|-------------|
| NFR-8 | NO secrets (API keys, tokens) in the GitHub repository |
| NFR-9 | All secrets via environment variables |
| NFR-10 | Public endpoint — no PII logging in production |
| NFR-11 | The summary filter (FR-2.14) is a security control, not just a UX nicety |

### 3.4 Maintainability
| ID | Requirement |
|----|-------------|
| NFR-12 | Code organized in clear modules (`app/`, `tests/`, `models/`, `services/`) |
| NFR-13 | README.md with runbook, env vars, deployment steps |
| NFR-14 | Unit tests for each classification rule + the 5 brief sample cases |

### 3.5 Observability
| ID | Requirement |
|----|-------------|
| NFR-15 | Structured logs (JSON preferred) for each `/sort-ticket` request |
| NFR-16 | Logs include ticket_id, latency_ms, case_type, confidence — but NO message body or PII |

### 3.6 Portability
| ID | Requirement |
|----|-------------|
| NFR-17 | Must run locally with a single command (e.g. `uvicorn app.main:app`) |
| NFR-18 | Must run in Docker with a single command (`docker run`) |
| NFR-19 | Python 3.11+ baseline |

---

## 4. Test Cases (from Brief §7)

These are the **acceptance tests** the implementation MUST pass:

| # | Message | Expected case_type | Expected Severity |
|---|---------|--------------------|--------------------|
| 1 | "I sent 3000 to wrong number" | `wrong_transfer` | `high` |
| 2 | "Payment failed but balance deducted" | `payment_failed` | `high` |
| 3 | "Someone called asking my OTP, is that bKash?" | `phishing_or_social_engineering` | `critical` |
| 4 | "Please refund my last transaction, I changed my mind" | `refund_request` | `low` |
| 5 | "App crashed when I opened it" | `other` | `low` |

Additional tests derived from requirements:
- T6: Phishing case → `human_review_required == true`
- T7: Critical severity → `human_review_required == true`
- T8: Non-phishing, non-critical case → `human_review_required == false`
- T9: Safety rule — summary that mentions "share your OTP" gets rewritten/rejected
- T10: Malformed JSON → HTTP 400
- T11: Missing required field → HTTP 422
- T12: Invalid enum value (e.g. `channel: "fax"`) → HTTP 422

---

## 5. Constraints & Assumptions

### 5.1 Constraints (from brief — non-negotiable)
- Public HTTPS endpoint
- /health < 10s, /sort-ticket < 30s
- No GPU
- No secrets in repo
- LLM usage allowed but not required

### 5.2 Assumptions (documented for transparency)
- **A1**: v1 supports English text well; Bangla (`bn`) and `mixed` locale are accepted in input but classification is best-effort in English
- **A2**: `ticket_id` is opaque to the service — no format validation beyond non-empty
- **A3**: Service is stateless — no caching, no DB, no session
- **A4**: Confidence score is rule-derived (number of matched patterns / total patterns evaluated), not probabilistic ML
- **A5**: Phishing detection is **always prioritized** — if both phishing and another pattern match, phishing wins
- **A6**: Free-tier deployment acceptable; no SLA commitment

---

## 6. Acceptance Criteria (Definition of Done)

The project is considered DONE when:
- [ ] All 5 brief sample cases produce the expected case_type and severity
- [ ] All additional tests T6–T12 pass
- [ ] `/health` returns 200 in < 10s on a fresh deploy
- [ ] `/sort-ticket` returns 200 in < 30s with valid JSON
- [ ] Public HTTPS URL is live and accessible
- [ ] No secrets present in repo (verified via grep / GitHub secret scanning)
- [ ] README runbook allows a new dev to deploy in < 15 minutes
- [ ] Dockerfile builds and runs successfully
- [ ] GitHub repo is public with README and source
- [ ] Google Form submitted with all required fields

---

## 7. Glossary

| Term | Definition |
|------|------------|
| **CRM** | Customer Relationship Management system |
| **OTP** | One-Time Password |
| **PIN** | Personal Identification Number |
| **Triage** | Initial classification/prioritization before detailed handling |
| **bKash** | A mobile financial service in Bangladesh (referenced in test cases) |
| **BDT** | Bangladeshi Taka (currency) |