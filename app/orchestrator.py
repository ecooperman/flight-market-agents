import asyncio
import time
from typing import AsyncGenerator

import httpx

from app.amadeus_client import search_flight_offers
from app.config import settings
from app.markets import FX_TO_USD, MARKETS
from app.mock_agent import mock_flight_offer
from app.models import MarketResult


async def run_market_agent(
    client: httpx.AsyncClient,
    market: dict,
    origin: str,
    destination: str,
    departure_date: str,
    adults: int,
) -> MarketResult:
    """One 'agent': prices the same route in one market's currency.

    Each agent is independent and network-bound, which is what makes
    running them concurrently (rather than one after another) actually
    matter for latency -- see compare_all_markets / stream_market_agents.
    """
    start = time.monotonic()
    currency = market["currency"]
    fx_rate = FX_TO_USD.get(currency, 1.0)

    try:
        if settings.use_mock_data:
            # Stagger sleeps a little per-currency so a demo run visibly
            # completes agents out of order, proving they're concurrent.
            await asyncio.sleep(0.3 + (abs(hash(currency)) % 10) / 10)
            offer = mock_flight_offer()
            usd_equivalent = offer["price_usd_terms"]
            native_price = round(usd_equivalent / fx_rate, 2) if fx_rate else usd_equivalent
            airline = offer["airline"]
            source = "mock"
        else:
            data = await search_flight_offers(
                client, origin, destination, departure_date, adults, currency
            )
            offers = data.get("data", [])
            if not offers:
                raise ValueError("No offers returned for this market")
            cheapest = min(offers, key=lambda o: float(o["price"]["total"]))
            native_price = float(cheapest["price"]["total"])
            airline = cheapest["itineraries"][0]["segments"][0]["carrierCode"]
            usd_equivalent = round(native_price * fx_rate, 2)
            source = "amadeus"

        latency_ms = int((time.monotonic() - start) * 1000)
        return MarketResult(
            market=market["market"],
            currency=currency,
            native_price=round(native_price, 2),
            usd_equivalent=round(usd_equivalent, 2),
            fx_rate_to_usd=fx_rate,
            airline=airline,
            latency_ms=latency_ms,
            source=source,
            error=None,
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return MarketResult(
            market=market["market"],
            currency=currency,
            native_price=0.0,
            usd_equivalent=0.0,
            fx_rate_to_usd=fx_rate,
            airline=None,
            latency_ms=latency_ms,
            source="mock" if settings.use_mock_data else "amadeus",
            error=str(exc),
        )


async def compare_all_markets(
    origin: str, destination: str, departure_date: str, adults: int
) -> list[MarketResult]:
    """Fans out one agent per market and waits for all of them."""
    async with httpx.AsyncClient() as client:
        tasks = [
            run_market_agent(client, market, origin, destination, departure_date, adults)
            for market in MARKETS
        ]
        return await asyncio.gather(*tasks)


async def stream_market_agents(
    origin: str, destination: str, departure_date: str, adults: int
) -> AsyncGenerator[str, None]:
    """Same fan-out, but yields each agent's result the moment it finishes
    (Server-Sent Events), so the frontend can render agents completing
    out of order -- the visible proof that they ran concurrently rather
    than sequentially.
    """
    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(
                run_market_agent(client, market, origin, destination, departure_date, adults)
            )
            for market in MARKETS
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {result.model_dump_json()}\n\n"
    yield "event: done\ndata: {}\n\n"
