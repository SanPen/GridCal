# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from VeraGridServer.db.model_ops import get_multicircuit_from_database
from VeraGridServer.endpoints.file_management import get_database_settings_or_raise

import VeraGridEngine.api as vge
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.Devices.Diagrams.base_diagram import PointsGroup
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridServer.interactive import WebSession, WebSessionManager

router: APIRouter = APIRouter(prefix="/api/circuits", tags=["circuits"])




def build_circuit_summary(circuit: MultiCircuit) -> Dict[str, Any]:
    """
    Construct a JSON-serializable dictionary summarizing circuit components.

    :param circuit: MultiCircuit instance.
    :return: Dictionary of component counts and metadata.
    """
    bus_count: int = circuit.get_bus_number()
    branch_count: int = circuit.get_branch_number(add_vsc=True, add_hvdc=True, add_switch=True)
    gen_count: int = len(circuit.generators)
    load_count: int = len(circuit.loads)
    battery_count: int = len(circuit.batteries)
    shunt_count: int = len(circuit.shunts)
    line_count: int = len(circuit.lines)
    trafo_count: int = len(circuit.transformers2w)

    return dict({
        "name": str(circuit.name),
        "buses_count": bus_count,
        "branches_count": branch_count,
        "lines_count": line_count,
        "transformers_count": trafo_count,
        "generators_count": gen_count,
        "loads_count": load_count,
        "batteries_count": battery_count,
        "shunts_count": shunt_count,
        "fbase": float(circuit.fBase),
        "sbase": float(circuit.Sbase),
    })


@router.post("/upload")
async def upload_circuit(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload a grid file and instantiate a new web session.

    :param file: Uploaded grid file.
    :return: Circuit session metadata.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    original_name: str = file.filename if file.filename is not None else "grid.veragrid"

    temp_dir: str = tempfile.mkdtemp(prefix="veragrid_upload_")
    destination_path: Path = Path(temp_dir) / Path(original_name).name

    try:
        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        loaded_circuit: MultiCircuit = vge.open_file(str(destination_path))
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse grid file: {exc}")

    shutil.rmtree(temp_dir, ignore_errors=True)

    session: WebSession = manager.create_session(
        circuit=loaded_circuit,
        file_name=original_name,
    )

    summary_data: Dict[str, Any] = build_circuit_summary(circuit=loaded_circuit)
    summary_data["session_id"] = session.get_session_id()
    summary_data["file_name"] = session.get_file_name()
    return summary_data


@router.post("/new")
async def create_new_circuit(request: Request) -> Dict[str, Any]:
    """
    Create a new blank circuit session.

    :param request: Creation options including circuit name.
    :return: Session metadata.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    raw_body = await request.json() if (request.headers.get("content-type", "").startswith("application/json")) else dict()
    grid_name = raw_body.get("name", "New Grid") if isinstance(raw_body, dict) else "New Grid"
    blank_circuit: MultiCircuit = MultiCircuit(name=grid_name)

    session: WebSession = manager.create_session(
        circuit=blank_circuit,
        file_name=f"{grid_name}.veragrid",
    )

    summary_data: Dict[str, Any] = build_circuit_summary(circuit=blank_circuit)
    summary_data["session_id"] = session.get_session_id()
    summary_data["file_name"] = session.get_file_name()
    return summary_data


@router.post("/demo/{demo_name}")
def load_demo_circuit(demo_name: str, request: Request) -> Dict[str, Any]:
    """
    Load a pre-packaged benchmark or geo-referenced demonstration circuit.

    :param demo_name: Name of the demo circuit (e.g. 'honduras', 'ieee14').
    :return: Circuit session metadata.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    grids_dir: Path = Path(__file__).resolve().parents[2] / "tests" / "data" / "grids"

    normalized_name: str = demo_name.lower().strip()
    target_path: Optional[Path] = None

    if normalized_name == "honduras" or normalized_name == "hydro" or normalized_name == "geo":
        target_path = grids_dir / "cnd_enee_15_bus_hydro.veragrid"
    elif normalized_name == "ieee14" or normalized_name == "case14":
        target_path = grids_dir / "case14.gridcal"
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo circuit '{demo_name}'. Available demos: honduras, ieee14",
        )

    if not target_path.exists():
        raise HTTPException(status_code=500, detail=f"Demo file not found on server: {target_path.name}")
    else:
        pass

    loaded_circuit: MultiCircuit = vge.open_file(str(target_path))
    session: WebSession = manager.create_session(
        circuit=loaded_circuit,
        file_name=target_path.name,
    )

    summary_data: Dict[str, Any] = build_circuit_summary(circuit=loaded_circuit)
    summary_data["session_id"] = session.get_session_id()
    summary_data["file_name"] = session.get_file_name()
    return summary_data


@router.post("/database/{file_idtag}")
def open_database_circuit(file_idtag: str, request: Request, model_idtag: str | None = None) -> Dict[str, Any]:
    """Load a stored model directly into a server-owned editing session.

    :param file_idtag: Stored file identifier.
    :param request: Server request.
    :param model_idtag: Optional scenario/model identifier.
    :return: Circuit session summary.
    """
    try:
        circuit: MultiCircuit = get_multicircuit_from_database(
            settings=get_database_settings_or_raise(), file_idtag=file_idtag, model_idtag=model_idtag)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=404, detail=str(error))
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: WebSession = manager.create_session(circuit=circuit, file_name=f"{circuit.name}.veragrid")
    summary: Dict[str, Any] = build_circuit_summary(circuit=circuit)
    summary["session_id"] = session.get_session_id()
    return summary


@router.get("")
def list_circuits(request: Request) -> List[Dict[str, Any]]:
    """
    List all active circuit sessions in memory.

    :return: List of session summaries.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session_ids: List[str] = manager.list_session_ids()
    sessions_list: List[Dict[str, Any]] = list()

    for s_id in session_ids:
        sess: Optional[WebSession] = manager.get_session(session_id=s_id)
        if sess is not None:
            circ: MultiCircuit = sess.get_circuit()
            s_dict: Dict[str, Any] = build_circuit_summary(circuit=circ)
            s_dict["session_id"] = sess.get_session_id()
            s_dict["file_name"] = sess.get_file_name()
            s_dict["created_at"] = sess.get_created_at()
            s_dict["last_accessed"] = sess.get_last_accessed()
            sessions_list.append(s_dict)
        else:
            pass

    return sessions_list


@router.get("/{session_id}/summary")
def get_circuit_summary(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Get detailed component counts and metadata for one session.

    :param session_id: Target session identifier.
    :return: Circuit summary dictionary.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        circuit: MultiCircuit = session.get_circuit()
        summary_payload: Dict[str, Any] = build_circuit_summary(circuit=circuit)
        summary_payload["session_id"] = session.get_session_id()
        summary_payload["file_name"] = session.get_file_name()
        return summary_payload


@router.get("/{session_id}/diagrams/schematic")
def get_schematic_diagram(session_id: str, request: Request, diagram_id: str | None = None) -> Dict[str, Any]:
    """
    Get an engine schematic, retaining the legacy full-model preview when no ID is given.

    :param session_id: Target session identifier.
    :param request: Server request.
    :param diagram_id: Optional explicit schematic identifier.
    :return: Schematic diagram payload.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        target_diagram: Optional[SchematicDiagram] = None

        if circuit.diagrams is not None and len(circuit.diagrams) > 0:
            for diag_candidate in circuit.diagrams:
                if isinstance(diag_candidate, SchematicDiagram) and (diagram_id is None or diag_candidate.idtag == diagram_id):
                    target_diagram = diag_candidate
                    break
                else:
                    pass
        else:
            pass

        if diagram_id is not None and target_diagram is None:
            raise HTTPException(status_code=404, detail="Schematic not found")
        else:
            pass

        nodes_list: List[Dict[str, Any]] = list()
        branches_list: List[Dict[str, Any]] = list()
        injections_list: List[Dict[str, Any]] = list()

        # Extract bus node locations
        default_x: float = 100.0
        default_y: float = 100.0
        spacing_x: float = 200.0
        spacing_y: float = 150.0
        cols: int = 5

        bus_idx: int = 0
        for bus in circuit.buses:
            x_coord: float = default_x + float(bus_idx % cols) * spacing_x
            y_coord: float = default_y + float(bus_idx // cols) * spacing_y
            width: float = 160.0
            height: float = 30.0
            rotation: float = 0.0

            if target_diagram is not None:
                loc: Optional[GraphicLocation] = target_diagram.query_point(device=bus)
                if loc is not None:
                    x_coord = float(loc.x)
                    y_coord = float(loc.y)
                    width = float(loc.w) if loc.w > 0 else 160.0
                    height = float(loc.h) if loc.h > 0 else 30.0
                    rotation = float(loc.r)
                else:
                    pass
            else:
                pass

            node_dict: Dict[str, Any] = dict({
                "idtag": bus.idtag,
                "name": bus.name,
                "vnom": float(bus.Vnom),
                "is_slack": bool(bus.is_slack),
                "is_dc": bool(bus.is_dc),
                "x": x_coord,
                "y": y_coord,
                "width": width,
                "height": height,
                "rotation": rotation,
            })
            nodes_list.append(node_dict)
            bus_idx += 1

        # Extract branches (lines and transformers)
        for line in (item for item in circuit.lines if item.bus_from is not None and item.bus_to is not None):
            line_dict: Dict[str, Any] = dict({
                "idtag": line.idtag,
                "name": line.name,
                "type": "Line",
                "from_bus": line.bus_from.idtag,
                "to_bus": line.bus_to.idtag,
                "from_bus_name": line.bus_from.name,
                "to_bus_name": line.bus_to.name,
                "rate": float(line.rate),
                "active": bool(line.active),
            })
            branches_list.append(line_dict)

        for trafo in (item for item in circuit.transformers2w if item.bus_from is not None and item.bus_to is not None):
            trafo_dict: Dict[str, Any] = dict({
                "idtag": trafo.idtag,
                "name": trafo.name,
                "type": "Transformer2W",
                "from_bus": trafo.bus_from.idtag,
                "to_bus": trafo.bus_to.idtag,
                "from_bus_name": trafo.bus_from.name,
                "to_bus_name": trafo.bus_to.name,
                "rate": float(trafo.rate),
                "active": bool(trafo.active),
            })
            branches_list.append(trafo_dict)

        collection: Any
        branch_name: str
        branch: BranchParent
        for collection, branch_name in ((circuit.switch_devices, "Switch"), (circuit.dc_lines, "DCLine"),
                                        (circuit.hvdc_lines, "HVDCLine")):
            for branch in collection:
                if branch.bus_from is not None and branch.bus_to is not None:
                    branches_list.append(dict(idtag=branch.idtag, name=branch.name, type=branch_name,
                                              from_bus=branch.bus_from.idtag, to_bus=branch.bus_to.idtag,
                                              active=bool(branch.active), rate=float(branch.rate)))
                else:
                    pass

        # Extract injections attached to buses
        for gen in (item for item in circuit.generators if item.bus is not None):
            gen_dict: Dict[str, Any] = dict({
                "idtag": gen.idtag,
                "name": gen.name,
                "type": "Generator",
                "bus": gen.bus.idtag,
                "bus_name": gen.bus.name,
                "p": float(gen.P),
                "active": bool(gen.active),
            })
            injections_list.append(gen_dict)

        for load in (item for item in circuit.loads if item.bus is not None):
            load_dict: Dict[str, Any] = dict({
                "idtag": load.idtag,
                "name": load.name,
                "type": "Load",
                "bus": load.bus.idtag,
                "bus_name": load.bus.name,
                "p": float(load.P),
                "q": float(load.Q),
                "active": bool(load.active),
            })
            injections_list.append(load_dict)

        for batt in (item for item in circuit.batteries if item.bus is not None):
            batt_dict: Dict[str, Any] = dict({
                "idtag": batt.idtag,
                "name": batt.name,
                "type": "Battery",
                "bus": batt.bus.idtag,
                "bus_name": batt.bus.name,
                "p": float(batt.P),
                "enom": float(batt.Enom),
                "active": bool(batt.active),
            })
            injections_list.append(batt_dict)

        shunt: Shunt
        for shunt in circuit.shunts:
            if shunt.bus is not None:
                injections_list.append(dict(idtag=shunt.idtag, name=shunt.name, type="Shunt",
                                            bus=shunt.bus.idtag, active=bool(shunt.active)))
            else:
                pass

        # Explicit views contain only their own equipment, never every circuit bus.
        if target_diagram is not None:
            locations: dict[str, GraphicLocation] = dict()
            group: PointsGroup
            for group in target_diagram.data.values():
                locations.update(group.locations)
            if diagram_id is not None:
                nodes_list = [item for item in nodes_list if item["idtag"] in locations]
                visible_buses: set[str] = set(item["idtag"] for item in nodes_list)
                branches_list = [item for item in branches_list if item["idtag"] in locations
                                 and item["from_bus"] in visible_buses and item["to_bus"] in visible_buses]
                # Qt renders bus-attached injections even in older files without separate locations.
                injections_list = [item for item in injections_list if item["bus"] in visible_buses]
            else:
                pass
            item: dict[str, Any]
            for collection in (branches_list, injections_list):
                for item in collection:
                    saved: GraphicLocation | None = locations.get(item["idtag"], None)
                    if saved is not None:
                        item["vertices"] = saved.poly_line
                        if saved.layout_metadata.get("web_position", False):
                            item["x"] = saved.x
                            item["y"] = saved.y
                        else:
                            pass
                    else:
                        pass
        else:
            pass

        return dict({
            "session_id": session_id,
            "revision": session.revision,
            "diagram_id": target_diagram.idtag if target_diagram is not None else None,
            "nodes": nodes_list,
            "branches": branches_list,
            "injections": injections_list,
        })


@router.get("/{session_id}/diagrams/map")
def get_map_diagram(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Get GeoJSON FeatureCollection for MapLibre GL GIS visualization.

    :param session_id: Target session identifier.
    :return: GeoJSON FeatureCollection dictionary.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        features: List[Dict[str, Any]] = list()

        # Create Point features for buses with coordinates
        for bus in circuit.buses:
            lat: float = float(bus.latitude)
            lon: float = float(bus.longitude)

            # Include all buses or those with coordinates
            point_feature: Dict[str, Any] = dict({
                "type": "Feature",
                "geometry": dict({
                    "type": "Point",
                    "coordinates": [lon, lat],
                }),
                "properties": dict({
                    "idtag": bus.idtag,
                    "name": bus.name,
                    "vnom": float(bus.Vnom),
                    "is_slack": bool(bus.is_slack),
                    "has_coordinates": bool(lat != 0.0 or lon != 0.0),
                    "x": float(bus.x),
                    "y": float(bus.y),
                }),
            })
            features.append(point_feature)

        # Create LineString features for lines
        for line in (item for item in circuit.lines if item.bus_from is not None and item.bus_to is not None):
            from_lat: float = float(line.bus_from.latitude)
            from_lon: float = float(line.bus_from.longitude)
            to_lat: float = float(line.bus_to.latitude)
            to_lon: float = float(line.bus_to.longitude)

            line_feature: Dict[str, Any] = dict({
                "type": "Feature",
                "geometry": dict({
                    "type": "LineString",
                    "coordinates": [
                        [from_lon, from_lat],
                        [to_lon, to_lat],
                    ],
                }),
                "properties": dict({
                    "idtag": line.idtag,
                    "name": line.name,
                    "type": "Line",
                    "from_bus": line.bus_from.name,
                    "to_bus": line.bus_to.name,
                    "from_bus_idtag": line.bus_from.idtag,
                    "to_bus_idtag": line.bus_to.idtag,
                    "rate": float(line.rate),
                }),
            })
            features.append(line_feature)

        # Create LineString features for transformers
        for trafo in (item for item in circuit.transformers2w if item.bus_from is not None and item.bus_to is not None):
            from_lat_t: float = float(trafo.bus_from.latitude)
            from_lon_t: float = float(trafo.bus_from.longitude)
            to_lat_t: float = float(trafo.bus_to.latitude)
            to_lon_t: float = float(trafo.bus_to.longitude)

            trafo_feature: Dict[str, Any] = dict({
                "type": "Feature",
                "geometry": dict({
                    "type": "LineString",
                    "coordinates": [
                        [from_lon_t, from_lat_t],
                        [to_lon_t, to_lat_t],
                    ],
                }),
                "properties": dict({
                    "idtag": trafo.idtag,
                    "name": trafo.name,
                    "type": "Transformer2W",
                    "from_bus": trafo.bus_from.name,
                    "to_bus": trafo.bus_to.name,
                    "from_bus_idtag": trafo.bus_from.idtag,
                    "to_bus_idtag": trafo.bus_to.idtag,
                    "rate": float(trafo.rate),
                }),
            })
            features.append(trafo_feature)

        return dict({
            "type": "FeatureCollection",
            "features": features,
            "revision": session.revision,
        })


@router.get("/{session_id}/export")
def export_circuit(session_id: str, request: Request) -> FileResponse:
    """
    Export and download the circuit session as a .veragrid file.

    :param session_id: Target session identifier.
    :return: FileResponse downloading the exported .veragrid archive.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: Optional[WebSession] = manager.get_session(session_id=session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    else:
        pass

    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        temp_dir: str = tempfile.mkdtemp(prefix="veragrid_export_")
        raw_name: str = circuit.name.strip()
        base_name: str = Path(raw_name).name if len(raw_name) > 0 else "grid"
        output_filename: str = f"{base_name}.veragrid"
        export_path: Path = Path(temp_dir) / output_filename

        try:
            vge.save_file(circuit, str(export_path))
        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Failed to export circuit: {exc}")

        return FileResponse(
            path=str(export_path),
            filename=output_filename,
            media_type="application/zip",
            background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
        )


@router.delete("/{session_id}")
def delete_circuit_session(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Remove one circuit session from memory.

    :param session_id: Target session identifier.
    :return: Success confirmation.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    removed: bool = manager.delete_session(session_id=session_id)

    if removed:
        return dict({"success": True, "message": f"Session '{session_id}' deleted."})
    else:
        raise HTTPException(status_code=404, detail="Session not found")
