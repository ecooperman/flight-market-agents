from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agent import run_pricing_agent
from app.models import CompareRequest
from app.orchestrator import compare_all_markets, stream_market_agents

app = FastAPI(title="Flight Market Agents Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/compare")
async def compare(req: CompareRequest):
    """Runs all market agents concurrently and returns everything at once."""
    results = await compare_all_markets(
        req.origin, req.destination, req.departure_date, req.adults
    )
    return {"results": [r.model_dump() for r in results]}


@app.get("/api/compare/stream")
async def compare_stream(origin: str, destination: str, departure_date: str, adults: int = 1):
    """Same as /api/compare, but streams each agent's result as it lands
    (Server-Sent Events) so the frontend can show them completing live."""
    return StreamingResponse(
        stream_market_agents(origin, destination, departure_date, adults),
        media_type="text/event-stream",
    )


@app.get("/api/agent/compare/stream")
async def agent_compare_stream(origin: str, destination: str, departure_date: str, adults: int = 1):
    """Real tool-use agent: Claude decides which markets to check, calls
    search_market_price for each, and writes the final recommendation
    itself -- as opposed to the fixed fan-out above."""
    return StreamingResponse(
        run_pricing_agent(origin, destination, departure_date, adults),
        media_type="text/event-stream",
    )


# Serves static/index.html and friends at the site root. Mounted last so
# it doesn't shadow the /api routes above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
