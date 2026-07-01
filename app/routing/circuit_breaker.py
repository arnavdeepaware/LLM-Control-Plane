import time
from dataclasses import dataclass, field
from typing import Literal

from app.config.loader import get_circuit_breaker_config
from app.observability.metrics import CIRCUIT_BREAKER_STATE

CircuitStateName = Literal["closed", "open", "half_open"]

_STATE_VALUES: dict[CircuitStateName, float] = {"closed": 0, "open": 1, "half_open": 2}


@dataclass
class CircuitState:
    state: CircuitStateName = "closed"
    failures: list[float] = field(default_factory=list)
    opened_at: float | None = None


_circuits: dict[str, CircuitState] = {}


def _key(provider: str, model: str) -> str:
    return f"{provider}:{model}"


def reset_circuits() -> None:
    """Clear all circuit state. Used by tests for isolation."""
    _circuits.clear()


def _get_or_create(key: str) -> CircuitState:
    if key not in _circuits:
        _circuits[key] = CircuitState()
    return _circuits[key]


def is_available(provider: str, model: str) -> bool:
    """Closed -> available. Open -> unavailable until cooldown elapses, then promotes to half-open."""
    circuit = _get_or_create(_key(provider, model))

    if circuit.state == "open":
        cooldown = get_circuit_breaker_config().cooldown_seconds
        if circuit.opened_at is not None and time.time() - circuit.opened_at >= cooldown:
            circuit.state = "half_open"
            CIRCUIT_BREAKER_STATE.labels(provider=provider, model=model).set(_STATE_VALUES[circuit.state])
        else:
            return False

    return True


def record_success(provider: str, model: str) -> None:
    """Closing on success covers both the half-open test request and normal closed-state traffic."""
    circuit = _get_or_create(_key(provider, model))
    circuit.state = "closed"
    circuit.failures = []
    circuit.opened_at = None
    CIRCUIT_BREAKER_STATE.labels(provider=provider, model=model).set(_STATE_VALUES[circuit.state])


def record_failure(provider: str, model: str) -> None:
    circuit = _get_or_create(_key(provider, model))
    config = get_circuit_breaker_config()
    now = time.time()

    if circuit.state == "half_open":
        circuit.state = "open"
        circuit.opened_at = now
        circuit.failures = [now]
        CIRCUIT_BREAKER_STATE.labels(provider=provider, model=model).set(_STATE_VALUES[circuit.state])
        return

    circuit.failures = [t for t in circuit.failures if now - t <= config.window_seconds]
    circuit.failures.append(now)

    if len(circuit.failures) >= config.failure_threshold:
        circuit.state = "open"
        circuit.opened_at = now
        CIRCUIT_BREAKER_STATE.labels(provider=provider, model=model).set(_STATE_VALUES[circuit.state])


def get_state(provider: str, model: str) -> CircuitState:
    """Return current state, pruning closed-circuit failures that have aged out of the window.

    Only pruned while closed: an open/half-open circuit's failure list documents why it
    tripped, which stays meaningful regardless of the rolling window.
    """
    circuit = _get_or_create(_key(provider, model))
    if circuit.state == "closed" and circuit.failures:
        window = get_circuit_breaker_config().window_seconds
        now = time.time()
        circuit.failures = [t for t in circuit.failures if now - t <= window]
    return circuit


def get_all_states() -> dict[str, CircuitState]:
    return dict(_circuits)
