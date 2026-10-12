# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from fastapi.testclient import TestClient
import httpx
import pytest

from VeraGridWeb.cluster.node import NodeState, BackendNode
from VeraGridWeb.cluster.cluster_manager import (
    ClusterManager,
    ClusterManagerRegistry,
    DispatchStrategy,
    parse_strategy,
)
from VeraGridWeb.main import app as web_app


def test_backend_node_state_transitions_and_circuit_breaker() -> None:
    """
    Verify BackendNode state lifecycle, metric tracking, and circuit breaker tripping.

    :return: None.
    """
    # 1. Initialize fresh node
    node: BackendNode = BackendNode(url="http://10.0.0.1:8000")
    assert node.get_url() == "http://10.0.0.1:8000"
    assert node.get_state() == NodeState.ONLINE
    assert node.is_available() is True
    assert node.get_consecutive_failures() == 0
    assert node.get_active_sessions() == 0

    # 2. Record successful ping with low latency
    node.record_success(latency_ms=25.5)
    assert node.get_latency_ms() == 25.5
    assert node.get_state() == NodeState.ONLINE
    assert node.is_available() is True

    # 3. Record high latency ping causing degradation
    node.record_success(latency_ms=2100.0)
    assert node.get_state() == NodeState.DEGRADED
    assert node.is_available() is True

    # 4. Trigger failures up to threshold (default: 3)
    node.record_failure(error_msg="Connection timed out", failure_threshold=3)
    assert node.get_consecutive_failures() == 1
    assert node.get_state() == NodeState.DEGRADED

    node.record_failure(error_msg="Connection refused", failure_threshold=3)
    assert node.get_consecutive_failures() == 2
    assert node.get_state() == NodeState.DEGRADED

    # 3rd failure trips circuit breaker to OFFLINE
    node.record_failure(error_msg="Host unreachable", failure_threshold=3)
    assert node.get_consecutive_failures() == 3
    assert node.get_state() == NodeState.OFFLINE
    assert node.is_available() is False

    # 5. Recovery ping restores node to ONLINE
    node.record_success(latency_ms=18.2)
    assert node.get_consecutive_failures() == 0
    assert node.get_state() == NodeState.ONLINE
    assert node.is_available() is True

    # 6. Session tracking
    node.increment_sessions()
    node.increment_sessions()
    assert node.get_active_sessions() == 2
    node.decrement_sessions()
    assert node.get_active_sessions() == 1
    node.decrement_sessions()
    assert node.get_active_sessions() == 0
    node.decrement_sessions()
    assert node.get_active_sessions() == 0


def test_cluster_manager_node_management_and_draining() -> None:
    """
    Verify adding, removing, draining, and querying nodes in ClusterManager.

    :return: None.
    """
    initial_nodes: List[str] = list(["http://10.0.0.1:8000", "http://10.0.0.2:8000"])
    mgr: ClusterManager = ClusterManager(initial_backends=initial_nodes)

    # 1. Assert initial state
    assert len(mgr.list_nodes()) == 2
    assert mgr.get_node(url="http://10.0.0.1:8000") is not None
    assert mgr.get_node(url="http://10.0.0.2:8000") is not None
    assert mgr.get_node(url="http://10.0.0.99:8000") is None

    # 2. Add third node
    added: bool = mgr.add_node(url="http://10.0.0.3:8000")
    assert added is True
    assert len(mgr.list_nodes()) == 3

    # Duplicate rejected
    assert mgr.add_node(url="http://10.0.0.3:8000") is False

    # 3. Drain node
    drained: bool = mgr.drain_node(url="http://10.0.0.3:8000")
    assert drained is True
    drained_node: Optional[BackendNode] = mgr.get_node(url="http://10.0.0.3:8000")
    assert drained_node is not None
    assert drained_node.get_state() == NodeState.DRAINING
    assert drained_node.is_available() is False

    # Available nodes excludes draining
    available: List[BackendNode] = mgr.get_available_nodes()
    assert len(available) == 2

    # Undrain node
    undrained: bool = mgr.undrain_node(url="http://10.0.0.3:8000")
    assert undrained is True
    assert drained_node.get_state() == NodeState.ONLINE
    assert drained_node.is_available() is True

    # 4. Remove node
    removed: bool = mgr.remove_node(url="http://10.0.0.3:8000")
    assert removed is True
    assert len(mgr.list_nodes()) == 2

    # Removing non-existent returns False
    assert mgr.remove_node(url="http://10.0.0.99:8000") is False


def test_cluster_dispatch_strategy_least_sessions() -> None:
    """
    Verify that LEAST_SESSIONS strategy routes to worker with fewest active sessions.

    :return: None.
    """
    initial_nodes: List[str] = list([
        "http://node-a:8000",
        "http://node-b:8000",
        "http://node-c:8000",
    ])
    mgr: ClusterManager = ClusterManager(
        initial_backends=initial_nodes,
        strategy=DispatchStrategy.LEAST_SESSIONS,
    )

    node_a: Optional[BackendNode] = mgr.get_node("http://node-a:8000")
    node_b: Optional[BackendNode] = mgr.get_node("http://node-b:8000")
    node_c: Optional[BackendNode] = mgr.get_node("http://node-c:8000")
    assert node_a is not None
    assert node_b is not None
    assert node_c is not None

    # Node A has 3 sessions, Node B has 1 session, Node C has 4 sessions
    for _ in range(3):
        node_a.increment_sessions()
    node_b.increment_sessions()
    for _ in range(4):
        node_c.increment_sessions()

    # Dispatch should select Node B (1 session)
    selected: str = mgr.select_backend(strategy=DispatchStrategy.LEAST_SESSIONS)
    assert selected == "http://node-b:8000"

    # Simulate Node B receiving another session (now 2 sessions)
    node_b.increment_sessions()
    # Now Node B has 2 sessions, still least
    selected_again: str = mgr.select_backend(strategy=DispatchStrategy.LEAST_SESSIONS)
    assert selected_again == "http://node-b:8000"

    # Node B reaches 3 sessions (tied with Node A)
    node_b.increment_sessions()
    node_a.set_latency_ms(15.0)
    node_b.set_latency_ms(45.0)
    # Tie broken by latency: Node A has lower latency
    selected_tie: str = mgr.select_backend(strategy=DispatchStrategy.LEAST_SESSIONS)
    assert selected_tie == "http://node-a:8000"


def test_cluster_dispatch_strategy_least_latency() -> None:
    """
    Verify that LEAST_LATENCY strategy routes to worker with lowest measured ping latency.

    :return: None.
    """
    initial_nodes: List[str] = list([
        "http://node-slow:8000",
        "http://node-fast:8000",
        "http://node-med:8000",
    ])
    mgr: ClusterManager = ClusterManager(
        initial_backends=initial_nodes,
        strategy=DispatchStrategy.LEAST_LATENCY,
    )

    node_slow: Optional[BackendNode] = mgr.get_node("http://node-slow:8000")
    node_fast: Optional[BackendNode] = mgr.get_node("http://node-fast:8000")
    node_med: Optional[BackendNode] = mgr.get_node("http://node-med:8000")
    assert node_slow is not None
    assert node_fast is not None
    assert node_med is not None

    node_slow.set_latency_ms(180.0)
    node_fast.set_latency_ms(12.4)
    node_med.set_latency_ms(65.0)

    selected: str = mgr.select_backend(strategy=DispatchStrategy.LEAST_LATENCY)
    assert selected == "http://node-fast:8000"


def test_cluster_dispatch_strategy_round_robin() -> None:
    """
    Verify that ROUND_ROBIN cycles systematically across all available workers.

    :return: None.
    """
    initial_nodes: List[str] = list([
        "http://node-1:8000",
        "http://node-2:8000",
    ])
    mgr: ClusterManager = ClusterManager(
        initial_backends=initial_nodes,
        strategy=DispatchStrategy.ROUND_ROBIN,
    )

    first: str = mgr.select_backend(strategy=DispatchStrategy.ROUND_ROBIN)
    second: str = mgr.select_backend(strategy=DispatchStrategy.ROUND_ROBIN)
    third: str = mgr.select_backend(strategy=DispatchStrategy.ROUND_ROBIN)

    assert first == "http://node-1:8000"
    assert second == "http://node-2:8000"
    assert third == "http://node-1:8000"


def test_cluster_dispatch_excludes_offline_and_draining_nodes() -> None:
    """
    Verify that offline and draining nodes are strictly excluded from dispatching.

    :return: None.
    """
    initial_nodes: List[str] = list([
        "http://node-dead:8000",
        "http://node-alive:8000",
    ])
    mgr: ClusterManager = ClusterManager(initial_backends=initial_nodes)

    node_dead: Optional[BackendNode] = mgr.get_node("http://node-dead:8000")
    assert node_dead is not None
    node_dead.set_state(state=NodeState.OFFLINE)

    for _ in range(5):
        selected: str = mgr.select_backend()
        assert selected == "http://node-alive:8000"


def test_parse_strategy_helper() -> None:
    """
    Verify strategy string parser and fallback behavior.

    :return: None.
    """
    assert parse_strategy("round_robin") == DispatchStrategy.ROUND_ROBIN
    assert parse_strategy("least_latency") == DispatchStrategy.LEAST_LATENCY
    assert parse_strategy("least_sessions") == DispatchStrategy.LEAST_SESSIONS
    assert parse_strategy("unknown_strategy") == DispatchStrategy.LEAST_SESSIONS


def test_cluster_rest_api_endpoints() -> None:
    """
    Verify all /api/cluster REST endpoints for node inspection, adding, draining, and strategy setting.

    :return: None.
    """
    client: TestClient = TestClient(web_app)

    # 1. Query nodes list
    get_resp = client.get("/api/cluster/nodes")
    assert get_resp.status_code == 200
    data: Dict[str, Any] = get_resp.json()
    assert "nodes" in data
    assert "strategy" in data
    assert "total_nodes" in data
    assert "online_nodes" in data
    assert "session_mappings" in data

    # 2. Add new node
    post_resp = client.post("/api/cluster/nodes", json=dict({"url": "http://127.0.0.1:8099"}))
    assert post_resp.status_code == 200
    post_data: Dict[str, Any] = post_resp.json()
    assert "Cluster node registered" in post_data.get("message", "")

    # Duplicate registration rejected
    dup_resp = client.post("/api/cluster/nodes", json=dict({"url": "http://127.0.0.1:8099"}))
    assert dup_resp.status_code == 400

    # 3. Drain node
    drain_resp = client.post("/api/cluster/nodes/drain", json=dict({"url": "http://127.0.0.1:8099"}))
    assert drain_resp.status_code == 200
    drain_data: Dict[str, Any] = drain_resp.json()
    assert drain_data.get("node", dict()).get("state", "") == "DRAINING"

    # 4. Undrain node
    undrain_resp = client.post("/api/cluster/nodes/undrain", json=dict({"url": "http://127.0.0.1:8099"}))
    assert undrain_resp.status_code == 200
    undrain_data: Dict[str, Any] = undrain_resp.json()
    assert undrain_data.get("node", dict()).get("state", "") == "ONLINE"

    # 5. Get and Update Strategy
    strat_resp = client.get("/api/cluster/strategy")
    assert strat_resp.status_code == 200

    put_strat = client.put("/api/cluster/strategy", json=dict({"strategy": "least_latency"}))
    assert put_strat.status_code == 200
    assert put_strat.json().get("strategy", "") == "least_latency"

    # 6. Remove node
    del_resp = client.request("DELETE", "/api/cluster/nodes", json=dict({"url": "http://127.0.0.1:8099"}))
    assert del_resp.status_code == 200
    del_data: Dict[str, Any] = del_resp.json()
    assert "Cluster node removed" in del_data.get("message", "")


async def mock_child_response_handler(request: httpx.Request) -> httpx.Response:
    """
    Mock HTTP handler returning registered child server dictionary.

    :param request: Incoming httpx Request.
    :return: Mocked httpx Response.
    """
    mock_child_response: Dict[str, Any] = dict({
        "worker_alpha:192.168.1.100:8001": dict({"ip": "192.168.1.100", "port": 8001}),
        "worker_beta:192.168.1.101:8002": dict({"ip": "192.168.1.101", "port": 8002}),
    })
    return httpx.Response(200, json=mock_child_response)


@pytest.mark.anyio
async def test_master_server_auto_discovery() -> None:
    """
    Verify auto-discovery of worker services from a master server endpoint.

    :return: None.
    """
    mgr: ClusterManager = ClusterManager(initial_backends=list(["http://127.0.0.1:8000"]))

    transport: httpx.MockTransport = httpx.MockTransport(mock_child_response_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        discovered: List[str] = await mgr.sync_with_master_server(
            master_url="http://master-server:8000",
            client=client,
        )

    assert len(discovered) == 2
    assert "http://192.168.1.100:8001" in discovered
    assert "http://192.168.1.101:8002" in discovered
    assert len(mgr.list_nodes()) == 3
