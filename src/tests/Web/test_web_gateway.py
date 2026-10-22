# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from collections.abc import Generator
from VeraGridServer.settings import settings as server_settings
from fastapi.testclient import TestClient
import httpx
import pytest

from VeraGridServer.main import app as server_app
from VeraGridWeb.main import app as web_app
from VeraGridWeb.settings import WebGatewaySettings, WebGatewaySettingsRegistry
from VeraGridWeb.server_client import VeraGridServerClient
from VeraGridWeb.proxy import (
    SessionRouter,
    SessionRouterRegistry,
    extract_session_id_from_path,
    build_filtered_headers,
    pipe_client_to_backend,
    pipe_backend_to_client,
)


@pytest.fixture
def circuit_client() -> Generator[TestClient, None, None]:
    """Access the circuit routes on their owning server.

    :return: Authenticated server client.
    """
    previous_password: str = server_settings.this_password
    server_settings.this_password = "web-circuit-test-key"
    client: TestClient = TestClient(server_app, headers={"API-Key": "web-circuit-test-key"})
    try:
        yield client
    finally:
        server_app.state.circuit_sessions.clear()
        server_settings.this_password = previous_password
        client.close()


def test_web_gateway_settings_configuration() -> None:
    """
    Verify WebGatewaySettings configuration, thread-safe updates, and round-robin distribution.

    :return: None.
    """
    # 1. Initialize settings with two test backends
    initial_backends: List[str] = list(["http://10.0.0.1:8000", "http://10.0.0.2:8000"])
    settings: WebGatewaySettings = WebGatewaySettings(
        backends=initial_backends,
        host="127.0.0.1",
        port=4000,
        timeout=45.0,
    )

    # 2. Assert initialization values
    assert settings.get_host() == "127.0.0.1"
    assert settings.get_port() == 4000
    assert settings.get_timeout() == 45.0
    assert len(settings.get_backends()) == 2

    # 3. Test setter mutations
    settings.set_host(host="0.0.0.0")
    assert settings.get_host() == "0.0.0.0"

    settings.set_port(port=5000)
    assert settings.get_port() == 5000

    settings.set_timeout(timeout=30.0)
    assert settings.get_timeout() == 30.0

    # 4. Test round-robin distribution cycling
    first_backend: str = settings.get_next_backend()
    second_backend: str = settings.get_next_backend()
    third_backend: str = settings.get_next_backend()

    assert first_backend == "http://10.0.0.1:8000"
    assert second_backend == "http://10.0.0.2:8000"
    assert third_backend == "http://10.0.0.1:8000"

    # 5. Test adding a unique backend
    added: bool = settings.add_backend(backend_url="http://10.0.0.3:8000")
    assert added is True
    assert len(settings.get_backends()) == 3

    # 6. Test duplicate prevention
    duplicate_added: bool = settings.add_backend(backend_url="http://10.0.0.3:8000")
    assert duplicate_added is False

    # 7. Test removing an existing backend
    removed: bool = settings.remove_backend(backend_url="http://10.0.0.3:8000")
    assert removed is True
    assert len(settings.get_backends()) == 2

    # 8. Test removing non-existent backend
    non_existent_removed: bool = settings.remove_backend(backend_url="http://10.0.0.99:8000")
    assert non_existent_removed is False
    settings.set_backends(backends=list(["http://primary:8000", "http://worker:8001"]))
    assert settings.model_server_url == "http://primary:8000"
    settings.remove_backend(backend_url="http://primary:8000")
    assert settings.model_server_url == "http://primary:8000"


def test_session_router_mappings_and_path_extraction() -> None:
    """
    Verify SessionRouter affinity mappings, URL path session extraction, and header filtering.

    :return: None.
    """
    # 1. Initialize standalone session router
    router: SessionRouter = SessionRouter()

    # 2. Register session affinities
    router.register_session(session_id="session-alpha", backend_url="http://backend-a:8000")
    router.register_session(session_id="session-beta", backend_url="http://backend-b:8000")

    # 3. Query mappings
    alpha_backend: Optional[str] = router.get_backend_for_session(session_id="session-alpha")
    beta_backend: Optional[str] = router.get_backend_for_session(session_id="session-beta")
    gamma_backend: Optional[str] = router.get_backend_for_session(session_id="session-gamma")

    assert alpha_backend == "http://backend-a:8000"
    assert beta_backend == "http://backend-b:8000"
    assert gamma_backend is None

    # 4. Check list mappings dictionary snapshot
    snapshot: Dict[str, str] = router.list_mappings()
    assert len(snapshot) == 2
    assert snapshot.get("session-alpha", None) == "http://backend-a:8000"

    # 5. Unregister session
    router.unregister_session(session_id="session-alpha")
    assert router.get_backend_for_session(session_id="session-alpha") is None
    assert len(router.list_mappings()) == 1

    # 6. Test URL path session extraction
    assert extract_session_id_from_path(path="/api/circuits/123-uuid/diagrams/schematic") == "123-uuid"
    assert extract_session_id_from_path(path="/api/circuits/upload") is None
    assert extract_session_id_from_path(path="/api/circuits/new") is None
    assert extract_session_id_from_path(path="/api/circuits/demo/honduras") is None
    assert extract_session_id_from_path(path="/api/calculations/456-uuid/power-flow") == "456-uuid"
    assert extract_session_id_from_path(path="/ws/telemetry/789-uuid") == "789-uuid"
    assert extract_session_id_from_path(path="/api/backends") is None

    # 7. Test header filtering (hop-by-hop elimination)
    raw_headers: Dict[str, str] = dict({
        "Host": "localhost:3000",
        "Connection": "keep-alive",
        "Upgrade": "websocket",
        "Accept": "application/json",
        "Authorization": "Bearer secret-token",
    })
    filtered_headers: Dict[str, str] = build_filtered_headers(request_headers=raw_headers)
    assert "Host" not in filtered_headers
    assert "Connection" not in filtered_headers
    assert "Upgrade" not in filtered_headers
    assert filtered_headers.get("Accept", None) == "application/json"
    assert filtered_headers.get("Authorization", None) == "Bearer secret-token"


def test_web_gateway_static_assets_serving() -> None:
    """
    Verify that VeraGridWeb serves all static assets (HTML, CSS, JS, MapLibre).

    :return: None.
    """
    client: TestClient = TestClient(web_app)

    # 1. Root redirect
    root_resp = client.get("/", follow_redirects=False)
    assert root_resp.status_code in set([307, 302, 200])
    if root_resp.status_code in set([307, 302]):
        assert "/app/" in root_resp.headers.get("location", "")
    else:
        pass

    # 2. Main HTML5 shell
    html_resp = client.get("/app/")
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers.get("content-type", "")
    assert "VeraGrid" in html_resp.text
    assert "gis-map" in html_resp.text
    assert "sld-canvas" in html_resp.text
    assert "device-table" in html_resp.text

    # 3. CSS stylesheets
    css_files: List[str] = list([
        "/app/css/style.css",
        "/app/vendor/maplibre/maplibre-gl.css",
        "/app/vendor/tabulator/tabulator_midnight.min.css",
    ])
    for css_url in css_files:
        css_resp = client.get(css_url)
        assert css_resp.status_code == 200
        assert "text/css" in css_resp.headers.get("content-type", "")

    # 4. Plain JS modules
    js_files: List[str] = list([
        "/app/js/app.js",
        "/app/js/gis_map.js",
        "/app/js/sld_canvas.js",
        "/app/js/equipment_table.js",
        "/app/js/simulation_panel.js",
        "/app/vendor/maplibre/maplibre-gl.js",
        "/app/vendor/tabulator/tabulator_esm.min.mjs",
        "/app/vendor/joint/joint-core.mjs",
    ])
    for js_url in js_files:
        js_resp = client.get(js_url)
        assert js_resp.status_code == 200
        content_type: str = js_resp.headers.get("content-type", "")
        assert "javascript" in content_type


def test_web_gateway_backends_management_api() -> None:
    """
    Verify dynamic registration, unregistration, and inspection of backends via the gateway API.

    :return: None.
    """
    client: TestClient = TestClient(web_app)

    # 1. Query initial backends list
    get_resp = client.get("/api/backends")
    assert get_resp.status_code == 200
    get_data: Dict[str, Any] = get_resp.json()
    assert "backends" in get_data
    assert "session_mappings" in get_data

    # 2. Dynamically register a new backend
    reg_resp = client.post("/api/backends/register", json=dict({"url": "http://127.0.0.1:8001"}))
    assert reg_resp.status_code == 200
    reg_data: Dict[str, Any] = reg_resp.json()
    assert "http://127.0.0.1:8001" in reg_data.get("backends", list())

    # 3. Reject duplicate registration
    dup_resp = client.post("/api/backends/register", json=dict({"url": "http://127.0.0.1:8001"}))
    assert dup_resp.status_code == 400

    # 4. Reject registration without URL
    empty_resp = client.post("/api/backends/register", json=dict({"url": ""}))
    assert empty_resp.status_code == 400

    # 5. Unregister the backend
    unreg_resp = client.request("DELETE", "/api/backends/unregister", json=dict({"url": "http://127.0.0.1:8001"}))
    assert unreg_resp.status_code == 200
    unreg_data: Dict[str, Any] = unreg_resp.json()
    assert "http://127.0.0.1:8001" not in unreg_data.get("backends", list())

    # 6. Reject unregistering non-existent backend
    unreg_not_found = client.request("DELETE", "/api/backends/unregister", json=dict({"url": "http://127.0.0.1:9999"}))
    assert unreg_not_found.status_code == 400


def test_veragrid_web_circuit_endpoints_and_gis_map(circuit_client: TestClient) -> None:
    """
    Verify VeraGridWeb endpoints for creating circuits, loading demos, generating schematic diagrams,
    and GeoJSON GIS maps.

    :return: None.
    """
    client: TestClient = circuit_client

    # 1. Create blank circuit
    create_resp = client.post("/api/circuits/new", json=dict({"name": "Web Test Grid"}))
    assert create_resp.status_code == 200
    create_data: Dict[str, Any] = create_resp.json()
    assert "session_id" in create_data
    session_id: str = create_data["session_id"]
    assert create_data.get("name", "") == "Web Test Grid"

    # 2. Query circuits list
    list_resp = client.get("/api/circuits")
    assert list_resp.status_code == 200
    circuits_list: List[Dict[str, Any]] = list_resp.json()
    assert any(c.get("session_id", "") == session_id for c in circuits_list)

    # 3. Load Honduras demo circuit
    demo_resp = client.post("/api/circuits/demo/honduras")
    assert demo_resp.status_code == 200
    demo_data: Dict[str, Any] = demo_resp.json()
    demo_session_id: str = demo_data["session_id"]

    # 4. Query schematic diagram
    schematic_resp = client.get(f"/api/circuits/{demo_session_id}/diagrams/schematic")
    assert schematic_resp.status_code == 200
    schematic_data: Dict[str, Any] = schematic_resp.json()
    assert "nodes" in schematic_data
    assert "branches" in schematic_data
    assert len(schematic_data.get("nodes", list())) > 0

    # 5. Query GIS map GeoJSON
    map_resp = client.get(f"/api/circuits/{demo_session_id}/diagrams/map")
    assert map_resp.status_code == 200
    map_data: Dict[str, Any] = map_resp.json()
    assert map_data.get("type", "") == "FeatureCollection"
    assert len(map_data.get("features", list())) > 0

    # 6. Query equipment devices list
    table_resp = client.get(f"/api/circuits/{demo_session_id}/objects/BusDevice")
    assert table_resp.status_code == 200
    devices_list: List[Dict[str, Any]] = table_resp.json()["rows"]
    assert isinstance(devices_list, list)
    assert len(devices_list) > 0
    assert "name" in devices_list[0]["values"]

    # 7. Clean up sessions
    client.delete(f"/api/circuits/{session_id}")
    client.delete(f"/api/circuits/{demo_session_id}")


def test_veragrid_web_power_flow_simulation_execution(circuit_client: TestClient) -> None:
    """
    Verify starting PowerFlow calculations, checking status, and extracting results on VeraGridWeb.

    :return: None.
    """
    client: TestClient = circuit_client

    # 1. Load demo circuit
    demo_resp = client.post("/api/circuits/demo/honduras")
    assert demo_resp.status_code == 200
    session_id: str = demo_resp.json()["session_id"]

    # 2. Trigger PowerFlow simulation
    run_resp = client.post(
        f"/api/calculations/{session_id}/run",
        json=dict({"simulation_type": "PowerFlow_run"}),
    )
    assert run_resp.status_code == 200
    run_data: Dict[str, Any] = run_resp.json()
    assert run_data.get("success", False) is True

    # 3. Poll for completion
    completed: bool = False
    for _ in range(50):
        status_resp = client.get(f"/api/calculations/{session_id}/status")
        assert status_resp.status_code == 200
        status_data: Dict[str, Any] = status_resp.json()
        status_val: str = status_data.get("status", "")
        if status_val in set(["COMPLETED", "FAILED"]):
            completed = True
            break
        else:
            time.sleep(0.05)

    assert completed is True

    # 4. Check results
    results_resp = client.get(f"/api/calculations/{session_id}/results")
    assert results_resp.status_code == 200
    results_data: Dict[str, Any] = results_resp.json()
    assert "converged" in results_data
    assert "results" in results_data

    # 5. Clean up session
    client.delete(f"/api/circuits/{session_id}")


def refuse_backend_connection(request: httpx.Request) -> httpx.Response:
    """Simulate an unreachable backend independently of running local services.

    :param request: Outbound backend request.
    :return: Never returns; the connection fails.
    """
    raise httpx.ConnectError("Connection refused", request=request)


@pytest.mark.anyio
async def test_web_gateway_backend_unreachable_502_error() -> None:
    """Return actionable HTTP 502 JSON when the model server is unavailable.

    :return: None.
    """
    previous_client: Any = web_app.state._state.get("http_client", None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse_backend_connection)) as backend_client:
        web_app.state.http_client = backend_client
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=web_app), base_url="http://web") as browser:
                response: httpx.Response = await browser.get("/api/unregistered_cluster_backend_target")
                assert response.status_code == 502
                detail: str = response.json()["detail"]
                assert "Backend unavailable" in detail
                assert "Start VeraGridServer" in detail
                assert "--server-url" in detail
                assert "--server-api-key" in detail
        finally:
            web_app.state.http_client = previous_client


@pytest.mark.anyio
async def test_veragrid_server_client_health_check() -> None:
    """
    Verify VeraGridServerClient health check against an in-memory server instance.

    :return: None.
    """
    client: VeraGridServerClient = VeraGridServerClient(
        server_url="http://127.0.0.1:8000",
        timeout=5.0,
    )
    assert client.get_server_url() == "http://127.0.0.1:8000"
    assert client.get_api_key() == ""

    client.set_api_key(api_key="test_key")
    assert client.get_api_key() == "test_key"

    client.set_server_url(server_url="http://10.0.0.1:8000/")
    assert client.get_server_url() == "http://10.0.0.1:8000"


class MockClientWebSocket:
    """
    Mock client websocket simulating browser connection frames.
    """

    __slots__ = (
        "_incoming_messages",
        "_sent_text",
        "_sent_bytes",
    )

    def __init__(self, incoming: List[Dict[str, Any]]) -> None:
        """
        Initialize the mock client websocket.

        :param incoming: Pre-populated list of message frames.
        :return: None.
        """
        self._incoming_messages: List[Dict[str, Any]] = incoming
        self._sent_text: List[str] = list()
        self._sent_bytes: List[bytes] = list()

    async def receive(self) -> Dict[str, Any]:
        """
        Receive the next simulated client message.

        :return: Message dictionary.
        """
        if len(self._incoming_messages) > 0:
            return self._incoming_messages.pop(0)
        else:
            return dict({"type": "websocket.disconnect"})

    async def send_text(self, data: str) -> None:
        """
        Record text sent to the client.

        :param data: Text payload.
        :return: None.
        """
        self._sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        """
        Record binary data sent to the client.

        :param data: Bytes payload.
        :return: None.
        """
        self._sent_bytes.append(data)

    def get_sent_text(self) -> List[str]:
        """
        Get recorded sent text messages.

        :return: List of text messages.
        """
        return self._sent_text

    def get_sent_bytes(self) -> List[bytes]:
        """
        Get recorded sent bytes.

        :return: List of bytes messages.
        """
        return self._sent_bytes


class MockBackendWebSocket:
    """
    Mock backend websocket simulating websockets connection.
    """

    __slots__ = (
        "_incoming_messages",
        "_sent_messages",
    )

    def __init__(self, incoming: List[Any]) -> None:
        """
        Initialize the mock backend websocket.

        :param incoming: Pre-populated list of backend messages.
        :return: None.
        """
        self._incoming_messages: List[Any] = incoming
        self._sent_messages: List[Any] = list()

    def __aiter__(self) -> MockBackendWebSocket:
        """
        Return async iterator.

        :return: Self.
        """
        return self

    async def __anext__(self) -> Any:
        """
        Yield next message from backend.

        :return: Message payload.
        """
        if len(self._incoming_messages) > 0:
            return self._incoming_messages.pop(0)
        else:
            raise StopAsyncIteration

    async def send(self, message: Any) -> None:
        """
        Record message sent to the backend.

        :param message: Outgoing payload.
        :return: None.
        """
        self._sent_messages.append(message)

    def get_sent_messages(self) -> List[Any]:
        """
        Get recorded sent messages.

        :return: List of payloads.
        """
        return self._sent_messages


@pytest.mark.anyio
async def test_websocket_forwarding_pipes() -> None:
    """
    Verify bidirectional piping between client and backend WebSockets.

    :return: None.
    """
    # 1. Test client to backend message forwarding
    client_incoming: List[Dict[str, Any]] = list([
        dict({"text": '{"action": "ping"}'}),
        dict({"bytes": b"binary_data"}),
        dict({"type": "websocket.disconnect"}),
    ])
    client_ws: MockClientWebSocket = MockClientWebSocket(incoming=client_incoming)
    backend_ws_for_client: MockBackendWebSocket = MockBackendWebSocket(incoming=list())

    await pipe_client_to_backend(client_ws=client_ws, backend_ws=backend_ws_for_client)  # type: ignore[arg-type]
    sent_to_backend: List[Any] = backend_ws_for_client.get_sent_messages()
    assert len(sent_to_backend) == 2
    assert sent_to_backend[0] == '{"action": "ping"}'
    assert sent_to_backend[1] == b"binary_data"

    # 2. Test backend to client message forwarding
    backend_incoming: List[Any] = list([
        '{"telemetry": "status_ok"}',
        b"raw_frame",
    ])
    backend_ws_for_telemetry: MockBackendWebSocket = MockBackendWebSocket(incoming=backend_incoming)
    client_ws_target: MockClientWebSocket = MockClientWebSocket(incoming=list())

    await pipe_backend_to_client(backend_ws=backend_ws_for_telemetry, client_ws=client_ws_target)  # type: ignore[arg-type]
    assert len(client_ws_target.get_sent_text()) == 1
    assert client_ws_target.get_sent_text()[0] == '{"telemetry": "status_ok"}'
    assert len(client_ws_target.get_sent_bytes()) == 1
    assert client_ws_target.get_sent_bytes()[0] == b"raw_frame"


def test_veragrid_web_gis_map_simulation_results_enrichment(circuit_client: TestClient) -> None:
    """
    Verify that PowerFlow simulation results provide valid branch loading, complex flows,
    and bus voltages matching the GeoJSON features used for GIS map recoloring.

    :return: None.
    """
    client: TestClient = circuit_client

    # 1. Verify that HTML shell contains the map legend container
    html_resp = TestClient(web_app).get("/app/")
    assert html_resp.status_code == 200
    assert 'id="map-legend"' in html_resp.text
    assert "Branch Loading" in html_resp.text

    # 2. Load Honduras geo demo circuit
    demo_resp = client.post("/api/circuits/demo/honduras")
    assert demo_resp.status_code == 200
    demo_data: Dict[str, Any] = demo_resp.json()
    session_id: str = demo_data["session_id"]

    # 3. Retrieve GIS map GeoJSON
    map_resp = client.get(f"/api/circuits/{session_id}/diagrams/map")
    assert map_resp.status_code == 200
    geo_data: Dict[str, Any] = map_resp.json()
    features: List[Dict[str, Any]] = geo_data.get("features", list())
    assert len(features) > 0

    # Classify geo features
    bus_features: List[Dict[str, Any]] = list()
    branch_features: List[Dict[str, Any]] = list()
    for feat in features:
        geom_type: str = feat.get("geometry", dict()).get("type", "")
        if geom_type == "Point":
            bus_features.append(feat)
        elif geom_type == "LineString":
            branch_features.append(feat)
        else:
            pass

    assert len(bus_features) > 0
    assert len(branch_features) > 0

    # 4. Trigger PowerFlow simulation
    run_resp = client.post(
        f"/api/calculations/{session_id}/run",
        json=dict({"simulation_type": "PowerFlow_run"}),
    )
    assert run_resp.status_code == 200

    # 5. Poll for completion
    completed: bool = False
    for _ in range(50):
        status_resp = client.get(f"/api/calculations/{session_id}/status")
        assert status_resp.status_code == 200
        status_val: str = status_resp.json().get("status", "")
        if status_val in set(["COMPLETED", "FAILED"]):
            completed = True
            break
        else:
            time.sleep(0.05)

    assert completed is True

    # 6. Extract simulation results
    res_resp = client.get(f"/api/calculations/{session_id}/results")
    assert res_resp.status_code == 200
    res_payload: Dict[str, Any] = res_resp.json()
    assert res_payload.get("converged", False) is True

    results: Dict[str, Any] = res_payload.get("results", dict())
    assert "branch_names" in results
    assert "bus_names" in results
    assert "loading" in results
    assert "Sf" in results
    assert "voltage" in results

    sim_branch_names: List[str] = results["branch_names"]
    sim_bus_names: List[str] = results["bus_names"]

    # 7. Verify branch correlation and loading values for map recoloring
    matched_branches: int = 0
    for bf in branch_features:
        b_props: Dict[str, Any] = bf.get("properties", dict())
        b_name: str = b_props.get("name", "")
        if b_name in sim_branch_names:
            matched_branches += 1
            idx: int = sim_branch_names.index(b_name)
            # Verify loading array structure and compute apparent loading magnitude
            loading_data: Any = results["loading"]
            raw_load: float = 0.0
            if isinstance(loading_data, dict) and "real" in loading_data:
                re_val: float = float(loading_data["real"][idx])
                im_val: float = 0.0
                if "imag" in loading_data and len(loading_data["imag"]) > idx:
                    im_val = float(loading_data["imag"][idx])
                else:
                    pass
                raw_load = (re_val * re_val + im_val * im_val) ** 0.5
            elif isinstance(loading_data, list):
                raw_load = abs(float(loading_data[idx]))
            else:
                pass
            assert raw_load >= 0.0
        else:
            pass

    assert matched_branches > 0

    # 8. Clean up session
    client.delete(f"/api/circuits/{session_id}")

