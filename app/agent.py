"""A real tool-use agent, as distinct from orchestrator.py's fixed async
fan-out. Here, Claude decides which markets are worth checking (it doesn't
have to check all of them, and can call several in parallel), reasons over
what comes back, and writes the final recommendation itself. The fan-out
underneath is the same run_market_agent() from orchestrator.py -- the model
is choosing what to feed into it, not replacing it.
"""

import asyncio
import json
from typing import AsyncGenerator

import anthropic
import httpx

from app.config import settings
from app.markets import MARKETS
from app.orchestrator import run_market_agent

TOOLS = [
    {
        "name": "search_market_price",
        "description": (
            "Prices the requested flight route in one market's currency and "
            "converts it to USD. Returns the native fare, USD-equivalent, "
            "airline, and search latency. Available markets: "
            + ", ".join(f'{m["market"]} ({m["currency"]})' for m in MARKETS)
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Market display name, e.g. 'Japan'",
                },
                "currency": {
                    "type": "string",
                    "description": "3-letter currency code, e.g. 'JPY'",
                },
            },
            "required": ["market", "currency"],
        },
    }
]

SYSTEM_PROMPT = (
    "You are a flight-pricing research agent. You have one tool, "
    "search_market_price, which prices a specific route/date in a given "
    "market's currency and converts it to USD.\n\n"
    "You do not need to check every available market. Decide which markets "
    "are actually worth checking for this route and briefly say why before "
    "calling any tools. You may call search_market_price multiple times in "
    "the same turn to check several markets in parallel. Once you have "
    "enough data, stop calling tools and write a short, direct "
    "recommendation: which market/currency came out cheapest, roughly how "
    "much it would save versus the most expensive one you checked, and any "
    "caveat worth flagging (e.g. a gap this small could just be FX "
    "movement, not a real price difference)."
)

MAX_AGENT_STEPS = 4
PLACEHOLDER_API_KEY = "your_anthropic_api_key_here"


def _recommendation_event(text: str) -> str:
    return f"event: recommendation\ndata: {json.dumps({'text': text})}\n\n"


async def run_pricing_agent(
    origin: str, destination: str, departure_date: str, adults: int
) -> AsyncGenerator[str, None]:
    """Runs the tool-use loop and yields Server-Sent Events as it goes:
    'plan' (the model's reasoning about which markets to check), unlabeled
    'data' events (one per completed market lookup, same shape as the
    non-agent endpoint), 'recommendation' (the model's final answer), then
    'done'.
    """
    if not settings.anthropic_api_key or settings.anthropic_api_key == PLACEHOLDER_API_KEY:
        yield _recommendation_event(
            "No ANTHROPIC_API_KEY set in .env -- add one to run the AI agent mode."
        )
        yield "event: done\ndata: {}\n\n"
        return

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    http_client = httpx.AsyncClient()
    market_lookup = {m["currency"]: m for m in MARKETS}

    messages = [
        {
            "role": "user",
            "content": (
                f"Route: {origin} -> {destination}, departing {departure_date}, "
                f"{adults} adult(s). Find the cheapest market to book this route in."
            ),
        }
    ]

    try:
        for step in range(MAX_AGENT_STEPS):
            try:
                response = await client.messages.create(
                    model=settings.agent_model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
            except anthropic.AuthenticationError:
                yield _recommendation_event(
                    "ANTHROPIC_API_KEY in .env was rejected (401) -- check it's a "
                    "valid, unrevoked key from console.anthropic.com."
                )
                break
            except anthropic.APIError as exc:
                yield _recommendation_event(f"Claude API error: {exc}")
                break

            plan_text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()

            tool_uses = [block for block in response.content if block.type == "tool_use"]

            if not tool_uses:
                # No further tool calls -- this text is the final answer.
                if plan_text:
                    yield f"event: recommendation\ndata: {json.dumps({'text': plan_text})}\n\n"
                break

            if plan_text:
                yield f"event: plan\ndata: {json.dumps({'text': plan_text})}\n\n"

            messages.append({"role": "assistant", "content": response.content})

            async def run_one(block):
                currency = str(block.input.get("currency", "")).upper()
                market_name = block.input.get("market", currency)
                market = market_lookup.get(currency, {"market": market_name, "currency": currency})
                result = await run_market_agent(
                    http_client, market, origin, destination, departure_date, adults
                )
                return block.id, result

            tool_runs = await asyncio.gather(*(run_one(block) for block in tool_uses))

            tool_result_blocks = []
            for tool_use_id, result in tool_runs:
                yield f"data: {result.model_dump_json()}\n\n"
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result.model_dump_json(),
                    }
                )

            messages.append({"role": "user", "content": tool_result_blocks})
        else:
            yield (
                "event: recommendation\n"
                f"data: {json.dumps({'text': f'Agent hit its {MAX_AGENT_STEPS}-step limit before finishing -- raise MAX_AGENT_STEPS in app/agent.py if needed.'})}\n\n"
            )
    finally:
        await http_client.aclose()

    yield "event: done\ndata: {}\n\n"
