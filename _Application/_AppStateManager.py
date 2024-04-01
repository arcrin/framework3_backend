from _Application._SystemEvent import NewTestCaseEvent
from _Application._SystemEventBus import SystemEventBus
from _Application._SystemEvent import BaseEvent
from typing import TYPE_CHECKING, Dict, Any, List
from _Application._DomainEntity._Session import Session, ControlSession, ViewSession    
import trio
import logging

if TYPE_CHECKING:
    from trio import MemorySendChannel
    from trio_websocket import WebSocketConnection # type: ignore
    from _Node._BaseNode import BaseNode


class ApplicationStateManager:
    def __init__(self, event_bus: SystemEventBus,
                 tc_data_send_channel: "MemorySendChannel[Dict[Any, Any]]",
                 node_executor_send_channel: "MemorySendChannel[BaseNode]",
                 ui_request_send_channel: "MemorySendChannel[str]",
                 test_profile): # type: ignore
        self._app_state = {}
        self._control_context = {}
        self._app_data = {}
        self._event_bus = event_bus
        self._tc_data_send_channel = tc_data_send_channel
        self._node_executor_send_channel = node_executor_send_channel
        self._ui_request_send_channel = ui_request_send_channel 
        self._test_profile = test_profile # type: ignore
        self._event_bus.subscribe(self.event_handler)
        self._control_session: ControlSession | None = None 
        self._sessions: Dict["WebSocketConnection", Session] = {}
        self._logger = logging.getLogger("ApplicationStateManager")

    @property
    def control_session(self):  
        return self._control_session
    
    @property
    def sessions(self):
        return self._sessions
        
    def add_session(self, ws_connection: "WebSocketConnection"):
        if not self._control_session:
            new_session = ControlSession(
                ws_connection,
                self._node_executor_send_channel,
                self._ui_request_send_channel,
                self._event_bus,
                self._test_profile, # type: ignore
            ) 
            self._control_session = new_session
        else:
            new_session = ViewSession(ws_connection)
        self._sessions[ws_connection] = new_session

    def remove_session(self, ws_connection: "WebSocketConnection"):
        session = self._sessions.pop(ws_connection)
        if isinstance(session, ControlSession):
            self._control_session = None

    async def event_handler(self, event: BaseEvent):
        if isinstance(event, NewTestCaseEvent):
            self._logger.info(f"New test case added to test run {event.payload["name"]} ")
            async with trio.open_nursery() as nursery:
                nursery.start_soon(self._tc_data_send_channel.send, {"type": "tcData", "message": event.payload})
            