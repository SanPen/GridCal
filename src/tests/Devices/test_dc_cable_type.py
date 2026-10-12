from pathlib import Path

import pytest

import VeraGridEngine.api as vge
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import TypLne
from VeraGridEngine.IO.dgs.dgs_to_veragrid import convert_dgs_to_dc_cable_type
from VeraGridEngine.IO.dgs.veragrid_to_dgs import circuit_to_dgs
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.IO.veragrid.pack_unpack import get_objects_dictionary
from VeraGridEngine.enumerations import DynamicSimulationMode, FileType


def _build_dc_cable_grid() -> tuple[MultiCircuit, UndergroundLineType, DcLine]:
    """
    Build a small DC grid with one physical cable template.

    :return: Grid, canonical cable template, and the line using it.
    """
    grid: MultiCircuit = MultiCircuit()
    grid.Sbase = 100.0
    bus_from: Bus = grid.add_bus(Bus(name='DC from', Vnom=320.0, is_dc=True))
    bus_to: Bus = grid.add_bus(Bus(name='DC to', Vnom=320.0, is_dc=True))
    cable_type: UndergroundLineType = UndergroundLineType(
        name='320 kV cable',
        Vnom=320.0,
        Imax=1.5,
        R=0.02,
        X=2.0 * 3.141592653589793 * 50.0 * 0.001,
        C=1.0,
        freq=50.0,
    )
    line: DcLine = DcLine(
        bus_from=bus_from,
        bus_to=bus_to,
        name='DC cable span',
        length=10.0,
        rate=250.0,
    )

    # Register the provider before its consumer, matching the persistence
    # dependency that must be reconstructed when the file is reopened.
    grid.add_underground_line(obj=cable_type)
    grid.add_dc_line(obj=line)
    line.apply_template(obj=cable_type, Sbase=grid.Sbase)
    return grid, cable_type, line


def _build_dgs_dc_cable_type(capacitance_uf_per_km: float | None,
                             susceptance_us_per_km: float | None) -> TypLne:
    """
    Build one complete PowerFactory DC cable declaration for import tests.

    :param capacitance_uf_per_km: Direct physical capacitance, when exported.
    :param susceptance_us_per_km: Frequency-based alternative, when exported.
    :return: Parsed DGS line type with all other required physical fields.
    """
    frequency_hz: float = 50.0
    inductance_h_per_km: float = 0.001
    source_type: TypLne = TypLne()
    source_type.ID = 'dc-cable-type'
    source_type.loc_name = '320 kV DC cable'
    source_type.systp = 1
    source_type.cohl_ = 0
    source_type.cohl_declared = True
    source_type.uline = 320.0
    source_type.sline = 1.5
    source_type.rline = 0.02
    source_type.xline = 2.0 * 3.141592653589793 * frequency_hz * inductance_h_per_km
    source_type.cline = capacitance_uf_per_km
    source_type.bline = susceptance_us_per_km
    source_type.frnom = frequency_hz
    return source_type


def test_dgs_dc_cable_import_rejects_ac_type_even_when_cable() -> None:
    """Keep installation evidence separate from the electrical system type.

    :return: None.
    """
    source_type: TypLne = _build_dgs_dc_cable_type(
        capacitance_uf_per_km=0.25,
        susceptance_us_per_km=None,
    )
    source_type.systp = 0
    logger: Logger = Logger()
    cable_type: UndergroundLineType | None = convert_dgs_to_dc_cable_type(
        typlne=source_type,
        logger=logger,
    )

    assert cable_type is None
    assert logger.warning_count() == 1
    assert logger.entries[0].device_property == 'systp'


def test_dgs_dc_cable_import_rejects_missing_installation_evidence() -> None:
    """Keep a DC type resistive when no source field declares a cable.

    :return: None.
    """
    source_type: TypLne = _build_dgs_dc_cable_type(
        capacitance_uf_per_km=0.25,
        susceptance_us_per_km=None,
    )
    source_type.cohl_declared = False
    logger: Logger = Logger()
    cable_type: UndergroundLineType | None = convert_dgs_to_dc_cable_type(
        typlne=source_type,
        logger=logger,
    )

    assert cable_type is None
    assert logger.warning_count() == 1
    assert logger.entries[0].device_property == 'aohl_/cohl_'
    assert logger.entries[0].msg == (
        'DGS line type does not explicitly identify a cable; not creating Cable System'
    )


@pytest.mark.parametrize(
    ('legacy_code', 'current_code', 'expected_message'),
    (
        (None, 1, 'DC line type is explicitly overhead; keeping resistive DcLine without a cable template'),
        ('cab', 1, 'DGS line installation fields disagree; not creating Cable System'),
    ),
)
def test_dgs_dc_cable_import_rejects_overhead_or_conflicting_installation(
        legacy_code: str | None,
        current_code: int,
        expected_message: str,
) -> None:
    """Reject explicit overhead and contradictory cable declarations.

    :param legacy_code: Optional legacy installation declaration.
    :param current_code: Current installation declaration.
    :param expected_message: Diagnostic explaining the resistive fallback.
    :return: None.
    """
    source_type: TypLne = _build_dgs_dc_cable_type(
        capacitance_uf_per_km=0.25,
        susceptance_us_per_km=None,
    )
    source_type.aohl_ = legacy_code
    source_type.aohl_declared = legacy_code is not None
    source_type.cohl_ = current_code
    logger: Logger = Logger()
    cable_type: UndergroundLineType | None = convert_dgs_to_dc_cable_type(
        typlne=source_type,
        logger=logger,
    )

    assert cable_type is None
    assert len(logger.entries) == 1
    assert logger.entries[0].device_property == 'aohl_/cohl_'
    assert logger.entries[0].msg == expected_message


@pytest.mark.parametrize(
    ('capacitance_uf_per_km', 'susceptance_us_per_km'),
    (
        (0.25, None),
        (None, 2.0 * 3.141592653589793 * 50.0 * 0.25),
    ),
)
def test_dgs_dc_cable_import_accepts_either_capacitance_representation(
        capacitance_uf_per_km: float | None,
        susceptance_us_per_km: float | None,
) -> None:
    """
    Verify cline and bline reconstruct the same physical cable capacitance.

    :param capacitance_uf_per_km: Direct capacitance supplied by this case.
    :param susceptance_us_per_km: Alternative susceptance supplied by this case.
    :return: None.
    """
    source_type: TypLne = _build_dgs_dc_cable_type(
        capacitance_uf_per_km=capacitance_uf_per_km,
        susceptance_us_per_km=susceptance_us_per_km,
    )
    logger: Logger = Logger()
    cable_type: UndergroundLineType | None = convert_dgs_to_dc_cable_type(
        typlne=source_type,
        logger=logger,
    )

    assert cable_type is not None
    assert cable_type.get_dc_parameters()[1] == pytest.approx(0.001)
    assert cable_type.get_dc_parameters()[2] == pytest.approx(0.25e-6)
    assert logger.warning_count() == 0


def test_dgs_dc_cable_import_prefers_capacitance_when_fields_disagree() -> None:
    """
    Verify incoherent duplicate fields are logged without replacing physical C.

    :return: None.
    """
    source_type: TypLne = _build_dgs_dc_cable_type(
        capacitance_uf_per_km=0.25,
        susceptance_us_per_km=100.0,
    )
    logger: Logger = Logger()
    cable_type: UndergroundLineType | None = convert_dgs_to_dc_cable_type(
        typlne=source_type,
        logger=logger,
    )

    assert cable_type is not None
    assert cable_type.get_dc_parameters()[2] == pytest.approx(0.25e-6)
    assert logger.warning_count() == 1
    assert logger.entries[0].device_property == 'bline'
    assert logger.entries[0].msg == (
        'DC cable capacitance and susceptance are inconsistent; using capacitance'
    )


def test_dgs_v3_dc_cable_import_preserves_template_identity(
        tmp_path: Path,
) -> None:
    """Import and persist the explicitly classified V3 DC cable provider.

    :param tmp_path: Temporary directory supplied by pytest.
    :return: None.
    """
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / 'data'
        / 'grids'
        / 'DGS'
        / 'hvdc_vsc_v3_complete_static_dynamic.dgs'
    )
    file_open: FileOpen = FileOpen(
        file_name=str(fixture_path),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
            dgs_dynamic_simulation_mode=DynamicSimulationMode.RMS,
        ),
    )
    grid: MultiCircuit | None = file_open.open()

    assert grid is not None
    assert file_open.logger.error_count() == 0
    assert len(grid.underground_cable_types) == 1
    assert len(grid.dc_lines) > 0
    assert all(
        line.template is grid.underground_cable_types[0]
        for line in grid.dc_lines
    )

    roundtrip_path: Path = tmp_path / 'dgs_v3_dc_cable.veragrid'
    vge.save_file(grid=grid, filename=str(roundtrip_path))
    roundtrip_grid: MultiCircuit = vge.open_file(filename=str(roundtrip_path))

    assert len(roundtrip_grid.underground_cable_types) == 1
    assert len(roundtrip_grid.dc_lines) == len(grid.dc_lines)
    assert all(
        line.template is roundtrip_grid.underground_cable_types[0]
        for line in roundtrip_grid.dc_lines
    )


def test_dc_cable_type_applies_physical_values_without_overwriting_rating() -> None:
    """
    Verify template assignment and the frequency-neutral dynamic coefficients.

    :return: None.
    """
    grid: MultiCircuit
    cable_type: UndergroundLineType
    line: DcLine
    grid, cable_type, line = _build_dc_cable_grid()
    logger: Logger = Logger()
    inductance_pu_seconds: float
    capacitance_pu_seconds: float
    inductance_pu_seconds, capacitance_pu_seconds = line.get_dynamic_values_pu_seconds(
        Sbase=grid.Sbase,
        logger=logger,
    )

    impedance_base: float = 320.0 * 320.0 / grid.Sbase
    assert line.template is cable_type
    assert line.R == pytest.approx(0.02 * 10.0 / impedance_base)
    assert inductance_pu_seconds == pytest.approx(0.001 * 10.0 / impedance_base)
    assert capacitance_pu_seconds == pytest.approx(0.000001 * 10.0 * impedance_base)
    assert line.rate == pytest.approx(250.0)
    assert logger.warning_count() == 0


def test_dc_line_uses_logged_canonical_defaults_without_cable_template() -> None:
    """
    Verify the established zero dynamic defaults keep a resistive line usable.

    :return: None.
    """
    line: DcLine = DcLine(name='Legacy resistive DC line')
    logger: Logger = Logger()
    inductance_pu_seconds: float
    capacitance_pu_seconds: float
    inductance_pu_seconds, capacitance_pu_seconds = line.get_dynamic_values_pu_seconds(
        Sbase=100.0,
        logger=logger,
    )

    assert inductance_pu_seconds == 0.0
    assert capacitance_pu_seconds == 0.0
    assert logger.warning_count() == 1
    assert logger.entries[0].value == 'L=0, C=0'


def test_dc_cable_type_precedes_dc_line_and_survives_copy() -> None:
    """
    Verify ordered registration and canonical reference identity after copying.

    :return: None.
    """
    grid: MultiCircuit
    cable_type: UndergroundLineType
    line: DcLine
    grid, cable_type, line = _build_dc_cable_grid()
    object_keys: list[str] = list(get_objects_dictionary().keys())
    copied_grid: MultiCircuit = grid.copy()
    copied_type: UndergroundLineType = copied_grid.underground_cable_types[0]
    copied_line: DcLine = copied_grid.dc_lines[0]

    assert 'dc_cable_types' not in object_keys
    assert object_keys.index('underground_cable_types') < object_keys.index('dc_line')
    assert cable_type.device_type == DeviceType.UnderGroundLineDevice
    assert grid.get_elements_by_type(DeviceType.UnderGroundLineDevice) == list([cable_type])
    assert copied_type is not cable_type
    assert copied_line is not line
    assert copied_line.template is copied_type


def test_dc_line_copy_keeps_cable_length_and_dynamic_values() -> None:
    """
    Verify a direct line copy cannot shorten the physical cable span.

    :return: None.
    """
    grid: MultiCircuit
    cable_type: UndergroundLineType
    line: DcLine
    grid, cable_type, line = _build_dc_cable_grid()
    copied_line: DcLine = line.copy()
    source_values: tuple[float, float] | None = (
        line.get_applied_dynamic_values_pu_seconds(Sbase=grid.Sbase)
    )
    copied_values: tuple[float, float] | None = (
        copied_line.get_applied_dynamic_values_pu_seconds(Sbase=grid.Sbase)
    )

    assert copied_line.length == line.length
    assert copied_line.template is cable_type
    assert copied_values == source_values


def test_dc_cable_type_roundtrip_preserves_template_identity(tmp_path: Path) -> None:
    """
    Save and reopen a DC cable to prove provider-before-consumer persistence.

    :param tmp_path: Temporary directory supplied by pytest.
    :return: None.
    """
    grid: MultiCircuit
    cable_type: UndergroundLineType
    line: DcLine
    grid, cable_type, line = _build_dc_cable_grid()
    file_name: Path = tmp_path / 'dc_cable_type.veragrid'
    vge.save_file(grid=grid, filename=str(file_name))
    loaded_grid: MultiCircuit = vge.open_file(filename=str(file_name))

    assert len(loaded_grid.underground_cable_types) == 1
    assert len(loaded_grid.dc_lines) == 1
    assert loaded_grid.dc_lines[0].template is loaded_grid.underground_cable_types[0]


def test_deleting_dc_cable_type_clears_dc_line_dependency() -> None:
    """
    Verify deleting a template cannot leave a dangling line reference.

    :return: None.
    """
    grid: MultiCircuit
    cable_type: UndergroundLineType
    line: DcLine
    grid, cable_type, line = _build_dc_cable_grid()
    grid.delete_underground_line(obj=cable_type)

    assert len(grid.underground_cable_types) == 0
    assert line.template is None


def test_dgs_export_emits_dc_cable_provider_before_line() -> None:
    """
    Verify DGS export reconstructs frequency-based X/B from physical L/C.

    :return: None.
    """
    grid: MultiCircuit
    cable_type: UndergroundLineType
    line: DcLine
    grid, cable_type, line = _build_dc_cable_grid()
    dgs_grid: DgsCircuit = circuit_to_dgs(grid=grid)
    dc_types: list[TypLne] = list(
        typlne for typlne in dgs_grid.typlnes if int(typlne.systp) == 1
    )

    assert len(dc_types) == 1
    assert len(dgs_grid.elmlnes) == 1
    assert dgs_grid.elmlnes[0].typ_id == dc_types[0].ID
    assert dc_types[0].rline == pytest.approx(cable_type.R)
    assert dc_types[0].xline == pytest.approx(
        2.0 * 3.141592653589793 * grid.fBase * cable_type.get_dc_parameters()[1]
    )
    assert dc_types[0].cline == pytest.approx(cable_type.get_dc_parameters()[2] * 1.0e6)
    assert dc_types[0].bline == pytest.approx(
        2.0 * 3.141592653589793 * grid.fBase * cable_type.get_dc_parameters()[2] * 1.0e6
    )


def test_dgs_export_keeps_resistive_fallback_energy_fields_blank() -> None:
    """
    Verify exporting a typeless DcLine does not persist invented cable L/C.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    grid.Sbase = 100.0
    bus_from: Bus = grid.add_bus(Bus(name='DC from', Vnom=320.0, is_dc=True))
    bus_to: Bus = grid.add_bus(Bus(name='DC to', Vnom=320.0, is_dc=True))
    line: DcLine = DcLine(
        bus_from=bus_from,
        bus_to=bus_to,
        name='Resistive span',
        r=0.02,
        length=5.0,
    )
    grid.add_dc_line(obj=line)
    dgs_grid: DgsCircuit = circuit_to_dgs(grid=grid)
    dc_types: list[TypLne] = list(
        typlne for typlne in dgs_grid.typlnes if int(typlne.systp) == 1
    )

    assert len(dc_types) == 1
    assert dc_types[0].rline == pytest.approx(
        line.R * 320.0 * 320.0 / grid.Sbase / line.length
    )
    assert dc_types[0].xline is None
    assert dc_types[0].cline is None
    assert dc_types[0].bline is None
