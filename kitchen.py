"""Keep short kitchen reminders relevant to the objects that triggered them."""
from __future__ import annotations

import math
from time import monotonic

KITCHEN_EVENTS = {"fire_started": "fire", "food_ready": "ready", "food_overcooking": "overcooking"}


def valid_object(item: dict, *, fire=False) -> bool:
    if not isinstance(item, dict) or type(item.get("object_id")) is not int:
        return False
    if type(item.get("cycle")) is not int or item["cycle"] < 0:
        return False
    if fire:
        return type(item.get("on_fire")) is bool
    if type(item.get("on_heat")) is not bool:
        return False
    if not isinstance(item.get("cooking_state"), str) or item["cooking_state"] not in {"idle", "progressing", "completed", "overdoing", "ruined"}:
        return False
    for key in ("cooking_progress", "cooking_time", "progress_ratio"):
        value = item.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return False
    return item["cooking_time"] > 0


class KitchenFeedback:
    def __init__(self):
        self.enabled = dict.fromkeys(KITCHEN_EVENTS.values(), True)
        self.clear()

    def clear(self):
        self._pending = {}

    def configure(self, enabled):
        self.enabled = dict(enabled)
        self._pending = {key: item for key, item in self._pending.items()
                         if self.enabled[KITCHEN_EVENTS[item[1]["event"]]]}

    def add(self, event):
        name = event["event"]
        if not self.enabled[KITCHEN_EVENTS[name]]:
            return
        if name == "food_overcooking":
            self._pending.pop(("food_ready", event["object_id"], event["cycle"]), None)
        key = (name, event["object_id"], event["cycle"])
        self._pending.setdefault(key, (monotonic(), dict(event)))

    def update_state(self, state):
        for key, (_, event) in list(self._pending.items()):
            if state.get("round_id") != event["round_id"] or state.get("in_round") is not True:
                self._pending.pop(key, None)
                continue
            fire = event["event"] == "fire_started"
            collection = "fires" if fire else "cooking"
            if collection not in state:
                continue
            objects = state[collection]
            if not isinstance(objects, list) or any(not valid_object(item, fire=fire) for item in objects):
                continue
            current = next((item for item in objects if item["object_id"] == event["object_id"]), None)
            if current is None:
                self._pending.pop(key, None)
                continue
            if current["cycle"] < event["cycle"]:
                continue
            if current["cycle"] == event["cycle"] and not fire:
                if current["cooking_progress"] + .01 < event["cooking_progress"]:
                    continue  # A snapshot queued before this event is not a cancellation.
            relevant = current["cycle"] == event["cycle"]
            if fire:
                relevant = relevant and current["on_fire"]
            else:
                expected = "overdoing" if event["event"] == "food_overcooking" else "completed"
                relevant = relevant and current["on_heat"] and current["cooking_state"] == expected
            if not relevant:
                self._pending.pop(key, None)

    def has_urgent(self):
        self._prune()
        return any(event["event"] != "food_ready" for _, event in self._pending.values())

    def has_pending(self):
        self._prune()
        return bool(self._pending)

    def _prune(self):
        now = monotonic()
        self._pending = {key: item for key, item in self._pending.items()
                         if now - item[0] <= (5 if item[1]["event"] == "food_ready" else 2)}

    def pop(self, *, urgent):
        self._prune()
        now = monotonic()
        for name in (("fire_started", "food_overcooking") if urgent else ("food_ready",)):
            group = [(key, received, event) for key, (received, event) in self._pending.items()
                     if event["event"] == name]
            if not group or not any(now - received >= (.3 if urgent else .8) for _, received, _ in group):
                continue
            items = [(key, event) for key, _, event in group]
            for key, _ in items:
                self._pending.pop(key)
            return dict(items[0][1], kitchen_count=len(items))
        return None
