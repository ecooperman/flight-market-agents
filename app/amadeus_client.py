import time

import httpx

from app.config import settings

# Simple in-memory token cache. Amadeus tokens are shared across markets
# since auth is per-account, not per-currency/market.
_token_cache: dict = {"token": None, "expires_at": 0.0}


async def get_access_token(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["token"]

    resp = await client.post(
        f"{settings.amadeus_base_url}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.amadeus_client_id,
            "client_secret": settings.amadeus_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 1800)
    return _token_cache["token"]


async def search_flight_offers(
    client: httpx.AsyncClient,
    origin: str,
    destination: str,
    departure_date: str,
    adults: int,
    currency_code: str,
) -> dict:
    """Calls Amadeus's Flight Offers Search API for one currency/market.

    Docs: https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search
    """
    token = await get_access_token(client)
    resp = await client.get(
        f"{settings.amadeus_base_url}/v2/shopping/flight-offers",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": departure_date,
            "adults": adults,
            "currencyCode": currency_code,
            "max": 5,
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()
