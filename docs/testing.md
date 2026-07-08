# Testing Guide

The test suite is designed to prove gateway behavior without real LLM provider keys. Automated tests use `MockProvider` for deterministic provider responses and `fakeredis` for Redis-backed rate limits and budgets.

## Quick Commands

```bash
pytest
pytest -q
pytest tests/test_integration_gateway.py -q
pytest tests/test_providers.py -q
pytest tests/test_metrics.py -q
```

If `pytest` is not on your shell path but you created the local virtual environment:

```bash
./.venv/bin/pytest -q
```

## What The Tests Cover

| Area | Coverage |
| --- | --- |
| Health | `/` and `/health` responses |
| Chat API | successful normalized chat response shape |
| Auth | missing, malformed, and invalid Bearer tokens |
| Authorization | per-team model access controls |
| Config | provider target, pricing, and route validation |
| Provider abstraction | target parsing, registry lookup, mock provider behavior |
| Rate limiting | Redis-backed request limit and `Retry-After` responses |
| Budgets | daily/monthly blocking and spend tracking |
| Retry | retryable provider errors, max retry bounds, non-retryable handling |
| Fallback | primary failure, fallback success, all-provider failure |
| Circuit breaker | closed/open/half-open transitions and independent target state |
| Observability | request IDs, metrics, counters, histograms, gauges |
| Integration | end-to-end gateway behavior through FastAPI `TestClient` |

## Full Suite

```bash
pytest
```

Expected result:

```text
93 passed
```

The exact warning count may vary by dependency version.

## Focused Regression Runs

```bash
pytest tests/test_chat_mvp.py -q
pytest tests/test_rate_limit.py -q
pytest tests/test_budget.py -q
pytest tests/test_retry.py -q
pytest tests/test_fallback.py -q
pytest tests/test_circuit_breaker.py -q
pytest tests/test_providers.py -q
pytest tests/test_metrics.py -q
pytest tests/test_integration_gateway.py -q
```

## Docker Compose Validation

Modern Compose:

```bash
docker compose config
```

Legacy Compose:

```bash
docker-compose config
```

This validates service wiring for the gateway, Redis, Prometheus, and Grafana.

## Smoke Test

Start the stack:

```bash
docker compose up --build
```

Run smoke checks:

```bash
python scripts/smoke_test.py --base-url http://localhost:8000
```

Expected output:

```text
PASS health 200
PASS metrics 200
PASS chat 200
PASS missing_auth 401
PASS invalid_auth 401
PASS disallowed_model 403
Smoke test passed: 6/6 checks
```

## Load Test

```bash
python scripts/load_test.py --requests 200 --concurrency 20
```

Expected output shape:

```text
Load test complete
Total requests: 200
Successes: <number>
Rate limited: <number>
Errors: 0
Average latency ms: <number>
P95 latency ms: <number>
Requests/sec: <number>
Result: PASS
```

The default `team_alpha` request limit is `60` requests per minute, so rate-limited responses are expected in larger local load runs.

## Testing Principles

- No automated test calls OpenAI, Anthropic, Ollama, or any paid provider.
- Tests should not require real API keys.
- Tests should not weaken existing behavior to pass.
- Failure-mode tests should use deterministic `MockProvider` queues.
- Redis behavior should stay isolated through `fakeredis`.
- Metrics labels should remain low-cardinality.
