"""Load terminal seeds include all ZIP terms at the solved PF voltage."""
from types import SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae


@pytest.mark.parametrize("voltage", [0.8, 1.0, 1.1])
@pytest.mark.parametrize("three_phase", [False, True])
def test_balanced_zip_power_seed(voltage, three_phase):
    load = Load(P=30., Q=12., Ir=9., Ii=-6., G=15., B=3.)
    context = SimpleNamespace(
        grid=SimpleNamespace(Sbase=100.),
        power_flow_results_3ph=object() if three_phase else None,
        _get_bus_voltage_vector=lambda index: np.array([0., voltage, voltage, voltage]),
    )
    seed = EmtProblemDae._get_load_fixed_power_vector(context, load, 0)
    expected = -(30. + 12j + (9. + 6j) * voltage + (15. - 3j) * voltage ** 2) / 300.
    np.testing.assert_allclose(seed, [0., expected, expected, expected])


def test_three_phase_zip_power_seed():
    load = Load(P1=10., P2=20., P3=30., Q1=2., Q2=4., Q3=6.,
                Ir1=3., Ir2=6., Ir3=9., Ii1=-1., Ii2=-2., Ii3=-3.,
                G1=5., G2=10., G3=15., B1=1., B2=2., B3=3.)
    context = SimpleNamespace(grid=SimpleNamespace(Sbase=100.), power_flow_results_3ph=object(),
                              _get_bus_voltage_vector=lambda index: np.array([0., .8, 1., 1.1]))
    seed = EmtProblemDae._get_load_fixed_power_vector(context, load, 0)
    expected = [0., -(10. + 2j + (3. + 1j) * .8 + (5. - 1j) * .8 ** 2) / 100.,
                -(20. + 4j + (6. + 2j) + (10. - 2j)) / 100.,
                -(30. + 6j + (9. + 3j) * 1.1 + (15. - 3j) * 1.1 ** 2) / 100.]
    np.testing.assert_allclose(seed, expected)


@pytest.mark.parametrize("three_phase", [False, True])
@pytest.mark.parametrize("explicit_phases", [False, True])
def test_shunt_power_seed_preserves_pf_data_and_signs(three_phase, explicit_phases):
    shunt = Shunt(G=30., B=12.)
    if explicit_phases:
        shunt.Ga, shunt.Gb, shunt.Gc = 5., 10., 15.
        shunt.Ba, shunt.Bb, shunt.Bc = -2., 4., 10.
    voltages = np.array([0., .8, 1., 1.1])
    context = SimpleNamespace(
        grid=SimpleNamespace(Sbase=100.),
        power_flow_results_3ph=object() if three_phase else None,
        _get_bus_voltage_vector=lambda index: voltages,
    )
    power = EmtProblemDae._get_shunt_fixed_power_vector(context, shunt, 0)
    if three_phase and explicit_phases:
        expected = -np.array([0., (5. + 2j) * .8 ** 2,
                             10. - 4j, (15. - 10j) * 1.1 ** 2]) / 100.
    else:
        expected = -np.array([0., (10. - 4j) * .8 ** 2,
                             10. - 4j, (10. - 4j) * 1.1 ** 2]) / 100.
    np.testing.assert_allclose(power, expected)
