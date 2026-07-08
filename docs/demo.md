# Demo Guide

This guide gives a reviewer-friendly walkthrough of the gateway in about five minutes. It uses only local services and the deterministic `MockProvider`.

## Prerequisites

- Python dependencies installed with `pip install -r requirements.txt`
- Docker and Docker Compose available
- Ports `8000`, `6379`, `9090`, and `3000` available

## Start The Stack

```bash
docker compose up --build
```

Legacy Compose:

```bash
docker-compose up --build
```

Keep that terminal running. In a second terminal, run:

```bash
bash scripts/demo.sh
```

## Demo Script

The script checks:

- gateway health
- successful chat completion
- missing auth rejection
- invalid API key rejection
- disallowed model rejection
- team limits endpoint
- team usage endpoint
- provider health endpoint
- metrics endpoint
- rate limiting under repeated local requests

Expected final line:

```text
Demo complete.
```

## Manual Walkthrough

### 1. Health

```bash
curl -s http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

### 2. Successful Chat Request

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer alpha-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "smart-chat",
    "messages": [
      {"role": "user", "content": "Hello gateway"}
    ]
  }'
```

Expected highlights:

```json
{
  "model_requested": "smart-chat",
  "model_served": "mock:mock-smart-chat",
  "provider": "mock",
  "fallback_used": false
}
```

### 3. Missing Auth

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"smart-chat","messages":[{"role":"user","content":"Hello"}]}'
```

Expected status: `401`

Expected body:

```json
{
  "error": "unauthorized",
  "message": "Missing authorization header"
}
```

### 4. Disallowed Model

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer beta-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"smart-chat","messages":[{"role":"user","content":"Hello"}]}'
```

Expected status: `403`

Expected body:

```json
{
  "error": "forbidden",
  "message": "Model 'smart-chat' is not allowed for team 'Team Beta'"
}
```

### 5. Usage And Limits

```bash
curl -s http://localhost:8000/admin/teams/team_alpha/limits
curl -s http://localhost:8000/admin/teams/team_alpha/usage
```

Expected highlights:

```json
{
  "team_id": "team_alpha",
  "rate_limits": {
    "requests_per_minute": 60
  },
  "budgets": {
    "daily_usd": 5.0,
    "monthly_usd": 50.0
  }
}
```

### 6. Provider Health

```bash
curl -s http://localhost:8000/providers/health
```

Expected highlights:

```json
{
  "provider": "mock",
  "model": "mock-smart-chat",
  "circuit_state": "closed"
}
```

### 7. Metrics

```bash
curl -s http://localhost:8000/metrics | grep llm_gateway_requests_total
```

Expected:

```text
# HELP llm_gateway_requests_total Total requests to the gateway
# TYPE llm_gateway_requests_total counter
```

### 8. Rate Limit

Run enough requests as `team_beta` to exceed the local default of `20` requests per minute:

```bash
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer beta-secret-key" \
    -H "Content-Type: application/json" \
    -d '{"model":"cheap-chat","messages":[{"role":"user","content":"Load demo"}]}'
done
```

Expected: initial `200` responses followed by `429` responses.

## Grafana And Prometheus

Open:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Useful Prometheus queries:

```text
llm_gateway_requests_total
llm_gateway_request_latency_seconds_count
llm_gateway_rate_limited_total
llm_gateway_tokens_total
llm_gateway_cost_usd_total
```

In Grafana, use the provisioned dashboard to show gateway traffic after running the demo and load scripts.
