import asyncio
import datetime
import time
from typing import AsyncGenerator

import httpx

from app.config import settings
from app.markets import FX_TO_USD, MARKETS
from app.mock_agent import mock_flight_offer
from app.models import DateResult, MarketResult
from app.serpapi_client import cheapest_itinerary, search_flights


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
            data = await search_flights(
                client, origin, destination, departure_date, adults, currency
            )
            cheapest = cheapest_itinerary(data)
            if cheapest is None:
                raise ValueError("No offers returned for this market")
            native_price = float(cheapest["price"])
            airline = cheapest["flights"][0]["airline"] if cheapest.get("flights") else None
            usd_equivalent = round(native_price * fx_rate, 2)
            source = "serpapi"

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
            source="mock" if settings.use_mock_data else "serpapi",
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


async def run_date_agent(
    client: httpx.AsyncClient,
    date: str,
    origin: str,
    destination: str,
    adults: int,
    currency: str,
) -> DateResult:
    """One 'agent': prices the same route/currency on one candidate
    departure date. Fanning these out concurrently across a date range is
    what answers "what's the cheapest day to fly" -- see scan_dates_stream.
    """
    start = time.monotonic()

    try:
        if settings.use_mock_data:
            await asyncio.sleep(0.3 + (abs(hash(date)) % 10) / 10)
            offer = mock_flight_offer()
            price = offer["price_usd_terms"]
            airline = offer["airline"]
            source = "mock"
        else:
            data = await search_flights(client, origin, destination, date, adults, currency)
            cheapest = cheapest_itinerary(data)
            if cheapest is None:
                raise ValueError("No offers returned for this date")
            price = float(cheapest["price"])
            airline = cheapest["flights"][0]["airline"] if cheapest.get("flights") else None
            source = "serpapi"

        latency_ms = int((time.monotonic() - start) * 1000)
        return DateResult(
            date=date,
            price=round(price, 2),
            currency=currency,
            airline=airline,
            latency_ms=latency_ms,
            source=source,
            error=None,
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return DateResult(
            date=date,
            price=0.0,
            currency=currency,
            airline=None,
            latency_ms=latency_ms,
            source="mock" if settings.use_mock_data else "serpapi",
            error=str(exc),
        )


def _date_range(start_date: str, days: int) -> list[str]:
    start = datetime.date.fromisoformat(start_date)
    return [(start + datetime.timedelta(days=i)).isoformat() for i in range(days)]


async def scan_dates_stream(
    origin: str, destination: str, start_date: str, days: int, adults: int, currency: str
) -> AsyncGenerator[str, None]:
    """Fans out one agent per candidate departure date and streams each
    result as it lands (Server-Sent Events), same pattern as
    stream_market_agents but scanning across dates instead of currencies.
    """
    dates = _date_range(start_date, days)
    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(run_date_agent(client, date, origin, destination, adults, currency))
            for date in dates
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {result.model_dump_json()}\n\n"
    yield "event: done\ndata: {}\n\n"
