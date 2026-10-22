# SPDX-License-Identifier: MPL-2.0
"""Release-owned user-model contracts, preserved source identities and connected legacy governors."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import dynamic_record_name
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.psse_conversion_report import PsseConversionStatus
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord, RawDyr
from VeraGridEngine.IO.raw.versioned.v35.generator import RawGeneratorV35
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import (
    make_raw_case, fuel_governor_record,
    test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium)


def legacy_governor_record(model: str, rating: float = 0., selector: int = -2,
                           flag: int = 1) -> str:
    """Build representative records from the exact supplied 33.10 allocation/layout sheets.

    :param model: Source user-subroutine name.
    :param rating: Turbine rating, zero selecting machine base.
    :param selector: Signed fuel-governor droop selector.
    :param flag: Fuel-governor fuel-speed characteristic.
    :return: Complete assignment preserving the USRMDL framing.
    """
    if model == 'GGOV1DU':
        return fuel_governor_record('GGOV1D',selector,flag,rating).replace(
            "1 'GGOV1D' '01'", "1 'USRMDL' '01' 'GGOV1DU' 5 0 2 35 10 22",1)
    elif model == 'IEEEG1SDU':
        return ("1 'USRMDL' '01' 'IEEEG1SDU' 5 0 0 23 6 3 "
            f"20 .1 .03 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 .001 -.002 {rating} /")
    else:
        assert model == 'IEEEG3DU'
        return ("1 'USRMDL' '01' 'IEEEG3DU' 5 0 0 17 4 2 "
            f".5 .04 .1 -.1 1.2 0 .05 .3 5 1 1 .5 1 1 .001 -.002 {rating} /")


@pytest.mark.parametrize('model,count,states,variables', (
    ('GGOV1DU',35,10,22),('IEEEG1SDU',23,6,3),('IEEEG3DU',17,4,2)))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_wrapper_schema_permission_is_release_owned(model: str, count: int, states: int,
                                                     variables: int, version: int) -> None:
    """A later release does not inherit permission merely because user-record framing is unchanged.

    :param model: Exact source subroutine identifier.
    :param count: CON allocation from the independently specified data sheet.
    :param states: Source NS allocation, unrelated to payload length.
    :param variables: Source NV allocation, unrelated to payload length.
    :param version: Explicit source parser profile.
    """
    document: RawDyr = parse_dyr(legacy_governor_record(model),version=version)
    record: DyrRecord = document.records[0]
    assert record.status == RecordStatus.VALID
    assert record.model == 'USRMDL'
    assert record.user_header is not None
    assert record.user_header.name == model
    assert record.user_header.state_count == states
    assert record.user_header.variable_count == variables
    if version == 33:
        assert record.user_schema is not None
        assert len(record.parameters) == count
        assert dynamic_record_name(record) == model
        assert record.parameters[-1].name == ('DBL' if model == 'GGOV1DU' else 'TRATE')
    else:
        assert record.user_schema is None
        assert record.parameters == ()
        assert dynamic_record_name(record) == 'USRMDL'


@pytest.mark.parametrize('model',('GGOV1DU','IEEEG1SDU','IEEEG3DU'))
@pytest.mark.parametrize('rating',(0.,75.))
@pytest.mark.parametrize('use_runtime',(False,True))
def test_legacy_governor_coupled_equilibrium(model: str, rating: float, use_runtime: bool) -> None:
    """The real network point satisfies stored and duplicated machine/controller equations on both power bases.

    :param model: Reviewed 33.10 user subroutine.
    :param rating: Turbine rating or machine-base selection.
    :param use_runtime: Check the runtime rather than the stored declarative graph.
    """
    check_equilibrium('GENSAE','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38',
        legacy_governor_record(model,rating),use_runtime,version=33)


@pytest.mark.parametrize('selector',(-2,-1,0,1))
@pytest.mark.parametrize('flag',(0,1))
def test_legacy_fuel_binding_preserves_source_data(selector: int, flag: int) -> None:
    """Conversion reuses physical equations without rewriting keyword, subroutine, tokens or allocations.

    :param selector: Signed permanent-droop source selector.
    :param flag: Source fuel-flow characteristic.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = 33
    document: RawDyr = parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        +legacy_governor_record('GGOV1DU',selector=selector,flag=flag),version=33)
    record: DyrRecord = document.records[1]
    tokens: tuple[str,...] = tuple(token.text for token in record.tokens)
    data: tuple[int|float|str,...] = record.data
    assert case.add_auxiliary(document)
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)
    assert record.model == 'USRMDL'
    assert record.user_header is not None and record.user_header.name == 'GGOV1DU'
    assert record.icons == (selector,flag)
    assert tuple(token.text for token in record.tokens) == tokens
    assert record.data == data


@pytest.mark.parametrize('field,value',((0,1),(1,1),(2,3),(3,34),(4,11),(5,23)))
def test_every_user_allocation_field_is_checked(field: int, value: int) -> None:
    """Even syntactically valid generic allocations cannot bypass the supplied model's exact calling contract.

    :param field: IC, IT, NI, NC, NS or NV position.
    :param value: Different but generically valid source allocation value.
    """
    counts: list[int] = [5,0,2,35,10,22]
    counts[field] = value
    payload: str = ' '.join('0' for index in range(counts[2]+counts[3]))
    header: str = ' '.join(str(value) for value in counts)
    document: RawDyr = parse_dyr(f"1 'USRMDL' '01' 'GGOV1DU' {header} {payload} /",version=33)
    assert document.records[0].status == RecordStatus.INVALID
    assert document.records[0].user_schema is None


@pytest.mark.parametrize('icons',("'-2' 1",'-2.0 1','-2 -1'))
def test_reviewed_user_icons_apply_explicit_field_types(icons: str) -> None:
    """User payloads cannot evade the signed/unsigned and unquoted integer constraints.

    :param icons: Quoted/real selector or negative unsigned fuel flag.
    """
    document: RawDyr = parse_dyr("1 'USRMDL' '01' 'GGOV1DU' 5 0 2 35 10 22 "+icons+' '
        +' '.join('0' for index in range(35))+' /',version=33)
    assert document.records[0].status == RecordStatus.INVALID


@pytest.mark.parametrize('name',('CUSTOM','GGOV1D','GENROU','GGOV1DU_CUSTOM'))
def test_unknown_user_subroutine_cannot_resolve_by_native_name(name: str) -> None:
    """A matching native catalogue name provides no implicit user-model schema or conversion permission.

    :param name: Unreviewed source subroutine identifier.
    """
    document: RawDyr = parse_dyr(f"1 'USRMDL' '01' '{name}' 5 0 0 0 0 0 /",version=33)
    assert document.records[0].status == RecordStatus.VALID
    assert document.records[0].user_schema is None
    assert dynamic_record_name(document.records[0]) == 'USRMDL'


@pytest.mark.parametrize('version',(34,35,36))
def test_later_release_retains_but_does_not_activate_legacy_wrapper(version: int) -> None:
    """Unverified wrapper allocations in later releases cannot activate a partially controlled plant.

    :param version: Explicit later source profile.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = version
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        +legacy_governor_record('GGOV1DU'),version=version))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None


@pytest.mark.parametrize('secondary_bus,identity',(('2','02'),('2',"'02'"),("'BUS2'",'02')))
@pytest.mark.parametrize('invalid_payload',(False,True))
def test_legacy_cross_compound_reference_preserves_exact_units(secondary_bus: str, identity: str,
                                                               invalid_payload: bool) -> None:
    """An unsupported shared governor blocks both named shafts while independent units at either bus remain active.

    :param secondary_bus: Numeric or named LP machine bus.
    :param identity: Quoted or unquoted LP equipment identity with a leading zero.
    :param invalid_payload: Retain valid targets even when a later constant is malformed.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = 33
    for number, equipment in ((1,'04'),(2,'02'),(2,'03')):
        raw: RawGeneratorV35 = RawGeneratorV35()
        raw.I = number
        raw.ID = equipment
        raw.MBASE = 50
        raw.ZR = .01
        raw.ZX = .2
        raw.PG = 20
        raw.QG = 5
        case.generators.append(raw)
    machines: str = '\n'.join(f"{number} 'GENROU' '{equipment}' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /"
        for number,equipment in ((1,'01'),(1,'04'),(2,'02'),(2,'03')))
    constants: str = ' '.join('NaN' if invalid_payload and index == 22 else '0' for index in range(23))
    document: RawDyr = parse_dyr(machines+f"\n'BUS1' 'USRMDL' '01' 'IEEEG1CDU' 11 0 0 23 6 3 {secondary_bus} {identity} {constants} /",version=33)
    record: DyrRecord = document.records[-1]
    assert record.user_header is not None
    assert record.user_header.references[1] == '02'
    assert len(record.remote_buses) == 1
    assert record.status == (RecordStatus.INVALID if invalid_payload else RecordStatus.VALID)
    assert case.add_auxiliary(document)
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    by_code: dict[str,Generator] = dict((generator.code,generator) for generator in grid.generators)
    assert by_code['1_01'].rms_template is None
    assert by_code['2_02'].rms_template is None
    assert by_code['1_04'].rms_template is not None
    assert by_code['2_03'].rms_template is not None


@pytest.mark.parametrize('identity',('01',"'01'", "'A1'"))
def test_cross_compound_header_retains_character_identity(identity: str) -> None:
    """The generic calling sequence preserves LP equipment identifiers even without a reviewed subroutine.

    :param identity: Numeric-looking or alphanumeric character equipment ID.
    """
    document: RawDyr = parse_dyr("1 'USRMDL' '01' 'IEEEG1CDU' 11 0 0 23 6 3 2 "+identity+' '
        +' '.join('0' for index in range(23))+' /',version=33)
    record: DyrRecord = document.records[0]
    assert record.status == RecordStatus.VALID
    assert record.user_header is not None
    assert record.user_header.references == (2,identity.strip("'"))


@pytest.mark.parametrize('identity',('1.0',"'LONG'"))
def test_cross_compound_malformed_secondary_identity_is_invalid(identity: str) -> None:
    """Malformed secondary references cannot silently select another machine.

    :param identity: Non-character-compatible secondary equipment token.
    """
    document: RawDyr = parse_dyr("1 'USRMDL' '01' 'IEEEG1CDU' 11 0 0 23 6 3 2 "+identity+' '
        +' '.join('0' for index in range(23))+' /',version=33)
    assert document.records[0].status == RecordStatus.INVALID


def test_changed_allocation_cannot_reuse_parser_permission() -> None:
    """Mutating a parsed calling contract invalidates its conversion identity instead of bypassing review."""
    case: PsseCircuit = make_raw_case()
    case.REV = 33
    document: RawDyr = parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        +legacy_governor_record('GGOV1DU'),version=33)
    assert document.records[1].user_header is not None
    document.records[1].user_header.variable_count = 23
    assert dynamic_record_name(document.records[1]) == 'USRMDL'
    assert case.add_auxiliary(document)
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None


@pytest.mark.parametrize('model',('GGOV1DU','IEEEG1SDU','IEEEG3DU'))
def test_wrapper_requires_usrmdl_framing(model: str) -> None:
    """Known subroutine names are not invented built-in model identifiers.

    :param model: Wrapper-only source identifier.
    """
    document: RawDyr = parse_dyr(f"1 '{model}' '01' 0 /",version=33)
    assert document.records[0].status == RecordStatus.UNSUPPORTED
    assert document.records[0].user_schema is None


@pytest.mark.parametrize('identity',("''","'LONG'"))
@pytest.mark.parametrize('model',('GGOV1DU','IEEEG1SDU','IEEEG3DU'))
def test_reviewed_wrapper_machine_identity_has_explicit_width(identity: str, model: str) -> None:
    """A valid allocation contract cannot activate an invalid machine identifier.

    :param identity: Empty or overlength primary unit identity.
    :param model: Reviewed source wrapper.
    """
    document: RawDyr = parse_dyr(legacy_governor_record(model).replace("'01'",identity,1),version=33)
    assert document.records[0].status == RecordStatus.INVALID


def test_user_model_named_like_native_machine_cannot_activate() -> None:
    """An arbitrary user subroutine matching a built-in name cannot inherit its native binding."""
    case: PsseCircuit = make_raw_case()
    case.REV = 33
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "'BUS1' 'USRMDL' '01' 'GENROU' 1 1 0 0 0 0 /",version=33))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
