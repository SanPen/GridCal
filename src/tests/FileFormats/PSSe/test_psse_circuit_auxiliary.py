# SPDX-License-Identifier: MPL-2.0
"""Auxiliary ownership, version dispatch and isolation from network serialization."""
from pathlib import Path
import json
import pytest
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode, PsseVersion
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType
from VeraGridEngine.IO.raw.psse_property import PsseProperty
from VeraGridEngine.IO.raw.raw_types import PsseAuxiliaryDocument
from VeraGridEngine.IO.raw.raw_parser_writer import read_raw, write_raw
from VeraGridEngine.IO.raw.rawx_parser_writer import parse_rawx, write_rawx
from VeraGridEngine.IO.raw.seq_parser import parse_seq
from VeraGridEngine.IO.raw.sub_parser import parse_sub
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import RawDyr
from VeraGridEngine.IO.raw.versioned.base.seq import RawSeq, Sequence35Layout
from VeraGridEngine.IO.raw.versioned.base.seq_records import SequenceGenerator
from VeraGridEngine.IO.raw.versioned.base.rop_records import RopBusVoltage
from VeraGridEngine.IO.raw.versioned.v35.bus import RawBusV35


def write_auxiliary_inputs(directory: Path, version: int) -> tuple[Path, ...]:
    """Create one nonempty manual-derived input per auxiliary format.

    :param directory: Temporary fixture directory.
    :param version: Explicit PSS/E major revision.
    :return: Ordered input paths, covering all eight formats.
    """
    sequence: str = f'0,{version}\n' + ('0\n' if version >= 34 else '') + '1,01,.01,.2\nQ'
    capability: str = (f'0,{version}\n' if version >= 35 else '') + '1,01,0,10,-10,20,15,-15\n0'
    inputs: tuple[tuple[str, str], ...] = (
        ('case.sub', 'SYSTEM s\nAREA 1\nEND\n'),
        ('case.mon', 'MONITOR ALL BRANCHES\n'),
        ('case.con', 'CONTINGENCY c\nOPEN BUS 1\nEND\n'),
        ('case.dyr', "1 'GENCLS' '01' 3.5 0 /"),
        ('case.seq', sequence),
        ('case.rop', '0\n1,1.1,.9,1.2,.8,1,2\nQ'),
        ('case.gcp', capability),
        ('case.loc', '1,-79,40,90,1.2'),
    )
    paths: list[Path] = list()
    for name, text in inputs:
        path: Path = directory / name
        path.write_text(text, encoding='utf-8')
        paths.append(path)
    return tuple(paths)


def test_auxiliary_collections_are_registered_and_instance_owned() -> None:
    """Registered collections match slots and are never shared by circuits."""
    circuit: PsseCircuit = PsseCircuit()
    other: PsseCircuit = PsseCircuit()
    properties: list[PsseProperty] = circuit.get_auxiliary_properties()
    assert [prop.file_type for prop in properties] == [PsseFileType.SUB, PsseFileType.MON, PsseFileType.CON, PsseFileType.DYR, PsseFileType.SEQ, PsseFileType.ROP, PsseFileType.GCP, PsseFileType.LOC]
    for prop in properties:
        assert prop in circuit.get_properties()
        assert circuit.get_prop_value(prop) == []
        assert circuit.get_prop_value(prop) is not other.get_prop_value(prop)
        assert circuit.get_objects_list(prop.property_name) is circuit.get_prop_value(prop)
        assert prop not in circuit.get_class_properties()
    assert circuit.auxiliary_logger is not other.auxiliary_logger
    assert circuit.get_auxiliary_documents() == ()
    assert all(prop.file_type == PsseFileType.RAW for prop in circuit.get_class_properties())
    assert all(prop.file_type == PsseFileType.RAW for prop in circuit.get_rawx_dict().values())


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_read_all_formats_into_concrete_circuit_collections(tmp_path: Path, version: int) -> None:
    """Circuit REV, rather than inherited RawObject.version, selects each grammar."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = version
    paths: tuple[Path, ...] = write_auxiliary_inputs(tmp_path, version)
    documents: list[PsseAuxiliaryDocument] = list()
    for path in paths:
        document: PsseAuxiliaryDocument | None = circuit.read_auxiliary_file(path)
        assert document is not None
        assert document.version == PsseVersion(version)
        assert type(document).__name__.endswith(f'V{version}')
        assert document.source == str(path)
        documents.append(document)
    assert list(circuit.get_auxiliary_documents()) == documents
    assert circuit.sub_files[0].subsystems[0].label == 's'
    assert len(circuit.mon_files[0].definitions) == 1
    assert circuit.con_files[0].contingencies[0].label == 'c'
    assert circuit.dyr_files[0].records[0].model == 'GENCLS'
    sequence: SequenceGenerator = circuit.seq_files[0].records[0].data
    assert isinstance(sequence, SequenceGenerator)
    assert sequence.r_positive == .01
    assert sequence.x_subtransient == .2
    opf: RopBusVoltage = circuit.rop_files[0].records[0].data
    assert isinstance(opf, RopBusVoltage)
    assert opf.v_normal_max == 1.1
    assert circuit.gcp_files[0].curves[0].points[1].p == 20
    assert circuit.loc_files[0].records[0].points[0].x == -79
    # Network primary-key checks and browsing still operate on network objects.
    network_logger: Logger = Logger()
    circuit.check_primary_keys(network_logger)
    assert not network_logger.has_logs()
    assert not circuit.auxiliary_logger.has_logs()
    assert circuit.buses == [] and circuit.generators == []


def test_attach_rejects_revision_mismatch_and_repeated_ownership() -> None:
    """A different major revision cannot be silently reinterpreted or inserted."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 35
    wrong: RawSeq = parse_seq('0,33\nQ', version=33)
    assert not circuit.add_auxiliary(wrong)
    assert circuit.seq_files == []
    matching: RawSeq = parse_seq('0,35\nQ', version=35)
    assert circuit.add_auxiliary(matching)
    assert circuit.seq_files[0] is matching
    assert not circuit.add_auxiliary(matching)
    assert len(circuit.seq_files) == 1
    assert circuit.auxiliary_logger.error_count() == 2


def test_invalid_input_and_unrecognized_dynamics_remain_inspectable(tmp_path: Path) -> None:
    """Storage retains failures and unsupported models without applying them."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 36
    sequence: RawSeq = parse_seq('0,36\n0\n1,01,bad\nQ', source='broken.seq')
    assert circuit.add_auxiliary(sequence)
    assert circuit.seq_files[0].records[0].data.status == RecordStatus.INVALID
    assert circuit.seq_files[0].rows[2].text == '1,01,bad'
    assert circuit.seq_files[0].rows[2].line_number == 3
    assert circuit.auxiliary_logger.error_count() == sequence.logger.error_count()
    errors_before: int = circuit.auxiliary_logger.error_count()
    assert not circuit.add_auxiliary(sequence)
    assert circuit.auxiliary_logger.error_count() == errors_before + 1
    path: Path = tmp_path / 'unknown.dyr'
    path.write_text("1 'UNREVIEWED_MODEL' '01' 1 2 /", encoding='utf-8')
    document: PsseAuxiliaryDocument | None = circuit.read_auxiliary_file(path)
    assert isinstance(document, RawDyr)
    assert len(document.records) == 1
    assert document.records[0].status == RecordStatus.UNSUPPORTED
    assert circuit.dyr_files[0] is document
    assert circuit.generators == []


def test_command_bus_mode_flows_between_files_and_can_be_overridden(tmp_path: Path) -> None:
    """The final SUB/MON/CON bus mode becomes the next command file's initial mode."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 35
    subsystem_path: Path = tmp_path / 'named.SUB'
    monitor_path: Path = tmp_path / 'named.mon'
    contingency_path: Path = tmp_path / 'numeric.con'
    subsystem_path.write_text("BUSNAMES\nSYSTEM s\nBUS 'ALPHA 345'\nEND\n", encoding='utf-8')
    monitor_path.write_text("MONITOR BRANCH FROM BUS 'ALPHA 345' TO BUS 'BETA 345' CIRCUIT 1\n", encoding='utf-8')
    contingency_path.write_text('CONTINGENCY c\nOPEN BUS 1\nEND\n', encoding='utf-8')
    assert circuit.read_auxiliary_file(subsystem_path) is not None
    assert circuit.auxiliary_bus_mode == BusInputMode.NAMES
    assert circuit.read_auxiliary_file(monitor_path) is not None
    assert circuit.mon_files[0].definitions[0].reference.buses[0].name == 'ALPHA 345'
    assert circuit.read_auxiliary_file(contingency_path, bus_mode=BusInputMode.NUMBERS) is not None
    assert circuit.auxiliary_bus_mode == BusInputMode.NUMBERS
    assert circuit.con_files[0].contingencies[0].events[0].bus.number == 1
    assert not circuit.auxiliary_logger.has_logs()


def test_updates_keep_file_mode_and_multiple_documents_without_changing_raw() -> None:
    """REPLACE/UPDATE intent is stored for later resolution, not eagerly executed."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 35
    bus: RawBusV35 = RawBusV35()
    bus.I = 1
    bus.NAME = 'ORIGINAL'
    circuit.buses.append(bus)
    first: RawSeq = parse_seq('0,35\n0\n1,01,.1\nQ', version=35)
    second: RawSeq = parse_seq('1,35\n0\n1,01,,.2\nQ', version=35)
    assert circuit.add_auxiliary(first)
    assert circuit.add_auxiliary(second)
    assert circuit.seq_files == [first, second]
    assert circuit.seq_files[1].records[0].data.row.text == '1,01,,.2'
    assert first.change != second.change
    assert circuit.buses == [bus] and bus.NAME == 'ORIGINAL'
    assert not circuit.auxiliary_logger.has_logs()


def test_seq_minor_layout_is_forwarded_by_circuit_loader(tmp_path: Path) -> None:
    """Selecting 35.0 cannot be replaced by the default 35.2 NCS grammar."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 35
    path: Path = tmp_path / 'legacy.seq'
    path.write_text('0,35\n' + '0\n' * 9 + '1,01,0,1,2\n0\nQ', encoding='utf-8')
    document: PsseAuxiliaryDocument | None = circuit.read_auxiliary_file(path, layout_35=Sequence35Layout.V35_0)
    assert isinstance(document, RawSeq)
    assert len(document.records) == 1
    assert not circuit.auxiliary_logger.has_logs()


@pytest.mark.parametrize('suffix', ('.xyz', '.raw', '.seq'))
def test_load_failures_do_not_create_partial_collections(tmp_path: Path, suffix: str) -> None:
    """Unknown formats and unreadable paths become circuit diagnostics."""
    circuit: PsseCircuit = PsseCircuit()
    assert circuit.read_auxiliary_file(tmp_path / ('missing' + suffix)) is None
    assert circuit.get_auxiliary_documents() == ()
    assert circuit.auxiliary_logger.error_count() == 1
    assert circuit.auxiliary_bus_mode == BusInputMode.NUMBERS


def test_unsupported_circuit_revision_preserves_legacy_raw_behavior(tmp_path: Path) -> None:
    """RAW 29–32 remain usable but cannot acquire unsupported auxiliary grammars."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 32
    assert circuit.read_auxiliary_file(tmp_path / 'case.seq') is None
    assert circuit.get_auxiliary_documents() == ()
    assert circuit.auxiliary_logger.has_logs()
    logger: Logger = Logger()
    circuit.check_primary_keys(logger)
    assert not logger.has_logs()


def test_read_raw_can_load_explicit_auxiliary_files_with_raw_revision(tmp_path: Path) -> None:
    """The public RAW reader attaches files only after reading the network header."""
    raw_path: Path = tmp_path / 'case.raw'
    raw_path.write_text("0,100.0,34,0,0,60.0\nTest\nTest 2\n1,'BUS1',230.0,3,1,1,1,1.0,0.0,1.1,0.9,1.1,0.9\n0 / END OF BUS DATA\nQ\n", encoding='utf-8')
    paths: tuple[Path, ...] = write_auxiliary_inputs(tmp_path, 34)
    logger: Logger = Logger()
    circuit: PsseCircuit = read_raw(str(raw_path), logger=logger, auxiliary_files=paths)
    assert circuit.REV == 34
    assert len(circuit.buses) == 1
    assert len(circuit.get_auxiliary_documents()) == 8
    assert all(document.version == PsseVersion.V34 for document in circuit.get_auxiliary_documents())
    assert not circuit.auxiliary_logger.has_logs()


def test_raw_reader_propagates_auxiliary_diagnostics(tmp_path: Path) -> None:
    """Caller diagnostics include failed selected auxiliary file reads."""
    raw_path: Path = tmp_path / 'case.raw'
    raw_path.write_text('0,100.0,33,0,0,60.0\nTest\nTest 2\n0 / END OF BUS DATA\nQ\n', encoding='utf-8')
    logger: Logger = Logger()
    circuit: PsseCircuit = read_raw(str(raw_path), logger=logger, auxiliary_files=(tmp_path / 'missing.seq',))
    assert circuit.auxiliary_logger.error_count() == 1
    assert any(entry.msg == 'Could not read PSS/E auxiliary file' for entry in logger.entries)


def test_raw_and_rawx_export_preserve_network_schema_and_report_omission(tmp_path: Path) -> None:
    """Owned auxiliary objects cannot be mistaken for RAWX network row objects."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 35
    bus: RawBusV35 = RawBusV35()
    bus.I = 1
    bus.NAME = 'BUS1'
    circuit.buses.append(bus)
    assert circuit.add_auxiliary(parse_sub('SYSTEM s\nAREA 1\nEND\n', source='case.sub', version=35))
    rawx_path: Path = tmp_path / 'case.rawx'
    logger: Logger = Logger()
    write_rawx(str(rawx_path), circuit, logger)
    payload: dict = json.loads(rawx_path.read_text())
    assert set(payload['network']) == set(circuit.get_rawx_dict())
    assert 'sub_files' not in payload['network'] and '' not in payload['network']
    assert payload['network']['bus']['data'][0][1] == 1
    assert any(entry.device == 'case.sub' for entry in logger.entries)
    restored: PsseCircuit = parse_rawx(str(rawx_path), logger=Logger())
    assert len(restored.buses) == 1 and restored.buses[0].I == 1
    assert restored.get_auxiliary_documents() == ()
    raw_path: Path = tmp_path / 'case.raw'
    raw_logger: Logger = write_raw(str(raw_path), circuit, version=35)
    assert any(entry.device == 'case.sub' for entry in raw_logger.entries)
    restored = read_raw(str(raw_path), logger=Logger())
    assert len(restored.buses) == 1 and restored.buses[0].NAME == 'BUS1'
    assert len(circuit.sub_files) == 1


def test_legacy_unsupported_bus_mode_directive_does_not_change_circuit_mode(tmp_path: Path) -> None:
    """A rejected 33 BUSNAMES directive cannot alter later file interpretation."""
    circuit: PsseCircuit = PsseCircuit()
    circuit.REV = 33
    path: Path = tmp_path / 'legacy.sub'
    path.write_text('BUSNAMES\nSYSTEM s\nAREA 1\nEND\n', encoding='utf-8')
    assert circuit.read_auxiliary_file(path) is not None
    assert circuit.auxiliary_bus_mode == BusInputMode.NUMBERS
    assert circuit.sub_files[0].directives[0].status == RecordStatus.INVALID
    assert circuit.auxiliary_logger.has_logs()


def test_raw_reader_supports_external_bus_names_mode_for_legacy_versions(tmp_path: Path) -> None:
    """33 needs externally selected name mode because in-file directives came later."""
    raw_path: Path = tmp_path / 'case.raw'
    raw_path.write_text('0,100.0,33,0,0,60.0\nTest\nTest 2\n0 / END OF BUS DATA\nQ\n', encoding='utf-8')
    subsystem_path: Path = tmp_path / 'case.sub'
    subsystem_path.write_text("SYSTEM s\nBUS 'ALPHA 345'\nEND\n", encoding='utf-8')
    circuit: PsseCircuit = read_raw(str(raw_path), logger=Logger(),
                                   auxiliary_files=(subsystem_path,), bus_mode=BusInputMode.NAMES)
    assert circuit.sub_files[0].subsystems[0].operations[0].selection.bus.name == 'ALPHA 345'
    assert circuit.auxiliary_bus_mode == BusInputMode.NAMES
    assert not circuit.auxiliary_logger.has_logs()
