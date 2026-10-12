from __future__ import annotations

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.Reliability.blackout_driver import CascadingDriver
from VeraGridEngine.Simulations.Stochastic.stochastic_power_flow_driver import StochasticPowerFlowDriver
from VeraGridEngine.Simulations.Topology.topology_reduction_driver import DeleteAndReduce
from VeraGridEngine.Simulations.Topology.topology_reduction_driver import TopologyReduction
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGrid.Session.session import GcThread


def test_simulation_completion_uses_qthread_finished_not_done_signal() -> None:
    """
    Ensure the simulation worker stack has no custom completion signal.

    :return: None.
    """
    assert "done_signal" not in DriverTemplate.__slots__
    assert "done_signal" not in GcThread.__dict__


def test_cancel_requests_only_mark_driver_cancelled() -> None:
    """
    Ensure cancellation remains a request and not a false completion boundary.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    power_flow_options: PowerFlowOptions = PowerFlowOptions()
    drivers: list[DriverTemplate] = list()
    drivers.append(StochasticPowerFlowDriver(grid=grid, options=power_flow_options))
    drivers.append(TopologyReduction(grid=grid, branch_indices=list()))
    drivers.append(DeleteAndReduce(grid=grid, objects=list(), sel_idx=list()))
    drivers.append(CascadingDriver(grid=grid, options=power_flow_options))

    driver: DriverTemplate
    for driver in drivers:
        driver.cancel()

        assert driver.is_cancel()
