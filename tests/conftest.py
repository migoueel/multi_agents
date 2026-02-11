import time
import pytest


def wait_for_status(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    """Poll until predicate() returns True or timeout (seconds) elapses.

    Raises TimeoutError if the condition isn't met in time.
    """
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(interval)
    raise TimeoutError("wait_for_status: condition not met within timeout")


@pytest.fixture
def wait_for_status_fn():
    """Fixture providing the wait_for_status helper for tests.

    Usage:
        wait_for_status_fn(lambda: some_condition(), timeout=3.0)
    """
    return wait_for_status
