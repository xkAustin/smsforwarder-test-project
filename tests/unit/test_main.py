import runpy

import pytest

from main import main

pytestmark = pytest.mark.unit


def test_main(capsys):
    """Test that main() prints the expected message to stdout."""
    main()
    captured = capsys.readouterr()
    assert captured.out == "Hello from smsforwarder-test-project!\n"


def test_entrypoint(capsys):
    """Test the __main__ entrypoint of main.py."""
    # Using runpy to execute main.py with __name__ set to "__main__"
    runpy.run_path("main.py", run_name="__main__")
    captured = capsys.readouterr()
    assert captured.out == "Hello from smsforwarder-test-project!\n"
