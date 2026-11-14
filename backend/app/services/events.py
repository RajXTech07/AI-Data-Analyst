import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID
from app.core.logging import logger
from app.schemas.events import Event

class EventBus:
    def __init__(self):
        # Maps analysis_id -> set of subscriber queues
        self._subscribers: dict[UUID, set[asyncio.Queue[Event | None]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, analysis_id: UUID) -> AsyncGenerator[Event, None]:
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        async with self._lock:
            if analysis_id not in self._subscribers:
                self._subscribers[analysis_id] = set()
            self._subscribers[analysis_id].add(queue)

        try:
            while True:
                item = await queue.get()
                if item is None:  # Sentinel value signaling end of stream
                    break
                yield item
        finally:
            async with self._lock:
                if analysis_id in self._subscribers:
                    self._subscribers[analysis_id].discard(queue)
                    if not self._subscribers[analysis_id]:
                        del self._subscribers[analysis_id]

    async def publish(self, analysis_id: UUID, event_type: str, data: dict[str, Any]) -> None:
        event = Event(event=event_type, data=data)  # type: ignore
        async with self._lock:
            queues = list(self._subscribers.get(analysis_id, []))

        for q in queues:
            await q.put(event)

    async def close(self, analysis_id: UUID) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(analysis_id, []))

        for q in queues:
            await q.put(None)

event_bus = EventBus()
