import subprocess
from pathlib import Path

import pytest

NOTEBOOKS = sorted((Path(__file__).parent.parent / "notebooks").glob("*.py"))


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda p: p.name)
def test_marimo_check(notebook):
    result = subprocess.run(["marimo", "check", str(notebook)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
