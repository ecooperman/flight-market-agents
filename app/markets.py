# The set of "market agents" this demo spins up concurrently.
# Each one queries the same route/date but prices it in a different
# currency via SerpApi's Google Flights `currency` parameter. This shows
# real, legitimate currency-driven pricing differences -- it does NOT spoof
# the requester's country or location. See README.md for why, and for an
# open caveat on how much of the difference is genuine currency-of-sale
# pricing vs. simple FX conversion.
MARKETS = [
    {"market": "United States", "currency": "USD"},
    {"market": "Japan", "currency": "JPY"},
    {"market": "United Kingdom", "currency": "GBP"},
    {"market": "Germany", "currency": "EUR"},
    {"market": "India", "currency": "INR"},
    {"market": "Brazil", "currency": "BRL"},
]

# Static, approximate FX rates to USD, for converting each market's
# native fare into a comparable number. These are illustrative demo
# values, not live rates -- swap in a live FX API (e.g. exchangerate.host,
# open.er-api.com) before relying on this for anything real.
FX_TO_USD = {
    "USD": 1.0,
    "JPY": 1 / 155.0,
    "GBP": 1.27,
    "EUR": 1.08,
    "INR": 1 / 83.5,
    "BRL": 1 / 5.4,
}
