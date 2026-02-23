import pytest
from tests.utils.trigger import _emulator_port

@pytest.mark.parametrize("serial, expected_port", [
    ("emulator-5554", 5554),
    ("emulator-5556", 5556),
    ("emulator-5558", 5558),
    ("device-1234", None),
    ("12345678", None),
    ("emulator-", None),
    ("emulator-abc", None),
    ("something-emulator-5554", None),
    ("emulator-5554-extra", None),
    ("", None),
])
def test_emulator_port_parsing(serial, expected_port):
    assert _emulator_port(serial) == expected_port
