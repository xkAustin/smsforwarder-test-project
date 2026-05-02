import pytest

from tests.performance.bench_webhook_receiver import run
from tests.utils.api_client import full_reset as reset

pytestmark = pytest.mark.performance


def test_webhook_receiver_smoke(mock_base):
    reset(mock_base, timeout=3.0)
    out = run(mock_base, n=20, timeout=3.0, warmup=2)
    assert out["ok"] == out["n"]
    assert out["success_rate"] >= 0.95
