from pathlib import Path
from typing import Any

import numpy as np
import pytest

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.sequence_line_type import SequenceLineType
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave


@pytest.mark.parametrize("voltage,base_power,length", ((132.0, 100.0, 3.7), (33.0, 50.0, 0.15)))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("use_capacitance", (False, True))
@pytest.mark.parametrize("conductance,zero_conductance", ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0)))
@pytest.mark.parametrize("decimals_rounding", (3, 6, 16))
def test_sequence_line_values_contract(
        voltage: float, base_power: float, length: float,
        frequency: float, use_capacitance: bool,
        conductance: float, zero_conductance: float, decimals_rounding: int,
) -> None:
    """Keep the public sequence tuple, physical units and rounding stable.

    :param voltage: Connected line-to-line voltage (kV).
    :param base_power: System base power (MVA).
    :param length: Line length (km).
    :param frequency: Network frequency (Hz).
    :param use_capacitance: Select Cnf/Cnf0 instead of B/B0.
    :param conductance: Positive-sequence conductance (uS/km).
    :param zero_conductance: Zero-sequence conductance (uS/km).
    :param decimals_rounding: Requested number of decimal digits.
    :return: None.
    """
    # The connected voltage must control conversion, even when the catalogue
    # rating differs. Non-unit ampacity exposes an assumed default line rating.
    template: SequenceLineType = SequenceLineType(
        Vnom=220.0, Imax=0.8,
        R=0.06, X=0.11, R0=0.18, X0=0.33,
        B=120.0, B0=60.0, CnF=200.0, CnF0=100.0,
        G=conductance, G0=zero_conductance, use_conductance=use_capacitance,
    )
    r_pu: float
    x_pu: float
    b_pu: float
    g_pu: float
    r0_pu: float
    x0_pu: float
    b0_pu: float
    g0_pu: float
    rate_mva: float
    # Unpack all nine positions as a public consumer would; arity and ordering
    # are checked against physical expectations rather than another converter.
    r_pu, x_pu, b_pu, g_pu, r0_pu, x0_pu, b0_pu, g0_pu, rate_mva = template.get_values(
        Sbase=base_power, freq=frequency, length=length, line_Vnom=voltage,
        logger=Logger(), decimals_rounding=decimals_rounding,
    )
    impedance_base: float = voltage * voltage / base_power
    susceptance: float
    zero_susceptance: float
    if use_capacitance:
        susceptance = 2.0 * np.pi * frequency * 200.0e-9
        zero_susceptance = 2.0 * np.pi * frequency * 100.0e-9
    else:
        susceptance = 120.0e-6
        zero_susceptance = 60.0e-6
    # Source Ohm/km and uS/km determine total p.u. values. The ampacity rating
    # depends on connected voltage, independently of line length or power base.
    expected_values: np.ndarray = np.array((
        0.06 * length / impedance_base,
        0.11 * length / impedance_base,
        susceptance * length * impedance_base,
        conductance * 1.0e-6 * length * impedance_base,
        0.18 * length / impedance_base,
        0.33 * length / impedance_base,
        zero_susceptance * length * impedance_base,
        zero_conductance * 1.0e-6 * length * impedance_base,
        0.8 * voltage * np.sqrt(3.0),
    ))
    actual_values: tuple[float, float, float, float, float, float, float, float, float] = (
        r_pu, x_pu, b_pu, g_pu, r0_pu, x0_pu, b0_pu, g0_pu, rate_mva,
    )
    value: float
    for value in actual_values:
        assert isinstance(value, float)
    np.testing.assert_allclose(
        actual_values, np.round(expected_values, decimals_rounding),
        rtol=1.0e-10, atol=1.0e-12,
    )
    # Omitting precision remains the documented six-decimal public default.
    default_values: tuple[float, float, float, float, float, float, float, float, float] = template.get_values(
        Sbase=base_power, freq=frequency, length=length, line_Vnom=voltage, logger=Logger(),
    )
    np.testing.assert_allclose(default_values, np.round(expected_values, 6), rtol=1.0e-10, atol=1.0e-12)


@pytest.mark.parametrize("voltage,base_power,length", ((132.0, 100.0, 3.7), (33.0, 50.0, 0.15)))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("use_capacitance", (False, True))
@pytest.mark.parametrize("conductance,zero_conductance", ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0)))
def test_sequence_template_compiles_total_per_unit_admittances(
        voltage: float, base_power: float, length: float,
        frequency: float, use_capacitance: bool,
        conductance: float, zero_conductance: float,
) -> None:
    """Check the compiled pi model against physical sequence impedances and charging.

    :param voltage: Line-to-line base voltage in kV.
    :param base_power: Three-phase system power base in MVA.
    :param length: Line length in km.
    :param frequency: Network frequency in Hz.
    :param use_capacitance: Use capacitance instead of susceptance as template input.
    :param conductance: Positive-sequence shunt conductance in uS/km.
    :param zero_conductance: Zero-sequence shunt conductance in uS/km.
    :return: None.
    """
    # Non-unit lengths and bases expose missing conversions in the ABC compiler path.
    grid: MultiCircuit = MultiCircuit(Sbase=base_power, fbase=frequency)
    source: Bus = grid.add_bus(Bus(name="Source", Vnom=voltage))
    target: Bus = grid.add_bus(Bus(name="Target", Vnom=voltage))
    template: SequenceLineType = SequenceLineType(
        Vnom=voltage, R=0.06, X=0.11, R0=0.18, X0=0.33,
        B=120.0, B0=60.0, CnF=200.0, CnF0=100.0,
        G=conductance, G0=zero_conductance,
        use_conductance=use_capacitance,
    )
    line: Line = Line(bus_from=source, bus_to=target, length=length)
    grid.add_line(line)
    line.apply_template(obj=template, Sbase=base_power, freq=frequency,
                        logger=Logger(), decimals_rounding=16)

    # Independent sequence projectors include mutual terms, not just phase diagonals.
    impedance_base: float = voltage * voltage / base_power
    zero_projector: np.ndarray = np.ones((3, 3), dtype=complex) / 3.0
    other_projector: np.ndarray = np.eye(3, dtype=complex) - zero_projector
    expected_series: np.ndarray = np.zeros((4, 4), dtype=complex)
    expected_shunt: np.ndarray = np.zeros((4, 4), dtype=complex)
    expected_series[1:, 1:] = impedance_base / length * (
        other_projector / (0.06 + 0.11j) + zero_projector / (0.18 + 0.33j)
    )
    if use_capacitance:
        susceptance: float = 2.0 * np.pi * frequency * 200.0e-9
        zero_susceptance: float = 2.0 * np.pi * frequency * 100.0e-9
    else:
        susceptance = 120.0e-6
        zero_susceptance = 60.0e-6
    expected_shunt[1:, 1:] = length * impedance_base * (
        complex(conductance * 1e-6, susceptance) * other_projector
        + complex(zero_conductance * 1e-6, zero_susceptance) * zero_projector
    )
    numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
    np.testing.assert_allclose(numerical.passive_branch_data.G, conductance * 1e-6 * length * impedance_base, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(numerical.passive_branch_data.G0, zero_conductance * 1e-6 * length * impedance_base, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(numerical.passive_branch_data.Yff3, expected_series + expected_shunt / 2.0)
    np.testing.assert_allclose(numerical.passive_branch_data.Ytt3, expected_series + expected_shunt / 2.0)
    np.testing.assert_allclose(numerical.passive_branch_data.Yft3, -expected_series)
    np.testing.assert_allclose(numerical.passive_branch_data.Ytf3, -expected_series)
    np.testing.assert_allclose(line.ysh.values * 1e-6, expected_shunt)

    # Reapplication must neither accumulate scaling nor alter catalogue values.
    line.apply_template(obj=template, Sbase=base_power, freq=frequency,
                        logger=Logger(), decimals_rounding=16)
    np.testing.assert_allclose(line.ys.values, expected_series)
    np.testing.assert_allclose(line.ysh.values * 1e-6, expected_shunt)
    assert line.template is template
    assert template.R == 0.06 and template.B == 120.0 and template.Cnf == 200.0
    assert template.G == conductance and template.G0 == zero_conductance


@pytest.mark.parametrize("voltage,base_power,length", ((132.0, 100.0, 3.7), (33.0, 50.0, 0.15)))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("conductance,zero_conductance", ((0.0, 0.0), (0.003, 0.0), (0.003, 0.004)))
def test_direct_line_conductance_survives_compilation_and_persistence(
        tmp_path: Path, voltage: float, base_power: float, length: float,
        frequency: float, conductance: float, zero_conductance: float,
) -> None:
    """Preserve declared and templated shunts through the native file lifecycle.

    :param tmp_path: Isolated native-file output directory.
    :param voltage: Line-to-line base voltage in kV.
    :param base_power: Three-phase system power base in MVA.
    :param length: Physical line length in km.
    :param frequency: Network frequency in Hz.
    :param conductance: Direct positive-sequence total conductance in p.u.
    :param zero_conductance: Direct zero-sequence total conductance in p.u.
    :return: None.
    """
    # Register the provider before the line so native references have an owner.
    grid: MultiCircuit = MultiCircuit(Sbase=base_power, fbase=frequency)
    source: Bus = grid.add_bus(Bus(name="Source", Vnom=voltage))
    target: Bus = grid.add_bus(Bus(name="Target", Vnom=voltage))
    template: SequenceLineType = SequenceLineType(
        name="Conductive sequence", Vnom=voltage,
        R=0.06, X=0.11, R0=0.18, X0=0.33, B=120.0, B0=60.0,
        G=conductance * 1e3, G0=zero_conductance * 1e3,
    )
    grid.add_sequence_line(template)
    direct: Line = Line(
        name="Direct", bus_from=source, bus_to=target, length=length,
        r=0.01, x=0.1, r0=0.02, x0=0.2, b=0.002, b0=0.001,
        g=conductance, g0=zero_conductance,
    )
    templated: Line = Line(name="Templated", bus_from=source, bus_to=target, length=length)
    grid.add_line(direct)
    grid.add_line(templated)
    templated.apply_template(obj=template, Sbase=base_power, freq=frequency,
                            logger=Logger(), decimals_rounding=16)
    impedance_base: float = voltage * voltage / base_power
    scale: float = length * impedance_base
    expected_g: np.ndarray = np.array((conductance, template.G * 1e-6 * scale))
    expected_g0: np.ndarray = np.array((zero_conductance, template.G0 * 1e-6 * scale))
    expected_b: np.ndarray = np.array((0.002, 120e-6 * scale))
    expected_b0: np.ndarray = np.array((0.001, 60e-6 * scale))
    expected_r: np.ndarray = np.array((0.01, 0.06 * length / impedance_base))
    expected_x: np.ndarray = np.array((0.1, 0.11 * length / impedance_base))
    expected_r0: np.ndarray = np.array((0.02, 0.18 * length / impedance_base))
    expected_x0: np.ndarray = np.array((0.2, 0.33 * length / impedance_base))

    # Persist real VeraGrid objects rather than a stand-in serialization format.
    output_path: Path = tmp_path / "line_conductance.veragrid"
    FileSave(circuit=grid, file_name=str(output_path)).save()
    restored: MultiCircuit = FileOpen(file_name=str(output_path)).open()
    assert restored.Sbase == base_power and restored.fBase == frequency
    assert len(restored.lines) == 2 and len(restored.sequence_line_types) == 1
    assert restored.lines[0].idtag == direct.idtag
    assert restored.lines[1].idtag == templated.idtag
    assert restored.lines[1].template is restored.sequence_line_types[0]
    assert restored.sequence_line_types[0].idtag == template.idtag

    # Check original, loaded and reconstructed matrices against sequence algebra.
    circuit: MultiCircuit
    line: Line
    index: int
    refresh: bool
    for circuit in (grid, restored):
        for refresh in (False, True):
            if refresh:
                circuit.lines[1].apply_template(
                    obj=circuit.sequence_line_types[0], Sbase=base_power, freq=frequency,
                    logger=Logger(), decimals_rounding=16,
                )
                for line in circuit.lines:
                    line.fill_3_phase_from_sequence()
            else:
                pass
            numerical: NumericalCircuit = compile_numerical_circuit_at(
                circuit=circuit, fill_three_phase=True,
            )
            np.testing.assert_allclose(numerical.passive_branch_data.G, expected_g, rtol=1e-10, atol=1e-12)
            np.testing.assert_allclose(numerical.passive_branch_data.G0, expected_g0, rtol=1e-10, atol=1e-12)
            for index, line in enumerate(circuit.lines):
                expected_shunt: np.ndarray = np.zeros((4, 4), dtype=complex)
                expected_series: np.ndarray = np.zeros((4, 4), dtype=complex)
                expected_shunt[1:, 1:] = _expected_phase_matrix(
                    complex(expected_g[index], expected_b[index]),
                    complex(expected_g0[index], expected_b0[index]),
                )
                expected_series[1:, 1:] = _expected_phase_matrix(
                    1.0 / complex(expected_r[index], expected_x[index]),
                    1.0 / complex(expected_r0[index], expected_x0[index]),
                )
                np.testing.assert_allclose(line.G, expected_g[index], rtol=1e-10, atol=1e-12)
                np.testing.assert_allclose(line.G0, expected_g0[index], rtol=1e-10, atol=1e-12)
                np.testing.assert_allclose(line.ysh.values * 1e-6, expected_shunt, rtol=1e-10, atol=1e-12)
                np.testing.assert_allclose(line.ys.values, expected_series, rtol=1e-10, atol=1e-12)
                row: slice = slice(4 * index, 4 * index + 4)
                np.testing.assert_allclose(numerical.passive_branch_data.Yff3[row], expected_series + expected_shunt / 2, rtol=1e-10, atol=1e-12)
                np.testing.assert_allclose(numerical.passive_branch_data.Ytt3[row], expected_series + expected_shunt / 2, rtol=1e-10, atol=1e-12)
                np.testing.assert_allclose(numerical.passive_branch_data.Yft3[row], -expected_series, rtol=1e-10, atol=1e-12)
                np.testing.assert_allclose(numerical.passive_branch_data.Ytf3[row], -expected_series, rtol=1e-10, atol=1e-12)



def _expected_phase_matrix(positive_sequence_value: complex,
                           zero_sequence_value: complex) -> np.ndarray:
    diagonal_value = (2.0 * positive_sequence_value + zero_sequence_value) / 3.0
    off_diagonal_value = (zero_sequence_value - positive_sequence_value) / 3.0
    matrix = np.full((3, 3), off_diagonal_value, dtype=np.complex128)
    np.fill_diagonal(matrix, diagonal_value)
    return matrix


def _assert_template_matrix_contract(template, expected_z: np.ndarray, expected_y: np.ndarray) -> None:
    np.testing.assert_allclose(template.z_nabc, expected_z)
    np.testing.assert_allclose(template.y_nabc, expected_y)
    np.testing.assert_array_equal(template.z_phases_nabc, np.array([1, 2, 3]))
    np.testing.assert_array_equal(template.y_phases_nabc, np.array([1, 2, 3]))

    line = Line(template=template, length=10.0)
    angular_frequency = 2.0 * np.pi * 50.0
    expected_tau = line.length * np.sqrt(np.imag(expected_z[0, 0]) * np.imag(expected_y[0, 0])) / angular_frequency
    assert np.isclose(line.get_tau(w=angular_frequency), expected_tau)


def test_sequence_line_type_exposes_physical_phase_matrices() -> None:
    template = SequenceLineType(R=0.1, X=0.4, B=12.0, G=2.0,
                                R0=0.3, X0=1.2, B0=6.0, G0=1.0)
    expected_z = _expected_phase_matrix(0.1 + 0.4j, 0.3 + 1.2j)
    expected_y = _expected_phase_matrix((2.0 + 12.0j) * 1.0e-6,
                                        (1.0 + 6.0j) * 1.0e-6)

    _assert_template_matrix_contract(template, expected_z, expected_y)


def test_sequence_line_type_builds_shunt_matrix_from_capacitance() -> None:
    template = SequenceLineType(CnF=12.0, CnF0=6.0, G=2.0, G0=1.0,
                                use_conductance=True)
    expected_y = _expected_phase_matrix(
        2.0e-6 + 2j * np.pi * 50.0 * 12.0e-9,
        1.0e-6 + 2j * np.pi * 50.0 * 6.0e-9,
    )

    np.testing.assert_allclose(template.y_nabc, expected_y)


def test_underground_line_type_exposes_physical_phase_matrices() -> None:
    template = UndergroundLineType(R=0.1, X=0.4, B=12.0,
                                   R0=0.3, X0=1.2, B0=6.0)
    expected_z = _expected_phase_matrix(0.1 + 0.4j, 0.3 + 1.2j)
    expected_y = _expected_phase_matrix(12.0e-6j, 6.0e-6j)

    _assert_template_matrix_contract(template, expected_z, expected_y)


def test_underground_line_type_builds_shunt_matrix_from_capacitance() -> None:
    template = UndergroundLineType(C=0.012, C0=0.006, freq=60.0)
    expected_y = _expected_phase_matrix(
        2j * np.pi * 60.0 * 0.012e-6,
        2j * np.pi * 60.0 * 0.006e-6,
    )

    np.testing.assert_allclose(template.y_nabc, expected_y)


def test_physical_line_templates_with_zero_sequence_scalars_are_not_reduced() -> None:
    """Keep matrix-defined tower and cable lines in the three-phase network.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    bus_from: Bus = grid.add_bus(Bus(name="From"))
    bus_to: Bus = grid.add_bus(Bus(name="To"))
    templates: tuple[OverheadLineType, UndergroundLineType] = (
        OverheadLineType(name="Single-phase tower"),
        UndergroundLineType(name="Single-phase cable"),
    )

    template: OverheadLineType | UndergroundLineType
    for template in templates:
        line: Line = Line(
            name=template.name,
            bus_from=bus_from,
            bus_to=bus_to,
            r=0.0,
            x=0.0,
            template=template,
        )
        grid.add_line(line)

    numerical_circuit: Any = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)

    np.testing.assert_array_equal(
        numerical_circuit.passive_branch_data.reducible,
        np.array([False, False]),
    )


def test_single_phase_overhead_line_without_neutral_applies_physical_matrix() -> None:
    """Apply a phase-C tower that has no neutral conductor.

    :return: None.
    """
    # Model the physical conductor exported by PowerFactory for LineConfig605.
    conductor: Wire = Wire(
        name="LineConfig605 conductor",
        r=0.6959,
        max_current=0.23,
        diameter=8.8392,
    )
    template: OverheadLineType = OverheadLineType(
        name="LineConfig605",
        Vnom=4.16,
        earth_resistivity=100.0,
        frequency=60.0,
    )
    template.add_wire_relationship(
        wire=conductor,
        xpos=0.1524,
        ypos=7.3152,
        phase=3,
    )

    # Applying the template must retain the physical matrix on phase C.
    bus_from: Bus = Bus(name="684", Vnom=4.16)
    bus_to: Bus = Bus(name="611", Vnom=4.16)
    line: Line = Line(
        name="LOHL684-611",
        bus_from=bus_from,
        bus_to=bus_to,
        length=0.0914,
    )
    logger: Logger = Logger()
    line.apply_template(obj=template, Sbase=100.0, freq=60.0, logger=logger)

    assert not logger.has_errors()
    assert line.template is template
    np.testing.assert_array_equal(template.z_phases_nabc, np.array([3]))
    np.testing.assert_array_equal(template.y_phases_nabc, np.array([3]))
    assert line.ys.phC
    assert not line.ys.phN
    assert line.ys.values[3, 3] != 0.0j
    assert line.ysh.values[3, 3] != 0.0j


@pytest.mark.parametrize("voltage,base_power,length", ((132.0, 100.0, 3.7), (33.0, 50.0, 0.15)))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("base_ratio", (0.5, 1.0, 2.0))
@pytest.mark.parametrize("conductance", (0.0, 2.0))
def test_line_change_base_preserves_physical_equivalent(
        tmp_path: Path, voltage: float, base_power: float, length: float,
        frequency: float, base_ratio: float, conductance: float,
) -> None:
    """Keep physical sequence and terminal quantities invariant under rebasing.

    :param tmp_path: Directory for a real native persistence round trip.
    :param voltage: Fixed line-to-line voltage base in kV.
    :param base_power: Initial three-phase power base in MVA.
    :param length: Physical line length in km.
    :param frequency: Network frequency in Hz for capacitive conversion.
    :param base_ratio: New power base divided by the initial base.
    :param conductance: Positive-sequence catalogue conductance in uS/km.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=base_power, fbase=frequency)
    source: Bus = grid.add_bus(Bus(name="Source", Vnom=voltage))
    target: Bus = grid.add_bus(Bus(name="Target", Vnom=voltage))
    template: SequenceLineType = SequenceLineType(
        Vnom=voltage, R=0.06, X=0.11, R0=0.18, X0=0.33,
        CnF=200.0, CnF0=100.0, G=conductance, G0=conductance / 2.0,
        use_conductance=True,
    )
    grid.add_sequence_line(template)
    line: Line = Line(bus_from=source, bus_to=target, length=length)
    grid.add_line(line)
    line.apply_template(obj=template, Sbase=base_power, freq=frequency,
                        logger=Logger(), decimals_rounding=16)

    # Physical data are the oracle; they do not depend on the rebasing implementation.
    omega: float = 2.0 * np.pi * frequency
    physical_z: np.ndarray = length * np.array((0.06 + 0.11j, 0.18 + 0.33j, 0.12 + 0.22j))
    physical_y: np.ndarray = length * np.array((
        complex(conductance * 1e-6, omega * 200e-9),
        complex(conductance * 0.5e-6, omega * 100e-9),
        complex(conductance * 0.3e-6, omega * 150e-9),
    ))
    initial_zbase: float = voltage * voltage / base_power
    line.R2 = float(physical_z[2].real / initial_zbase)
    line.X2 = float(physical_z[2].imag / initial_zbase)
    line.G2 = float(physical_y[2].real * initial_zbase)
    line.B2 = float(physical_y[2].imag * initial_zbase)
    # Existing ABC reconstruction assumes Z2=Z1; rebasing must preserve that policy.
    zero_projector: np.ndarray = np.ones((3, 3), dtype=complex) / 3.0
    other_projector: np.ndarray = np.eye(3, dtype=complex) - zero_projector
    physical_series: np.ndarray = other_projector / physical_z[0] + zero_projector / physical_z[1]
    physical_shunt: np.ndarray = other_projector * physical_y[0] + zero_projector * physical_y[1]
    phase_rotation: np.ndarray = np.exp(2j * np.pi * np.array((0.0, -1.0, 1.0)) / 3.0)
    vf: np.ndarray = np.array((1.0, 0.97, 1.02)) * phase_rotation
    vt: np.ndarray = np.array((0.98, 1.01, 0.96)) * phase_rotation * np.exp(-0.025j)
    voltage_phase_base: float = voltage * 1e3 / np.sqrt(3.0)
    expected_if: np.ndarray = (physical_series @ (vf - vt) + physical_shunt @ vf / 2.0) * voltage_phase_base
    expected_it: np.ndarray = (physical_series @ (vt - vf) + physical_shunt @ vt / 2.0) * voltage_phase_base
    scalar_voltage: np.ndarray = np.array((1.0 + 0.0j, 0.98 * np.exp(-0.025j)))
    expected_scalar_current: complex = (
        (scalar_voltage[0] - scalar_voltage[1]) / physical_z[0]
        + physical_y[0] * scalar_voltage[0] / 2.0
    ) * voltage_phase_base
    expected_power: np.ndarray = voltage_phase_base * np.array((
        np.sum(vf * np.conj(expected_if)), np.sum(vt * np.conj(expected_it)),
    ))
    target_base: float
    for target_base in (base_power * base_ratio, base_power):
        grid.change_base(Sbase_new=target_base)
        zbase: float = voltage * voltage / target_base
        current_base: float = target_base * 1e6 / (np.sqrt(3.0) * voltage * 1e3)
        actual_z: np.ndarray = np.array((complex(line.R, line.X), complex(line.R0, line.X0), complex(line.R2, line.X2))) * zbase
        actual_y: np.ndarray = np.array((complex(line.G, line.B), complex(line.G0, line.B0), complex(line.G2, line.B2))) / zbase
        np.testing.assert_allclose(actual_z, physical_z, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(actual_y, physical_y, rtol=1e-10, atol=1e-12)
        numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
        np.testing.assert_allclose(numerical.passive_branch_data.G[0] / zbase, physical_y[0].real, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(numerical.passive_branch_data.G0[0] / zbase, physical_y[1].real, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(line.ys.values[1:, 1:] / zbase, physical_series, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(line.ysh.values[1:, 1:] * 1e-6 / zbase, physical_shunt, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(numerical.passive_branch_data.Yff3[1:, 1:] / zbase, physical_series + physical_shunt / 2.0, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(numerical.passive_branch_data.Ytt3[1:, 1:] / zbase, physical_series + physical_shunt / 2.0, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(numerical.passive_branch_data.Yft3[1:, 1:] / zbase, -physical_series, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(numerical.passive_branch_data.Ytf3[1:, 1:] / zbase, -physical_series, rtol=1e-10, atol=1e-12)
        actual_if: np.ndarray = (numerical.passive_branch_data.Yff3[1:, 1:] @ vf + numerical.passive_branch_data.Yft3[1:, 1:] @ vt) * current_base
        actual_it: np.ndarray = (numerical.passive_branch_data.Ytf3[1:, 1:] @ vf + numerical.passive_branch_data.Ytt3[1:, 1:] @ vt) * current_base
        np.testing.assert_allclose(actual_if, expected_if, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(actual_it, expected_it, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(voltage_phase_base * np.array((np.sum(vf * np.conj(actual_if)), np.sum(vt * np.conj(actual_it)))), expected_power, rtol=1e-10, atol=1e-12)
        scalar_current: np.ndarray = numerical.get_admittance_matrices().Yf @ scalar_voltage * current_base
        np.testing.assert_allclose(scalar_current[0], expected_scalar_current, rtol=1e-10, atol=1e-12)

        # Persistence must retain the new base and canonical object/reference identity.
        output_path: Path = tmp_path / "rebased_line.veragrid"
        FileSave(circuit=grid, file_name=str(output_path)).save()
        restored: MultiCircuit = FileOpen(file_name=str(output_path)).open()
        loaded: Line = restored.lines[0]
        assert restored.Sbase == target_base and restored.fBase == frequency
        assert loaded.idtag == line.idtag
        assert loaded.template is restored.sequence_line_types[0]
        assert loaded.template.idtag == template.idtag
        loaded_z: np.ndarray = np.array((complex(loaded.R, loaded.X), complex(loaded.R0, loaded.X0), complex(loaded.R2, loaded.X2))) * zbase
        loaded_y: np.ndarray = np.array((complex(loaded.G, loaded.B), complex(loaded.G0, loaded.B0), complex(loaded.G2, loaded.B2))) / zbase
        np.testing.assert_allclose(loaded_z, physical_z, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(loaded_y, physical_y, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(loaded.ys.values, line.ys.values, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(loaded.ysh.values, line.ysh.values, rtol=1e-10, atol=1e-12)
        loaded.apply_template(obj=restored.sequence_line_types[0], Sbase=target_base,
                              freq=frequency, logger=Logger(), decimals_rounding=16)
        np.testing.assert_allclose(loaded.ys.values, line.ys.values, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(loaded.ysh.values, line.ysh.values, rtol=1e-10, atol=1e-12)
        assert template.R == 0.06 and template.R0 == 0.18
        assert template.G == conductance and template.G0 == conductance / 2.0
        assert template.Cnf == 200.0 and template.Cnf0 == 100.0


@pytest.mark.parametrize("base_ratio", (0.5, 1.0, 2.0))
@pytest.mark.parametrize("empty", (False, True))
def test_line_change_base_preserves_custom_phase_data(base_ratio: float, empty: bool) -> None:
    """Preserve matrix storage, phase selections and custom unbalanced coupling.

    :param base_ratio: New system power base divided by the initial base.
    :param empty: Exercise a line with no stored phase matrices.
    :return: None.
    """
    line: Line = Line()
    # Custom/empty stored data require disabling the established lazy reconstruction.
    line.disable_auto_updates()
    size: int = 0 if empty else 4
    series: AdmittanceMatrix = AdmittanceMatrix(size=size)
    shunt: AdmittanceMatrix = AdmittanceMatrix(size=size)
    matrix: AdmittanceMatrix
    for matrix in (series, shunt):
        matrix.phN = True
        matrix.phA = True
        matrix.phB = False
        matrix.phC = True
    if empty:
        pass
    else:
        # These unequal entries cannot be recovered by balanced sequence regeneration.
        series.values = np.array(((2 + 3j, 0.1j, 0j, -0.2j), (0.1j, 4 + 5j, 0j, -0.3j), (0j, 0j, 0j, 0j), (-0.2j, -0.3j, 0j, 6 + 7j)))
        shunt.values = np.array(((3 + 2j, 0.2j, 0j, -0.1j), (0.2j, 5 + 4j, 0j, -0.4j), (0j, 0j, 0j, 0j), (-0.1j, -0.4j, 0j, 7 + 6j)))
    line.ys = series
    line.ysh = shunt
    series_array: np.ndarray = series.values
    shunt_array: np.ndarray = shunt.values
    series_before: np.ndarray = series_array.copy()
    shunt_before: np.ndarray = shunt_array.copy()
    line.change_base(Sbase_old=100.0, Sbase_new=100.0 * base_ratio)
    assert line.ys is series and line.ysh is shunt
    assert series.values is series_array and shunt.values is shunt_array
    np.testing.assert_allclose(series.values, series_before / base_ratio, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(shunt.values, shunt_before / base_ratio, rtol=1e-12, atol=1e-12)
    for matrix in (series, shunt):
        assert matrix.size == size
        assert matrix.phN and matrix.phA and not matrix.phB and matrix.phC


@pytest.mark.parametrize("old_base,new_base", ((0.0, 100.0), (-1.0, 100.0), (np.nan, 100.0), (np.inf, 100.0), (100.0, 0.0), (100.0, -1.0), (100.0, np.nan), (100.0, np.inf)))
def test_line_change_base_rejects_invalid_bases(old_base: float, new_base: float) -> None:
    """Retain the existing device-level no-op for invalid power bases.

    :param old_base: Original system power base in MVA.
    :param new_base: Requested system power base in MVA.
    :return: None.
    """
    line: Line = Line(r=0.01, x=0.1, b=0.002, g=0.003,
                      r0=0.02, x0=0.2, b0=0.004, g0=0.005,
                      r2=0.03, x2=0.3, b2=0.006, g2=0.007)
    line.fill_3_phase_from_sequence()
    before: np.ndarray = np.array((line.R, line.X, line.B, line.G, line.R0, line.X0, line.B0, line.G0, line.R2, line.X2, line.B2, line.G2))
    series_before: np.ndarray = line.ys.values.copy()
    shunt_before: np.ndarray = line.ysh.values.copy()
    line.change_base(Sbase_old=old_base, Sbase_new=new_base)
    after: np.ndarray = np.array((line.R, line.X, line.B, line.G, line.R0, line.X0, line.B0, line.G0, line.R2, line.X2, line.B2, line.G2))
    np.testing.assert_array_equal(after, before)
    np.testing.assert_array_equal(line.ys.values, series_before)
    np.testing.assert_array_equal(line.ysh.values, shunt_before)
