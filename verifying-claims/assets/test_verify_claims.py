"""verifying-claims claim verification as a pytest — forcing function #2.

Drop this into the repo's tests/. It runs verifying-claims on each gated spec and asserts
exit 0, so the spec's claims are checked whenever the test suite runs — which
CI already gates. This is the elegant integration when verifying-claims wraps a TDD loop:
the literate spec's claims become just more tests behind the same green bar.

Edit SPECS to point at the docs you want gated. Keep gated specs all-green —
do not include teaching/demo claims that intentionally FAIL.

Assumes scripts/verify_claims.py is reachable from the repo root. Adjust VERSO if your
layout differs.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSO = REPO_ROOT / "scripts" / "verify_claims.py"

# Docs to gate. Each must be all-green.
SPECS = [
    "README.md",
    # "docs/spec.md",
]


@pytest.mark.parametrize("spec", SPECS)
def test_verify_claims(spec):
    """Every claim in `spec` must resolve to PASS."""
    spec_path = REPO_ROOT / spec
    if not spec_path.exists():
        pytest.skip(f"{spec} not found")
    proc = subprocess.run(
        [sys.executable, str(VERSO), str(spec_path)],
        capture_output=True,
        text=True,
    )
    # verifying-claims exits 0 only when every claim passes; surface its report on failure.
    assert proc.returncode == 0, (
        f"verifying-claims reported drift in {spec}:\n{proc.stdout}\n{proc.stderr}"
    )
