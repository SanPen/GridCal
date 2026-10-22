# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import time
import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Callable

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import SimulationTypes
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.driver_handler import create_driver
from VeraGridEngine.Simulations.types import DRIVER_OBJECTS, RESULTS_OBJECTS


class SimulationStatus(str, Enum):
    """
    Lifecycle status of a simulation running on a web session.
    """
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SimulationProgressEvent:
    """
    Event record emitted whenever the simulation progresses or changes state.
    """

    __slots__ = (
        "session_id",
        "progress",
        "message",
        "status",
        "timestamp",
    )

    def __init__(self,
                 session_id: str,
                 progress: float,
                 message: str,
                 status: SimulationStatus,
                 timestamp: str) -> None:
        """
        Build one progress event.

        :param session_id: Session identifier.
        :param progress: Progress percentage in range [0.0, 100.0].
        :param message: Informational message from simulation.
        :param status: Current lifecycle status.
        :param timestamp: ISO format timestamp string.
        :return: None.
        """
        self.session_id: str = session_id
        self.progress: float = progress
        self.message: str = message
        self.status: SimulationStatus = status
        self.timestamp: str = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the event to a JSON-serializable dictionary.

        :return: Dictionary with event payload.
        """
        return dict({
            "session_id": self.session_id,
            "progress": self.progress,
            "message": self.message,
            "status": str(self.status.value),
            "timestamp": self.timestamp,
        })


class WebProgressSignal:
    """
    Callback signal adapter matching DriverTemplate's progress_signal and progress_text interface.
    """

    __slots__ = ("_callback",)

    def __init__(self, callback: Callable[[Any], None]) -> None:
        """
        Construct the signal adapter.

        :param callback: Target function to receive emitted values.
        :return: None.
        """
        self._callback: Callable[[Any], None] = callback

    def emit(self, val: Any = "") -> None:
        """
        Emit a value by forwarding it to the target callback.

        :param val: Emitted numerical or string progress payload.
        :return: None.
        """
        # Forward value safely to the consumer
        self._callback(val)


class WebSimulationWorker:
    """
    Thread-safe runner executing any VeraGridEngine DriverTemplate in a background thread.
    """

    __slots__ = (
        "_session_id",
        "_driver",
        "_status",
        "_progress",
        "_message",
        "_thread",
        "_failed",
        "_cancelled",
        "_results",
        "_listeners",
        "_lock",
        "_start_time",
        "_end_time",
        "_error_message",
    )

    def __init__(self, session_id: str, driver: DRIVER_OBJECTS) -> None:
        """
        Build one worker for a simulation driver.

        :param session_id: Owning session identifier.
        :param driver: DriverTemplate instance to execute.
        :return: None.
        """
        self._session_id: str = session_id
        self._driver: DRIVER_OBJECTS = driver
        self._status: SimulationStatus = SimulationStatus.IDLE
        self._progress: float = 0.0
        self._message: str = "Ready"
        self._thread: Optional[threading.Thread] = None
        self._failed: bool = False
        self._cancelled: bool = False
        self._results: Optional[RESULTS_OBJECTS] = None
        self._listeners: List[Callable[[SimulationProgressEvent], None]] = list()
        self._lock: threading.Lock = threading.Lock()
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._error_message: str = ""

        # Connect driver progress hooks to worker callbacks
        self._driver.progress_signal = WebProgressSignal(callback=self._on_progress_value)
        self._driver.progress_text = WebProgressSignal(callback=self._on_progress_text)

    def get_status(self) -> SimulationStatus:
        """
        Get the current execution status.

        :return: SimulationStatus enumeration member.
        """
        with self._lock:
            return self._status

    def get_progress(self) -> float:
        """
        Get the current progress value.

        :return: Float between 0.0 and 100.0.
        """
        with self._lock:
            return self._progress

    def get_message(self) -> str:
        """
        Get the latest progress text message.

        :return: Progress text string.
        """
        with self._lock:
            return self._message

    def get_results(self) -> Optional[RESULTS_OBJECTS]:
        """
        Get the simulation results if available.

        :return: Driver results object or None.
        """
        with self._lock:
            return self._results

    def get_error_message(self) -> str:
        """
        Get the error message if execution failed.

        :return: Error message string.
        """
        with self._lock:
            return self._error_message

    def is_running(self) -> bool:
        """
        Check if the worker thread is currently running.

        :return: True if actively executing, False otherwise.
        """
        with self._lock:
            if self._status == SimulationStatus.RUNNING:
                return True
            else:
                return False

    def add_listener(self, listener: Callable[[SimulationProgressEvent], None]) -> None:
        """
        Register a progress event listener.

        :param listener: Callable receiving SimulationProgressEvent.
        :return: None.
        """
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[SimulationProgressEvent], None]) -> None:
        """
        Remove a registered progress event listener.

        :param listener: Previously registered listener callable.
        :return: None.
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
            else:
                pass

    def _notify_listeners(self, event: SimulationProgressEvent) -> None:
        """
        Dispatch one event to all registered listeners.

        :param event: SimulationProgressEvent to dispatch.
        :return: None.
        """
        active_listeners: List[Callable[[SimulationProgressEvent], None]] = list()
        with self._lock:
            for registered_listener in self._listeners:
                active_listeners.append(registered_listener)

        for listener_candidate in active_listeners:
            try:
                listener_candidate(event)
            except Exception:
                pass

    def _on_progress_value(self, val: Any) -> None:
        """
        Receive numeric progress from the driver.

        :param val: Numeric progress value.
        :return: None.
        """
        numeric_val: float = 0.0
        try:
            numeric_val = float(val)
        except (ValueError, TypeError):
            numeric_val = 0.0

        event: Optional[SimulationProgressEvent] = None
        with self._lock:
            self._progress = numeric_val
            event = SimulationProgressEvent(
                session_id=self._session_id,
                progress=self._progress,
                message=self._message,
                status=self._status,
                timestamp=datetime.now().isoformat(),
            )

        if event is not None:
            self._notify_listeners(event=event)
        else:
            pass

    def _on_progress_text(self, val: Any) -> None:
        """
        Receive textual status update from the driver.

        :param val: Text message.
        :return: None.
        """
        text_val: str = str(val)
        event: Optional[SimulationProgressEvent] = None
        with self._lock:
            self._message = text_val
            event = SimulationProgressEvent(
                session_id=self._session_id,
                progress=self._progress,
                message=self._message,
                status=self._status,
                timestamp=datetime.now().isoformat(),
            )

        if event is not None:
            self._notify_listeners(event=event)
        else:
            pass

    def start(self) -> None:
        """
        Launch the driver in a background worker thread.

        :return: None.
        """
        with self._lock:
            if self._status == SimulationStatus.RUNNING:
                return None
            else:
                self._status = SimulationStatus.RUNNING
                self._failed = False
                self._cancelled = False
                self._error_message = ""
                self._progress = 0.0
                self._message = "Starting simulation..."
                self._start_time = time.time()

        initial_event: SimulationProgressEvent = SimulationProgressEvent(
            session_id=self._session_id,
            progress=0.0,
            message="Starting simulation...",
            status=SimulationStatus.RUNNING,
            timestamp=datetime.now().isoformat(),
        )
        self._notify_listeners(event=initial_event)

        worker_thread: threading.Thread = threading.Thread(
            target=self._run_target,
            name=f"WebSimWorker-{self._session_id}",
            daemon=True,
        )
        self._thread = worker_thread
        worker_thread.start()

    def _run_target(self) -> None:
        """
        Thread target that runs the simulation and captures results or exceptions.

        :return: None.
        """
        final_status: SimulationStatus = SimulationStatus.COMPLETED
        err_msg: str = ""

        try:
            # Execute the core simulation driver
            self._driver.run()

            with self._lock:
                if self._cancelled:
                    final_status = SimulationStatus.CANCELLED
                else:
                    final_status = SimulationStatus.COMPLETED
                    self._results = self._driver.results
        except Exception as exc:
            err_msg = str(exc)
            final_status = SimulationStatus.FAILED

        self._end_time = time.time()

        with self._lock:
            self._status = final_status
            self._error_message = err_msg
            if final_status == SimulationStatus.COMPLETED:
                self._progress = 100.0
                self._message = "Done"
            elif final_status == SimulationStatus.CANCELLED:
                self._message = "Cancelled"
            else:
                self._failed = True
                self._message = f"Failed: {err_msg}"

            completion_event: SimulationProgressEvent = SimulationProgressEvent(
                session_id=self._session_id,
                progress=self._progress,
                message=self._message,
                status=self._status,
                timestamp=datetime.now().isoformat(),
            )

        self._notify_listeners(event=completion_event)

    def cancel(self) -> None:
        """
        Signal the driver to abort execution.

        :return: None.
        """
        with self._lock:
            self._cancelled = True
            self._message = "Cancelling..."

        try:
            self._driver.cancel()
        except Exception:
            pass

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the worker thread to finish.

        :param timeout: Maximum seconds to wait or None for unbounded wait.
        :return: True if thread terminated, False if wait timed out.
        """
        target_thread: Optional[threading.Thread] = None
        with self._lock:
            target_thread = self._thread

        if target_thread is not None:
            target_thread.join(timeout=timeout)
            if target_thread.is_alive():
                return False
            else:
                return True
        else:
            return True


class WebSession:
    """
    Represents an active web modeling session owning a MultiCircuit and simulation state.
    """

    __slots__ = (
        "_session_id",
        "_circuit",
        "_file_name",
        "_created_at",
        "_last_accessed",
        "_worker",
        "_lock",
        "revision",
    )

    def __init__(self,
                 session_id: str,
                 circuit: Optional[MultiCircuit] = None,
                 file_name: str = "") -> None:
        """
        Construct a new WebSession.

        :param session_id: Unique session UUID.
        :param circuit: MultiCircuit instance or None to instantiate empty.
        :param file_name: Source file name if loaded from disk.
        :return: None.
        """
        self._session_id: str = session_id
        self.revision: int = 0
        if circuit is not None:
            self._circuit: MultiCircuit = circuit
        else:
            self._circuit: MultiCircuit = MultiCircuit(name="New Grid")

        self._file_name: str = file_name
        current_time_str: str = datetime.now().isoformat()
        self._created_at: str = current_time_str
        self._last_accessed: str = current_time_str
        self._worker: Optional[WebSimulationWorker] = None
        self._lock: threading.RLock = threading.RLock()

    def get_model_lock(self) -> threading.RLock:
        """
        Expose the lock shared by model edits and simulation startup.

        :return: Session model lock.
        """
        return self._lock

    def invalidate_results(self) -> None:
        """
        Discard completed results after an electrical model edit.

        The caller holds the model lock and has checked that no study is running.

        :return: None.
        """
        self._worker = None
        self.revision += 1

    def get_session_id(self) -> str:
        """
        Return the session unique identifier.

        :return: UUID string.
        """
        return self._session_id

    def get_circuit(self) -> MultiCircuit:
        """
        Get the loaded MultiCircuit instance.

        :return: MultiCircuit reference.
        """
        with self._lock:
            return self._circuit

    def set_circuit(self, circuit: MultiCircuit, file_name: str = "") -> None:
        """
        Update the loaded circuit instance.

        :param circuit: New MultiCircuit instance.
        :param file_name: Optional file name string.
        :return: None.
        """
        with self._lock:
            self._circuit = circuit
            self._file_name = file_name
            self._last_accessed = datetime.now().isoformat()

    def get_file_name(self) -> str:
        """
        Return the associated grid file name.

        :return: File name string.
        """
        with self._lock:
            return self._file_name

    def get_created_at(self) -> str:
        """
        Return creation timestamp.

        :return: ISO timestamp string.
        """
        return self._created_at

    def get_last_accessed(self) -> str:
        """
        Return last accessed timestamp.

        :return: ISO timestamp string.
        """
        with self._lock:
            return self._last_accessed

    def touch(self) -> None:
        """
        Update the last accessed timestamp.

        :return: None.
        """
        with self._lock:
            self._last_accessed = datetime.now().isoformat()

    def get_worker(self) -> Optional[WebSimulationWorker]:
        """
        Get the active or most recent simulation worker.

        :return: WebSimulationWorker instance or None.
        """
        with self._lock:
            return self._worker

    def run_simulation(self, driver_tpe: SimulationTypes) -> WebSimulationWorker:
        """
        Create and launch a simulation on this session's circuit.

        :param driver_tpe: SimulationTypes enumeration member.
        :return: Active WebSimulationWorker instance.
        """
        with self._lock:
            self._last_accessed = datetime.now().isoformat()

            # Ensure previous worker is not running
            if self._worker is not None and self._worker.is_running():
                raise RuntimeError("A simulation is already in progress for this session.")
            else:
                pass

            driver: Optional[DRIVER_OBJECTS] = create_driver(
                grid=self._circuit,
                driver_tpe=driver_tpe,
                time_indices=None,
            )

            if driver is None:
                raise ValueError(f"Could not construct driver for simulation type: {driver_tpe}")
            else:
                pass

            worker: WebSimulationWorker = WebSimulationWorker(
                session_id=self._session_id,
                driver=driver,
            )
            self._worker = worker
            worker.start()
            return worker

    def cancel_simulation(self) -> bool:
        """
        Cancel the running simulation if one is active.

        :return: True if active worker was signalled, False if no active worker.
        """
        with self._lock:
            if self._worker is not None and self._worker.is_running():
                self._worker.cancel()
                return True
            else:
                return False


class WebSessionManager:
    """
    Thread-safe registry managing all active WebSession instances.
    """

    __slots__ = (
        "_sessions",
        "_lock",
    )

    def __init__(self) -> None:
        """
        Initialize the session manager.

        :return: None.
        """
        self._sessions: Dict[str, WebSession] = dict()
        self._lock: threading.Lock = threading.Lock()

    def create_session(self,
                       session_id: Optional[str] = None,
                       circuit: Optional[MultiCircuit] = None,
                       file_name: str = "") -> WebSession:
        """
        Create a new session and register it.

        :param session_id: Optional specific UUID string or None for auto-generated.
        :param circuit: Optional pre-loaded MultiCircuit.
        :param file_name: Source file name.
        :return: Created WebSession instance.
        """
        assigned_id: str = ""
        if session_id is not None and len(session_id) > 0:
            assigned_id = session_id
        else:
            assigned_id = uuid.uuid4().hex

        session: WebSession = WebSession(
            session_id=assigned_id,
            circuit=circuit,
            file_name=file_name,
        )

        with self._lock:
            self._sessions[assigned_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[WebSession]:
        """
        Retrieve one session by its identifier.

        :param session_id: Target UUID string.
        :return: WebSession or None if not found.
        """
        with self._lock:
            session: Optional[WebSession] = self._sessions.get(session_id, None)
            if session is not None:
                session.touch()
                return session
            else:
                return None

    def delete_session(self, session_id: str) -> bool:
        """
        Remove a session from the registry.

        :param session_id: Target UUID string.
        :return: True if found and removed, False otherwise.
        """
        with self._lock:
            if session_id in self._sessions:
                session: WebSession = self._sessions[session_id]
                session.cancel_simulation()
                del self._sessions[session_id]
                return True
            else:
                return False

    def list_session_ids(self) -> List[str]:
        """
        List all active session identifiers.

        :return: List of session UUID strings.
        """
        with self._lock:
            active_ids: List[str] = list()
            for key in self._sessions.keys():
                active_ids.append(key)
            return active_ids

    def clear(self) -> None:
        """
        Cancel and delete all sessions.

        :return: None.
        """
        with self._lock:
            for session in self._sessions.values():
                session.cancel_simulation()
            self._sessions.clear()
