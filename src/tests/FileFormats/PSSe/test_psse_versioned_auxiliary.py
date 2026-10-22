# SPDX-License-Identifier: MPL-2.0
"""Typed results, strict failures and documented version boundaries.

Fixtures below are minimal records derived from POM 33 section 8.1,
CheatSheets 35 SUB/MON/CON, and POM 35 section 16.1.1, not simulator output.
"""
import pytest

from VeraGridEngine.IO.raw.con_parser import parse_con
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.mon_parser import parse_mon
from VeraGridEngine.IO.raw.psse_auxiliary import AuxiliaryFormat, BusInputMode, PsseVersion, parse_command_file
from VeraGridEngine.IO.raw.sub_parser import parse_sub
from VeraGridEngine.IO.raw.versioned.base.auxiliary import BranchReference, EquipmentKind, Quantity, RecordStatus, SelectionKind, ValueUnit
from VeraGridEngine.IO.raw.versioned.base.con_ import AutomaticContingency, AutomaticKind, Contingency, ContingencySkip, EventAction, RawCon
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord, RawDyr
from VeraGridEngine.IO.raw.versioned.base.mon import MonitorKind, MonitoringDefinition, RawMon
from VeraGridEngine.IO.raw.versioned.base.sub import Comparison, RawSub, SubOperation, SubOperationKind, Subsystem
from VeraGridEngine.IO.raw.versioned.v33.sub import RawSubV33
from VeraGridEngine.IO.raw.versioned.v34.sub import RawSubV34
from VeraGridEngine.IO.raw.versioned.v35.sub import RawSubV35
from VeraGridEngine.IO.raw.versioned.v36.sub import RawSubV36
from VeraGridEngine.IO.raw.versioned.v33.mon import RawMonV33
from VeraGridEngine.IO.raw.versioned.v34.mon import RawMonV34
from VeraGridEngine.IO.raw.versioned.v35.mon import RawMonV35
from VeraGridEngine.IO.raw.versioned.v36.mon import RawMonV36
from VeraGridEngine.IO.raw.versioned.v33.con_ import RawConV33
from VeraGridEngine.IO.raw.versioned.v34.con_ import RawConV34
from VeraGridEngine.IO.raw.versioned.v35.con_ import RawConV35
from VeraGridEngine.IO.raw.versioned.v36.con_ import RawConV36
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from VeraGridEngine.IO.raw.versioned.v35.dyr import RawDyrV35
from VeraGridEngine.IO.raw.versioned.v36.dyr import RawDyrV36


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_dispatch_returns_concrete_version_objects(version: int) -> None:
    """Dispatch must select real version classes, not wrap a generic token tree."""
    sub_classes: dict[int, type[RawSub]] = dict([(33, RawSubV33), (34, RawSubV34), (35, RawSubV35), (36, RawSubV36)])
    mon_classes: dict[int, type[RawMon]] = dict([(33, RawMonV33), (34, RawMonV34), (35, RawMonV35), (36, RawMonV36)])
    con_classes: dict[int, type[RawCon]] = dict([(33, RawConV33), (34, RawConV34), (35, RawConV35), (36, RawConV36)])
    dyr_classes: dict[int, type[RawDyr]] = dict([(33, RawDyrV33), (34, RawDyrV34), (35, RawDyrV35), (36, RawDyrV36)])
    assert type(parse_sub('SYSTEM s\nAREA 1\nEND\n', version=version)) is sub_classes[version]
    assert type(parse_mon('MONITOR ALL BRANCHES\n', version=version)) is mon_classes[version]
    assert type(parse_con('CONTINGENCY c\nOPEN BUS 1\nEND\n', version=version)) is con_classes[version]
    assert type(parse_dyr("1 'GENCLS' '01' 3.5 0 /", version=version)) is dyr_classes[version]


def test_sub_operations_are_typed_and_ordered() -> None:
    """Union, JOIN intersection, exclusions and weights remain distinct operations."""
    result: RawSub = parse_sub("""SUBSYSTEM 'MY COMPANY'
AREA 5
JOIN 'GROUP 1'
AREA 6
ZONES 8 10
END
SKIP BUS WITH IN-SERVICE GENUPLIMIT LESS 10 MW
PARTICIPATE
BUS 101 110
BUS 102 -10
END
END
""", version=33)
    assert result.logger.error_count() == 0
    subsystem: Subsystem = result.subsystems[0]
    assert subsystem.status == RecordStatus.VALID
    assert subsystem.label == 'MY COMPANY'
    assert [operation.kind for operation in subsystem.operations] == [
        SubOperationKind.SELECT, SubOperationKind.JOIN, SubOperationKind.EXCLUDE, SubOperationKind.PARTICIPATE]
    assert subsystem.operations[0].selection.kind == SelectionKind.AREA
    assert subsystem.operations[0].selection.first == 5
    assert subsystem.operations[1].children[1].selection.first == 8
    assert subsystem.operations[1].children[1].selection.last == 10
    exclusion: SubOperation = subsystem.operations[2]
    assert exclusion.quantity == Quantity.GENUPLIMIT
    assert exclusion.comparison == Comparison.LESS
    assert exclusion.threshold == 10.0
    assert exclusion.unit == ValueUnit.MW
    assert exclusion.in_service
    assert subsystem.operations[3].weights[0].bus.number == 101
    assert subsystem.operations[3].weights[1].factor == -10.0


@pytest.mark.parametrize('body', (
    'AREA banana', 'AREAS 5 2', 'BUS -1', 'AREA 1 garbage',
    'JOIN\nAREA 1\nJOIN\nAREA 2\nAREA 3\nEND\nEND',
    'SKIP BUS 1\nAREA 2', 'PARTICIPATE\nBUS 1 0\nEND',
    'PARTICIPATE\nBUS 1 -1\nEND', 'PARTICIPATE\nBUS 1 1\nEND\nAREA 2',
))
def test_invalid_sub_cannot_be_applied(body: str) -> None:
    """Malformed values, nesting and operation order invalidate the definition."""
    result: RawSub = parse_sub('SUBSYSTEM s\n' + body + '\nEND\n')
    assert result.logger.error_count() > 0
    assert result.subsystems[0].status != RecordStatus.VALID


def test_mon_direction_ratings_filters_and_optional_limits() -> None:
    """Named fields expose winding direction, interface ratings and voltage intent."""
    result: RawMon = parse_mon("""MONITOR INTERFACE 'North / South' RATINGS 100 110 120 MW
MONITOR BRANCH FROM BUS 101 TO BUS 102 TO BUS 103 CIRCUIT '01'
END
MONITOR TIES FROM AREA 1 TO AREA 2 IN KVRANGE 100 500
MONITOR VOLTAGE DEVIATION ALL BUSES .05
MONITOR VOLTAGE RANGE AREA 1 KV 345 .95 1.05
""", version=35)
    assert result.logger.error_count() == 0
    interface: MonitoringDefinition = result.definitions[0]
    assert interface.kind == MonitorKind.INTERFACE
    assert interface.label == 'North / South'
    assert interface.ratings == (100.0, 110.0, 120.0)
    reference: BranchReference | None = interface.members[0].reference
    assert [bus.number for bus in reference.buses] == [101, 102, 103]
    assert reference.circuit == '01'
    assert result.definitions[1].selection.first == 1
    assert result.definitions[1].to_selection.first == 2
    assert result.definitions[1].kv_range == (100.0, 500.0)
    assert result.definitions[2].lower == .05
    assert result.definitions[2].upper is None
    assert result.definitions[3].kv_range == (345.0, 345.0)
    assert result.definitions[3].upper == 1.05


@pytest.mark.parametrize('text', (
    'MONITOR BRANCH banana 1 TO BUS 2',
    'MONITOR BRANCH FROM BUS 1 TO BUS 2 CKT abc',
    'MONITOR VOLTAGE RANGE ALL BUSES 1.05 .95',
    'MONITOR VOLTAGE RANGE AREA 1 .95 1.05 garbage',
    'MONITOR INTERFACE x RATINGS 1 nope 3\n1 2\nEND',
    'MONITOR TIES FROM AREA 1 TO AREA 2 IN KVRANGE 500 100',
))
def test_invalid_mon_values_and_trailing_fields(text: str) -> None:
    """Malformed monitored elements must not produce usable definitions."""
    result: RawMon = parse_mon(text + '\n')
    assert result.logger.error_count() > 0
    assert result.definitions[0].status == RecordStatus.INVALID


def test_con_typed_targets_dispatch_and_automatic_requests() -> None:
    """Individual events and deferred combinatorial generation stay distinguishable."""
    result: RawCon = parse_con("""CATEGORY weather
VALUE storm
END
CONTINGENCY c .01 2
TRIP LINE FROM BUS 101 TO BUS 102 CKT '01'
SET BUS 101 GENERATION TO 10 MW DISPATCH
BUS 102 1
END
REMOVE MACHINE '02' FROM BUS 103 DISPATCH
BUS 104 100
END
MOVE LOAD '03' 20 PERCENT FROM BUS 105 TO BUS 106
END
SKIP BRANCH
101 TO 102 CIRCUIT '01'
END
DOUBLE TIE FROM AREA 1 TO AREA 2
""", version=35)
    assert result.logger.error_count() == 0
    contingency: Contingency = result.contingencies[0]
    assert contingency.status == RecordStatus.VALID
    assert contingency.frequency == .01
    assert contingency.duration == 2.0
    assert contingency.categories == ('weather', 'storm')
    assert contingency.events[0].action == EventAction.OPEN
    assert contingency.events[0].branch.circuit == '01'
    assert contingency.events[1].quantity == Quantity.GENERATION
    assert contingency.events[1].value == 10.0
    assert contingency.events[1].dispatch[0].bus.number == 102
    assert contingency.events[2].equipment == EquipmentKind.MACHINE
    assert contingency.events[2].device_id == '02'
    assert contingency.events[2].dispatch[0].factor == 100.0
    assert contingency.events[3].to_bus.number == 106
    assert isinstance(result.operations[2], ContingencySkip)
    assert result.operations[2].branches[0].buses[0].number == 101
    assert isinstance(result.operations[3], AutomaticContingency)
    assert result.operations[3].kind == AutomaticKind.DOUBLE
    assert result.operations[3].ties


@pytest.mark.parametrize('event', (
    'OPEN LOAD 1 AT BUS 1', 'CLOSE BUS 1', 'SET BRANCH FROM BUS 1 TO BUS 2 TO 10 MW',
    'SET BUS 1 VMAX TO 1 PERUNIT', 'SET BUS 1 LOAD TO NaN MW',
    'SET BUS 1 LOAD TO 10 OHMS', 'SET MACHINE 1 AT BUS 1 VSCHED TO 1 MW',
    'REMOVE MACHINE 1 FROM BUS 1 garbage',
    'CHANGE BUS 1 LOAD BY 10 MW DISPATCH\nBUS 2 -1\nEND',
    'SET BUS 1 LOAD TO 10 MW DISPATCH\nEND',
))
def test_invalid_con_event_is_not_silently_accepted(event: str) -> None:
    """Actions, units, amounts and dispatch must match an actual event grammar."""
    result: RawCon = parse_con('CONTINGENCY c\n' + event + '\nEND\n')
    assert result.logger.error_count() > 0
    assert result.contingencies[0].status == RecordStatus.INVALID
    assert result.contingencies[0].events[0].status == RecordStatus.INVALID


def test_unknown_commands_are_retained_without_a_valid_typed_claim() -> None:
    """Extensions remain inspectable and cannot masquerade as validated events."""
    monitoring: RawMon = parse_mon('VENDOR_EXTENSION 1 2\n')
    assert len(monitoring.unsupported) == 1
    assert len(monitoring.definitions) == 0
    contingency: RawCon = parse_con('CONTINGENCY c\nVENDOR_EXTENSION 1 2\nEND\n')
    assert contingency.contingencies[0].status == RecordStatus.UNSUPPORTED
    assert contingency.contingencies[0].events[0].record.tokens[0].text == 'VENDOR_EXTENSION'


def test_dyr_model_parameters_and_user_allocations() -> None:
    """Model data sheets and NI/NC headers determine typed field meaning."""
    result: RawDyr = parse_dyr("""101 'GENCLS' '01' 3.5 0 /
101 'USRMDL' '02' 'VENDOR' 1 1 2 2 3 4 7 'A' 1D-3 2.0 /
""", version=33)
    assert result.logger.error_count() == 0
    generator: DyrRecord = result.records[0]
    assert generator.status == RecordStatus.VALID
    assert generator.equipment_id == '01'
    assert [(parameter.name, parameter.value) for parameter in generator.parameters] == [('H', 3.5), ('D', 0.0)]
    custom: DyrRecord = result.records[1]
    assert custom.status == RecordStatus.VALID
    assert custom.user_header.name == 'VENDOR'
    assert custom.user_header.icon_count == 2
    assert custom.user_header.constant_count == 2
    assert custom.user_header.state_count == 3
    assert custom.icons == (7, 'A')
    assert custom.constants == (.001, 2.0)


@pytest.mark.parametrize('text', (
    "1 'GENCLS' '1' 3.5 /", "1 'GENCLS' '1' nan 0 /", "1 'GENCLS' '1' 3.5 0 1 /",
    "1 'GENCLS' '1' 3.5,,0 /", "1 'GENCLS' '1' 3.5,\n,0 /",
    "1 'GENCLS' '1' 3.5 '0' /", "1 'USRMDL' '1' 'V' 1 1 1 2 0 0 3 4 /",
    "1 'USRMDL' '1' 'V' 1 1 1.5 2 0 0 3 4 5 /",
))
def test_invalid_dyr_payloads_preserve_tokens(text: str) -> None:
    """Missing fields must not shift data or produce a validated model."""
    result: RawDyr = parse_dyr(text)
    assert result.logger.error_count() > 0
    assert result.records[0].status == RecordStatus.INVALID
    assert len(result.records[0].tokens) > 0


def test_unknown_dyr_model_has_no_inferred_machine_id() -> None:
    """Not every dynamic assignment attaches to a machine."""
    result: RawDyr = parse_dyr("'DC / line' 'CUSTOM' '01' 2 3 /", version=35)
    assert result.records[0].identifier == 'DC / line'
    assert result.records[0].equipment_id is None
    assert result.records[0].data == ('01', 2, 3)
    assert result.records[0].status == RecordStatus.UNSUPPORTED
    assert result.logger.warning_count() == 1


def test_dyr_reserved_icons_and_cross_compound_headers() -> None:
    """NRI is not a data payload count; IC=11 adds LP references before ICONs."""
    result: RawDyr = parse_dyr("""1 'USRLOD' '1' 'LOADBL' 12 1 1 2 3 4 5 7 8.0 9.0 /
1 'USRMDL' '1' 'GOVERNOR' 11 0 1 1 0 0 2 '02' 7 8.0 /
""", version=35)
    assert result.logger.error_count() == 0
    assert result.records[0].user_header.reserved_icon_count == 5
    assert result.records[0].icons == (7,)
    assert result.records[0].constants == (8.0, 9.0)
    assert result.records[1].user_header.references == (2, '02')
    assert result.records[1].icons == (7,)


def test_unverified_34_features_are_not_guessed() -> None:
    """Unavailable auxiliary chapters cannot be replaced with RAW-based guesses."""
    monitoring: RawMon = parse_mon('MONITOR INTERFACE i RATINGS 1 2 3 4\n1 2\nEND\n', version=34)
    contingency: RawCon = parse_con('CONTINGENCY c CATEGORY weather\nOPEN BUS 1\nEND\n', version=34)
    assert monitoring.definitions[0].status == RecordStatus.UNSUPPORTED
    assert monitoring.logger.warning_count() == 1
    assert contingency.contingencies[0].status == RecordStatus.UNSUPPORTED
    assert contingency.logger.warning_count() == 1


def test_version_rules_apply_to_typed_fields_and_context() -> None:
    """Legacy names come from caller context; directives and modern features differ."""
    named: RawSub = parse_sub("SYSTEM s\nBUS 'ALPHA 345'\nEND\n", bus_mode=BusInputMode.NAMES, version=33)
    assert named.subsystems[0].operations[0].selection.bus.name == 'ALPHA 345'
    rejected: RawSub = parse_sub('BUSNAMES\nSYSTEM s\nBUS 1\nEND\n', version=33)
    assert rejected.directives[0].status == RecordStatus.INVALID
    assert rejected.bus_mode == BusInputMode.NUMBERS
    for version in (33, 34, 35, 36):
        result: RawDyr = parse_dyr("1 'USRSWS2' '01' 'SHUNTMODEL' 1 1 0 2 0 0 3.5 0 /", version=version)
        assert result.records[0].equipment_id == '01'
        assert result.records[0].status == (RecordStatus.INVALID if version in (33, 34) else RecordStatus.VALID)


def test_source_locations_and_partial_records_survive_errors() -> None:
    """Unclosed blocks and incomplete dynamic records remain available for diagnosis."""
    subsystem: RawSub = parse_sub('COM comment\nSYSTEM s\nAREA 1\n')
    assert subsystem.subsystems[0].record.line_number == 2
    assert subsystem.subsystems[0].status == RecordStatus.INVALID
    dynamics: RawDyr = parse_dyr("1 'GENCLS' '1' 3.5 0")
    assert len(dynamics.records) == 0
    assert dynamics.rejected[0][1].text == 'GENCLS'
    assert dynamics.logger.error_count() == 1


def test_truncated_records_do_not_raise_or_lose_their_source() -> None:
    """Every prefix of representative records is a valid parser input boundary."""
    monitoring: str = 'MONITOR BRANCH FROM BUS 101 TO BUS 102 CIRCUIT 01'
    event: str = 'SET MACHINE 01 AT BUS 101 ACTIVE TO 100 MW'
    dynamics: str = "101 'USRMDL' '01' 'CUSTOM' 1 1 1 2 0 0 7 3.5 0 /"
    for length in range(len(monitoring) + 1):
        parsed_monitoring: RawMon = parse_mon(monitoring[:length])
        assert parsed_monitoring.source == '<mon>'
    for length in range(len(event) + 1):
        parsed_events: RawCon = parse_con('CONTINGENCY c\n' + event[:length] + '\nEND\n')
        assert parsed_events.contingencies[0].label == 'c'
    for length in range(len(dynamics) + 1):
        parsed_dynamics: RawDyr = parse_dyr(dynamics[:length])
        assert parsed_dynamics.source == '<dyr>'


def test_huge_numeric_values_report_errors_without_overflow() -> None:
    """Malformed constants must not escape the parser as OverflowError."""
    huge: str = '9' * 400
    result: RawDyr = parse_dyr("1 'GENCLS' '1' " + huge + ' 0 /')
    assert result.records[0].status == RecordStatus.INVALID
    assert result.logger.error_count() > 0


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_user_model_calling_sequence_is_versioned(version: int) -> None:
    """POM 33 stops at renewable IC=107; POM 35 includes torque IC=108."""
    result: RawDyr = parse_dyr("1 'USRMDL' '1' 'TORQUEMODEL' 108 0 0 1 0 0 1.0 /", version=version)
    if version == 33:
        assert result.records[0].status == RecordStatus.INVALID
    elif version == 34:
        assert result.records[0].status == RecordStatus.UNSUPPORTED
        assert result.logger.warning_count() == 1
    else:
        assert result.records[0].status == RecordStatus.VALID


def test_concrete_version_rejects_mismatched_syntax() -> None:
    """Direct use of a version class cannot silently adopt another version's tree."""
    result: RawSubV33 = RawSubV33()
    result.parse(parse_command_file('SYSTEM s\nAREA 1\nEND\n', AuxiliaryFormat.SUB,
                                    '<test>', BusInputMode.NUMBERS, PsseVersion.V35))
    assert result.logger.error_count() == 1
    assert result.version == PsseVersion.V33
    assert result.subsystems == ()


def test_end_with_extra_arguments_invalidates_the_block() -> None:
    """END must not silently discard fields or hide an incomplete definition."""
    result: RawSub = parse_sub('SYSTEM s\nAREA 1\nEND extra\n')
    assert result.subsystems[0].status == RecordStatus.INVALID
    assert result.logger.error_count() == 1


def test_directives_work_inside_join_interface_and_dispatch_blocks() -> None:
    """35.2 bus mode directives apply at any depth without becoming data records."""
    subsystem: RawSub = parse_sub("""SYSTEM s
JOIN
AREA 1
BUSNAMES
BUS 'A 345'
END
PARTICIPATE
BUSNUMBERS
BUS 1 100
END
END
""", version=35)
    assert subsystem.logger.error_count() == 0
    assert subsystem.subsystems[0].operations[0].children[1].selection.bus.name == 'A 345'
    assert subsystem.subsystems[0].operations[1].weights[0].bus.number == 1
    monitoring: RawMon = parse_mon("""MONITOR INTERFACE i RATING 100
BUSNAMES
BRANCH FROM BUS 'A 345' TO BUS 'B 345'
BUSNUMBERS
1 2 '01'
END
""", version=35)
    assert monitoring.logger.error_count() == 0
    assert len(monitoring.definitions[0].members) == 2
    assert monitoring.definitions[0].members[0].reference.buses[0].name == 'A 345'
    assert monitoring.definitions[0].members[1].reference.buses[0].number == 1
    contingency: RawCon = parse_con("""CONTINGENCY c
BUSNAMES
OPEN BRANCH FROM BUS 'A 345' TO BUS 'B 345'
SET BUS 'A 345' GENERATION TO 10 MW DISPATCH
BUSNUMBERS
BUS 2 1
END
END
""", version=35)
    assert contingency.logger.error_count() == 0
    assert len(contingency.contingencies[0].events) == 2
    assert contingency.contingencies[0].events[1].dispatch[0].bus.number == 2


def test_invalid_directives_propagate_into_parent_status() -> None:
    """Ignoring an unsupported directive must not leave its enclosing block valid."""
    result: RawSub = parse_sub('SYSTEM s\nBUSNAMES\nBUS 1\nEND\n', version=33)
    assert result.subsystems[0].status == RecordStatus.INVALID
    assert result.directives[0].status == RecordStatus.INVALID


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_legacy_automatic_from_bus_and_breakers(version: int) -> None:
    """Legacy breaker-branch selection must not be confused with node topology."""
    result: RawCon = parse_con('SINGLE BRANCH FROM BUS 101\nDOUBLE BREAKER IN AREA 1\n', version=version)
    assert result.logger.error_count() == 0
    assert result.logger.warning_count() == 0
    assert isinstance(result.operations[0], AutomaticContingency)
    assert result.operations[0].selection.bus.number == 101
    assert result.operations[1].equipment == EquipmentKind.BREAKER


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_node_breaker_events_and_requests_are_versioned(version: int) -> None:
    """CheatSheets 35 section 1.4.3 specifies node isolation and stuck breakers."""
    result: RawCon = parse_con("""CONTINGENCY c
ISOLATE SUBSTATION 10 NODE 2
STUCK BREAKER SUBSTATION 10 FROM NODE 2 TO NODE 3 CIRCUIT '01'
END
SINGLE STUCK BREAKER IN AREA 1
SINGLE OPEN TERMINAL FROM BUS 101
""", version=version)
    assert result.contingencies[0].events[0].branch.substation == 10
    assert result.contingencies[0].events[0].branch.from_node == 2
    assert result.contingencies[0].events[1].action == EventAction.STUCK
    assert result.operations[1].action == EventAction.STUCK
    if version == 33:
        assert result.contingencies[0].status == RecordStatus.INVALID
    elif version == 34:
        assert result.contingencies[0].status == RecordStatus.UNSUPPORTED
    else:
        assert result.logger.error_count() == 0
        assert result.contingencies[0].status == RecordStatus.VALID


def test_invalid_default_categories_propagate_to_contingencies() -> None:
    """Default metadata is part of the contingency's validation context."""
    result: RawCon = parse_con('CATEGORY weather\nEND\nCONTINGENCY c\nOPEN BUS 1\nEND\n', version=33)
    assert result.contingencies[0].status == RecordStatus.INVALID


def test_unsupported_andes_extension_is_not_treated_as_psse_equipment() -> None:
    """ANDES Toggle records are extensions, not PSS/E bus/model assignments."""
    result: RawDyr = parse_dyr("Line 'Toggle' Line_1 1.0 /\n1 'GENCLS' '1' 3.5 0 /\n", version=33)
    assert result.records[0].status == RecordStatus.INVALID
    assert result.records[0].tokens[0].text == 'Line'
    assert result.records[1].status == RecordStatus.VALID


def test_dyr_branch_relay_and_auxiliary_header_fields_are_named() -> None:
    """Header variations expose typed fields rather than requiring caller offsets."""
    result: RawDyr = parse_dyr("""1 'USR3WT' 2 3 '01' 'TXMODEL' 303 0 1 1 0 0 7 1.5 /
1 'USRREL' 2 '02' 1 'RELAYMODEL' 14 0 1 1 0 0 2 7 1.5 /
1 'USRAUX' 3 2 'AUXMODEL' 17 0 0 1 0 0 1.5 /
'GENERATOR 345' 'GENCLS ' '01' 3.5 0 /
""", version=35)
    assert result.logger.error_count() == 0
    assert result.records[0].target_kind == EquipmentKind.THREE_WINDING
    assert result.records[0].bus.number == 1
    assert [bus.number for bus in result.records[0].remote_buses] == [2, 3]
    assert result.records[0].equipment_id == '01'
    assert result.records[1].relay_side == 1
    assert result.records[1].equipment_id == '02'
    assert result.records[1].user_header.reserved_icon_count == 2
    assert result.records[2].auxiliary_device_type == 3
    assert result.records[2].signal_index == 2
    assert result.records[3].model == 'GENCLS'
    assert result.records[3].bus.name == 'GENERATOR 345'
    assert all(record.status == RecordStatus.VALID for record in result.records)


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_builtin_stabilizer_integer_header(version: int) -> None:
    """Selectors and remote bus numbers stay separate from the ordered real constants."""
    document: RawDyr = parse_dyr("1 'IEEEST' '01' 5 42 .3 .02 .4 .03 .2 .01 .2 .05 .2 .05 5 5 1 .1 -.1 1.1 .9 /", version=version)
    record: DyrRecord = document.records[0]
    assert record.status == RecordStatus.VALID
    assert record.icons == (5, 42)
    assert len(record.constants) == 17
    assert record.parameters[0].name == 'A1'
    assert record.constants[0] == .3
    assert record.parameters[-1].name == 'VCL'
    assert record.constants[-1] == .9
    assert document.get_model_schema('IEEEST').icon_names == ('IC', 'IB')


@pytest.mark.parametrize('header', ('5.0 42', "'5' 42", '5 -42', '5 42.0', '5', '5 42 0'))
def test_builtin_stabilizer_rejects_invalid_integer_header(header: str) -> None:
    """Malformed ICONs cannot shift the subsequent constant layout or activate a model."""
    document: RawDyr = parse_dyr("1 'IEEEST' '01' "+header+" .3 .02 .4 .03 .2 .01 .2 .05 .2 .05 5 5 1 .1 -.1 1.1 .9 /", version=35)
    assert document.records[0].status == RecordStatus.INVALID
    assert document.logger.error_count() > 0


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_dual_input_stabilizer_integer_header(version: int) -> None:
    """Both source measurement selectors precede the sixteen controller constants."""
    document: RawDyr = parse_dyr("1 'IEE2ST' '01' 3 0 5 42 2 -3 .02 .1 5 5 .2 .05 .3 .1 .1 .05 .1 -.1 1.1 .9 /", version=version)
    record: DyrRecord = document.records[0]
    assert record.status == RecordStatus.VALID
    assert record.icons == (3, 0, 5, 42)
    assert len(record.constants) == 16
    assert record.parameters[0].name == 'K1'
    assert record.parameters[1].value == -3
    assert record.parameters[-1].name == 'VCL'


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_hydraulic_deadband_direct_layout_is_version_specific(version: int) -> None:
    """A direct 35-series assignment is not retrofitted onto the older user-model wrapper.

    :param version: Explicit parser profile under review.
    """
    document: RawDyr = parse_dyr("1 'IEEEG3D' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 1 .001 -.002 25 /", version=version)
    record = document.records[0]
    if version in (35, 36):
        assert record.status == RecordStatus.VALID
        assert tuple(parameter.name for parameter in record.parameters)[-3:] == ('DBH', 'DBL', 'TRATE')
        assert record.parameters[-1].value == 25
    else:
        assert record.status == RecordStatus.UNSUPPORTED
        assert len(record.parameters) == 0
        assert len(record.data) == 18


@pytest.mark.parametrize('version', (33, 34, 35, 36))
@pytest.mark.parametrize('model,constants,count', (
    ('PSS2A', '3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .1 -.1', 17),
    ('PSS2B', '3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .04 .02 2 -2 2 -2 .1 -.1', 23),
))
def test_ramp_tracking_stabilizer_six_icon_layout(version: int, model: str, constants: str, count: int) -> None:
    """Both source snapshots place ramp orders after exactly two measurement selector pairs.

    :param version: Explicit parser profile.
    :param model: Exact source stabilizer identifier.
    :param constants: Documented ordered constants.
    :param count: Independently specified CON count.
    """
    document: RawDyr = parse_dyr(f"1 '{model}' '01' 1 0 3 0 2 2 {constants} /", version=version)
    record: DyrRecord = document.records[0]
    assert record.status == RecordStatus.VALID
    assert record.icons == (1, 0, 3, 0, 2, 2)
    assert len(record.parameters) == count
    assert tuple(parameter.name for parameter in record.parameters)[-2:] == ('VSTMAX', 'VSTMIN')


@pytest.mark.parametrize('header', ('1 0 3 0 2', '1 0 3 0 -1 1', "1 0 3 0 '2' 1", '1 0 3 0 2.0 1'))
def test_ramp_tracking_stabilizer_malformed_order_header(header: str) -> None:
    """Missing, negative, quoted and floating-point order fields cannot shift CON interpretation.

    :param header: Invalid six-ICON selector/order payload.
    """
    document: RawDyr = parse_dyr(f"1 'PSS2A' '01' {header} 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .1 -.1 /", version=35)
    assert document.records[0].status == RecordStatus.INVALID


@pytest.mark.parametrize('version', (33, 34, 35, 36))
@pytest.mark.parametrize('identifier', ("'01'", '01', "'A1'"))
def test_steam_governor_secondary_identity_is_not_a_constant(version: int, identifier: str) -> None:
    """The cross-compound header preserves the secondary equipment identifier, including leading zeros.

    :param version: Explicit parser profile.
    :param identifier: Quoted or numeric secondary machine identity.
    """
    document: RawDyr = parse_dyr(f"1 'IEEEG1' '01' 2 {identifier} 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 /", version=version)
    record: DyrRecord = document.records[0]
    assert record.status == RecordStatus.VALID
    assert record.icons == (2, identifier.strip("'"))
    assert len(record.parameters) == 20
    assert record.parameters[0].name == 'K'
    assert record.parameters[0].value == 20


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_deadband_steam_direct_header_is_version_specific(version: int) -> None:
    """The newer direct built-in header is not inferred from an older user-model allocation layout.

    :param version: Explicit parser profile.
    """
    document: RawDyr = parse_dyr("1 'IEEEG1D' '01' 0 '00' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 .001 -.002 25 /", version=version)
    record: DyrRecord = document.records[0]
    assert record.status == (RecordStatus.VALID if version in (35, 36) else RecordStatus.UNSUPPORTED)
    if version in (35, 36):
        assert record.icons == (0, '00')
        assert record.parameters[-1].name == 'TRATE'
    else:
        assert not record.parameters


@pytest.mark.parametrize('version', (33,34,35,36))
@pytest.mark.parametrize('model,count', (('GGOV1',33),('GGOV1D',35)))
def test_tracked_fuel_governor_signed_header_profile(version: int, model: str, count: int) -> None:
    """Negative droop codes are schema-specific and direct asymmetric records remain release-specific.

    :param version: Explicit parser profile.
    :param model: Source direct governor identifier.
    :param count: Exact number of source constants.
    """
    constants: str = ' '.join('0' for index in range(count))
    document: RawDyr = parse_dyr(f"1 '{model}' '01' -2 1 {constants} /",version=version)
    record: DyrRecord = document.records[0]
    if model == 'GGOV1D' and version in (33,34):
        assert record.status == RecordStatus.UNSUPPORTED
        assert not record.parameters
    else:
        assert record.status == RecordStatus.VALID
        assert record.icons == (-2,1)
        assert len(record.parameters) == count
        assert record.parameters[27].name == 'TRATE'
        assert record.parameters[-1].name == ('DBL' if model == 'GGOV1D' else 'RDOWN')


@pytest.mark.parametrize('header', ("'-2' 1", '-2.0 1', '-2 -1'))
def test_fuel_signed_header_does_not_relax_other_fields(header: str) -> None:
    """Quoted/floating selectors and negative unsigned flags cannot masquerade as signed integer codes.

    :param header: Invalid source ICON payload.
    """
    document: RawDyr = parse_dyr(f"1 'GGOV1' '01' {header} "+' '.join('0' for index in range(33))+' /',version=35)
    assert document.records[0].status == RecordStatus.INVALID
