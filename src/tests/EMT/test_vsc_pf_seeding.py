"""VSC PF seeding conventions across PF formats and terminal orientations."""
from types import SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowReferenceType as Ref


class SeedRecorder:
    """Run the real PF-seeding methods while recording mapped assignments."""
    _get_vsc_terminal_indices = EmtProblemDae._get_vsc_terminal_indices
    _get_bus_voltage_vector = EmtProblemDae._get_bus_voltage_vector
    _get_bus_voltage_vector_balanced = EmtProblemDae._get_bus_voltage_vector_balanced
    _get_bus_voltage_vector_3ph = EmtProblemDae._get_bus_voltage_vector_3ph
    _get_vsc_pf_powers = EmtProblemDae._get_vsc_pf_powers
    _set_vsc_pf_positive_sequence = EmtProblemDae._set_vsc_pf_positive_sequence
    _seed_vsc_ac_terminals = EmtProblemDae._seed_vsc_ac_terminals
    _seed_branch_terminal_voltage_derivatives = EmtProblemDae._seed_branch_terminal_voltage_derivatives
    _seed_ac_branch_phase_powers = EmtProblemDae._seed_ac_branch_phase_powers
    _seed_branch_terminal_powers = EmtProblemDae._seed_branch_terminal_powers
    _try_set_vsc_branch_pf_init = EmtProblemDae._try_set_vsc_branch_pf_init

    def __init__(self, balanced, three_phase):
        self.power_flow_results = balanced
        self.power_flow_results_3ph = three_phase
        self.grid = SimpleNamespace(buses=[SimpleNamespace(is_dc=True), SimpleNamespace(is_dc=False)], fBase=50.)
        self._local_external_mapping_by_block_uid = {}
        self._temp_post_init_guess = {}
        self.values = {}
        self.preserved = set()
        self.feedforward = None

    def set_if_exists(self, mdl, key, value, persist_after_native_init=False):
        self.values[key] = value
        if persist_after_native_init:
            self.preserved.add(key)

    def set_external_param(self, mdl, key, value):
        self.values[key] = value

    def _assign_event_mapping_value_if_present(self, mdl, key, value):
        self.feedforward = value


def make_case(three_phase, positive_sequence):
    rotation = np.exp(2j * np.pi / 3.)
    voltage = .97 * np.exp(.2j)
    balanced = SimpleNamespace(voltage=np.array([1.05, voltage]),
                               St_vsc=np.array([-.6-.12j]), Pfp_vsc=np.array([.6]),
                               Pfn_vsc=np.array([0.]), Sbus=np.array([.6, -.6-.12j]))
    pf3 = None
    if three_phase:
        pf3 = SimpleNamespace(
            voltage_N=np.zeros(2), voltage_A=np.array([0., voltage]),
            voltage_B=np.array([0., .9 * voltage * rotation ** 2]),
            voltage_C=np.array([0., 1.1 * voltage * rotation]),
            St_vsc_A=np.array([-.2-.04j]), St_vsc_B=np.array([-.22-.06j]),
            St_vsc_C=np.array([-.18-.02j]), Pfp_vsc=np.array([.6]),
        )
    recorder = SeedRecorder(balanced, pf3)
    factory = VarFactory()
    mapping = {}
    for key in Ref:
        if positive_sequence or key not in (Ref.Vpk, Ref.phi_v):
            mapping[key] = factory.add_var(key.value, reference=key)
    # References belong to the second child: no positional child assumption.
    model = Block(children=[Block(name="Unrelated"), Block(name="Converter", external_mapping=mapping)])
    return recorder, model


@pytest.mark.parametrize("three_phase", [False, True])
@pytest.mark.parametrize("positive_sequence", [False, True])
@pytest.mark.parametrize("ac_is_from", [False, True])
def test_vsc_seed_terminal_orientation_and_power_conventions(three_phase, positive_sequence, ac_is_from):
    problem, model = make_case(three_phase, positive_sequence)
    from_bus, to_bus = (1, 0) if ac_is_from else (0, 1)
    problem._try_set_vsc_branch_pf_init(model, from_bus, to_bus, 1., 0)
    values = problem.values
    np.testing.assert_allclose(values[Ref.Pf], -.6 if ac_is_from else .6)
    np.testing.assert_allclose(values[Ref.Pt], .6 if ac_is_from else -.6)
    np.testing.assert_allclose(values[Ref.P], .6 if positive_sequence else -.6)
    np.testing.assert_allclose(values[Ref.Q], .12 if positive_sequence else -.12)
    np.testing.assert_allclose(values[Ref.If_dc], .6 / 1.05)
    assert {Ref.Vdc, Ref.If_dc} <= problem.preserved
    assert problem.feedforward == -.6
    active_current = Ref.if_A if ac_is_from else Ref.it_A
    inactive_current = Ref.it_A if ac_is_from else Ref.if_A
    assert values[active_current] == values[Ref.i_A]
    assert values[inactive_current] == 0.
    assert values[Ref.i_N] == 0.
    voltages = problem._get_bus_voltage_vector(1)[1:]
    powers = np.array([-.2-.04j, -.22-.06j, -.18-.02j]) if three_phase else np.full(3, -.2-.04j)
    currents = 3. * np.conj(powers / voltages)
    for key, current in zip((Ref.i_A, Ref.i_B, Ref.i_C), currents):
        np.testing.assert_allclose(values[key], np.sqrt(2.) * current.imag)
    if positive_sequence:
        np.testing.assert_allclose(values[Ref.Pe], .6)
        np.testing.assert_allclose(values[Ref.Qe], .12)
        rotation = np.exp(2j * np.pi / 3.)
        sequence_voltage = (voltages[0] + rotation * voltages[1] + rotation ** 2 * voltages[2]) / 3.
        sequence_current = (currents[0] + rotation * currents[1] + rotation ** 2 * currents[2]) / 3.
        np.testing.assert_allclose(values[Ref.Vpk], np.sqrt(2.) * abs(sequence_voltage))
        np.testing.assert_allclose(values[Ref.Ipk], np.sqrt(2.) * abs(sequence_current))


@pytest.mark.parametrize("three_phase", [False, True])
def test_vsc_missing_ac_power_uses_balanced_dc_fallback(three_phase):
    problem, model = make_case(three_phase, True)
    problem.power_flow_results.St_vsc[:] = 0.
    if three_phase:
        problem.power_flow_results_3ph.St_vsc_A[:] = 0.
        problem.power_flow_results_3ph.St_vsc_B[:] = 0.
        problem.power_flow_results_3ph.St_vsc_C[:] = 0.
    problem._try_set_vsc_branch_pf_init(model, 0, 1, 1., 0)
    np.testing.assert_allclose(problem.values[Ref.P], .6)
    np.testing.assert_allclose(problem.values[Ref.Q], 0.)


def test_vsc_zero_voltage_seeds_finite_zero_currents():
    problem, model = make_case(False, True)
    problem.power_flow_results.voltage[:] = 0.
    problem._try_set_vsc_branch_pf_init(model, 0, 1, 1., 0)
    for key in (Ref.i_A, Ref.i_B, Ref.i_C, Ref.If_dc, Ref.Ipk, Ref.Vpk):
        assert problem.values[key] == 0.
