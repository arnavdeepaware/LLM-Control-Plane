# Load Testing Guide

The load test script sends normal non-streaming chat requests through the gateway using MockProvider. It is intended for local verification, not production benchmarking.

## Default Run

Start the gateway first. Docker Compose is recommended because it also starts Redis, which the chat path requires for rate limiting and budget tracking:

```bash
docker compose up --build
```

If using `uvicorn` directly, start Redis separately before running the load test.

Then run:

```bash
python scripts/load_test.py --requests 200 --concurrency 20
```

Defaults:

- `--base-url http://localhost:8000`
- `--requests 200`
- `--concurrency 20`
- `--model cheap-chat`
- `--api-key alpha-secret-key`
- `--timeout-seconds 10`

## Smaller Local Check

```bash
python scripts/load_test.py --requests 20 --concurrency 5
```

## Output

```text
Load test complete
Total requests: 200
Successes: 60
Rate limited: 140
Errors: 0
Average latency ms: <number>
P95 latency ms: <number>
Requests/sec: <number>
Result: PASS
```

Fields:

- `Successes` are `2xx` responses with the expected mock response shape.
- `Rate limited` counts `429` responses separately.
- `Errors` includes transport failures, timeouts, `5xx`, unexpected `4xx`, and invalid success response shapes.
- `Average latency ms` and `P95 latency ms` are measured client-side.
- `Requests/sec` is the observed client-side throughput for the run.

## Rate Limits

The default `team_alpha` rate limit is 60 requests per minute, so a 200-request load test will usually include expected `429` responses. This is useful because it proves rate limiting still works under concurrent traffic.

Use strict mode when any rate limit should fail the run:

```bash
python scripts/load_test.py --requests 50 --concurrency 5 --fail-on-rate-limit
```

## Safety

- The script uses MockProvider only through the configured gateway route.
- No real provider API keys are required.
- No paid external LLM APIs are called.
- Keep request and concurrency values modest for laptop runs.
