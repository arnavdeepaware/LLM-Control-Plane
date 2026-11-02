from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry()

READINESS = Gauge("llm_gateway_ready", "Gateway readiness (0=unavailable, 1=ready)", registry=REGISTRY)

REQUEST_COUNT = Counter(
    "llm_gateway_requests_total",
    "Total requests to the gateway",
    ["team_id", "model_requested", "status_code"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "llm_gateway_request_latency_seconds",
    "Request latency in seconds",
    ["team_id", "model_requested"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

PROVIDER_ERRORS = Counter(
    "llm_gateway_provider_errors_total",
    "Provider errors",
    ["provider", "model_requested", "error_type"],
    registry=REGISTRY,
)

FALLBACK_COUNT = Counter(
    "llm_gateway_fallbacks_total",
    "Fallback activations",
    ["team_id", "model_requested"],
    registry=REGISTRY,
)

RETRY_COUNT = Counter(
    "llm_gateway_retries_total",
    "Retry attempts",
    ["provider", "model_requested"],
    registry=REGISTRY,
)

RATE_LIMITED_COUNT = Counter(
    "llm_gateway_rate_limited_total",
    "Requests blocked by rate limiting",
    ["team_id"],
    registry=REGISTRY,
)

BUDGET_BLOCKED_COUNT = Counter(
    "llm_gateway_budget_blocked_total",
    "Requests blocked by budget limits",
    ["team_id"],
    registry=REGISTRY,
)

TOKENS_USED = Counter(
    "llm_gateway_tokens_total",
    "Tokens consumed",
    ["team_id", "model_requested", "token_type"],
    registry=REGISTRY,
)

ESTIMATED_COST = Counter(
    "llm_gateway_cost_usd_total",
    "Estimated cost in USD",
    ["team_id", "model_requested"],
    registry=REGISTRY,
)

CIRCUIT_BREAKER_STATE = Gauge(
    "llm_gateway_circuit_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["provider", "model"],
    registry=REGISTRY,
)
