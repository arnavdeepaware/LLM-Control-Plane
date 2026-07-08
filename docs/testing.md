# Testing Guide

This project is designed to run locally without real LLM provider keys. Automated tests use MockProvider and fakeredis.

## Setup

```bash
pip install -r requirements.txt
```

## Automated Tests

Run the full suite:

```bash
pytest -q
```

Run the integration gateway tests:

```bash
pytest tests/test_integration_gateway.py -q
```

Useful focused regression commands:

```bash
pytest tests/test_fallback.py -q
pytest tests/test_circuit_breaker.py -q
pytest tests/test_metrics.py -q
pytest tests/test_providers.py -q
```

## Local Smoke Test

The smoke test exercises the chat path, so Redis must be available. The simplest local path is Docker Compose:

```bash
docker compose up --build
```

Or, with legacy Compose:

```bash
docker-compose up --build
```

If running the gateway directly, start Redis separately and then run:

```bash
uvicorn app.main:app --reload
```

Run smoke checks:

```bash
python scripts/smoke_test.py --base-url http://localhost:8000
```

Expected successful output shape:

```text
PASS health 200
PASS metrics 200
PASS chat 200
PASS missing_auth 401
PASS invalid_auth 401
PASS disallowed_model 403
Smoke test passed: 6/6 checks
```

## Docker Compose Verification

Modern Compose:

```bash
docker compose config
docker compose up --build
python scripts/smoke_test.py --base-url http://localhost:8000
python scripts/load_test.py --requests 200 --concurrency 20
docker compose down
```

Legacy Compose:

```bash
docker-compose config
docker-compose up --build
python scripts/smoke_test.py --base-url http://localhost:8000
python scripts/load_test.py --requests 200 --concurrency 20
docker-compose down
```

## Notes

- No automated test calls real OpenAI, Anthropic, or Ollama APIs.
- Smoke and load scripts target a running local gateway; they do not start services for you.
- Chat smoke/load checks require Redis because rate limiting and budget checks run before provider calls.
- The load script may report expected `429` responses because local team rate limits are intentionally low.
- Prometheus is available at `http://localhost:9090` and Grafana at `http://localhost:3000` when the Compose stack is running.
