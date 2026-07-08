# LLM Control Plane

A production-style API gateway for managing LLM traffic across multiple providers with team authentication, rate limiting, budget controls, fallback routing, circuit breakers, and observability.

## Overview

LLM Gateway is an infrastructure project that sits between client applications and LLM providers such as OpenAI, Anthropic, Ollama, or mock/local providers.

Instead of each application calling LLM providers directly, applications call this gateway. The gateway handles authentication, model routing, provider abstraction, rate limits, cost tracking, fallback behavior, and monitoring in one centralized place.

```text
Client App
   ↓
LLM Gateway
   ↓
OpenAI / Anthropic / Ollama / Mock Provider
```

## Problem Statement

As teams adopt LLM APIs, direct provider integrations create operational problems:

- API keys are scattered across applications.
- Teams can accidentally exceed rate limits or budgets.
- There is no unified view of token usage, cost, latency, or errors.
- Provider outages can break applications.
- Different teams may implement inconsistent retry, fallback, or safety logic.
- Observability is fragmented across providers.

This project solves that by building a centralized LLM control plane.

## Core Features

- Unified chat completion API
- Team API key authentication
- Per-team model access control
- Provider abstraction layer
- Model alias routing
- Redis-backed rate limiting
- Budget tracking and enforcement
- Retry with exponential backoff
- Automatic fallback routing
- Circuit breaker for failing providers
- Structured logs
- Prometheus metrics
- Grafana dashboard
- Docker Compose local stack
- Integration tests and demo scripts

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| API Framework | FastAPI |
| Async HTTP Client | httpx |
| Validation | Pydantic |
| Config | YAML |
| Rate Limiting | Redis |
| Metrics | Prometheus |
| Dashboard | Grafana |
| Testing | pytest, pytest-asyncio |
| Containerization | Docker, Docker Compose |
| Providers | Mock provider first, optional OpenAI/Ollama later |

## Architecture

```text
                    ┌────────────────────┐
                    │ Client Application │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   FastAPI Gateway  │
                    └─────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐     ┌────────────────┐     ┌────────────────┐
│ Auth Module  │     │ Rate Limiter   │     │ Budget Manager │
└──────────────┘     └────────────────┘     └────────────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Routing Engine     │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
      ┌────────────┐  ┌──────────────┐  ┌────────────┐
      │ OpenAI     │  │ Ollama       │  │ Mock       │
      │ Adapter    │  │ Adapter      │  │ Provider   │
      └────────────┘  └──────────────┘  └────────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Observability      │
                    └────────────────────┘
```

## Request Flow

```text
1. Client sends request to /v1/chat/completions.
2. Gateway validates Bearer API key.
3. Gateway identifies the team.
4. Gateway checks whether the team can use the requested model alias.
5. Gateway checks rate limits.
6. Gateway checks budget.
7. Router selects primary provider/model.
8. Circuit breaker checks provider health.
9. Gateway calls provider.
10. If provider fails, gateway retries.
11. If retries fail, gateway falls back to backup provider.
12. Gateway normalizes response.
13. Gateway records usage, cost, logs, and metrics.
14. Gateway returns response to client.
```

## Planned API

### Health Check

```http
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

### Chat Completion

```http
POST /v1/chat/completions
Authorization: Bearer alpha-secret-key
Content-Type: application/json
```

Example request:

```json
{
  "model": "smart-chat",
  "messages": [
    {
      "role": "user",
      "content": "Explain distributed systems simply."
    }
  ],
  "stream": false,
  "priority": "normal"
}
```

Example response:

```json
{
  "id": "chatcmpl_mock_123",
  "object": "chat.completion",
  "model_requested": "smart-chat",
  "model_served": "mock:mock-smart-chat",
  "provider": "mock",
  "fallback_used": false,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Mock response from the gateway."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "input_tokens": 12,
    "output_tokens": 24,
    "total_tokens": 36
  }
}
```

### Admin Usage

```http
GET /admin/teams/{team_id}/usage
```

### Provider Health

```http
GET /providers/health
```

### Metrics

```http
GET /metrics
```

## Example Configuration

```yaml
teams:
  team_alpha:
    api_key: alpha-secret-key
    allowed_models:
      - smart-chat
      - cheap-chat
    rate_limits:
      requests_per_minute: 60
      tokens_per_minute: 50000
    budgets:
      daily_usd: 5.00
      monthly_usd: 50.00

  team_beta:
    api_key: beta-secret-key
    allowed_models:
      - cheap-chat
    rate_limits:
      requests_per_minute: 20
      tokens_per_minute: 10000
    budgets:
      daily_usd: 1.00
      monthly_usd: 20.00

models:
  smart-chat:
    primary: mock:mock-smart-chat
    fallbacks:
      - mock:mock-backup-chat

  cheap-chat:
    primary: mock:mock-cheap-chat
    fallbacks:
      - mock:mock-backup-cheap
```

## Project Structure

```text
llm-gateway/
│
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── health.py
│   │   ├── chat.py
│   │   └── admin.py
│   ├── auth/
│   │   └── api_key.py
│   ├── config/
│   │   ├── loader.py
│   │   └── teams.yaml
│   ├── models/
│   │   ├── chat.py
│   │   └── team.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── mock_provider.py
│   │   ├── openai_provider.py
│   │   └── ollama_provider.py
│   ├── routing/
│   │   ├── router.py
│   │   ├── fallback.py
│   │   └── circuit_breaker.py
│   ├── rate_limit/
│   │   └── limiter.py
│   ├── budget/
│   │   └── manager.py
│   └── observability/
│       ├── logging.py
│       └── metrics.py
│
├── tests/
│   ├── test_health.py
│   ├── test_chat_mvp.py
│   ├── test_auth.py
│   ├── test_rate_limit.py
│   ├── test_budget.py
│   ├── test_fallback.py
│   └── test_circuit_breaker.py
│
├── grafana/
├── prometheus.yml
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── instructions.md
└── README.md
```

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/llm-gateway.git
cd llm-gateway
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run locally

```bash
uvicorn app.main:app --reload
```

### 5. Test health endpoint

```bash
curl http://localhost:8000/health
```

### 6. Run with Docker Compose

```bash
docker compose up --build
```

## Example Curl Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer alpha-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "smart-chat",
    "messages": [
      {
        "role": "user",
        "content": "Hello gateway"
      }
    ],
    "stream": false,
    "priority": "normal"
  }'
```

## Testing

Run all tests:

```bash
pytest
```

Run a specific test file:

```bash
pytest tests/test_rate_limit.py
```

Recommended test coverage:

- Health check
- API key authentication
- Model access control
- Provider routing
- Mock provider responses
- Rate limiting
- Budget tracking
- Fallback routing
- Circuit breaker transitions
- Prometheus metrics

## Development Phases

### Phase 1: Repo Setup

- Create GitHub repo.
- Add README.md and instructions.md.
- Add FastAPI app.
- Add health endpoint.
- Add Dockerfile and Docker Compose.
- Add first pytest health test.

### Phase 2: MVP Proxy

- Add `/v1/chat/completions`.
- Add Pydantic request/response models.
- Add YAML team config.
- Add Bearer API key authentication.
- Add MockProvider.
- Return normalized chat response.

### Phase 3: Provider Abstraction

- Add BaseProvider interface.
- Add provider registry.
- Add model alias routing.
- Add typed provider errors.
- Add mock failure modes.

### Phase 4: Rate Limits and Budgets

- Add Redis-backed request rate limiting.
- Return 429 with Retry-After.
- Add budget manager.
- Track estimated per-team cost.
- Add admin usage endpoint.

### Phase 5: Resilience

- Add retry with exponential backoff.
- Add fallback routing.
- Add circuit breaker.
- Add provider health endpoint.
- Add failure simulation tests.

### Phase 6: Observability

- Add structured logs.
- Add Prometheus metrics.
- Add `/metrics`.
- Add Prometheus and Grafana to Docker Compose.
- Add basic dashboard.

### Phase 7: Testing and Demo

- Add integration tests.
- Add load test script.
- Add demo commands.
- Polish README.
- Record final demo.

## Demo Flow

1. Start the full stack.

```bash
docker compose up --build
```

2. Show health endpoint.

```bash
curl http://localhost:8000/health
```

3. Send a normal request.

4. Send a request with an invalid API key and show 401.

5. Send a request for a disallowed model and show 403.

6. Trigger rate limiting and show 429.

7. Simulate provider failure and show fallback routing.

8. Trigger repeated provider failures and show circuit breaker opening.

9. Open Grafana and show live metrics.

## Success Criteria

The project is complete when:

- The gateway runs locally.
- The gateway runs through Docker Compose.
- Teams can authenticate with API keys.
- Teams are restricted to allowed models.
- Requests are routed through provider abstraction.
- Rate limits work.
- Budgets are tracked.
- Fallback behavior works.
- Circuit breaker behavior works.
- Metrics are exposed.
- Tests pass.
- README explains setup and demo clearly.

## Future Work

- Real OpenAI adapter
- Real Anthropic adapter
- Real Ollama adapter
- Streaming support
- Hot-reload config
- Slack alert integration
- Persistent database for request logs
- Web admin dashboard
- OpenTelemetry tracing
- Kubernetes deployment
- CI/CD pipeline
- More accurate tokenizer-based cost calculation

## Provider Docs

- See `docs/provider-abstraction.md` for the provider contract, registry behavior, and how to add a new provider safely.

## Project Narrative

I built a production-style LLM API gateway that centralizes access to multiple LLM providers. The gateway authenticates teams, enforces rate limits and budgets, routes requests to the correct provider, automatically falls back during provider failures, and exposes unified metrics for monitoring. The goal is to solve the operational problems companies face when multiple teams use LLMs independently: uncontrolled costs, scattered API keys, poor observability, provider outages, and inconsistent reliability logic.
