# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path

import numpy as np
import pytest

import VeraGridEngine.Devices as dev
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import CableResistanceInput


def build_pf_606_cable() -> dev.UndergroundCableType:
    """Build the full-precision ``250 AA CN`` PowerFactory construction.

    :return: Physical cable input used by the PowerFactory 606 system.
    """
    return dev.UndergroundCableType(
        name='250 AA CN',
        nominal_voltage=15.0,
        core_dc_resistance=0.222551,
        core_diameter=12.716179847717285,
        core_internal_diameter=0.0,
        cable_diameter=30.54450798034668,
        sheath_thickness=0.15925799310207367,
        main_insulation_thickness=7.103906154632568,
        core_resistivity=2.8264000415802,
        sheath_resistivity=1.7240999937057495,
        core_filling_factor=100.0,
        sheath_filling_factor=99.44011688232422,
        main_insulation_permittivity=2.299999952316284,
        outer_insulation_permittivity=2.5,
        main_insulation_loss_tangent=0.0,
        outer_insulation_loss_tangent=0.0,
        core_relative_permeability=1.0,
        sheath_relative_permeability=0.999993622303009,
        skin_effect_factor=1.0,
        proximity_effect_factor=1.0,
    )


def build_pf_606_system(cable: dev.UndergroundCableType) -> dev.UndergroundLineType:
    """Build and calculate the full-precision PowerFactory 606 geometry.

    :param cable: Shared physical cable construction.
    :return: Calculated three-phase cable system.
    """
    system: dev.UndergroundLineType = dev.UndergroundLineType(
        name='606',
        Imax=0.26,
        Vnom=15.0,
        freq=60.0,
        earth_resistivity=100.0,
    )
    x_positions: np.ndarray = np.array([-0.1524, 0.0, 0.1524], dtype=float)
    phase_index: int
    for phase_index in range(3):
        system.add_cable_relationship(
            cable=cable,
            xpos=float(x_positions[phase_index]),
            ypos=0.609599980492801,
            phase=phase_index + 1,
        )
    assert system.compute()
    return system


def test_pf_606_primitive_matrices_match_powerfactory_2024() -> None:
    """Match full-precision primitive values read from PowerFactory 2024.

    :return: None.
    """
    system: dev.UndergroundLineType = build_pf_606_system(cable=build_pf_606_cable())
    expected_impedance: np.ndarray = np.array(
        [
            0.2822073966824634 + 0.9089254735303836j,
            1.338651047334841 + 0.8329460885648026j,
            0.05912471567796385 + 0.65056887441533j,
            0.059124687236848154 + 0.5983068106852449j,
            0.05912476191650118 + 0.8330938788964809j,
        ],
        dtype=complex,
    )
    actual_impedance: np.ndarray = np.array(
        [
            system.z_primitive[0, 0],
            system.z_primitive[3, 3],
            system.z_primitive[0, 1],
            system.z_primitive[0, 2],
            system.z_primitive[0, 3],
        ],
        dtype=complex,
    )
    expected_admittance: np.ndarray = np.array(
        [64.3048474379772e-6j, 522.6045601338822e-6j],
        dtype=complex,
    )
    actual_admittance: np.ndarray = np.array(
        [system.y_primitive[0, 0], system.y_primitive[3, 3]],
        dtype=complex,
    )
    np.testing.assert_allclose(actual_impedance, expected_impedance, rtol=0.0, atol=1.0e-8)
    np.testing.assert_allclose(actual_admittance, expected_admittance, rtol=0.0, atol=1.0e-15)


def test_physical_cable_system_survives_veragrid_roundtrip(tmp_path: Path) -> None:
    """Preserve physical inputs and catalogue references in native files.

    :param tmp_path: Isolated pytest output directory.
    :return: None.
    """
    cable: dev.UndergroundCableType = build_pf_606_cable()
    system: dev.UndergroundLineType = build_pf_606_system(cable=cable)
    circuit: dev.MultiCircuit = dev.MultiCircuit()
    circuit.add_underground_cable(obj=cable)
    circuit.add_underground_line(obj=system)
    output_path: Path = tmp_path / 'physical_underground_cable.veragrid'
    FileSave(circuit=circuit, file_name=str(output_path)).save()

    restored: dev.MultiCircuit = FileOpen(file_name=str(output_path)).open()
    assert len(restored.underground_cable_constructions) == 1
    assert len(restored.underground_cable_types) == 1
    restored_cable: dev.UndergroundCableType = restored.underground_cable_constructions[0]
    restored_system: dev.UndergroundLineType = restored.underground_cable_types[0]
    assert restored_system.cables_in_system.data[0].cable is restored_cable
    assert restored_system.compute()
    np.testing.assert_allclose(restored_system.z_primitive, system.z_primitive, rtol=0.0, atol=1.0e-12)
    np.testing.assert_array_equal(restored_system.y_primitive, system.y_primitive)
    assert restored_cable.sheath_filling_factor == cable.sheath_filling_factor
    assert restored_cable.outer_insulation_permittivity == cable.outer_insulation_permittivity


def test_powerfactory_v7_dgs_imports_physical_cables() -> None:
    """Import the tracked V7.00 cable project fixture end to end.

    :return: None.
    """
    dgs_path: Path = (
        Path(__file__).resolve().parents[1]
        / 'data'
        / 'grids'
        / 'DGS'
        / 'UnbalancedNetworkModel_Cables_606_v7.dgs'
    )
    circuit: dev.MultiCircuit = FileOpen(file_name=str(dgs_path)).open()
    assert len(circuit.underground_cable_constructions) == 3
    assert len(circuit.underground_cable_types) == 4

    system_606: dev.UndergroundLineType = next(
        system for system in circuit.underground_cable_types if system.name == '606'
    )
    line_606: dev.Line = next(line for line in circuit.lines if line.name == 'LC692-675')
    line_607: dev.Line = next(line for line in circuit.lines if line.name == 'LC684-652')
    assert line_606.template is system_606
    assert isinstance(line_607.template, dev.UndergroundLineType)
    assert line_607.template.z_nabc.shape == (1, 1)
    # PF exposes this core admittance when the eliminated concentric-neutral sheath is grounded.
    np.testing.assert_allclose(
        line_607.template.y_nabc,
        np.array([[52.11094270079967e-6j]], dtype=complex),
        rtol=0.0,
        atol=1.0e-15,
    )
    np.testing.assert_allclose(
        system_606.z_primitive[0, 0],
        0.2822073966824634 + 0.9089254735303836j,
        rtol=0.0,
        atol=1.0e-7,
    )
    assert np.isclose(system_606.cables_in_system.data[0].cable.sheath_filling_factor, 99.44012)


def test_resistance_input_modes_produce_equivalent_matrices() -> None:
    """Both measured resistances and equivalent material inputs give the same matrices."""
    material = build_pf_606_cable()
    material.core_filling_factor = 85.0
    material.sheath_filling_factor = 72.0
    reference = build_pf_606_system(material)
    direct = build_pf_606_cable()
    direct.resistance_input = CableResistanceInput.DcResistance
    direct.core_dc_resistance = material.core_dc_resistance
    direct.sheath_dc_resistance = material.sheath_dc_resistance
    # Inactive material values must not influence or invalidate the DC input.
    direct.core_resistivity = float('nan')
    direct.core_filling_factor = 0.0
    direct.sheath_resistivity = float('nan')
    direct.sheath_filling_factor = 0.0
    system = build_pf_606_system(direct)
    np.testing.assert_allclose(system.z_primitive, reference.z_primitive, rtol=1e-7, atol=1e-9)
    np.testing.assert_allclose(system.z_nabc, reference.z_nabc, rtol=1e-7, atol=1e-9)
    np.testing.assert_array_equal(system.y_primitive, reference.y_primitive)
    direct.core_dc_resistance *= 2.0
    assert system.compute()
    assert not np.allclose(system.z_nabc, reference.z_nabc)
    direct.core_dc_resistance = material.core_dc_resistance
    direct.sheath_dc_resistance *= 2.0
    assert system.compute()
    assert not np.allclose(system.z_primitive[3:, 3:], reference.z_primitive[3:, 3:])
    assert not np.allclose(system.z_nabc, reference.z_nabc)
    np.testing.assert_array_equal(system.y_primitive, reference.y_primitive)


def test_material_mode_uses_derived_resistance_and_preserves_legacy_matrices() -> None:
    """An old informational R cannot override or contradict the active inputs."""
    cable = build_pf_606_cable()
    system = build_pf_606_system(cable)
    before = system.z_primitive.copy()
    expected_r = 1000.0 * cable.core_resistivity * 1e-8 / (
        np.pi * (cable.core_diameter * 0.5e-3) ** 2 * cable.core_filling_factor / 100.0
    )
    cable.core_dc_resistance = 99.0  # Simulate an inconsistent legacy rpha field.
    assert cable.resistance_input == CableResistanceInput.Resistivity
    assert cable.core_dc_resistance == pytest.approx(expected_r)
    assert system.compute()
    np.testing.assert_array_equal(system.z_primitive, before)
    cable.core_filling_factor /= 2.0
    assert cable.core_dc_resistance == pytest.approx(2.0 * expected_r)


@pytest.mark.parametrize('layer', ['core', 'sheath'])
@pytest.mark.parametrize('resistance', [0.0, -1.0, float('nan'), float('inf')])
def test_invalid_direct_resistance_is_reported_before_calculation(layer: str, resistance: float) -> None:
    cable = build_pf_606_cable()
    system = build_pf_606_system(cable)
    cable.set_value(cable.registered_properties['resistance_input'], None, CableResistanceInput.DcResistance)
    setattr(cable, f'{layer}_dc_resistance', resistance)
    logger = Logger()
    assert not system.compute(logger=logger)
    assert logger.has_errors()
    assert f'{layer.capitalize()} DC resistance' in str(logger)


def test_direct_resistance_survives_native_roundtrip(tmp_path: Path) -> None:
    cable = build_pf_606_cable()
    cable.resistance_input = CableResistanceInput.DcResistance
    cable.core_dc_resistance = 0.42
    cable.sheath_dc_resistance = 1.35
    system = build_pf_606_system(cable)
    circuit = dev.MultiCircuit()
    circuit.add_underground_cable(cable)
    circuit.add_underground_line(system)
    path = tmp_path / 'direct_resistance.veragrid'
    FileSave(circuit=circuit, file_name=str(path)).save()
    restored = FileOpen(file_name=str(path)).open()
    restored_cable = restored.underground_cable_constructions[0]
    restored_system = restored.underground_cable_types[0]
    assert restored_cable.resistance_input == CableResistanceInput.DcResistance
    assert restored_cable.core_dc_resistance == 0.42
    assert restored_cable.sheath_dc_resistance == 1.35
    assert restored_system.cables_in_system.data[0].cable is restored_cable
    assert restored_system.compute()
    np.testing.assert_array_equal(restored_system.z_primitive, system.z_primitive)


def test_legacy_native_cable_without_selector_uses_material_inputs() -> None:
    from VeraGridEngine.IO.veragrid.pack_unpack import gather_model_as_jsons, parse_veragrid_data

    cable = build_pf_606_cable()
    system = build_pf_606_system(cable)
    circuit = dev.MultiCircuit()
    circuit.add_underground_cable(cable)
    circuit.add_underground_line(system)
    payload = gather_model_as_jsons(circuit)
    entry = payload['model_data']['underground_cable_constructions'][0]
    del entry['resistance_input']
    del entry['core_dc_resistance']
    del entry['sheath_dc_resistance']
    entry['rpha'] = 99.0  # Old alias and inconsistent informational value.
    restored = parse_veragrid_data(payload, logger=Logger())
    restored_cable = restored.underground_cable_constructions[0]
    restored_system = restored.underground_cable_types[0]
    assert restored_cable.resistance_input == CableResistanceInput.Resistivity
    assert restored_cable.core_dc_resistance == cable.core_dc_resistance
    assert restored_system.compute()
    np.testing.assert_array_equal(restored_system.z_primitive, system.z_primitive)


def test_direct_resistance_matches_low_frequency_core_limit() -> None:
    """Check units and area conversion independently of the material-input path."""
    from VeraGridEngine.Devices.Branches.underground_cable_calculation import calculate_solid_surface_impedance

    cable = dev.UndergroundCableType(resistance_input=CableResistanceInput.DcResistance,
                                    core_dc_resistance=0.35, sheath_dc_resistance=1.1, core_diameter=18.0)
    resistivity, filling_factor = cable.get_core_material_properties()
    z_core = calculate_solid_surface_impedance(
        resistivity_uohm_cm=resistivity, filling_factor_percent=filling_factor,
        relative_permeability=1.0, skin_effect_factor=1.0,
        radius_m=0.009, frequency_hz=0.001,
    )
    assert z_core.real == pytest.approx(0.35, rel=1e-7)


def test_sheath_resistance_uses_annular_area_and_controls_tube_impedance() -> None:
    from VeraGridEngine.Devices.Branches.underground_cable_calculation import calculate_tube_surface_impedances

    cable = dev.UndergroundCableType(core_diameter=10.0, main_insulation_thickness=5.0,
                                    sheath_thickness=1.0, sheath_filling_factor=80.0)
    area = np.pi * (0.011**2 - 0.010**2)
    expected = 1000.0 * 1.7241e-8 / (0.8 * area)
    assert cable.sheath_dc_resistance == pytest.approx(expected)
    cable.set_value(cable.registered_properties['resistance_input'], None, CableResistanceInput.DcResistance)
    assert cable.sheath_dc_resistance == pytest.approx(expected)
    cable.sheath_dc_resistance = 0.75
    resistivity, filling = cable.get_sheath_material_properties()
    impedance = calculate_tube_surface_impedances(
        resistivity_uohm_cm=resistivity, filling_factor_percent=filling,
        relative_permeability=1.0, inner_radius_m=0.010, outer_radius_m=0.011, frequency_hz=0.001,
    )
    np.testing.assert_allclose(np.real(impedance), 0.75, rtol=1e-7, atol=0.0)
    cable.sheath_thickness = 2.0
    assert cable.sheath_dc_resistance == 0.75  # Measured input stays fixed.
    cable.set_value(cable.registered_properties['resistance_input'], None, CableResistanceInput.Resistivity)
    assert cable.sheath_dc_resistance == pytest.approx(0.75)
    cable.sheath_thickness = 1.0
    assert cable.sheath_dc_resistance > 0.75  # Material inputs stay fixed now.


def test_core_only_selector_file_recovers_legacy_sheath_resistance() -> None:
    from VeraGridEngine.IO.veragrid.pack_unpack import gather_model_as_jsons, parse_veragrid_data

    cable = build_pf_606_cable()
    sheath_r = cable.sheath_dc_resistance
    cable.set_value(cable.registered_properties['resistance_input'], None, CableResistanceInput.DcResistance)
    cable.core_dc_resistance = 0.42
    system = build_pf_606_system(cable)
    circuit = dev.MultiCircuit()
    circuit.add_underground_cable(cable)
    circuit.add_underground_line(system)
    payload = gather_model_as_jsons(circuit)
    entry = payload['model_data']['underground_cable_constructions'][0]
    entry['core_resistance_input'] = entry.pop('resistance_input')
    del entry['sheath_dc_resistance']
    restored = parse_veragrid_data(payload, logger=Logger())
    restored_cable = restored.underground_cable_constructions[0]
    assert restored_cable.resistance_input == CableResistanceInput.DcResistance
    assert restored_cable.core_dc_resistance == 0.42
    assert restored_cable.sheath_dc_resistance == pytest.approx(sheath_r)
    restored_system = restored.underground_cable_types[0]
    assert restored_system.compute()
    np.testing.assert_array_equal(restored_system.z_primitive, system.z_primitive)


def test_legacy_constructor_alias_does_not_add_another_selector() -> None:
    cable = dev.UndergroundCableType(core_resistance_input=CableResistanceInput.DcResistance,
                                    core_dc_resistance=0.4)
    cable.validate_resistance_inputs()
    assert cable.sheath_dc_resistance == cable.get_sheath_dc_resistance_from_material()
    assert cable.resistance_input == cable.core_resistance_input == CableResistanceInput.DcResistance
    selectors = [p.name for p in cable.property_list if p.tpe is CableResistanceInput]
    assert selectors == ['resistance_input']
