from typing import Optional

import httpx

from app.config import settings

SERPAPI_URL = "https://serpapi.com/search"


async def search_flights(
    client: httpx.AsyncClient,
    origin: str,
    destination: str,
    departure_date: str,
    adults: int,
    currency: str = "USD",
) -> dict:
    """Calls SerpApi's Google Flights engine for one route/date/currency.

    One-way search (type=2) -- this app never asks for a return date. Docs:
    https://serpapi.com/google-flights-api
    """
    resp = await client.get(
        SERPAPI_URL,
        params={
            "engine": "google_flights",
            "api_key": settings.serpapi_key,
            "departure_id": origin.upper(),
            "arrival_id": destination.upper(),
            "outbound_date": departure_date,
            "type": 2,  # one-way
            "adults": adults,
            "currency": currency,
            "hl": "en",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        # SerpApi returns HTTP 200 with an "error" field for bad params
        # (e.g. unrecognized airport code) rather than a 4xx status.
        raise ValueError(data["error"])
    return data


def cheapest_itinerary(data: dict) -> Optional[dict]:
    """Picks the lowest-priced itinerary out of best_flights + other_flights.

    Each entry represents a full itinerary (possibly multi-leg); its
    top-level "price" is the total for the trip, and "flights" is the list
    of individual legs.
    """
    candidates = data.get("best_flights", []) + data.get("other_flights", [])
    if not candidates:
        return None
    return min(candidates, key=lambda c: c["price"])
