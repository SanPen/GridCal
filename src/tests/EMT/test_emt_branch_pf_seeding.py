"""Branch getter contracts across balanced and three-phase PF results."""

from types import SimpleNamespace

import numpy as np

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import VarPowerFlowReferenceType as Ref


def test_balanced_and_pf3_powers_share_nabc_order_and_base() -> None:
    balanced = SimpleNamespace(Sf=np.array([90 + 30j]), St=np.array([-87 - 24j]))
    pf3 = SimpleNamespace(**{
        f"{end}_{phase}": power / 3
        for end, power in (("Sf", balanced.Sf), ("St", balanced.St)) for phase in "ABC"
    })
    context = SimpleNamespace(power_flow_results=balanced, power_flow_results_3ph=None)
    balanced_powers = EmtProblemDae.get_branch_powers(context, 0, 100.0)
    context.power_flow_results_3ph = pf3
    phase_powers = EmtProblemDae.get_branch_powers(context, 0, 100.0)
    for actual, expected in zip(phase_powers, balanced_powers):
        assert actual.shape == (4,)
        assert actual.dtype == np.complex128
        assert actual[0] == 0.0j
        np.testing.assert_allclose(actual, expected)
    np.testing.assert_allclose(np.sum(phase_powers[0]), balanced.Sf[0] / 100.0)
    np.testing.assert_allclose(np.sum(phase_powers[1]), balanced.St[0] / 100.0)


def test_missing_pf3_powers_are_skipped_but_present_zero_is_seeded() -> None:
    context = SimpleNamespace(power_flow_results_3ph=SimpleNamespace(
        Sf_A=np.array([0.0j]), Sf_B=np.array([]), Sf_C=None,
        St_A=None, St_B=np.array([0.0j]), St_C=np.array([5 + 2j]),
    ))
    from_powers, to_powers = EmtProblemDae.get_branch_powers(context, 0, 100.0)
    model = Block()
    model.external_mapping = {
        key: Var(key.name) for key in (Ref.Sf_A, Ref.Sf_B, Ref.Sf_C, Ref.St_A, Ref.St_B, Ref.St_C)
    }
    seeded = {}
    setter = SimpleNamespace(set_if_exists=lambda mdl, key, value: seeded.__setitem__(key, value))
    totals = EmtProblemDae._seed_ac_branch_phase_powers(setter, model, from_powers, to_powers)
    assert seeded == {Ref.Sf_A: 0.0, Ref.St_B: 0.0, Ref.St_C: 0.05}
    np.testing.assert_allclose(totals, [0.0j, 0.05 + 0.02j])


def test_pf3_currents_use_phase_base_and_handle_missing_power_and_zero_voltage() -> None:
    context = SimpleNamespace(power_flow_results_3ph=SimpleNamespace(
        Sf_A=np.array([30 + 10j]), Sf_B=None, Sf_C=np.array([20 + 5j]),
        St_A=np.array([-29 - 8j]), St_B=np.array([0.0j]), St_C=np.array([]),
    ))
    context.get_branch_powers = lambda index, base: EmtProblemDae.get_branch_powers(context, index, base)
    vf = np.array([0.0j, 1.0 + 0.0j, -0.5 - 0.8j, 0.0j])
    vt = np.array([0.0j, 0.98 - 0.02j, -0.5 - 0.8j, -0.5 + 0.8j])
    currents_f, currents_t = EmtProblemDae.get_branch_currents(
        context, 0, vf, vt, 100.0, Line(),
    )
    np.testing.assert_allclose(currents_f, [0.0j, 0.9 - 0.3j, 0.0j, 0.0j])
    np.testing.assert_allclose(currents_t, [0.0j, 3 * np.conj((-29 - 8j) / 100 / vt[1]), 0.0j, 0.0j])


def test_current_seed_policy_preserves_balanced_impedance_and_physical_neutral() -> None:
    model = Block()
    model.external_mapping = {key: Var(key.name) for key in (Ref.if_N, Ref.it_N)}
    from_currents = np.array([2j, 1j, 2j, 3j])
    to_currents = -from_currents
    # PF3, balanced power fallback, impedance projection, and physical neutral.
    for preserve_current_seed, has_physical_g, expected_neutral, persist_phase, persist_neutral in (
        (False, False, -6.0, False, False),
        (False, False, -6.0, False, False),
        (True, False, -6.0, True, False),
        (True, True, 2.0, True, True),
    ):
        seeded = {}
        def set_seed(mdl, key, value, persist_after_native_init):
            seeded[key] = (value, persist_after_native_init)
        context = SimpleNamespace(set_if_exists=set_seed)
        EmtProblemDae._seed_branch_phase_currents(
            context, model, from_currents, to_currents, preserve_current_seed, has_physical_g,
        )
        np.testing.assert_allclose(seeded[Ref.if_N][0], np.sqrt(2) * expected_neutral)
        np.testing.assert_allclose(seeded[Ref.it_N][0], -np.sqrt(2) * expected_neutral)
        assert seeded[Ref.if_N][1] == persist_neutral
        assert seeded[Ref.it_N][1] == persist_neutral
        assert seeded[Ref.if_A][1] == persist_phase
        assert seeded[Ref.it_A][1] == persist_phase
