"""Fixed-SI terminal stamps and solved PF/PF3 comparisons for ordinary Lines."""

import numpy as np
import pytest

from VeraGridEngine.api import power_flow, power_flow3ph
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.sequence_line_type import SequenceLineType
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import ShuntConnectionType
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("conductance", (0.0, 2.0))
def test_line_pf3_terminal_stamp_si_equivalence(reverse: bool, conductance: float) -> None:
    """Check all four compiled stamps and both port currents against SI matrices.

    :param reverse: Reverse unequal nominal voltage bases.
    :param conductance: Source shunt conductance in uS/km.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    source: Bus = grid.add_bus(Bus(Vnom=128.04 if reverse else 132.0))
    target: Bus = grid.add_bus(Bus(Vnom=132.0 if reverse else 128.04))
    provider: SequenceLineType = SequenceLineType(Vnom=132.0, R=0.6, X=1.1, R0=1.8, X0=3.3,
                                                 B=120.0, B0=60.0, G=conductance, G0=conductance / 2.0)
    line: Line = grid.add_line(Line(bus_from=source, bus_to=target, length=3.7))
    line.apply_template(provider, grid.Sbase, grid.fBase, decimals_rounding=16)
    numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
    zero: np.ndarray = np.ones((3, 3), dtype=complex) / 3.0
    positive: np.ndarray = np.eye(3) - zero
    ys_si: np.ndarray = positive / (2.22 + 4.07j) + zero / (6.66 + 12.21j)
    ysh_si: np.ndarray = 3.7e-6 * (positive * complex(conductance, 120.0) + zero * complex(conductance / 2.0, 60.0))
    ff: np.ndarray = (ys_si + ysh_si / 2.0) * source.Vnom ** 2 / grid.Sbase
    tt: np.ndarray = (ys_si + ysh_si / 2.0) * target.Vnom ** 2 / grid.Sbase
    ft: np.ndarray = -ys_si * source.Vnom * target.Vnom / grid.Sbase
    np.testing.assert_allclose(numerical.passive_branch_data.Yff3[1:4, 1:4], ff, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(numerical.passive_branch_data.Ytt3[1:4, 1:4], tt, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(numerical.passive_branch_data.Yft3[1:4, 1:4], ft, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(numerical.passive_branch_data.Ytf3[1:4, 1:4], ft, rtol=1e-10, atol=1e-12)
    phase: np.ndarray = np.exp(2j * np.pi * np.array((0.0, -1.0, 1.0)) / 3.0)
    vf: np.ndarray = np.array((1.0, 0.97, 1.02)) * phase
    vt: np.ndarray = np.array((0.98, 1.01, 0.96)) * phase * np.exp(-0.025j)
    vf_si: np.ndarray = vf * source.Vnom * 1e3 / np.sqrt(3.0)
    vt_si: np.ndarray = vt * target.Vnom * 1e3 / np.sqrt(3.0)
    if_si: np.ndarray = ys_si @ (vf_si - vt_si) + ysh_si @ vf_si / 2.0
    it_si: np.ndarray = ys_si @ (vt_si - vf_si) + ysh_si @ vt_si / 2.0
    ib_f: float = grid.Sbase * 1e3 / (np.sqrt(3.0) * source.Vnom)
    ib_t: float = grid.Sbase * 1e3 / (np.sqrt(3.0) * target.Vnom)
    np.testing.assert_allclose((ff @ vf + ft @ vt) * ib_f, if_si, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose((ft @ vf + tt @ vt) * ib_t, it_si, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(vf * np.conj(ff @ vf + ft @ vt) * grid.Sbase * 1e6 / 3.0,
                               vf_si * np.conj(if_si), rtol=1e-10, atol=1e-10)


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("conductance", (0.0, 2.0))
def test_line_solved_pf_pf3_known_reference(reverse: bool, conductance: float) -> None:
    """Solve the same fixed-SI balanced network in the scalar and PF3 lanes.

    :param reverse: Reverse the unequal terminal nominal bases.
    :param conductance: Physical positive/zero sequence conductance in uS/km.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    source: Bus = grid.add_bus(Bus(Vnom=128.04 if reverse else 132.0, is_slack=True))
    target: Bus = grid.add_bus(Bus(Vnom=132.0 if reverse else 128.04))
    provider: SequenceLineType = SequenceLineType(Vnom=132.0, R=0.6, X=1.1, R0=0.6, X0=1.1,
                                                 B=120.0, B0=120.0, G=conductance, G0=conductance)
    line: Line = grid.add_line(Line(bus_from=source, bus_to=target, length=3.7))
    line.apply_template(provider, grid.Sbase, grid.fBase, decimals_rounding=16)
    grid.add_generator(bus=source, api_obj=Generator(vset=1.0))
    load: Load = Load(P=10.0, Q=1.0, P1=10.0 / 3.0, P2=10.0 / 3.0, P3=10.0 / 3.0,
                      Q1=1.0 / 3.0, Q2=1.0 / 3.0, Q3=1.0 / 3.0)
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=target, api_obj=load)
    pf: PowerFlowResults = power_flow(grid)
    pf3: PowerFlowResults3Ph = power_flow3ph(grid)
    assert pf.converged and pf3.converged
    np.testing.assert_allclose(pf3.voltage_A, pf.voltage, rtol=2e-8, atol=2e-8)
    np.testing.assert_allclose(pf3.Sf_A * 3.0, pf.Sf, rtol=2e-8, atol=2e-8)
    np.testing.assert_allclose(pf3.St_A * 3.0, pf.St, rtol=2e-8, atol=2e-8)
    # Verify the known physical load power, independently of lane agreement.
    assert complex(pf.St[0]) == pytest.approx(-10.0 - 1.0j, rel=2e-8, abs=2e-8)
