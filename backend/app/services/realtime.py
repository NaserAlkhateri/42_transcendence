"""One pub/sub reader per API process, with bounded per-socket queues and indexed delivery."""

import asyncio
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

import redis.asyncio
from redis.asyncio.retry import Retry as AsyncRetry
from pydantic import BaseModel, StringConstraints, ValidationError
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from app.services import events

logger = logging.getLogger(__name__)
CHANNEL = "sijil:realtime:v1"
VIN_PATTERN = r"^[A-HJ-NPR-Z0-9]{17}$"
Vin = Annotated[str, StringConstraints(pattern=VIN_PATTERN)]
MAX_SUBSCRIPTIONS = 20
HEARTBEAT_SECONDS = 25


class RecordAdded(BaseModel):
    vin: Vin
    record_id: UUID
    service_date: date
    is_mileage_flagged: bool
    corrects_record_id: UUID | None


class NotificationCreated(BaseModel):
    notification_id: UUID
    event_type: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    created_at: datetime


def frame(kind: str, data: dict, request_id: str | None = None) -> dict:
    result = {"v": 1, "id": str(uuid4()), "type": kind, "occurred_at": datetime.now(UTC).isoformat(), "data": data}
    if request_id is not None:
        result["request_id"] = request_id
    return result


class Publication(BaseModel):
    type: Literal["record.added", "notification.created", "notification.read_state_changed"]
    data: dict
    recipient: UUID | None = None

    def public_data(self) -> dict:
        if self.type == "notification.read_state_changed":
            return {}
        model = RecordAdded if self.type == "record.added" else NotificationCreated
        return model.model_validate(self.data).model_dump(mode="json")


@dataclass(eq=False)
class Peer:
    user_id: UUID
    vins: set[str] = field(default_factory=set)
    outbound: asyncio.Queue[dict | int] = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    closed: bool = False

    def close(self, code: int) -> None:
        if not self.closed:
            self.closed = True
            while not self.outbound.empty():
                self.outbound.get_nowait()
            self.outbound.put_nowait(code)


class RealtimeHub:
    def __init__(self, *, available: bool = True):
        self.available = available
        self.by_user: defaultdict[UUID, set[Peer]] = defaultdict(set)
        self.by_vin: defaultdict[str, set[Peer]] = defaultdict(set)

    def attach(self, user_id: UUID) -> Peer:
        peer = Peer(user_id)
        self.by_user[user_id].add(peer)
        return peer

    def watch(self, peer: Peer, vin: str) -> None:
        peer.vins.add(vin)
        self.by_vin[vin].add(peer)

    def unwatch(self, peer: Peer, vin: str) -> None:
        if vin in peer.vins:
            peer.vins.remove(vin)
            self.by_vin[vin].discard(peer)
            if not self.by_vin[vin]:
                del self.by_vin[vin]

    def detach(self, peer: Peer) -> None:
        for vin in tuple(peer.vins):
            self.unwatch(peer, vin)
        self.by_user[peer.user_id].discard(peer)
        if not self.by_user[peer.user_id]:
            del self.by_user[peer.user_id]

    def disconnect(self) -> None:
        self.available = False
        self.reset_peers()

    def reset_peers(self) -> None:
        for peers in self.by_user.values():
            for peer in peers:
                peer.close(1012)

    def deliver(self, event: Publication) -> None:
        data = event.public_data()  # allowlist payload fields, including those read from Redis
        peers = self.by_vin.get(data["vin"], ()) if event.type == "record.added" else self.by_user.get(event.recipient, ())
        if not peers:
            return
        message = frame(event.type, data)
        for peer in peers:
            if not peer.closed:
                try:
                    peer.outbound.put_nowait(message)
                except asyncio.QueueFull:
                    peer.close(1013)  # refetch after reconnect instead of holding an unbounded backlog


async def listen(hub: RealtimeHub, client: redis.asyncio.Redis) -> None:
    while True:
        try:
            async with client.pubsub() as subscription:
                await subscription.subscribe(CHANNEL)
                ready = await subscription.get_message(timeout=5)
                if not ready or ready["type"] != "subscribe":
                    raise RedisError("No realtime subscription acknowledgement")
                hub.available = True
                async for message in subscription.listen():
                    if message["type"] == "message":
                        try:
                            hub.deliver(Publication.model_validate_json(message["data"]))
                        except ValidationError:
                            logger.warning("Discarded an invalid realtime event")
                raise RedisError("Realtime subscription ended")
        except (RedisError, OSError):
            logger.warning("Redis realtime subscription interrupted; reconnecting")
            hub.disconnect()
            await asyncio.sleep(1)


async def publish_queued(hub: RealtimeHub, client: redis.asyncio.Redis, queue: asyncio.Queue[Publication]) -> None:
    while True:
        first = await queue.get()
        batch = [first]
        while len(batch) < 128 and not queue.empty():
            batch.append(queue.get_nowait())
        try:
            async with client.pipeline(transaction=False) as pipe:
                for event in batch:
                    pipe.publish(CHANNEL, event.model_dump_json())
                await pipe.execute()
        except (RedisError, OSError):
            logger.warning("Could not publish realtime invalidations; REST state is still committed")
            hub.reset_peers()


@asynccontextmanager
async def realtime(relay_url: str | None):
    loop = asyncio.get_running_loop()
    hub = RealtimeHub(available=relay_url is None)
    publisher = redis.asyncio.Redis.from_url(relay_url, socket_connect_timeout=1, socket_timeout=1,
                                            retry=AsyncRetry(NoBackoff(), 0)) if relay_url else None
    # Pub/Sub reads may idle indefinitely. A failed connection forces a new subscription and client resync.
    reader = redis.asyncio.Redis.from_url(relay_url, socket_connect_timeout=2,
                                           retry=AsyncRetry(NoBackoff(), 0)) if relay_url else None
    listener = asyncio.create_task(listen(hub, reader)) if reader is not None else None
    queue: asyncio.Queue[Publication] = asyncio.Queue(maxsize=4096)
    writer = asyncio.create_task(publish_queued(hub, publisher, queue)) if publisher is not None else None

    def enqueue(event: Publication) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            hub.reset_peers()

    def forward(kind: str, payload: dict) -> None:
        if kind not in ("record.added", "notification.created", "notification.read_state_changed"):
            return
        event = Publication(type=kind, data=payload, recipient=payload.get("user_id") if kind != "record.added" else None)
        event.data = event.public_data()
        if publisher is None:
            loop.call_soon_threadsafe(hub.deliver, event)
            return
        loop.call_soon_threadsafe(enqueue, event)

    unsubscribe = events.subscribe(forward)
    try:
        yield hub
    finally:
        unsubscribe()
        for task in (listener, writer):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        if reader is not None:
            await reader.aclose()
        if publisher is not None:
            await publisher.aclose()
