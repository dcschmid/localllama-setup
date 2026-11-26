"""Persist the identifiers of replayed events."""


def checkpoint(events):
    return {"event_ids": [event["id"] for event in events]}
