# DADA1 — Trip Planner Agent

A conversational trip-planning agent. Ask for a day in a city and it checks the weather, finds sights and food, and returns a plan with a source link for each recommendation. Refine the plan in the same chat ("make it rainy-day friendly and add dinner") and it adjusts what it already made. At the end it can export the plan as a structured JSON itinerary.

```
Deployed app: https://mandar-dada1-trip-planner.onrender.com/
```

> The free Render tier sleeps when idle, so the first request can take about 30 seconds.

## Design principle: say what you don't know

The agent uses two kinds of data source, and they fail in different ways:

| Kind | Tools | Typical failure |
|---|---|---|
| Structured APIs | Open-Meteo, Ticketmaster | A documented field comes back empty (fewer than 1 in 10 events has `priceRanges`). |
| Web search (prose) | Tavily | Snippets may be stale and never contain opening hours. |

The agent is built to report what its tools returned and nothing more.

- **No invented facts.** It does not guess opening hours, journey times, or prices.
- **Absent is not zero.** A missing price is `unknown`, and a published `0` is a seller placeholder, not "free".
- **Forecast limits.** It says so when a date is past the 16-day forecast window, and does not describe "usual" weather.
- **Ambiguous places.** Ambiguous names (Cambridge, England or Massachusetts; Portland, Oregon or Maine) get a clarifying question before any planning.
- **Sources.** Every recommendation carries the URL it came from.

## Tools

| Tool | Source | Purpose |
|---|---|---|
| `get_weather(city, date)` | [Open-Meteo](https://open-meteo.com/en/docs) | Geocodes the city, then returns the forecast for one date (16-day window). Warns when the city name is ambiguous. |
| `find_attractions(city, interest)` | Tavily | Sights, museums, parks. |
| `find_restaurants(city, budget)` | Tavily | Places to eat. |
| `find_events(city, date, category)` | [Ticketmaster Discovery](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/) | Ticketed events with real dates and venues. Uses the venue-local date filters, so a requested day means that day in the venue's time zone. |
| `get_transit_info(city)` | Tavily | General guidance on getting around, not timetables. |

Every tool returns a readable string and never raises, so the model can act on failures.

## Architecture

```
trip_planner/
├── app.py            # Gradio web UI and Render entry point
├── agentui.py        # Chat UI wrapper
└── agent/
    ├── agent.py      # create_agent + InMemorySaver memory; terminal chat loop
    ├── tools.py      # the five tools
    ├── prompts.py    # system prompt (grounding, pricing and citation rules)
    └── itinerary.py  # Pydantic models + build_itinerary (structured output)
```

- **Agent:** LangChain `create_agent` with a Gemini model (`gemini-3.5-flash-lite`). A middleware injects today's date (America/New_York) into every prompt so "tomorrow" and "this weekend" resolve to exact dates.
- **Memory:** a LangGraph `InMemorySaver` checkpointer keyed by `thread_id`, so refinements edit the existing plan.
- **Structured itinerary:** `build_itinerary` runs `with_structured_output(Itinerary)` over the conversation transcript. The model is `Itinerary → DayPlan → Activity`.
  - `Activity.cost` is a **string**, so `"unknown"` is a valid value and the model never has to make up a number.
  - `Itinerary.unknowns` lists everything the tools could not confirm, such as opening hours and unpriced items.

## Getting started

### Prerequisites

- Python 3.10+
- API keys:
  - `GOOGLE_API_KEY` — Gemini. OpenRouter or NVIDIA also work if you change the model in `agent/agent.py`.
  - `TAVILY_API_KEY` — free at [tavily.com](https://tavily.com).
  - `TICKETMASTER_API_KEY` — free at [developer.ticketmaster.com](https://developer.ticketmaster.com/products-and-docs/apis/getting-started/).
- Open-Meteo needs no key.

### Install and run

```bash
cd trip_planner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `trip_planner/.env`:

```bash
GOOGLE_API_KEY=your_key
TAVILY_API_KEY=your_key
TICKETMASTER_API_KEY=your_key
```

Run it:

```bash
python -m agent.agent    # chat in the terminal; prints the itinerary JSON on quit
python app.py            # web UI at http://127.0.0.1:7860
```

In the web UI, the **Build itinerary from this conversation** button shows the structured JSON under the chat.

> `.env` is git-ignored. Never commit API keys.

## Deployment (Render)

Deploy as a **Web Service** on the free tier:

| Setting | Value |
|---|---|
| Root Directory | `trip_planner` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python app.py` |
| Environment variables | `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `TICKETMASTER_API_KEY` |

`app.py` binds to `0.0.0.0` on Render's `$PORT`.

## Testing

[`test_prompts.md`](test_prompts.md) has the evaluation prompts. Each one lists what a good answer looks like and what a failing one looks like. They cover:

- baseline planning and refinement
- weather past the forecast window
- ambiguous cities
- opening hours and journey times, which the agent must decline to give
- cost totals and missing prices
- event date filtering and invalid categories

Run them in order against the deployed app or `python -m agent.agent`.

## Documentation

- [`DADA1_SPEC.md`](DADA1_SPEC.md) — assignment specification and required behaviors
- [`AGENTS.md`](AGENTS.md) — guidance for AI coding assistants working on this repo
- [`test_prompts.md`](test_prompts.md) — test prompts

## Tech stack

Python · LangChain · LangGraph · Gemini · Tavily · Open-Meteo · Ticketmaster Discovery API · Pydantic · Gradio · Render
