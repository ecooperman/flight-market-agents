import random

_AIRLINES = ["UA", "AA", "DL", "NH", "BA", "LH", "JL", "AC"]


def mock_flight_offer(base_usd_price: float = 650.0) -> dict:
    """Generates a plausible fake fare so the demo runs instantly with no
    API keys configured. The variance here is invented for demo purposes
    only -- it is NOT a claim about real observed pricing patterns.
    """
    variance = random.uniform(-0.12, 0.12)
    price_in_usd_terms = round(base_usd_price * (1 + variance), 2)
    return {
        "price_usd_terms": price_in_usd_terms,
        "airline": random.choice(_AIRLINES),
    }
