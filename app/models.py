from typing import Optional

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="IATA origin airport code, e.g. ORD")
    destination: str = Field(..., min_length=3, max_length=3, description="IATA destination airport code, e.g. NRT")
    departure_date: str = Field(..., description="YYYY-MM-DD")
    adults: int = Field(1, ge=1, le=9)


class MarketResult(BaseModel):
    market: str
    currency: str
    native_price: float
    usd_equivalent: float
    fx_rate_to_usd: float
    airline: Optional[str] = None
    latency_ms: int
    source: str  # "serpapi" or "mock"
    error: Optional[str] = None


class DateScanRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="IATA origin airport code, e.g. ORD")
    destination: str = Field(..., min_length=3, max_length=3, description="IATA destination airport code, e.g. NRT")
    start_date: str = Field(..., description="YYYY-MM-DD -- first departure date to check")
    days: int = Field(7, ge=1, le=21, description="How many consecutive departure dates to check")
    adults: int = Field(1, ge=1, le=9)
    currency: str = Field("USD", min_length=3, max_length=3)


class DateResult(BaseModel):
    date: str
    price: float
    currency: str
    airline: Optional[str] = None
    latency_ms: int
    source: str  # "serpapi" or "mock"
    error: Optional[str] = None
