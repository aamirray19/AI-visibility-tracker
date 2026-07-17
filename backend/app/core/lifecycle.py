from typing import Protocol

from app.core.error_codes import INVALID_STATE_TRANSITION
from app.core.errors import AppError

# Valid transitions per system_design.md §5. Terminal statuses map to an empty set.
TRANSITIONS: dict[str, set[str]] = {
    "created": {"enriching", "cancelled"},
    "enriching": {"awaiting_verification", "failed"},
    "awaiting_verification": {"verifying", "cancelled"},
    "verifying": {"awaiting_verification", "scope_pending", "failed"},
    "scope_pending": {"queued"},
    "queued": {"generating_prompts"},
    "generating_prompts": {"executing", "failed"},
    "executing": {"evaluating", "failed"},
    "evaluating": {"aggregating", "failed"},
    "aggregating": {"completed", "completed_with_gaps", "failed"},
    "completed": set(),
    "completed_with_gaps": set(),
    "failed": set(),
    "cancelled": set(),
}


class _HasStatus(Protocol):
    status: str


def transition(scan: _HasStatus, to_status: str) -> None:
    """Mutate scan.status if the move is legal, else raise AppError(409)."""
    allowed = TRANSITIONS.get(scan.status, set())
    if to_status not in allowed:
        raise AppError(
            INVALID_STATE_TRANSITION,
            f"Cannot move scan from '{scan.status}' to '{to_status}'",
            status_code=409,
            details={"from": scan.status, "to": to_status},
        )
    scan.status = to_status
