from app.services import events


def test_subscribers_receive_published_events_until_they_unsubscribe() -> None:
    received: list[tuple[str, dict]] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append((event_type, payload)))

    events.publish("record.added", {"vin": "JN8AY2NY4K9012345"})
    unsubscribe()
    events.publish("record.added", {"vin": "JTNBK3EK6N3012345"})

    assert received == [("record.added", {"vin": "JN8AY2NY4K9012345"})]


def test_a_failing_subscriber_does_not_stop_the_others() -> None:
    received: list[str] = []

    def broken(event_type: str, payload: dict) -> None:
        raise RuntimeError("websocket down")

    undo_broken = events.subscribe(broken)
    undo_ok = events.subscribe(lambda event_type, payload: received.append(event_type))
    try:
        events.publish("record.added", {})
    finally:
        undo_broken()
        undo_ok()

    assert received == ["record.added"]
