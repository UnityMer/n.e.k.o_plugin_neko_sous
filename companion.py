"""Pacing for occasional conversation during a round."""
from __future__ import annotations

import random
import time
import uuid
from collections import OrderedDict, deque

FREQUENCIES = {"quiet": (60, 80, 1), "balanced": (35, 50, 2), "lively": (18, 25, 5)}


class Companion:
    def __init__(self):
        self.enabled = True
        self.frequency = "balanced"
        self._counts = OrderedDict()
        self.reset()

    def reset(self):
        self._event_times = deque()
        self._state = None
        self._round = None
        self._started = time.monotonic()
        self._updated = 0
        self._score = None
        self.defer()

    def defer(self):
        low, high, _ = FREQUENCIES[self.frequency]
        now = time.monotonic()
        while self._event_times and now - self._event_times[0] > 60:
            self._event_times.popleft()
        factor = 1 + min(len(self._event_times), 4) * .25
        self._next = now + random.uniform(low, high) * factor

    def event_spoke(self):
        self._event_times.append(time.monotonic())
        self.defer()

    def observe(self, state: dict):
        now = time.monotonic()
        round_id = state.get("round_id")
        if round_id != self._round:
            self._round = round_id
            self._started = now
            self._score = state.get("score")
            self.defer()
            if round_id:
                self._counts.setdefault(round_id, 0)
                while len(self._counts) > 32:
                    self._counts.popitem(last=False)
        self._state = dict(state)
        self._updated = now

    def candidate(self) -> dict | None:
        now = time.monotonic()
        state = self._state
        opening_delay = 20 if self.frequency == "lively" else 35
        if (not self.enabled or not state or not self._round or now - self._updated > 8
                or state.get("in_round") is not True or state.get("phase") != "playing"
                or state.get("timer_suppressed") is not False
                or now - self._started < opening_delay or now < self._next):
            return None
        remaining = state.get("remaining_seconds")
        if remaining is not None and remaining - (now - self._updated) <= 35:
            return None
        if self._counts.get(self._round, 0) >= FREQUENCIES[self.frequency][2]:
            return None
        current = state.get("score")
        change = current - self._score if type(current) is int and type(self._score) is int else None
        return {**state, "event": "companion_chat", "event_id": uuid.uuid4().hex, "score_change": change}

    def spoke(self, event: dict):
        round_id = event["round_id"]
        self._counts[round_id] = self._counts.get(round_id, 0) + 1
        self._score = event.get("score")
        self.defer()

    def status(self):
        now = time.monotonic()
        state = self._state or {}
        return {"round_id": self._round, "phase": state.get("phase"),
                "remaining_seconds": state.get("remaining_seconds"),
                "timer_suppressed": state.get("timer_suppressed"),
                "state_age_seconds": round(now - self._updated, 1) if self._updated else None,
                "round_age_seconds": round(now - self._started, 1),
                "next_in_seconds": round(max(0, self._next - now), 1),
                "count": self._counts.get(self._round, 0),
                "events_last_minute": sum(now - stamp <= 60 for stamp in self._event_times)}
