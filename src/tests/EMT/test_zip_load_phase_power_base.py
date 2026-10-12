"""Check that an EMT ZIP phase uses the grid's three-phase power base."""

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template


def test_zip_default_matches_static_constant_power_load() -> None:
    template = get_load_ZIP_emt_template(VarFactory())
    coefficients = {
        var.name: float(value.value)
        for var, value in template.block.event_dict.items()
        if var.name in {"a1", "a2", "a3", "a4", "a5", "a6"}
    }
    assert coefficients == {
        "a1": 0.0, "a2": 0.0, "a3": 1.0,
        "a4": 0.0, "a5": 0.0, "a6": 1.0,
    }


def test_zip_phase_current_delivers_scheduled_phase_power() -> None:
    """A phase power of P/Sbase needs three times that per-unit current."""
    template = get_load_ZIP_emt_template(VarFactory(), phA=True, phB=False, phC=False)
    phase = next(block for block in template.block.get_all_blocks() if block.algebraic_vars)
    variables = {var.name: var for var in (
        phase.in_vars + phase.state_vars + phase.algebraic_vars
        + list(template.block.event_dict) + list(template.block.api_obj_mapping.values())
    )}

    phase_power_on_grid_base = 0.1
    voltage_peak = np.sqrt(2.0)
    expected_current_peak = -3.0 * voltage_peak * phase_power_on_grid_base
    values = {
        "u_A": voltage_peak, "q_A": 0.0, "P_A": -phase_power_on_grid_base,
        "Q_A": 0.0, "i_A": expected_current_peak, "eps": 1e-12,
    }
    bindings = {variables[name].uid: value for name, value in values.items()}
    current_index = next(index for index, var in enumerate(phase.algebraic_vars) if var.name == "i_A")
    current_equation = phase.algebraic_eqs[current_index]
    current_init_equation = phase.init_eqs[variables["i_A"]]

    assert np.isclose(current_equation.eval_uid(bindings), 0.0, atol=1e-12)
    assert np.isclose(current_init_equation.eval_uid(bindings), expected_current_peak, atol=1e-12)
