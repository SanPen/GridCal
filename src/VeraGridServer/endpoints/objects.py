"""Engine-derived object tables for server-owned interactive circuits."""
from __future__ import annotations

import math
from enum import Enum, EnumMeta
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, GCProp
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.enumerations import DeviceType
from VeraGridServer.interactive import WebSession, WebSessionManager, WebSimulationWorker


class CellType(Enum):
    """Editors supported by the object table wire format."""

    TEXT = "text"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    COMPLEX = "complex"
    ENUM = "enum"
    REFERENCE = "reference"
    STRUCTURED = "structured"


def get_cell_type(prop: GCProp) -> CellType:
    """Select an editor from engine metadata.

    :param prop: Engine property declaration.
    :return: Wire editor type.
    """
    if prop.tpe is str:
        return CellType.TEXT
    elif prop.tpe is bool:
        return CellType.BOOLEAN
    elif prop.tpe is int:
        return CellType.INTEGER
    elif prop.tpe is float:
        return CellType.NUMBER
    elif prop.tpe is complex:
        return CellType.COMPLEX
    elif isinstance(prop.tpe, DeviceType):
        return CellType.REFERENCE
    elif isinstance(prop.tpe, EnumMeta):
        return CellType.ENUM
    else:
        return CellType.STRUCTURED


def encode_value(value: Any) -> Any:
    """Encode cells without leaking Python objects or invalid JSON numbers.

    :param value: Engine snapshot value.
    :return: JSON cell value.
    """
    if isinstance(value, EditableDevice):
        return value.idtag
    elif isinstance(value, Enum):
        return value.name
    elif isinstance(value, complex):
        return str(value)
    elif isinstance(value, float):
        return value if math.isfinite(value) else None
    elif value is None or isinstance(value, (str, int, bool)):
        return value
    else:
        return str(value)


async def read_edit_body(request: Request) -> dict[str, Any]:
    """Reject malformed JSON before reading mutation fields.

    :param request: Untrusted API request.
    :return: JSON object payload.
    """
    try:
        body: Any = await request.json()
    except ValueError:
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    if isinstance(body, dict):
        return body
    else:
        raise HTTPException(status_code=422, detail="Expected a JSON object")


def get_session(request: Request, session_id: str) -> WebSession:
    """Resolve a circuit strictly from the receiving server instance.

    :param request: Server request.
    :param session_id: Circuit session identifier.
    :return: Live server session.
    """
    manager: WebSessionManager = request.app.state.circuit_sessions
    session: WebSession | None = manager.get_session(session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Circuit session not found")
    else:
        return session


def get_template(circuit: MultiCircuit, device_type: str) -> EditableDevice:
    """Resolve wire identifiers only against engine-declared collections.

    :param circuit: Authoritative model.
    :param device_type: DeviceType member name.
    :return: Engine template.
    """
    template: EditableDevice
    for template in circuit.get_template_objects_list():
        if template.device_type.name == device_type:
            return template
        else:
            pass
    raise HTTPException(status_code=404, detail="Unknown device collection")


def get_reference_choices(circuit: MultiCircuit, template: EditableDevice,
                          prop: GCProp) -> list[EditableDevice]:
    """Reuse Qt's engine-side dependency lists, including specialized templates.

    :param circuit: Authoritative model.
    :param template: Edited device template.
    :param prop: Reference property.
    :return: Allowed reference targets.
    """
    reference_lists: dict[Any, list[EditableDevice]]
    _, reference_lists = circuit.get_dictionary_of_lists(elm_type=template.device_type)
    special: list[EditableDevice] | None = reference_lists.get((prop.name, prop.tpe), None)
    if special is not None:
        return special
    elif prop.tpe == DeviceType.PhysicalDeviceType:
        if isinstance(template, PointerDeviceParent) and prop.name == "device" and DeviceType.PhysicalDeviceType not in template.pointer_dev_tpes:
            return [device for reference_type, devices in reference_lists.items()
                    if reference_type in template.pointer_dev_tpes for device in devices]
        elif prop.name == "monitored_device":
            return [device for reference_type, devices in reference_lists.items()
                    if reference_type in (DeviceType.BusDevice, DeviceType.LineDevice, DeviceType.Transformer2WDevice)
                    for device in devices]
        else:
            return [device for devices in reference_lists.values() for device in devices
                    if isinstance(device, PhysicalDevice)]
    else:
        return reference_lists.get(prop.tpe, list())


def can_edit(device: EditableDevice, prop: GCProp) -> bool:
    """Apply Qt's instance rules, including initially empty bus references.

    :param device: Edited engine device.
    :param prop: Registered property.
    :return: Whether the snapshot cell can be edited here.
    """
    empty_bus: bool = prop.tpe == DeviceType.BusDevice and device.get_value(prop=prop, t_idx=None) is None
    return (prop.display and prop.name != "idtag" and get_cell_type(prop=prop) != CellType.STRUCTURED
            and ((prop.editable and device.is_property_editable(prop=prop)) or empty_bus))


def check_revision(session: WebSession, body: Any) -> None:
    """Reject malformed, stale or concurrent edits while holding the model lock.

    :param session: Server circuit session.
    :param body: Untrusted mutation request.
    :return: None.
    """
    if not isinstance(body, dict) or type(body.get("revision", None)) is not int:
        raise HTTPException(status_code=422, detail="Expected an integer model revision")
    else:
        pass
    worker: WebSimulationWorker | None = session.get_worker()
    if body["revision"] != session.revision or (worker is not None and worker.is_running()):
        raise HTTPException(status_code=409, detail="Model changed or a study is running; reload before editing")
    else:
        pass


def get_object_types(session_id: str, request: Request) -> dict[str, Any]:
    """Discover all engine collections, including empty collections.

    :param session_id: Circuit session identifier.
    :param request: Server request.
    :return: Grouped collection descriptors.
    """
    session: WebSession = get_session(request=request, session_id=session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        collections: list[dict[str, Any]] = list()
        group: str
        templates: list[EditableDevice]
        for group, templates in circuit.template_objects_dict.items():
            template: EditableDevice
            for template in templates:
                collections.append(dict(name=template.device_type.name, label=template.device_type.value,
                                        group=group, count=len(circuit.get_elements_by_type(template.device_type))))
        return dict(revision=session.revision, collections=collections)


def get_object_table(session_id: str, device_type: str, request: Request,
                     query: str = "") -> dict[str, Any]:
    """Read all rows in engine collection order with their property metadata.

    :param session_id: Circuit session identifier.
    :param device_type: Engine device type name.
    :param request: Server request.
    :param query: Case-insensitive name, code or identifier search.
    :return: Metadata, reference choices and rows.
    """
    session: WebSession = get_session(request=request, session_id=session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        template: EditableDevice = get_template(circuit=circuit, device_type=device_type)
        properties: list[GCProp] = [prop for prop in template.property_list if prop.display]
        columns: list[dict[str, Any]] = list()
        prop: GCProp
        for prop in properties:
            cell_type: CellType = get_cell_type(prop=prop)
            choices: list[dict[str, Any]] = list()
            if cell_type == CellType.ENUM:
                choices = [dict(value=member.name, label=str(member.value)) for member in prop.tpe]
            elif cell_type == CellType.REFERENCE:
                choices = [dict(value=device.idtag, label=device.name) for device in
                           get_reference_choices(circuit=circuit, template=template, prop=prop)]
            else:
                pass
            columns.append(dict(name=prop.name, units=prop.units, description=prop.definition,
                                kind=cell_type.value, editable=(prop.editable or prop.tpe == DeviceType.BusDevice) and prop.name != "idtag"
                                and cell_type != CellType.STRUCTURED,
                                profile=prop.has_profile(), choices=choices))
        devices: list[EditableDevice] = circuit.get_elements_by_type(template.device_type)
        matched: list[EditableDevice] = [device for device in devices if query.casefold() in
                                        f"{device.name} {device.code} {device.idtag}".casefold()]
        rows: list[dict[str, Any]] = list()
        device: EditableDevice
        for device in matched:
            values: dict[str, Any] = dict()
            editable: list[str] = list()
            for prop in properties:
                values[prop.name] = encode_value(device.get_value(prop=prop, t_idx=None))
                if can_edit(device=device, prop=prop):
                    editable.append(prop.name)
                else:
                    pass
            rows.append(dict(idtag=device.idtag, values=values, editable=editable))
        return dict(revision=session.revision, columns=columns, rows=rows,
                    total=len(matched))


def decode_value(circuit: MultiCircuit, template: EditableDevice, prop: GCProp, value: Any) -> Any:
    """Validate wire values before calling engine setters.

    :param circuit: Authoritative model.
    :param template: Edited collection template.
    :param prop: Registered property.
    :param value: Untrusted JSON cell value.
    :return: Typed engine value.
    """
    cell_type: CellType = get_cell_type(prop=prop)
    if cell_type == CellType.TEXT and isinstance(value, str):
        return value
    elif cell_type == CellType.BOOLEAN and isinstance(value, bool):
        return value
    elif cell_type == CellType.INTEGER and isinstance(value, int) and not isinstance(value, bool):
        return value
    elif cell_type == CellType.NUMBER and isinstance(value, (float, int)) and not isinstance(value, bool):
        if math.isfinite(value):
            return float(value)
        else:
            pass
    elif cell_type == CellType.COMPLEX and isinstance(value, str):
        try:
            parsed: complex = complex(value)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid complex value")
        if math.isfinite(parsed.real) and math.isfinite(parsed.imag):
            return parsed
        else:
            pass
    elif cell_type == CellType.ENUM and isinstance(value, str):
        member: Enum | None = prop.tpe.__members__.get(value, None)
        if member is not None:
            return member
        else:
            pass
    elif cell_type == CellType.REFERENCE:
        if value is None:
            return None
        else:
            device: EditableDevice
            for device in get_reference_choices(circuit=circuit, template=template, prop=prop):
                if device.idtag == value:
                    return device
                else:
                    pass
    else:
        pass
    raise HTTPException(status_code=422, detail=f"Invalid value for {prop.name}")


async def patch_object_table(session_id: str, device_type: str, request: Request) -> dict[str, Any]:
    """Commit a validated cell batch against one model revision.

    :param session_id: Circuit session identifier.
    :param device_type: Engine device type name.
    :param request: JSON revision and edits.
    :return: New model revision.
    """
    body: dict[str, Any] = await read_edit_body(request=request)
    if not isinstance(body.get("edits", None), list):
        raise HTTPException(status_code=422, detail="Expected revision and edits")
    else:
        pass
    edits: list[Any] = body["edits"]
    if not 1 <= len(edits) <= 1000:
        raise HTTPException(status_code=422, detail="Expected 1 to 1000 cell edits")
    else:
        pass
    session: WebSession = get_session(request=request, session_id=session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        check_revision(session=session, body=body)
        template: EditableDevice = get_template(circuit=circuit, device_type=device_type)
        devices: dict[str, EditableDevice] = dict((device.idtag, device) for device in
                                                circuit.get_elements_by_type(template.device_type))
        changes: list[tuple[EditableDevice, GCProp, Any, Any]] = list()
        edit: Any
        for edit in edits:
            if not isinstance(edit, dict):
                raise HTTPException(status_code=422, detail="Invalid cell edit")
            else:
                pass
            device: EditableDevice | None = devices.get(str(edit.get("idtag", "")), None)
            prop: GCProp | None = template.registered_properties.get(str(edit.get("property", "")), None)
            if device is None or prop is None:
                raise HTTPException(status_code=404, detail="Device or property not found")
            elif not can_edit(device=device, prop=prop):
                raise HTTPException(status_code=422, detail="Property is read-only")
            else:
                value: Any = decode_value(circuit=circuit, template=template, prop=prop, value=edit.get("value", None))
                changes.append((device, prop, value, device.get_value(prop=prop, t_idx=None)))
        # Validate the entire batch first; restore prior values if an engine setter rejects it.
        applied: list[tuple[EditableDevice, GCProp, Any, Any]] = list()
        try:
            for device, prop, value, previous in changes:
                if value != previous:
                    device.set_value(prop=prop, t_idx=None, value=value)
                    applied.append((device, prop, value, previous))
                else:
                    pass
        except (ValueError, TypeError, AssertionError) as error:
            for device, prop, value, previous in reversed(applied):
                device.set_value(prop=prop, t_idx=None, value=previous)
            raise HTTPException(status_code=422, detail=str(error))
        session.invalidate_results()
        return dict(revision=session.revision)


async def create_object(session_id: str, device_type: str, request: Request) -> dict[str, Any]:
    """Create an engine-default device in its owning circuit collection.

    :param session_id: Circuit session identifier.
    :param device_type: Engine collection name.
    :param request: JSON model revision.
    :return: Created identifier and revision.
    """
    body: dict[str, Any] = await read_edit_body(request=request)
    session: WebSession = get_session(request=request, session_id=session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        check_revision(session=session, body=body)
        template: EditableDevice = get_template(circuit=circuit, device_type=device_type)
        device: EditableDevice
        device, _ = circuit.get_dictionary_of_lists(elm_type=template.device_type)
        circuit.add_element(obj=device)
        session.invalidate_results()
        return dict(idtag=device.idtag, revision=session.revision)


async def patch_schematic_position(session_id: str, idtag: str, request: Request) -> dict[str, Any]:
    """Persist an equipment position or branch route into the selected engine schematic.

    :param session_id: Circuit session identifier.
    :param idtag: Equipment identifier.
    :param request: Model revision, diagram identifier, finite position and optional route vertices.
    :return: New revision.
    """
    body: dict[str, Any] = await read_edit_body(request=request)
    session: WebSession = get_session(request=request, session_id=session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        check_revision(session=session, body=body)
        x: Any = body.get("x", None)
        y: Any = body.get("y", None)
        if (type(x) not in (float, int) or type(y) not in (float, int)
                or not math.isfinite(x) or not math.isfinite(y)):
            raise HTTPException(status_code=422, detail="Expected finite x/y coordinates")
        else:
            pass
        devices: dict[str, EditableDevice]
        devices, _ = circuit.get_all_elements_dict()
        bus: EditableDevice | None = devices.get(idtag, None)
        if bus is None:
            raise HTTPException(status_code=404, detail="Device not found")
        else:
            pass
        diagram_id: Any = body.get("diagram_id", None)
        diagram: SchematicDiagram | None = next((item for item in circuit.diagrams
                                               if isinstance(item, SchematicDiagram)
                                               and (diagram_id is None or item.idtag == diagram_id)), None)
        if diagram_id is not None and diagram is None:
            raise HTTPException(status_code=404, detail="Schematic not found")
        else:
            pass
        vertices: Any = body.get("vertices", list())
        if (not isinstance(vertices, list) or len(vertices) > 1000
                or any(not isinstance(point, list) or len(point) != 2
                       or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                       for point in vertices)):
            raise HTTPException(status_code=422, detail="Expected finite route vertices")
        else:
            pass
        if diagram is None:
            diagram = SchematicDiagram(name="Schematic")
            circuit.add_diagram(diagram=diagram)
        else:
            pass
        location: GraphicLocation | None = diagram.query_point(device=bus)
        if location is None:
            location = GraphicLocation(api_object=bus, x=float(x), y=float(y), w=160.0, h=30.0)
            diagram.set_point(device=bus, location=location)
        else:
            location.x = float(x)
            location.y = float(y)
        if "vertices" in body:
            location.poly_line = [tuple(point) for point in vertices]
        else:
            pass
        location.layout_metadata["web_position"] = True
        session.revision += 1
        return dict(revision=session.revision)


async def schematic_collection(session_id: str, request: Request) -> dict[str, Any]:
    """List or create engine-owned schematic views without copying electrical equipment.

    :param session_id: Circuit session identifier.
    :param request: Optional creation name, revision and include_existing flag.
    :return: Schematics and current model revision.
    """
    body: dict[str, Any] = await read_edit_body(request) if request.method == "POST" else dict()
    session: WebSession = get_session(request, session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        created_id: str | None = None
        if request.method == "POST":
            check_revision(session, body)
            name: Any = body.get("name", "Schematic")
            include_existing: Any = body.get("include_existing", False)
            if not isinstance(name, str) or not name.strip() or len(name) > 200 or type(include_existing) is not bool:
                raise HTTPException(status_code=422, detail="Expected a name and boolean include_existing")
            else:
                pass
            diagram: SchematicDiagram = SchematicDiagram(name=name.strip())
            if include_existing:
                # Reuse the same engine devices; only their graphic locations belong to the view.
                bus_index: int
                bus: Bus
                for bus_index, bus in enumerate(circuit.buses):
                    diagram.set_point(bus, GraphicLocation(api_object=bus, x=100 + bus_index % 5 * 240,
                                                          y=100 + bus_index // 5 * 200, w=160, h=10))
                devices: dict[str, EditableDevice]
                devices, _ = circuit.get_all_elements_dict()
                device: EditableDevice
                for device in devices.values():
                    if isinstance(device, (BranchParent, InjectionParent)):
                        diagram.set_point(device, GraphicLocation(api_object=device))
                    else:
                        pass
            else:
                pass
            circuit.add_diagram(diagram)
            session.revision += 1
            created_id = diagram.idtag
        else:
            pass
        return dict(revision=session.revision, created_id=created_id,
                    diagrams=[dict(idtag=item.idtag, name=item.name) for item in circuit.diagrams
                              if isinstance(item, SchematicDiagram)])


async def create_schematic_device(session_id: str, diagram_id: str, request: Request) -> dict[str, Any]:
    """Create and connect an engine device atomically from a graphical editing gesture.

    :param session_id: Circuit session identifier.
    :param diagram_id: Owning schematic view.
    :param request: Device type, finite position, terminal bus identifiers and model revision.
    :return: Created device identifier and revision.
    """
    body: dict[str, Any] = await read_edit_body(request)
    session: WebSession = get_session(request, session_id)
    circuit: MultiCircuit = session.get_circuit()
    with session.get_model_lock():
        check_revision(session, body)
        diagram: SchematicDiagram | None = next((item for item in circuit.diagrams
                                                if isinstance(item, SchematicDiagram) and item.idtag == diagram_id), None)
        if diagram is None:
            raise HTTPException(status_code=404, detail="Schematic not found")
        else:
            pass
        template: EditableDevice = get_template(circuit, str(body.get("device_type", "")))
        if template.device_type not in (DeviceType.BusDevice, DeviceType.LineDevice, DeviceType.Transformer2WDevice,
                                        DeviceType.SwitchDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice,
                                        DeviceType.GeneratorDevice, DeviceType.LoadDevice, DeviceType.BatteryDevice,
                                        DeviceType.ShuntDevice):
            raise HTTPException(status_code=422, detail="Unsupported schematic device")
        else:
            pass
        x: Any = body.get("x", None)
        y: Any = body.get("y", None)
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (x, y)):
            raise HTTPException(status_code=422, detail="Expected finite x/y coordinates")
        else:
            pass
        buses: dict[str, Bus] = dict((bus.idtag, bus) for bus in circuit.buses)
        first: Bus | None = buses.get(str(body.get("bus", "")), None)
        second: Bus | None = buses.get(str(body.get("to_bus", "")), None)
        device: EditableDevice
        device, _ = circuit.get_dictionary_of_lists(template.device_type)
        if isinstance(device, (BranchParent, InjectionParent)):
            if first is None or diagram.query_point(first) is None:
                raise HTTPException(status_code=422, detail="Select a bus in this schematic")
            else:
                pass
            if isinstance(device, BranchParent):
                if second is None or second is first or diagram.query_point(second) is None:
                    raise HTTPException(status_code=422, detail="Select a different destination bus in this schematic")
                else:
                    device.bus_from = first
                    device.bus_to = second
                    if isinstance(device, Transformer2W):
                        # Match Qt construction, which derives winding ratings from connected buses.
                        device.set_hv_and_lv(HV=None, LV=None)
                    else:
                        pass
            else:
                device.bus = first
        else:
            pass
        names: set[str] = set(item.name for item in circuit.get_elements_by_type(template.device_type))
        suffix: int = len(names) + 1
        while f"{template.name} {suffix}" in names:
            suffix += 1
        device.name = f"{template.name} {suffix}"
        circuit.add_element(device)
        diagram.set_point(device, GraphicLocation(api_object=device, x=float(x), y=float(y), w=160, h=10,
                                                 layout_metadata=dict(web_position=True)))
        session.invalidate_results()
        return dict(idtag=device.idtag, revision=session.revision)


def create_objects_router() -> APIRouter:
    """Build object endpoints without a module-level router singleton.

    :return: Object table router.
    """
    router: APIRouter = APIRouter(prefix="/api/circuits", tags=["objects"])
    router.add_api_route("/{session_id}/object-types", get_object_types, methods=["GET"])
    router.add_api_route("/{session_id}/objects/{device_type}", get_object_table, methods=["GET"])
    router.add_api_route("/{session_id}/objects/{device_type}", patch_object_table, methods=["PATCH"])
    router.add_api_route("/{session_id}/objects/{device_type}", create_object, methods=["POST"])
    router.add_api_route("/{session_id}/diagrams/schematic/{idtag}", patch_schematic_position, methods=["PATCH"])
    router.add_api_route("/{session_id}/schematics", schematic_collection, methods=["GET", "POST"])
    router.add_api_route("/{session_id}/schematics/{diagram_id}/devices", create_schematic_device, methods=["POST"])
    return router
