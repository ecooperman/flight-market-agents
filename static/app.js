// The page's behaviour: the market comparison (fixed fan-out and the AI agent) and the cheapest-day
// scan, all streamed over Server-Sent Events. Needs Global from shared-assets' theme.js.
//
// Rows are built with textContent, never innerHTML: names, airlines and error text come from the
// API (and, in live mode, from SerpApi), so they are never trusted as markup.

const MARKETS = [
  { market: "United States", currency: "USD" },
  { market: "Japan", currency: "JPY" },
  { market: "United Kingdom", currency: "GBP" },
  { market: "Germany", currency: "EUR" },
  { market: "India", currency: "INR" },
  { market: "Brazil", currency: "BRL" },
];

const board = document.getElementById("board");
const form = document.getElementById("search-form");
const launchBtn = document.getElementById("launch-btn");
const aiAgentBtn = document.getElementById("ai-agent-btn");
const elapsedEl = document.getElementById("elapsed");
const modeNote = document.getElementById("mode-note");
const planPanel = document.getElementById("plan-panel");
const planBody = document.getElementById("plan-body");
const recPanel = document.getElementById("rec-panel");
const recBody = document.getElementById("rec-body");

// Default the date pickers to 60 days out so a fresh page load has a sensible value without the
// user needing to think about it.
const dateInput = document.getElementById("date");
const defaultDate = new Date();
defaultDate.setDate(defaultDate.getDate() + 60);
dateInput.value = defaultDate.toISOString().slice(0, 10);

const dateScanForm = document.getElementById("date-scan-form");
const scanBtn = document.getElementById("scan-btn");
const scanStartDateInput = document.getElementById("scan-start-date");
const dateBoard = document.getElementById("date-board");
const dateElapsedEl = document.getElementById("date-elapsed");
scanStartDateInput.value = defaultDate.toISOString().slice(0, 10);

// --- one board row (a market, or a date) ---

function statusPill(kind, text) {
  return Global.el("span", { class: `status ${kind}`, text });
}

// `price` is a list of nodes for the price cell; `sub` is the small grey line under the name.
function fillRow(row, { name, sub, status, price, latency }) {
  row.replaceChildren(
    Global.el("div", {}, [Global.el("div", { class: "market-name", text: name }), sub ? Global.el("div", { class: "market-sub", text: sub }) : null]),
    Global.el("div", {}, [status]),
    Global.el("div"),
    Global.el("div", { class: "price" }, price),
    Global.el("div", { class: "latency", text: latency || "" })
  );
}

function pendingRow(id, name, sub) {
  const row = Global.el("div", { class: "row", id });
  fillRow(row, { name, sub, status: statusPill("pending", "Pending"), price: ["—"] });
  return row;
}

function markBest(row, tag) {
  if (!row) return;
  row.classList.add("best");
  row.querySelector(".price").appendChild(Global.el("span", { class: "best-tag", text: tag }));
}

// --- market comparison ---

function resetPanels() {
  planPanel.hidden = true;
  recPanel.hidden = true;
  planBody.textContent = "";
  recBody.textContent = "";
  modeNote.textContent = "";
}

function renderPendingBoard() {
  board.replaceChildren(
    ...MARKETS.map((m) => {
      const row = pendingRow(`row-${m.currency}`, m.market, m.currency);
      row.dataset.touched = "false";
      return row;
    })
  );
}

function markUntouchedAsSkipped() {
  MARKETS.forEach((m) => {
    const row = document.getElementById(`row-${m.currency}`);
    if (row && row.dataset.touched === "false") {
      row.classList.add("skipped");
      row.querySelector(".status").replaceWith(statusPill("skipped", "Skipped"));
      row.querySelector(".price").textContent = "not checked";
    }
  });
}

function renderResult(result) {
  const row = document.getElementById(`row-${result.currency}`);
  if (!row) return;
  row.classList.add("done");
  row.dataset.touched = "true";
  fillRow(row, {
    name: result.market,
    sub: `${result.currency} · ${result.source}`,
    status: result.error ? statusPill("error", "Error") : statusPill("done", "Priced"),
    price: result.error
      ? [Global.el("span", { class: "price-error", text: result.error })]
      : [
          `$${result.usd_equivalent.toFixed(0)}`,
          Global.el("span", { class: "native", text: `${result.native_price.toLocaleString()} ${result.currency} · ${result.airline ?? ""}` }),
        ],
    latency: `${result.latency_ms} ms`,
  });
}

function highlightBest(results) {
  const priced = results.filter((r) => !r.error);
  if (priced.length === 0) return;
  const best = priced.reduce((a, b) => (a.usd_equivalent < b.usd_equivalent ? a : b));
  markBest(document.getElementById(`row-${best.currency}`), "BEST FARE");
}

function readInputs() {
  const origin = document.getElementById("origin").value.trim().toUpperCase();
  const destination = document.getElementById("destination").value.trim().toUpperCase();
  const departureDate = dateInput.value;
  const adults = document.getElementById("adults").value || 1;
  if (origin.length !== 3 || destination.length !== 3 || !departureDate) {
    Global.showMessage("Enter a 3-letter origin and destination, plus a departure date.", "error");
    return null;
  }
  return { origin, destination, departureDate, adults };
}

function setButtonsDisabled(disabled) {
  launchBtn.disabled = disabled;
  aiAgentBtn.disabled = disabled;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const inputs = readInputs();
  if (!inputs) return;
  const { origin, destination, departureDate, adults } = inputs;

  resetPanels();
  modeNote.textContent = "Fixed fan-out: every market below is always queried, in a hardcoded loop.";
  renderPendingBoard();
  setButtonsDisabled(true);
  launchBtn.textContent = "Agents running…";
  const startedAt = performance.now();
  elapsedEl.textContent = "";

  const params = new URLSearchParams({ origin, destination, departure_date: departureDate, adults });
  const source = new EventSource(`/api/compare/stream?${params.toString()}`);
  const results = [];

  source.onmessage = (event) => {
    const result = JSON.parse(event.data);
    results.push(result);
    renderResult(result);
  };

  source.addEventListener("done", () => {
    source.close();
    setButtonsDisabled(false);
    launchBtn.textContent = "Run concurrent agents";
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    elapsedEl.textContent = `All ${MARKETS.length} agents settled in ${elapsed}s`;
    highlightBest(results);
  });

  source.onerror = () => {
    source.close();
    setButtonsDisabled(false);
    launchBtn.textContent = "Run concurrent agents";
  };
});

aiAgentBtn.addEventListener("click", () => {
  const inputs = readInputs();
  if (!inputs) return;
  const { origin, destination, departureDate, adults } = inputs;

  resetPanels();
  modeNote.textContent = "AI agent mode: Claude decides which markets below are worth checking, then writes the recommendation itself.";
  renderPendingBoard();
  setButtonsDisabled(true);
  aiAgentBtn.textContent = "Agent thinking…";
  const startedAt = performance.now();
  elapsedEl.textContent = "";

  const params = new URLSearchParams({ origin, destination, departure_date: departureDate, adults });
  const source = new EventSource(`/api/agent/compare/stream?${params.toString()}`);
  const results = [];

  source.addEventListener("plan", (event) => {
    const { text } = JSON.parse(event.data);
    planPanel.hidden = false;
    planBody.textContent += (planBody.textContent ? "\n\n" : "") + text;
  });

  source.onmessage = (event) => {
    const result = JSON.parse(event.data);
    results.push(result);
    renderResult(result);
  };

  source.addEventListener("recommendation", (event) => {
    const { text } = JSON.parse(event.data);
    recPanel.hidden = false;
    recBody.textContent = text;
  });

  source.addEventListener("done", () => {
    source.close();
    setButtonsDisabled(false);
    aiAgentBtn.textContent = "Run AI agent";
    markUntouchedAsSkipped();
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    elapsedEl.textContent = `Agent finished in ${elapsed}s`;
    if (results.length > 0) highlightBest(results);
  });

  source.onerror = () => {
    source.close();
    setButtonsDisabled(false);
    aiAgentBtn.textContent = "Run AI agent";
  };
});

// --- cheapest day to fly ---

function renderDatePendingBoard(dates) {
  dateBoard.replaceChildren(...dates.map((date) => pendingRow(`date-row-${date}`, date)));
}

function renderDateResult(result) {
  const row = document.getElementById(`date-row-${result.date}`);
  if (!row) return;
  row.classList.add("done");
  fillRow(row, {
    name: result.date,
    status: result.error ? statusPill("error", "Error") : statusPill("done", "Priced"),
    price: result.error
      ? [Global.el("span", { class: "price-error", text: result.error })]
      : [
          `${result.price.toLocaleString()} ${result.currency}`,
          Global.el("span", { class: "native", text: `${result.airline ?? ""} · ${result.source}` }),
        ],
    latency: `${result.latency_ms} ms`,
  });
}

function highlightBestDate(results) {
  const priced = results.filter((r) => !r.error);
  if (priced.length === 0) return;
  const best = priced.reduce((a, b) => (a.price < b.price ? a : b));
  markBest(document.getElementById(`date-row-${best.date}`), "CHEAPEST DAY");
}

dateScanForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const origin = document.getElementById("origin").value.trim().toUpperCase();
  const destination = document.getElementById("destination").value.trim().toUpperCase();
  const adults = document.getElementById("adults").value || 1;
  const currency = document.getElementById("scan-currency").value.trim().toUpperCase() || "USD";
  const startDate = scanStartDateInput.value;
  const days = document.getElementById("scan-days").value || 7;

  if (origin.length !== 3 || destination.length !== 3 || !startDate) {
    Global.showMessage("Enter a 3-letter origin/destination (above) and a start date.", "error");
    return;
  }

  const dates = [];
  const cursor = new Date(startDate + "T00:00:00");
  for (let i = 0; i < days; i++) {
    dates.push(new Date(cursor.getTime() + i * 86400000).toISOString().slice(0, 10));
  }

  renderDatePendingBoard(dates);
  scanBtn.disabled = true;
  scanBtn.textContent = "Scanning…";
  const startedAt = performance.now();
  dateElapsedEl.textContent = "";

  const params = new URLSearchParams({ origin, destination, start_date: startDate, days, adults, currency });
  const source = new EventSource(`/api/dates/scan/stream?${params.toString()}`);
  const results = [];

  source.onmessage = (event) => {
    const result = JSON.parse(event.data);
    results.push(result);
    renderDateResult(result);
  };

  source.addEventListener("done", () => {
    source.close();
    scanBtn.disabled = false;
    scanBtn.textContent = "Scan date range";
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    dateElapsedEl.textContent = `All ${dates.length} dates settled in ${elapsed}s`;
    highlightBestDate(results);
  });

  source.onerror = () => {
    source.close();
    scanBtn.disabled = false;
    scanBtn.textContent = "Scan date range";
  };
});

renderPendingBoard();
