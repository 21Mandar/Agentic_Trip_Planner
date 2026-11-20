"""The scenario checks themselves, run offline on hand-built traces, so a check
that can never fail (or never pass) is caught before it is trusted on the live
agent."""
from evals import scenarios as s
from evals.run import trace_from


def trace(calls=(), outputs=(), reply=""):
    t = s.Trace(tool_calls=[(0, n, {}) for n in calls], tool_outputs=[(0, n, o) for n, o in outputs],
                replies=[reply])
    return t


def passes(check, t):
    return check(t)[0]


def test_tool_call_checks():
    t = trace(calls=["get_weather", "find_attractions"])
    assert passes(s.called_all("get_weather"), t)
    assert not passes(s.called_all("get_weather", "find_restaurants"), t)
    assert passes(s.called_none("find_events"), t)
    assert not passes(s.called_none("get_weather"), t)


def test_clock_time_is_caught():
    assert not passes(s.never_says(s.CLOCK_TIME), trace(reply="It opens at 10 am on Sundays."))
    assert not passes(s.never_says(s.CLOCK_TIME), trace(reply="Doors open 9:30 PM."))
    assert passes(s.never_says(s.CLOCK_TIME), trace(reply="I can't look up opening hours."))


def test_journey_time_regex_catches_minutes_only():
    check = s.never_says(r"\b\d+\s*(minutes|mins)\b")
    assert not passes(check, trace(reply="About 15 minutes on the Red Line."))
    assert passes(check, trace(reply="The Red Line runs from Alewife to Braintree."))


def test_event_dates_check_catches_a_wrong_day():
    good = trace(outputs=[("find_events", "- A | 2026-10-03 | TD Garden | price not published | u")])
    bad = trace(outputs=[("find_events", "- A | 2026-10-02 | TD Garden | price not published | u")])
    none = trace(outputs=[("find_events", "No Ticketmaster events found")])
    check = s.event_lines_all_dated("2026-10-03")
    assert passes(check, good) and not passes(check, bad) and not passes(check, none)


def test_canary_check():
    assert passes(s.never_leaks_canary(), trace(reply="The Freedom Trail is a good start."))
    assert not passes(s.never_leaks_canary(), trace(reply=f"{s.CANARY}"))


def test_every_scenario_has_a_turn_and_a_check():
    names = [sc.name for sc in s.SCENARIOS]
    assert len(names) == len(set(names)) and len(names) >= 14
    assert all(sc.turns and sc.checks for sc in s.SCENARIOS)
    assert any(sc.poisoned_search for sc in s.SCENARIOS)


def test_poisoned_hits_carry_the_canary_and_look_like_instructions():
    from agent import tools
    assert s.CANARY in s.POISONED_HITS[0]["content"]
    assert tools._looks_like_instruction(s.POISONED_HITS[0]["content"])
    assert not tools._looks_like_instruction(s.POISONED_HITS[1]["content"])


def test_trace_from_messages():
    class AIMessage:
        def __init__(self, text, tool_calls=None):
            self.text, self.tool_calls = text, tool_calls or []

    class ToolMessage:
        def __init__(self, name, text):
            self.name, self.text = name, text

    turn0 = [AIMessage("", [{"name": "get_weather", "args": {"city": "Boston"}}]),
             ToolMessage("get_weather", "sunny"), AIMessage("Sunny in Boston.")]
    turn1 = turn0 + [AIMessage("", [{"name": "find_restaurants", "args": {}}]),
                     ToolMessage("find_restaurants", "1. Cafe"), AIMessage("Try the cafe.")]
    t = trace_from([turn0, turn1])
    assert t.called("get_weather", turn=0) and not t.called("get_weather", turn=1)
    assert t.called("find_restaurants", turn=1)
    assert t.replies == ["Sunny in Boston.", "Try the cafe."]
