# Interview Notes

## Project Motivation

LLM Gateway was built to solve a common infrastructure problem: once multiple teams start using LLM APIs, direct provider integrations become difficult to govern. API keys spread across services, costs become hard to attribute, provider failures affect product reliability, and each team tends to reimplement retries, fallbacks, and monitoring differently.

The gateway centralizes those concerns behind one API so application teams can request model aliases while the platform layer handles authentication, routing, rate limits, budgets, resilience, and observability.

## Elevator Pitch

I built a FastAPI-based LLM control plane that sits in front of model providers. It authenticates teams, enforces model access, rate limits, and budgets, routes model aliases to provider targets, handles retries and fallback, protects failing providers with circuit breakers, and exposes Prometheus/Grafana observability. It runs locally with Docker Compose and is fully testable without paid provider keys.

## Architecture

The request path is:

1. Client calls `/v1/chat/completions`.
2. Bearer API key maps to a team.
3. The requested model alias is checked against the team's allowed models.
4. Redis enforces request rate limits.
5. Redis-backed budget state blocks teams that have reached daily or monthly caps.
6. The router resolves the alias to a primary provider target and fallback targets.
7. The resilience layer checks circuit state, retries retryable errors, and falls back when needed.
8. The provider returns a normalized response.
9. The gateway records spend, tokens, logs, and metrics.

This keeps application code simple while making gateway behavior testable and provider-agnostic.

## Engineering Tradeoffs

- `MockProvider` first: makes the whole system locally runnable and deterministic without real LLM credentials.
- YAML config: easy to review and demo, though a larger system would likely move config to a managed control plane or database.
- Redis for limits and spend: simple and fast for runtime counters, but not a permanent financial ledger.
- Provider abstraction before real adapters: keeps routing and resilience clean before provider-specific complexity arrives.
- Prometheus metrics before tracing: gives immediate operational visibility while keeping the implementation scope reasonable.
- No streaming support: avoids complicating retries, fallbacks, and response accounting in the portfolio phase.
- Separate data-plane and control-plane authentication: team keys authorize model traffic, while an expiring HttpOnly admin session protects global console and Grafana data. This avoids giving application credentials operational visibility or mutation rights.
- Environment-backed static keys: keeps the public demo deterministic and removes usable credentials from routing configuration, while deliberately deferring a database-backed key lifecycle and SSO.

## Scaling Discussion

At higher scale, I would focus on:

- horizontal gateway replicas behind a load balancer
- shared Redis or Redis Cluster for rate-limit and budget counters
- persistent usage events in Postgres or a warehouse
- provider adapter pools with explicit timeouts
- per-provider and per-model concurrency controls
- richer budget reservation to prevent overspend under concurrency
- OpenTelemetry traces for cross-service debugging
- authenticated admin APIs and audit logs

The current design already separates these concerns well enough that those changes would extend the system rather than require a rewrite.

## Failure Handling

The gateway distinguishes retryable and non-retryable provider failures.

Retryable failures such as timeouts, rate limits, and server errors can be retried and then routed to a fallback target. Non-retryable failures such as auth or configuration errors stop immediately because fallback could hide a serious operator issue.

Circuit breakers protect repeatedly failing provider targets. Each provider/model target has independent state, so one failing model does not poison unrelated routes.

## Observability Story

The project emits:

- structured request logs with request IDs
- response `X-Request-ID` headers
- request counters by team, model alias, and status code
- latency histograms
- provider error counters
- retry and fallback counters
- rate-limit and budget-block counters
- token and estimated-cost counters
- circuit-breaker state gauges

The important design choice is low-cardinality labels. Prompt text, raw user content, API keys, and request IDs are not used as Prometheus labels.

## Lessons Learned

- A clean provider contract pays off quickly once retries, fallbacks, and metrics enter the system.
- Deterministic provider failures make resilience tests much more trustworthy.
- Budget and rate-limit checks should happen before provider calls to avoid unnecessary cost.
- Observability needs to be designed alongside behavior, not bolted on after.
- Documentation is part of the product for infrastructure projects because reviewers need to understand operational intent quickly.

## Resume Bullet

Built a FastAPI LLM gateway that centralizes team auth, model routing, Redis-backed rate limits and budgets, retry/fallback behavior, circuit breakers, and Prometheus/Grafana observability, with 90+ automated tests and Docker Compose demo workflow.

## GitHub Description

Production-style LLM API gateway with team auth, model routing, rate limits, budgets, retries, fallback routing, circuit breakers, and Prometheus/Grafana observability.
