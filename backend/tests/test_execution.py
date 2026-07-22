from app.core.keypool import PoolExhausted
from app.llm.base import LLMResponse
from app.services import execution


class FakeProvider:
    model = "gemma-4-31b-it"

    def __init__(self, response=None, raises=None):
        self._response = response
        self._raises = raises
        self.last_tools = "unset"

    async def complete(self, prompt, *, tools=None, timeout=60.0, **kwargs):
        self.last_tools = tools
        if self._raises:
            raise self._raises
        return self._response


def _response(**overrides):
    fields = dict(
        text="the answer",
        latency_ms=10,
        model="gemma-4-31b-it",
        tokens_in=5,
        tokens_out=5,
        citations=[],
        cost_usd=0.0,
        key_id="k1",
    )
    fields.update(overrides)
    return LLMResponse(**fields)


async def test_execute_success_returns_full_fields():
    provider = FakeProvider(response=_response(citations=[{"url": "https://g2.com/x", "domain": "g2.com"}]))
    fields = await execution.execute(provider, "google_ai_studio", "some prompt")
    assert fields["status"] == "success"
    assert fields["raw_response"] == "the answer"
    assert fields["citations"] == [{"url": "https://g2.com/x", "domain": "g2.com"}]
    assert fields["api_key_id"] == "k1"
    assert fields["model"] == "gemma-4-31b-it"


async def test_execute_does_not_request_tools_for_google():
    provider = FakeProvider(response=_response())
    await execution.execute(provider, "google_ai_studio", "some prompt")
    assert provider.last_tools is None


async def test_execute_requests_web_search_tool_for_groq():
    provider = FakeProvider(response=_response())
    await execution.execute(provider, "groq", "some prompt")
    assert provider.last_tools == ["web_search"]


async def test_execute_pool_exhausted_returns_skipped_with_model_still_set():
    provider = FakeProvider(raises=PoolExhausted("google_exec"))
    fields = await execution.execute(provider, "google_ai_studio", "some prompt")
    assert fields == {"status": "skipped", "model": "gemma-4-31b-it"}


async def test_execute_other_failure_returns_failed_with_model_still_set():
    provider = FakeProvider(raises=RuntimeError("boom"))
    fields = await execution.execute(provider, "google_ai_studio", "some prompt")
    assert fields["status"] == "failed"
    assert fields["model"] == "gemma-4-31b-it"
    assert fields["error_code"] == "RuntimeError"
