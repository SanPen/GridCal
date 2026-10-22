# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request

from VeraGridEngine.enumerations import SimulationTypes
from VeraGridEngine.Simulations.types import RESULTS_OBJECTS
from VeraGridServer.interactive import (
    WebSession,
    WebSessionManager,
    WebSimulationWorker,
    SimulationStatus,
)

router: APIRouter = APIRouter(prefix="/api/calculations", tags=["calculations"])




def parse_simulation_type(type_string: str) -> SimulationTypes:
    """
    Parse a string identifier into a SimulationTypes enumeration member.

    :param type_string: Simulation type string (e.g., 'PowerFlow_run').
    :return: SimulationTypes enumeration member.
    """
    cleaned_string: str = type_string.strip()

    # Match against SimulationTypes member names or string values
    for sim_member in SimulationTypes:
        if sim_member.name == cleaned_string:
            return sim_member
        elif sim_member.value == cleaned_string:
            return sim_member
        else:
            pass

    # Fallback to default PowerFlow_run
    return SimulationTypes.PowerFlow_run


@router.post("/{session_id}/run")
async def start_simulation(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Start an asynchronous simulation run on a loaded circuit session.

    :param session_id: Target session identifier.
    :param request: Simulation execution options.
    :return: Execution initiation status dictionary.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    raw_body = await request.json() if (request.headers.get("content-type", "").startswith("application/json")) else dict()
    sim_type_str = raw_body.get("simulation_type", "PowerFlow_run") if isinstance(raw_body, dict) else "PowerFlow_run"
    driver_tpe: SimulationTypes = parse_simulation_type(type_string=str(sim_type_str))

    try:
        worker: WebSimulationWorker = session.run_simulation(driver_tpe=driver_tpe)
    except RuntimeError as r_err:
        raise HTTPException(status_code=409, detail=str(r_err))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to start simulation: {exc}")

    return dict({
        "success": True,
        "session_id": session_id,
        "simulation_type": driver_tpe.name,
        "status": str(worker.get_status().value),
        "message": worker.get_message(),
    })


@router.get("/{session_id}/status")
def get_simulation_status(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Get the current execution status, progress percentage, and messages.

    :param session_id: Target session identifier.
    :return: Status payload dictionary.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    worker: Optional[WebSimulationWorker] = session.get_worker()

    if worker is None:
        return dict({
            "session_id": session_id,
            "status": str(SimulationStatus.IDLE.value),
            "progress": 0.0,
            "message": "No simulation has been run on this session.",
            "error_message": "",
            "has_results": False,
        })
    else:
        status_val: SimulationStatus = worker.get_status()
        has_results: bool = worker.get_results() is not None

        return dict({
            "session_id": session_id,
            "status": str(status_val.value),
            "progress": worker.get_progress(),
            "message": worker.get_message(),
            "error_message": worker.get_error_message(),
            "has_results": has_results,
        })


@router.post("/{session_id}/cancel")
def cancel_simulation(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Cancel an active simulation running on the session.

    :param session_id: Target session identifier.
    :return: Cancellation confirmation dictionary.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    cancelled: bool = session.cancel_simulation()

    if cancelled:
        return dict({"success": True, "message": "Simulation cancellation requested."})
    else:
        return dict({"success": False, "message": "No active simulation was running to cancel."})


@router.get("/{session_id}/results")
def get_simulation_results(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Get structured numerical results from the most recent simulation.

    :param session_id: Target session identifier.
    :return: Results payload dictionary.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    worker: Optional[WebSimulationWorker] = session.get_worker()

    if worker is None:
        raise HTTPException(status_code=404, detail="No simulation has been run on this session.")
    else:
        pass

    results_obj: Optional[RESULTS_OBJECTS] = worker.get_results()

    if results_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Simulation results not available (status: {worker.get_status().value})."
        )
    else:
        pass

    results_dict: Dict[str, Any] = dict()
    try:
        results_dict = results_obj.get_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to serialize simulation results: {exc}")

    converged_status: bool = False
    try:
        converged_status = bool(results_obj.converged)
    except Exception:
        converged_status = True

    elapsed_time: float = 0.0
    try:
        elapsed_time = float(results_obj.elapsed)
    except Exception:
        elapsed_time = 0.0

    return dict({
        "session_id": session_id,
        "converged": converged_status,
        "elapsed": elapsed_time,
        "results": results_dict,
    })
