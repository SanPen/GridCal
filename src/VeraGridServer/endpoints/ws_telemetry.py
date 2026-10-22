# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from VeraGridServer.endpoints.file_management import verify_api_key_header

from VeraGridServer.interactive import (
    WebSession,
    WebSessionManager,
    WebSimulationWorker,
    SimulationProgressEvent,
)

router: APIRouter = APIRouter(tags=["telemetry"])


class TelemetryQueueDispatcher:
    """
    Bridge dispatching simulation progress events from background worker threads
    into an asyncio event loop queue.
    """

    __slots__ = ("_loop", "_queue")

    def __init__(self,
                 loop: asyncio.AbstractEventLoop,
                 queue: asyncio.Queue[Dict[str, Any]]) -> None:
        """
        Construct the queue dispatcher bridge.

        :param loop: Target asyncio event loop.
        :param queue: Asyncio queue receiving event dictionaries.
        :return: None.
        """
        self._loop: asyncio.AbstractEventLoop = loop
        self._queue: asyncio.Queue[Dict[str, Any]] = queue

    def dispatch(self, event: SimulationProgressEvent) -> None:
        """
        Deliver one event safely from any worker thread into the asyncio queue.

        :param event: SimulationProgressEvent record.
        :return: None.
        """
        try:
            event_payload: Dict[str, Any] = event.to_dict()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event_payload)
        except Exception:
            pass


@router.websocket("/ws/telemetry/{session_id}")
async def websocket_telemetry_endpoint(websocket: WebSocket, session_id: str) -> None:
    """
    Stream live simulation progress events, convergence messages, and lifecycle updates over WebSocket.

    :param websocket: FastAPI WebSocket connection.
    :param session_id: Target session identifier.
    :return: None.
    """
    verify_api_key_header(api_key=websocket.headers.get("API-Key", None))
    await websocket.accept()

    manager: WebSessionManager = websocket.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        await websocket.send_json(dict({
            "error": "Session not found",
            "session_id": session_id,
        }))
        await websocket.close(code=1008)
        return None
    else:
        pass

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    dispatcher: TelemetryQueueDispatcher = TelemetryQueueDispatcher(
        loop=loop,
        queue=event_queue,
    )

    # Attach to existing worker if available
    subscribed_worker: Optional[WebSimulationWorker] = session.get_worker()
    if subscribed_worker is not None:
        subscribed_worker.add_listener(listener=dispatcher.dispatch)
    else:
        pass

    try:
        while True:
            # Check if session has a new worker we haven't subscribed to yet
            current_worker: Optional[WebSimulationWorker] = session.get_worker()
            if current_worker is not None and current_worker != subscribed_worker:
                if subscribed_worker is not None:
                    subscribed_worker.remove_listener(listener=dispatcher.dispatch)
                else:
                    pass
                subscribed_worker = current_worker
                subscribed_worker.add_listener(listener=dispatcher.dispatch)
            else:
                pass

            try:
                # Wait for next event with a short timeout to permit keepalive checks
                event_dict: Dict[str, Any] = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=1.0,
                )
                await websocket.send_json(event_dict)
            except asyncio.TimeoutError:
                # Send periodic heartbeat so client connection stays alive
                await websocket.send_json(dict({
                    "type": "heartbeat",
                    "session_id": session_id,
                }))

    except WebSocketDisconnect:
        pass
    finally:
        if subscribed_worker is not None:
            subscribed_worker.remove_listener(listener=dispatcher.dispatch)
        else:
            pass
