"""Tests for solver-independent remedial action group conditions."""

from pathlib import Path
from typing import Dict, List

import pytest

import VeraGridEngine.Devices as dev
from VeraGridEngine.enumerations import RemedialActionPropertyEnum
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave


def test_remedial_action_group_exposes_only_device_specific_limits() -> None:
    """
    Check that each supported device exposes only its applicable limits.

    :return: None.
    """
    group: dev.RemedialActionGroup = dev.RemedialActionGroup()
    assert group.conn_group is None
    assert group.get_allowed_property_types() == []
    assert group.is_condition_met(observed_value=0.0)

    bus: dev.Bus = dev.Bus()
    group.monitored_device = bus
    assert group.get_allowed_property_types() == [
        RemedialActionPropertyEnum.Vmin,
        RemedialActionPropertyEnum.Vmax,
    ]

    line: dev.Line = dev.Line()
    group.monitored_device = line
    assert group.get_allowed_property_types() == [
        RemedialActionPropertyEnum.Loading,
        RemedialActionPropertyEnum.ContingencyLoading,
    ]

    transformer: dev.Transformer2W = dev.Transformer2W()
    group.monitored_device = transformer
    assert group.get_allowed_property_types() == [
        RemedialActionPropertyEnum.Loading,
        RemedialActionPropertyEnum.ContingencyLoading,
    ]

    with pytest.raises(ValueError, match='property_type is not applicable'):
        group.property_type = RemedialActionPropertyEnum.Vmin

    with pytest.raises(ValueError, match='bus, line, or two-winding transformer'):
        group.monitored_device = dev.Generator()


def test_remedial_action_group_evaluates_bus_voltage_limits() -> None:
    """
    Check strict lower and upper bus-voltage limit violations.

    :return: None.
    """
    bus: dev.Bus = dev.Bus(vmin=0.9, vmax=1.1)
    group: dev.RemedialActionGroup = dev.RemedialActionGroup()
    group.monitored_device = bus
    group.property_type = RemedialActionPropertyEnum.Vmin

    assert group.get_limit_value() == pytest.approx(0.9)
    assert group.is_condition_met(observed_value=0.899j)
    assert not group.is_condition_met(observed_value=0.9)

    group.property_type = RemedialActionPropertyEnum.Vmax
    assert group.get_limit_value() == pytest.approx(1.1)
    assert not group.is_condition_met(observed_value=1.1)
    assert group.is_condition_met(observed_value=1.101j)


def test_remedial_action_group_evaluates_branch_loading_limits() -> None:
    """
    Check normal and contingency per-unit loading limit violations.

    :return: None.
    """
    line: dev.Line = dev.Line(contingency_factor=1.2)
    group: dev.RemedialActionGroup = dev.RemedialActionGroup()
    group.monitored_device = line
    group.property_type = RemedialActionPropertyEnum.Loading

    assert group.get_limit_value() == pytest.approx(1.0)
    assert not group.is_condition_met(observed_value=1.0)
    assert group.is_condition_met(observed_value=-1.01)

    group.property_type = RemedialActionPropertyEnum.ContingencyLoading
    assert group.get_limit_value() == pytest.approx(1.2)
    assert not group.is_condition_met(observed_value=1.2)
    assert group.is_condition_met(observed_value=1.201)


def test_changing_monitored_device_clears_an_incompatible_limit() -> None:
    """
    Check that a stale property cannot survive a monitored-device change.

    :return: None.
    """
    group: dev.RemedialActionGroup = dev.RemedialActionGroup()
    group.monitored_device = dev.Line()
    group.property_type = RemedialActionPropertyEnum.Loading

    group.monitored_device = dev.Bus()

    assert group.property_type is None
    assert 'lower_bound' not in group.registered_properties
    assert 'upper_bound' not in group.registered_properties


def test_remedial_action_group_dependency_builds_an_acyclic_cascade() -> None:
    """
    Check independent, cascaded, self-referencing, and cyclic dependencies.

    :return: None.
    """
    first_group: dev.RemedialActionGroup = dev.RemedialActionGroup(name='First')
    second_group: dev.RemedialActionGroup = dev.RemedialActionGroup(name='Second')
    second_group.prev_ra = first_group
    third_group: dev.RemedialActionGroup = dev.RemedialActionGroup(name='Third')
    third_group.prev_ra = second_group

    assert first_group.prev_ra is None
    assert second_group.prev_ra is first_group
    assert third_group.prev_ra is second_group

    with pytest.raises(ValueError, match='cannot depend on itself'):
        first_group.prev_ra = first_group

    with pytest.raises(ValueError, match='cannot depend on itself'):
        first_group.prev_ra = third_group

    with pytest.raises(TypeError, match='RemedialActionGroup or None'):
        first_group.prev_ra = dev.Bus()

    assert first_group.prev_ra is None


def test_remedial_action_group_dependencies_survive_unordered_roundtrip(tmp_path: Path) -> None:
    """Preserve forward and backward group references through native save and load.

    :param tmp_path: Isolated pytest output directory.
    :return: None.
    """
    groups: List[dev.RemedialActionGroup] = [
        dev.RemedialActionGroup(name='Group 0'),
        dev.RemedialActionGroup(name='Group 1'),
        dev.RemedialActionGroup(name='Group 2'),
        dev.RemedialActionGroup(name='Group 3'),
        dev.RemedialActionGroup(name='Group 4'),
    ]
    for index in range(1, len(groups)):
        groups[index].prev_ra = groups[index - 1]

    circuit: dev.MultiCircuit = dev.MultiCircuit()
    storage_order: List[int] = [4, 2, 0, 3, 1]
    for index in storage_order:
        circuit.add_remedial_action_group(obj=groups[index])

    output_path: Path = tmp_path / 'unordered_remedial_action_groups.veragrid'
    FileSave(circuit=circuit, file_name=str(output_path)).save()
    restored: dev.MultiCircuit = FileOpen(file_name=str(output_path)).open()

    restored_by_name: Dict[str, dev.RemedialActionGroup] = {
        group.name: group for group in restored.remedial_action_groups
    }
    assert [group.name for group in restored.remedial_action_groups] == [
        groups[index].name for index in storage_order
    ]
    for index, group in enumerate(groups):
        restored_group: dev.RemedialActionGroup = restored_by_name[group.name]
        if index == 0:
            assert restored_group.prev_ra is None
        else:
            assert restored_group.prev_ra is restored_by_name[groups[index - 1].name]
    equal, logger = restored.compare_circuits(circuit)
    if not equal:
        logger.print()
    else:
        pass
    assert equal


def test_remedial_action_group_monitored_device_survives_roundtrip(tmp_path: Path) -> None:
    """Resolve a broad physical-device reference after native circuit loading.

    :param tmp_path: Isolated pytest output directory.
    :return: None.
    """
    monitored_bus: dev.Bus = dev.Bus(name='Monitored bus')
    group: dev.RemedialActionGroup = dev.RemedialActionGroup(name='Bus voltage condition')
    group.monitored_device = monitored_bus

    circuit: dev.MultiCircuit = dev.MultiCircuit()
    circuit.add_bus(obj=monitored_bus)
    circuit.add_remedial_action_group(obj=group)

    output_path: Path = tmp_path / 'remedial_action_group_monitored_device.veragrid'
    FileSave(circuit=circuit, file_name=str(output_path)).save()
    file_open: FileOpen = FileOpen(file_name=str(output_path))
    restored: dev.MultiCircuit = file_open.open()

    restored_group: dev.RemedialActionGroup = restored.remedial_action_groups[0]
    assert restored_group.monitored_device is restored.buses[0]
    assert not any(entry.severity.value == 'Error' for entry in file_open.logger.entries)
