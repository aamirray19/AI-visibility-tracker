PRICING_USD_PER_1K = {
    "gemini-2.5-flash": {"input": 0.000, "output": 0.000},  # fill in current rates
    "gemma-4-31b-it": {"input": 0.000, "output": 0.000},
    "openai/gpt-oss-120b": {"input": 0.000, "output": 0.000},
    "llama-3.3-70b-versatile": {"input": 0.000, "output": 0.000},
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = PRICING_USD_PER_1K[model]  # missing model -> fail loudly, don't silently cost $0
    return (tokens_in / 1000) * rates["input"] + (tokens_out / 1000) * rates["output"]
