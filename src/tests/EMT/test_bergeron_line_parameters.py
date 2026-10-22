"""Physical-unit checks for Bergeron line parameters."""
from types import SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import (
    _build_line_parameter_matrices_from_template_or_balanced_data,
)


@pytest.mark.parametrize("length_km", [1.0, 10.0, 35.0])
def test_tower_parameters_use_kilometres_consistently(length_km):
    # At 100 kV and 100 MVA, Zbase = 100 ohms and Ybase = 0.01 S.
    # Include mutual terms to check the entire matrix conversion.
    resistance_per_km = np.array([[0.2, 0.05], [0.05, 0.3]])
    reactance_per_km = np.array([[0.4, 0.1], [0.1, 0.5]])
    susceptance_per_km = np.array([[3e-6, -1e-6], [-1e-6, 4e-6]])
    tower = SimpleNamespace(
        z_nabc=resistance_per_km + 1j * reactance_per_km,
        y_nabc=1j * susceptance_per_km,
    )
    line = SimpleNamespace(template=tower, length=length_km,
                           bus_from=SimpleNamespace(Vnom=100.0))
    resistance, inductance, capacitance = (
        _build_line_parameter_matrices_from_template_or_balanced_data(line, 100.0, 50.0)
    )
    omega = 2.0 * np.pi * 50.0
    # Convert back to physical total impedance/admittance for comparison.
    np.testing.assert_allclose(resistance * 100.0, resistance_per_km * length_km)
    np.testing.assert_allclose(inductance * omega * 100.0, reactance_per_km * length_km)
    np.testing.assert_allclose(capacitance * omega * 0.01, susceptance_per_km * length_km)
