from app.models.campaign import derive_campaign_status
from app.models.prompt import PromptStatus


def test_derive_campaign_status_created_when_all_prompts_pending() -> None:
    assert derive_campaign_status([PromptStatus.PENDING, PromptStatus.PENDING]) == "CREATED"


def test_derive_campaign_status_processing_when_any_prompt_processing() -> None:
    assert derive_campaign_status([PromptStatus.PROCESSING, PromptStatus.PENDING]) == "PROCESSING"


def test_derive_campaign_status_completed_when_all_prompts_completed() -> None:
    assert derive_campaign_status([PromptStatus.COMPLETED, PromptStatus.COMPLETED]) == "COMPLETED"


def test_derive_campaign_status_failed_when_all_prompts_failed() -> None:
    assert derive_campaign_status([PromptStatus.FAILED, PromptStatus.FAILED]) == "FAILED"


def test_derive_campaign_status_partial_when_terminal_mix_exists() -> None:
    assert derive_campaign_status([PromptStatus.COMPLETED, PromptStatus.FAILED]) == "PARTIAL"

