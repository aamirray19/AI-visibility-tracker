import pytest

from app.core.pricing import estimate_cost_usd


def test_known_model_returns_a_float():
    cost = estimate_cost_usd("gemini-2.5-flash", tokens_in=1000, tokens_out=500)
    assert isinstance(cost, float)


def test_unknown_model_raises_instead_of_defaulting_to_zero():
    with pytest.raises(KeyError):
        estimate_cost_usd("not-a-real-model", tokens_in=1000, tokens_out=500)
