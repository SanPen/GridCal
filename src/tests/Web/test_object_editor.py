"""Integration checks for engine-driven editing through the web gateway."""
from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridServer.endpoints import circuits, interactive_calculations
from VeraGridServer.endpoints.file_management import verify_api_key_header
from VeraGridServer.endpoints.objects import create_objects_router
from VeraGridServer.interactive import WebSessionManager
from VeraGridServer.settings import settings
from VeraGridWeb.main import app as gateway
from VeraGridWeb.settings import WebGatewaySettingsRegistry


@pytest.fixture
def anyio_backend() -> str:
    """Use the installed asyncio backend for gateway integration.

    :return: Async backend name.
    """
    return "asyncio"


@pytest.fixture
def editor_client() -> Generator[TestClient, None, None]:
    """Build an isolated server using real engine models and authenticated routes.

    :return: Local API client.
    """
    previous_password: str = settings.this_password
    settings.this_password = "editor-test-key"
    server: FastAPI = FastAPI()
    server.state.circuit_sessions = WebSessionManager()
    server.include_router(circuits.router, dependencies=[Depends(verify_api_key_header)])
    server.include_router(interactive_calculations.router, dependencies=[Depends(verify_api_key_header)])
    server.include_router(create_objects_router(), dependencies=[Depends(verify_api_key_header)])
    client: TestClient = TestClient(server, headers={"API-Key": "editor-test-key"})
    try:
        yield client
    finally:
        server.state.circuit_sessions.clear()
        settings.this_password = previous_password
        client.close()


def create_test_session(client: TestClient) -> tuple[str, MultiCircuit]:
    """Create two buses and a load to exercise object identity and references.

    :param client: Isolated server client.
    :return: Session identifier and actual server circuit.
    """
    circuit: MultiCircuit = MultiCircuit(name="Editor round trip")
    circuit.add_bus(Bus(name="First", latitude=28.1, longitude=-15.4))
    circuit.add_bus(Bus(name="Second"))
    circuit.add_load(bus=circuit.buses[0], api_obj=Load(name="Demand", P=10.0))
    session: Any = client.app.state.circuit_sessions.create_session(circuit=circuit)
    return session.get_session_id(), circuit


def test_engine_collections_and_empty_schemas(editor_client: TestClient) -> None:
    """Expose every engine collection without a frontend equipment whitelist.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(client=editor_client)
    response: httpx.Response = editor_client.get(f"/api/circuits/{session_id}/object-types")
    assert response.status_code == 200
    collections: list[dict[str, Any]] = response.json()["collections"]
    assert len(collections) == len(circuit.get_template_objects_list())
    collection: dict[str, Any]
    for collection in collections:
        response = editor_client.get(f'/api/circuits/{session_id}/objects/{collection["name"]}')
        assert response.status_code == 200, collection["name"]
        assert response.json()["columns"], collection["name"]
    response = editor_client.get(f"/api/circuits/{session_id}/objects/BusDevice?query=First")
    assert response.json()["total"] == 1
    assert response.json()["rows"][0]["idtag"] == circuit.buses[0].idtag
    assert editor_client.get(f"/api/circuits/{session_id}/objects/Unknown").status_code == 404


def test_complete_collection_keeps_insertion_order(editor_client: TestClient) -> None:
    """Return every row and keep new objects after existing objects.

    :param editor_client: Isolated API client.
    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit(name="Continuous table")
    index: int
    for index in range(550):
        circuit.add_bus(Bus(name=f"Z bus {index}"))
    session: Any = editor_client.app.state.circuit_sessions.create_session(circuit=circuit)
    url: str = f"/api/circuits/{session.get_session_id()}/objects/BusDevice"
    response: httpx.Response = editor_client.post(url, json=dict(revision=0))
    assert response.status_code == 200
    created_id: str = response.json()["idtag"]
    table: dict[str, Any] = editor_client.get(url).json()
    assert table["total"] == 551
    assert len(table["rows"]) == 551
    assert table["rows"][0]["values"]["name"] == "Z bus 0"
    assert table["rows"][549]["values"]["name"] == "Z bus 549"
    assert table["rows"][-1]["idtag"] == created_id


def test_create_every_engine_collection(editor_client: TestClient) -> None:
    """Create and read defaults through the same engine paths used by Qt.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str = editor_client.post("/api/circuits/new", json=dict(name="Defaults")).json()["session_id"]
    collections: list[dict[str, Any]] = editor_client.get(f"/api/circuits/{session_id}/object-types").json()["collections"]
    revision: int = 0
    collection: dict[str, Any]
    for collection in collections:
        url: str = f'/api/circuits/{session_id}/objects/{collection["name"]}'
        response: httpx.Response = editor_client.post(url, json=dict(revision=revision))
        assert response.status_code == 200, collection["name"]
        revision = response.json()["revision"]
        response = editor_client.get(url)
        assert response.status_code == 200, collection["name"]
        assert response.json()["total"] >= 1, collection["name"]
    assert editor_client.get(f"/api/circuits/{session_id}/diagrams/schematic").status_code == 200
    assert editor_client.get(f"/api/circuits/{session_id}/diagrams/map").status_code == 200


def test_typed_edits_references_and_stale_revisions(editor_client: TestClient) -> None:
    """Use engine setters and real reference objects, rejecting stale batches.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(client=editor_client)
    url: str = f"/api/circuits/{session_id}/objects/BusDevice"
    response: httpx.Response = editor_client.patch(url, json=dict(revision=0, edits=[
        dict(idtag=circuit.buses[0].idtag, property="name", value="<edited>"),
        dict(idtag=circuit.buses[0].idtag, property="Vnom", value=132.0),
        dict(idtag=circuit.buses[0].idtag, property="active", value=False)]))
    assert response.status_code == 200, response.text
    assert circuit.buses[0].name == "<edited>"
    assert circuit.buses[0].Vnom == 132.0
    assert circuit.buses[0].active is False
    assert editor_client.patch(url, json=dict(revision=0, edits=[
        dict(idtag=circuit.buses[0].idtag, property="name", value="stale")])).status_code == 409
    assert circuit.buses[0].name == "<edited>"
    response = editor_client.patch(f"/api/circuits/{session_id}/objects/LoadDevice", json=dict(revision=1, edits=[
        dict(idtag=circuit.loads[0].idtag, property="bus", value=circuit.buses[1].idtag)]))
    # Match Qt: an already assigned bus may be read-only in engine metadata.
    if response.status_code == 200:
        assert circuit.loads[0].bus is circuit.buses[1]
    else:
        assert response.status_code == 422
        assert circuit.loads[0].bus is circuit.buses[0]
    table: dict[str, Any] = editor_client.get(url).json()
    columns: dict[str, Any] = dict((column["name"], column) for column in table["columns"])
    enum_column: Any = next((column for column in table["columns"] if column["kind"] == "enum"), None)
    assert enum_column is not None
    choice: str = enum_column["choices"][-1]["value"]
    response = editor_client.patch(url, json=dict(revision=table["revision"], edits=[
        dict(idtag=circuit.buses[0].idtag, property=enum_column["name"], value=choice)]))
    assert response.status_code == 200, response.text
    assert circuit.buses[0].get_value(circuit.buses[0].registered_properties[enum_column["name"]], None).name == choice
    assert columns["idtag"]["editable"] is False


def test_invalid_batch_leaves_model_unchanged(editor_client: TestClient) -> None:
    """Validate every cell before applying a batch and protect identifiers.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(client=editor_client)
    url: str = f"/api/circuits/{session_id}/objects/BusDevice"
    response: httpx.Response = editor_client.patch(url, json=dict(revision=0, edits=[
        dict(idtag=circuit.buses[0].idtag, property="name", value="must not commit"),
        dict(idtag=circuit.buses[0].idtag, property="active", value="false")]))
    assert response.status_code == 422
    assert editor_client.patch(url, content="{", headers={"Content-Type": "application/json"}).status_code == 422
    assert editor_client.patch(url, json=dict(revision=True, edits=[
        dict(idtag=circuit.buses[0].idtag, property="name", value="invalid revision")])).status_code == 422
    assert circuit.buses[0].name == "First"
    assert editor_client.get(url).json()["revision"] == 0
    assert editor_client.patch(url, json=dict(revision=0, edits=[
        dict(idtag=circuit.buses[0].idtag, property="idtag", value="changed")])).status_code == 422
    assert editor_client.patch(url, json=dict(revision=0, edits=[
        dict(idtag=circuit.buses[0].idtag, property="area", value="foreign-model-id")])).status_code == 422
    assert editor_client.get(url, headers={"API-Key": "wrong"}).status_code == 403


def test_pointer_constraints_and_engine_rejection(editor_client: TestClient) -> None:
    """Keep pointer choices consistent with Qt and restore accepted prior cells.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(client=editor_client)
    response: httpx.Response = editor_client.post(f"/api/circuits/{session_id}/objects/GeneratorDevice", json=dict(revision=0))
    assert response.status_code == 200
    generator_id: str = response.json()["idtag"]
    url: str = f"/api/circuits/{session_id}/objects/ContingencyDevice"
    response = editor_client.post(url, json=dict(revision=1))
    assert response.status_code == 200
    contingency_id: str = response.json()["idtag"]
    table: dict[str, Any] = editor_client.get(url).json()
    column: dict[str, Any] = next(column for column in table["columns"] if column["name"] == "device")
    choices: set[str] = set(choice["value"] for choice in column["choices"])
    assert generator_id in choices
    assert circuit.loads[0].idtag not in choices
    assert circuit.buses[0].idtag not in choices
    response = editor_client.patch(url, json=dict(revision=2, edits=[
        dict(idtag=contingency_id, property="device", value=circuit.loads[0].idtag)]))
    assert response.status_code == 422
    response = editor_client.patch(url, json=dict(revision=2, edits=[
        dict(idtag=contingency_id, property="device", value=generator_id)]))
    assert response.status_code == 200
    previous_name: str = circuit.contingencies[0].name
    response = editor_client.patch(url, json=dict(revision=3, edits=[
        dict(idtag=contingency_id, property="name", value="must roll back"),
        dict(idtag=contingency_id, property="device", value=None)]))
    assert response.status_code == 422, response.text
    assert circuit.contingencies[0].name == previous_name
    assert circuit.contingencies[0].device is circuit.generators[0]
    assert editor_client.get(url).json()["revision"] == 3


def test_model_edit_discards_completed_results(editor_client: TestClient) -> None:
    """Prevent a completed study from being reused after electrical model changes.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str = editor_client.post("/api/circuits/demo/ieee14").json()["session_id"]
    response: httpx.Response = editor_client.post(f"/api/calculations/{session_id}/run",
                                                 json=dict(simulation_type="PowerFlow_run"))
    assert response.status_code == 200, response.text
    session: Any = editor_client.app.state.circuit_sessions.get_session(session_id)
    assert session.get_worker().wait(timeout=10.0)
    assert editor_client.get(f"/api/calculations/{session_id}/results").status_code == 200
    response = editor_client.patch(f"/api/circuits/{session_id}/objects/BusDevice", json=dict(revision=0, edits=[
        dict(idtag=session.get_circuit().buses[0].idtag, property="name", value="Edited after study")]))
    assert response.status_code == 200
    assert editor_client.get(f"/api/calculations/{session_id}/status").json()["status"] == "IDLE"
    assert editor_client.get(f"/api/calculations/{session_id}/results").status_code == 404


def test_create_connect_position_and_export(editor_client: TestClient, tmp_path: Path) -> None:
    """Round-trip table edits, engine references and diagram coordinates.

    :param editor_client: Isolated API client.
    :param tmp_path: Temporary archive directory.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(client=editor_client)
    response: httpx.Response = editor_client.post(f"/api/circuits/{session_id}/objects/LineDevice", json=dict(revision=0))
    assert response.status_code == 200, response.text
    line_id: str = response.json()["idtag"]
    assert len(circuit.lines) == 1
    assert editor_client.get(f"/api/circuits/{session_id}/diagrams/schematic").status_code == 200
    response = editor_client.patch(f"/api/circuits/{session_id}/objects/LineDevice", json=dict(revision=1, edits=[
        dict(idtag=line_id, property="bus_from", value=circuit.buses[0].idtag),
        dict(idtag=line_id, property="bus_to", value=circuit.buses[1].idtag),
        dict(idtag=line_id, property="R", value=0.0123456789)]))
    assert response.status_code == 200, response.text
    assert circuit.lines[0].bus_from is circuit.buses[0]
    response = editor_client.patch(f"/api/circuits/{session_id}/diagrams/schematic/{circuit.buses[0].idtag}",
                                   json=dict(revision=2, x=345.25, y=678.5))
    assert response.status_code == 200, response.text
    response = editor_client.patch(f"/api/circuits/{session_id}/objects/BusDevice", json=dict(revision=3, edits=[
        dict(idtag=circuit.buses[0].idtag, property="latitude", value=29.2),
        dict(idtag=circuit.buses[0].idtag, property="longitude", value=-16.3)]))
    assert response.status_code == 200
    geojson: dict[str, Any] = editor_client.get(f"/api/circuits/{session_id}/diagrams/map").json()
    assert geojson["features"][0]["geometry"]["coordinates"] == [-16.3, 29.2]
    response = editor_client.get(f"/api/circuits/{session_id}/export")
    assert response.status_code == 200
    archive: Path = tmp_path / "edited.veragrid"
    archive.write_bytes(response.content)
    restored: MultiCircuit = FileOpen(file_name=str(archive)).open()
    assert restored.lines[0].R == 0.0123456789
    assert restored.lines[0].bus_from is restored.buses[0]
    assert restored.buses[0].latitude == 29.2
    assert restored.diagrams[0].query_point(restored.buses[0]).x == 345.25
    assert restored.diagrams[0].query_point(restored.buses[0]).y == 678.5


@pytest.mark.anyio
async def test_gateway_uses_server_model(editor_client: TestClient) -> None:
    """Forward real HTTP edits to the server instead of keeping a gateway copy.

    :param editor_client: Isolated server client.
    :return: None.
    """
    previous_client: Any = gateway.state._state.get("http_client", None)
    gateway_settings: Any = WebGatewaySettingsRegistry.get_settings()
    previous_key: str = gateway_settings.server_api_key
    gateway_settings.server_api_key = "editor-test-key"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=editor_client.app)) as server_http:
        gateway.state.http_client = server_http
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url="http://web") as browser:
                response: httpx.Response = await browser.post("/api/circuits/new", json=dict(name="Remote"), headers={"api-key": "untrusted-browser-key"})
                assert response.status_code == 200, response.text
                session_id: str = response.json()["session_id"]
                response = await browser.post(f"/api/circuits/{session_id}/objects/BusDevice", json=dict(revision=0))
                assert response.status_code == 200
                idtag: str = response.json()["idtag"]
                response = await browser.patch(f"/api/circuits/{session_id}/objects/BusDevice", json=dict(revision=1, edits=[
                    dict(idtag=idtag, property="name", value="Server bus")]))
                assert response.status_code == 200
                session: Any = editor_client.app.state.circuit_sessions.get_session(session_id)
                assert session.get_circuit().buses[0].name == "Server bus"
                assert "circuit_sessions" not in gateway.state._state
                assert not any(route.path == "/api/circuits/new" for route in gateway.routes)
        finally:
            gateway.state.http_client = previous_client
            gateway_settings.server_api_key = previous_key


def test_independent_schematics_create_real_equipment(editor_client: TestClient, tmp_path: Path) -> None:
    """Keep layouts independent while graphical gestures mutate the shared engine model.

    :param editor_client: Isolated API client.
    :param tmp_path: Temporary export directory.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(editor_client)
    base: str = f"/api/circuits/{session_id}"
    result: httpx.Response = editor_client.post(f"{base}/schematics", json=dict(
        revision=0, name="Whole grid", include_existing=True))
    assert result.status_code == 200, result.text
    first: str = result.json()["created_id"]
    result = editor_client.post(f"{base}/schematics", json=dict(revision=1, name="New feeder"))
    assert result.status_code == 200, result.text
    second: str = result.json()["created_id"]
    assert len(circuit.diagrams) == 2
    assert editor_client.get(f"{base}/diagrams/schematic", params=dict(diagram_id=second)).json()["nodes"] == []
    result = editor_client.post(f"{base}/schematics/{second}/devices", json=dict(
        revision=2, device_type="BusDevice", x=200, y=300))
    assert result.status_code == 200, result.text
    first_bus: str = result.json()["idtag"]
    result = editor_client.post(f"{base}/schematics/{second}/devices", json=dict(
        revision=3, device_type="BusDevice", x=500, y=300))
    second_bus: str = result.json()["idtag"]
    # Reject stale and invalid terminals before creating any electrical equipment.
    assert editor_client.post(f"{base}/schematics/{second}/devices", json=dict(
        revision=3, device_type="LineDevice", bus=first_bus, to_bus=second_bus, x=0, y=0)).status_code == 409
    assert editor_client.post(f"{base}/schematics/{second}/devices", json=dict(
        revision=4, device_type="LineDevice", bus=first_bus, to_bus=first_bus, x=0, y=0)).status_code == 422
    assert editor_client.post(f"{base}/schematics/{second}/devices", json=dict(
        revision=4, device_type="LoadDevice", bus=circuit.buses[0].idtag, x=0, y=0)).status_code == 422
    assert len(circuit.lines) == 0
    result = editor_client.post(f"{base}/schematics/{second}/devices", json=dict(
        revision=4, device_type="LineDevice", bus=first_bus, to_bus=second_bus, x=0, y=0))
    assert result.status_code == 200, result.text
    line_id: str = result.json()["idtag"]
    assert circuit.lines[0].bus_from.idtag == first_bus
    assert circuit.lines[0].bus_to.idtag == second_bus
    result = editor_client.patch(f"{base}/diagrams/schematic/{line_id}", json=dict(
        revision=5, diagram_id=second, x=0, y=0, vertices=[[250, 310], [480, 310]]))
    assert result.status_code == 200
    diagram: dict[str, Any] = editor_client.get(f"{base}/diagrams/schematic", params=dict(diagram_id=second)).json()
    assert len(diagram["nodes"]) == 2 and len(diagram["branches"]) == 1
    assert diagram["branches"][0]["vertices"] == [[250, 310], [480, 310]]
    diagram = editor_client.get(f"{base}/diagrams/schematic", params=dict(diagram_id=first)).json()
    assert len(diagram["nodes"]) == 2 and len(diagram["injections"]) == 1
    assert not diagram["branches"]
    assert len(circuit.buses) == 4
    assert editor_client.get(f"{base}/diagrams/schematic", params=dict(diagram_id="missing")).status_code == 404
    archive: Path = tmp_path / "multiple-views.veragrid"
    archive.write_bytes(editor_client.get(f"{base}/export").content)
    restored: MultiCircuit = FileOpen(file_name=str(archive)).open()
    assert len(restored.diagrams) == 2
    assert restored.diagrams[1].query_point(restored.lines[0]).poly_line == [[250, 310], [480, 310]]


def test_shared_bus_layouts_and_invalid_route_edits(editor_client: TestClient) -> None:
    """Move shared equipment in one view without changing another view or accepting invalid routes.

    :param editor_client: Isolated API client.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(editor_client)
    base: str = f"/api/circuits/{session_id}"
    first: str = editor_client.post(f"{base}/schematics", json=dict(
        revision=0, name="First", include_existing=True)).json()["created_id"]
    second: str = editor_client.post(f"{base}/schematics", json=dict(
        revision=1, name="Second", include_existing=True)).json()["created_id"]
    position_url: str = f"{base}/diagrams/schematic/{circuit.buses[0].idtag}"
    assert editor_client.patch(position_url, json=dict(revision=2, diagram_id=first, x=900, y=800,
                                                     vertices=[[1, "invalid"]])).status_code == 422
    assert editor_client.patch(position_url, json=dict(revision=2, diagram_id="missing", x=900, y=800)).status_code == 404
    assert editor_client.patch(position_url, json=dict(revision=2, diagram_id=first, x=900, y=800)).status_code == 200
    assert circuit.diagrams[0].query_point(circuit.buses[0]).x == 900
    assert circuit.diagrams[1].query_point(circuit.buses[0]).x == 100
    assert editor_client.get(f"{base}/diagrams/schematic", params=dict(diagram_id=second)).json()["nodes"][0]["x"] == 100
    assert len(circuit.buses) == 2


def test_schematic_palette_devices_and_archive(editor_client: TestClient, tmp_path: Path) -> None:
    """Create every palette type through engine factories and preserve both layouts in exports.

    :param editor_client: Isolated API client.
    :param tmp_path: Temporary export directory.
    :return: None.
    """
    session_id: str
    circuit: MultiCircuit
    session_id, circuit = create_test_session(editor_client)
    base: str = f"/api/circuits/{session_id}"
    result: dict[str, Any] = editor_client.post(f"{base}/schematics", json=dict(
        revision=0, name="Palette", include_existing=True)).json()
    diagram_id: str = result["created_id"]
    revision: int = result["revision"]
    circuit.buses[0].Vnom = 132
    circuit.buses[1].Vnom = 33
    device_type: str
    for device_type in ("LineDevice", "Transformer2WDevice", "SwitchDevice", "DCLineDevice", "HVDCLineDevice",
                        "GeneratorDevice", "LoadDevice", "BatteryDevice", "ShuntDevice"):
        response: httpx.Response = editor_client.post(f"{base}/schematics/{diagram_id}/devices", json=dict(
            revision=revision, device_type=device_type, bus=circuit.buses[0].idtag,
            to_bus=circuit.buses[1].idtag, x=120, y=230))
        assert response.status_code == 200, response.text
        revision = response.json()["revision"]
    diagram: dict[str, Any] = editor_client.get(f"{base}/diagrams/schematic", params=dict(diagram_id=diagram_id)).json()
    assert len(diagram["branches"]) == 5
    assert len(diagram["injections"]) == 5
    assert circuit.transformers2w[0].HV == 132
    assert circuit.transformers2w[0].LV == 33
    archive: Path = tmp_path / "schematic.veragrid"
    archive.write_bytes(editor_client.get(f"{base}/export").content)
    restored: MultiCircuit = FileOpen(file_name=str(archive)).open()
    assert len(restored.diagrams) == 1
    assert len(restored.hvdc_lines) == 1
    assert restored.diagrams[0].query_point(restored.batteries[0]).x == 120
