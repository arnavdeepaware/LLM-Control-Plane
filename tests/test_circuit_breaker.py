import time

from app.routing import circuit_breaker

# teams.yaml circuit_breaker config: failure_threshold=5, window_seconds=30, cooldown_seconds=60.
PROVIDER = "mock"
MODEL = "mock-circuit-test-model"


def test_starts_closed():
    assert circuit_breaker.get_state(PROVIDER, MODEL).state == "closed"
    assert circuit_breaker.is_available(PROVIDER, MODEL) is True


def test_stays_closed_below_threshold():
    for _ in range(4):
        circuit_breaker.record_failure(PROVIDER, MODEL)

    assert circuit_breaker.get_state(PROVIDER, MODEL).state == "closed"
    assert circuit_breaker.is_available(PROVIDER, MODEL) is True


def test_opens_after_threshold_failures():
    for _ in range(5):
        circuit_breaker.record_failure(PROVIDER, MODEL)

    assert circuit_breaker.get_state(PROVIDER, MODEL).state == "open"
    assert circuit_breaker.is_available(PROVIDER, MODEL) is False


def test_half_open_after_cooldown_elapses():
    for _ in range(5):
        circuit_breaker.record_failure(PROVIDER, MODEL)
    circuit_breaker.get_state(PROVIDER, MODEL).opened_at = time.time() - 61

    assert circuit_breaker.is_available(PROVIDER, MODEL) is True
    assert circuit_breaker.get_state(PROVIDER, MODEL).state == "half_open"


def test_half_open_success_closes_circuit():
    for _ in range(5):
        circuit_breaker.record_failure(PROVIDER, MODEL)
    circuit_breaker.get_state(PROVIDER, MODEL).opened_at = time.time() - 61
    circuit_breaker.is_available(PROVIDER, MODEL)  # promotes open -> half_open

    circuit_breaker.record_success(PROVIDER, MODEL)

    state = circuit_breaker.get_state(PROVIDER, MODEL)
    assert state.state == "closed"
    assert state.failures == []


def test_half_open_failure_reopens_circuit():
    for _ in range(5):
        circuit_breaker.record_failure(PROVIDER, MODEL)
    circuit_breaker.get_state(PROVIDER, MODEL).opened_at = time.time() - 61
    circuit_breaker.is_available(PROVIDER, MODEL)  # promotes open -> half_open

    circuit_breaker.record_failure(PROVIDER, MODEL)

    assert circuit_breaker.get_state(PROVIDER, MODEL).state == "open"


def test_independent_provider_model_keys_have_independent_state():
    circuit_breaker.record_failure(PROVIDER, "model-a")
    assert circuit_breaker.get_state(PROVIDER, "model-b").state == "closed"


def test_stale_failures_outside_window_are_pruned_on_read():
    circuit_breaker.get_state(PROVIDER, MODEL).failures = [time.time() - 100] * 4  # window_seconds is 30

    state = circuit_breaker.get_state(PROVIDER, MODEL)
    assert state.failures == []
    assert state.state == "closed"


def test_stale_failures_do_not_count_toward_threshold():
    # 4 failures aged out of the window, then 2 fresh ones: should stay closed (not 4+2=6 >= 5).
    circuit_breaker.get_state(PROVIDER, MODEL).failures = [time.time() - 100] * 4
    circuit_breaker.record_failure(PROVIDER, MODEL)
    circuit_breaker.record_failure(PROVIDER, MODEL)

    assert circuit_breaker.get_state(PROVIDER, MODEL).state == "closed"
