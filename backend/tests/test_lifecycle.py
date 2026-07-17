from dataclasses import dataclass

import pytest

from app.core.errors import AppError
from app.core.lifecycle import transition


@dataclass
class FakeScan:
    status: str


def test_legal_transition_moves_status():
    scan = FakeScan(status="created")
    transition(scan, "enriching")
    assert scan.status == "enriching"


def test_illegal_transition_raises_409():
    scan = FakeScan(status="scope_pending")
    with pytest.raises(AppError) as exc_info:
        transition(scan, "executing")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"
    assert scan.status == "scope_pending"


def test_terminal_status_allows_no_transitions():
    scan = FakeScan(status="completed")
    with pytest.raises(AppError):
        transition(scan, "executing")
