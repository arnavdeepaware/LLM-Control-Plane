# Architecture

LLM Gateway is a FastAPI control plane for LLM traffic. It centralizes team authentication, model access control, model routing, provider abstraction, rate limiting, budget enforcement, resilience behavior, and observability.

The implementation is intentionally modular: API routes stay in `app/api`, authentication in `app/auth`, provider-specific logic in `app/providers`, routing and resilience in `app/routing`, Redis-backed limits in `app/rate_limit` and `app/budget`, and metrics/logging in `app/observability`.

## Overall Architecture

```mermaid
flowchart LR
    Client["Client application"] --> API["FastAPI API layer"]
    API --> Auth["Auth: Bearer API key"]
    API --> Config["YAML config"]
    API --> RateLimit["Redis rate limiter"]
    API --> Budget["Budget manager"]
    API --> Router["Model router"]
    Router --> Resilience["Retry, fallback, circuit breaker"]
    Resilience --> Registry["Provider registry"]
    Registry --> Mock["MockProvider"]
    RateLimit --> Redis["Redis"]
    Budget --> Redis
    API --> Logs["Structured JSON logs"]
    API --> Metrics["Prometheus metrics"]
    Metrics --> Prometheus["Prometheus"]
    Prometheus --> Grafana["Grafana"]
```

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as FastAPI Gateway
    participant Auth
    participant Redis
    participant Router
    participant Provider as Provider Layer
    participant Metrics

    Client->>Gateway: POST /v1/chat/completions
    Gateway->>Auth: Validate Bearer API key
    Auth-->>Gateway: Team config
    Gateway->>Router: Resolve model alias
    Router-->>Gateway: Primary and fallback targets
    Gateway->>Redis: Consume request rate-limit token
    Redis-->>Gateway: Allowed or 429
    Gateway->>Redis: Check daily/monthly budget
    Redis-->>Gateway: Allowed or 402
    Gateway->>Provider: Call primary target with retries
    Provider-->>Gateway: Normalized response
    Gateway->>Redis: Record spend and token usage
    Gateway->>Metrics: Increment counters and observe latency
    Gateway-->>Client: ChatCompletionResponse
```

## Authentication boundaries

```mermaid
flowchart LR
    Reviewer -->|Admin access code once| Session[Signed HttpOnly admin session]
    Session --> Console[Teams, usage, providers]
    Session --> Grafana[Read-only Grafana]
    Application -->|Team Bearer key| Identity[/v1/me]
    Application -->|Team Bearer key| Chat[/v1/chat/completions]
    Developer -->|Local dev token| TestLab[/dev controls]
```

Data-plane team keys identify the calling team and constrain chat behavior. The separate control-plane session protects global operational metadata. Development controls remain a third, local-only credential so neither a team key nor a read-only admin session can mutate demo state.

## Provider Routing

```mermaid
flowchart TD
    Start["Request model alias"] --> Allowed{"Alias allowed for team?"}
    Allowed -- "No" --> Forbidden["403 forbidden"]
    Allowed -- "Yes" --> Route{"Route configured?"}
    Route -- "No" --> Missing["404 route missing"]
    Route -- "Yes" --> Primary["Build primary ProviderTarget"]
    Primary --> Fallbacks["Build fallback ProviderTargets"]
    Fallbacks --> Validate["ProviderRegistry validates targets"]
    Validate --> Chain["Ordered target chain"]
    Chain --> Resilience["Resilience layer executes chain"]
```

## Retry And Fallback Flow

```mermaid
flowchart TD
    Start["Target selected"] --> Circuit{"Circuit available?"}
    Circuit -- "No" --> NextTarget["Skip to next target"]
    Circuit -- "Yes" --> Call["Call provider"]
    Call --> Success{"Success?"}
    Success -- "Yes" --> RecordSuccess["Record circuit success"]
    RecordSuccess --> Return["Return normalized response"]
    Success -- "Retryable error" --> Retry{"Retries left?"}
    Retry -- "Yes" --> Backoff["Sleep with backoff and jitter"]
    Backoff --> Call
    Retry -- "No" --> RecordFailure["Record provider failure"]
    RecordFailure --> NextTarget
    Success -- "Non-retryable error" --> Stop["Record failure and return provider error"]
    NextTarget --> More{"More targets?"}
    More -- "Yes" --> Circuit
    More -- "No" --> Unavailable["503 no_provider_available"]
```

## Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> closed
    closed --> closed: success or failures below threshold
    closed --> open: failures reach threshold within window
    open --> open: cooldown not elapsed
    open --> half_open: cooldown elapsed
    half_open --> closed: trial request succeeds
    half_open --> open: trial request fails
```

State values exposed through `llm_gateway_circuit_state`:

| State | Gauge value |
| --- | --- |
| `closed` | `0` |
| `open` | `1` |
| `half_open` | `2` |

## Docker Deployment

```mermaid
flowchart LR
    subgraph DockerCompose["Docker Compose"]
        Gateway["gateway: FastAPI app"]
        Redis["redis:7-alpine"]
        Prometheus["prometheus:v2.53.0"]
        Grafana["grafana:11.1.0"]
    end

    User["Developer / reviewer"] --> Gateway
    Gateway --> Redis
    Prometheus --> Gateway
    Grafana --> Prometheus
```

Exposed ports:

| Service | Port |
| --- | --- |
| Gateway | `8000` |
| Redis | `6379` |
| Prometheus | `9090` |
| Grafana | `3000` |

## Design Boundaries

- API routes do orchestration and response handling.
- Provider adapters do provider-specific calls and response normalization.
- Routing code owns alias resolution, retry, fallback, and circuit-breaker behavior.
- Redis is used for runtime rate-limit and budget state.
- Configuration is static YAML loaded by the application.
- Observability avoids high-cardinality labels and never records prompt content as metric labels.
