"""Trip planner: the structured itinerary.

To be used to extract one typed itinerary from the conversation.

Please note `cost` is a STRING, not a number, so that
"unknown" is something the itinerary can actually say, and so a price can carry
where it came from. If it were a float the model would have to invent a figure
to fill it, and a made-up price looks exactly like a real one.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Activity(BaseModel):
    """One thing the traveller does."""
    time: str = Field(description="When it starts, e.g. '09:30' or 'morning'")
    name: str = Field(description="What it is, e.g. 'Museum of Fine Arts'")
    kind: Literal["sight", "food", "event", "travel", "other"] = Field(
        description="Which tool this came from: sight, food, event, travel, other")
    cost: str = Field(
        description="'free' only when something actually says it is free; a price "
                    "a tool gave you, marked with where it came from, like "
                    "'$45-120 (Ticketmaster)' or '$27 (blog, unconfirmed)'; or "
                    "'unknown'. Most things will be 'unknown' — that is the honest "
                    "answer, and an unknown price is never 0.")
    source: str = Field(description="The URL this came from, or 'none' if there isn't one")


# TODO: write DayPlan. One day of the trip: a date, what the weather said, and a
# list of Activity. An itinerary is a list of days, each holding a list of
# activities — one level more nesting than W03a.2.
class DayPlan(BaseModel):
    """One day of the trip."""
    date: str = Field(
        description="The calendar date of this day as YYYY-MM-DD, "
                    "taken from the conversation. Never 'tomorrow'.")
    weather: str = Field(
        description="The forecast the weather tool actually returned "
                    "for this date, in one short line. If the tool "
                    "found no forecast, write 'not available'. Never "
                    "fill this in from what the season is usually like.")
    activities: list[Activity] = Field(
        description="Every activity planned for this day, in order, taken from the "
                    "conversation. Do not invent activities. If the order is unclear, "
                    "any order is fine. If the time is unclear, write 'unknown' in the time field."
                    "Copy each item's source URL and price exactly as the tools reported them; use 'unknown' when no price was given.")

class Itinerary(BaseModel):
    """A complete plan for a trip."""
    city: str = Field(description="The city the trip is to, as given in the conversation. Never 'the city' or 'the destination'.")
    days: list[DayPlan] = Field(description="The list of days in the trip, in order. Each day has a date, weather, and a list of activities.")
    unknowns: list[str] = Field(
        description="Everything the tools could not confirm, one short item each: "
                "opening hours (no tool returns them), prices marked 'unknown', "
                "journey times, anything the traveller asked about that nobody "
                "looked up. An empty list means you are sure nothing is missing, "
                "which is rarely true.")



ITINERARIES = []


def build_itinerary(model, result) -> Itinerary:
    """Extract a structured itinerary from a finished planning conversation.

    This is `file_ticket` from W03b.1 pointed at a trip. Build the transcript from
    result["messages"], call model.with_structured_output(Itinerary) on it, append
    to ITINERARIES, and return it.
    """
    transcript = "\n".join(
        f"{type(m).__name__}: {m.text}" for m in result["messages"] if m.text
    )
    itinerary = model.with_structured_output(Itinerary).invoke(
        f"Create an itinerary from this trip-planning conversation. Use only "
        f"what the conversation says; do not add anything it does not:\n\n{transcript}")
    ITINERARIES.append(itinerary)
    return itinerary
