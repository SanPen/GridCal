# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Independent auxiliary readers must retain syntax without touching RAW import."""

from pathlib import Path

import pytest

from VeraGridEngine.IO.raw.con_parser import parse_con, read_con
from VeraGridEngine.IO.raw.dyr_parser import DyrFile, parse_dyr, read_dyr
from VeraGridEngine.IO.raw.mon_parser import parse_mon, read_mon
from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode, PsseAuxiliaryFile, PsseCommand, PsseRecord, PsseVersion
from VeraGridEngine.IO.raw.sub_parser import parse_sub, read_sub


def test_sub_nested_selection_and_participation() -> None:
    """Keep union, intersection, exclusion and participation operations distinct."""
    result: PsseAuxiliaryFile = parse_sub("""COM subsystem example
SUBSYSTEM 'MY COMPANY'
AREA 5
JOIN 'GROUP 1'
AREA 6
ZONES 8 10
END
SKIP BUS 567
PARTICIPATE
BUS 123 1.0
END
END
END
""")
    assert result.logger.error_count() == 0
    assert len(result.records) == 1
    subsystem: PsseRecord = result.records[0]
    assert subsystem.command == PsseCommand.SUBSYSTEM
    assert subsystem.tokens[1].text == 'MY COMPANY'
    assert [record.command for record in subsystem.children] == [
        PsseCommand.AREA, PsseCommand.JOIN, PsseCommand.SKIP, PsseCommand.PARTICIPATE]
    assert len(subsystem.children[1].children) == 2
    assert subsystem.children[3].children[0].tokens[2].text == '1.0'


def test_bus_modes_quotes_and_comments() -> None:
    """Names containing slashes and doubled quotes survive mode changes."""
    result: PsseAuxiliaryFile = parse_sub("""BUSNAMES
SYSTEM 'owner''s / region'
BUS 'ALPHA BETA 345' / trailing comment
BUSNUMBERS
BUS 101
END
""")
    assert result.logger.error_count() == 0
    subsystem: PsseRecord = result.records[1]
    assert subsystem.tokens[1].text == "owner's / region"
    assert subsystem.children[0].bus_mode == BusInputMode.NAMES
    assert subsystem.children[0].tokens[1].text == 'ALPHA BETA 345'
    assert subsystem.children[2].bus_mode == BusInputMode.NUMBERS
    assert result.bus_mode == BusInputMode.NUMBERS


def test_mon_interfaces_lists_skips_and_voltage() -> None:
    """The documented monitoring forms keep their grouping and direction."""
    result: PsseAuxiliaryFile = parse_mon("""SKIP
100 TO 200 TO 300
END
MONITOR INTERFACE 'North / South' RATINGS 100 110 MW
101 102 'A'
MONITOR TIES FROM AREA 1 TO AREA 5 IN KVRANGE 100 999
END
MONITOR BRANCHES
101 102
102 103 '2'
END
BRANCH FROM BUS 101 TO BUS 102
MONITOR BRANCH FROM BUS 101 TO BUS 102 TO BUS 103 CKT '1'
MONITOR VOLTAGE RANGE AREAS 1 5 .95 1.05
END
""")
    assert result.logger.error_count() == 0
    assert result.logger.warning_count() == 0
    assert len(result.records) == 6
    assert result.records[0].children[0].command == PsseCommand.MEMBER
    assert result.records[1].tokens[2].text == 'North / South'
    assert result.records[1].children[1].command == PsseCommand.TIES
    assert len(result.records[2].children) == 2
    assert result.records[-1].command == PsseCommand.VOLTAGE


def test_con_categories_events_dispatch_and_automatic_outages() -> None:
    """Dispatch END must close the event, not the enclosing contingency."""
    result: PsseAuxiliaryFile = parse_con("""CATEGORY 'weather'
VALUE 'storm'
END
CONTINGENCY 'line outage' .01 2 CATEGORY 'weather,storm'
TRIP LINE FROM BUS 101 TO BUS 102 CKT 'A'
SET BUS 101 GENERATION TO 10 MW DISPATCH
BUS 102 1.0
END
CLOSE BRANCH FROM BUS 103 TO BUS 104
END
SKIP BRANCH
101 TO 102 CIRCUIT 'A'
END
SINGLE BRANCH IN SUBSYSTEM 'MY COMPANY'
DOUBLE TIE FROM AREA 1 TO AREA 2
END
""")
    assert result.logger.error_count() == 0
    assert result.logger.warning_count() == 0
    assert len(result.records) == 5
    contingency: PsseRecord = result.records[1]
    assert contingency.tokens[1].text == 'line outage'
    assert [event.command for event in contingency.children] == [
        PsseCommand.OPEN, PsseCommand.SET, PsseCommand.CLOSE]
    assert contingency.children[0].tokens[0].text == 'TRIP'
    assert contingency.children[1].children[0].command == PsseCommand.BUS
    assert result.records[3].command == PsseCommand.SINGLE


def test_dyr_multiline_models_and_typed_values() -> None:
    """Keep quoted IDs, device names, instance IDs and user-model headers."""
    result: DyrFile = parse_dyr("""// comment
101, 'GENCLS', '01', 3.5,
  0.0 / generator comment
'DC / line' 'CUSTOM' 2 1D-3 /
7 'USRMSC' 'my_model' 0 0 1 2 3 4 5 6.0 7.0 /
101 'USRMDL' '1' 'vendor_model' 1 1 0 2 1 0 3.0 4.0 /
""")
    assert result.logger.error_count() == 0
    assert len(result.records) == 4
    assert result.records[0].identifier == 101
    assert result.records[0].model == 'GENCLS'
    assert result.records[0].data == ('01', 3.5, 0.0)
    assert result.records[0].line_number == 2
    assert result.records[1].identifier == 'DC / line'
    assert result.records[1].data == (2, .001)
    assert result.records[2].identifier == 7
    assert result.records[2].data[0] == 'my_model'
    assert result.records[3].data[:2] == ('1', 'vendor_model')


def test_malformed_input_has_diagnostics_and_keeps_partial_tree() -> None:
    """Incomplete or unsupported input must be visible to the caller."""
    subsystem: PsseAuxiliaryFile = parse_sub("SUBSYSTEM 'broken'\nJOIN\nAREA\n")
    assert subsystem.logger.error_count() > 0
    assert subsystem.records[0].children[0].children[0].command == PsseCommand.AREA
    monitoring: PsseAuxiliaryFile = parse_mon('VENDOR_EXTENSION 1 2\nEND\nMONITOR ALL BRANCHES\n')
    assert monitoring.records[0].command == PsseCommand.UNKNOWN
    assert monitoring.logger.warning_count() >= 2
    contingency: PsseAuxiliaryFile = parse_con('OPEN BUS 101\nCONTINGENCY\nEND\n')
    assert contingency.logger.error_count() >= 2
    dynamics: DyrFile = parse_dyr("101 GENCLS '1' 3.5 0 /\n102 'GENCLS' '1' 3 0\n")
    assert dynamics.logger.error_count() == 2
    assert len(dynamics.records) == 0


def test_inherited_mode_and_includes_are_explicit() -> None:
    """Retain MUST INCLUDE instructions without implicitly reading other files."""
    subsystem: PsseAuxiliaryFile = parse_sub("BUSNAMES\nSUBSYSTEM named\nBUS 'A 345'\nEND\n")
    monitoring: PsseAuxiliaryFile = parse_mon("INCLUDE 'other.mon'\nBRANCH FROM BUS 'A 345' TO BUS 'B 345'\n",
                           bus_mode=subsystem.bus_mode)
    assert monitoring.logger.error_count() == 0
    assert monitoring.logger.warning_count() == 1
    assert monitoring.records[1].bus_mode == BusInputMode.NAMES


def test_file_readers_and_independent_diagnostics(tmp_path: Path) -> None:
    """Exercise all path-based entry points and ensure logs are per parse."""
    sub_path: Path = tmp_path / 'sample.sub'
    mon_path: Path = tmp_path / 'sample.mon'
    con_path: Path = tmp_path / 'sample.con'
    dyr_path: Path = tmp_path / 'sample.dyr'
    sub_path.write_text("SUBSYSTEM 'España'\nAREA 1\nEND\n", encoding='utf-8')
    mon_path.write_text('MONITOR ALL BRANCHES\nEND\n', encoding='utf-8')
    con_path.write_text("CONTINGENCY c\nOPEN BUS 101\nEND\nEND\n", encoding='utf-8')
    dyr_path.write_text("101 'GENCLS' '1' 3.5 0 /\n", encoding='utf-8')
    assert read_sub(sub_path).records[0].tokens[1].text == 'España'
    assert read_mon(mon_path).records[0].command == PsseCommand.ALL
    assert read_con(con_path).records[0].command == PsseCommand.CONTINGENCY
    assert read_dyr(dyr_path).records[0].model == 'GENCLS'
    broken: PsseAuxiliaryFile = parse_sub('SUBSYSTEM broken\n')
    clean: PsseAuxiliaryFile = parse_sub('SUBSYSTEM clean\nEND\n')
    assert broken.logger.error_count() == 1
    assert clean.logger.error_count() == 0


def test_comments_quoted_keywords_and_dispatch_aliases() -> None:
    """Comment prose and keyword aliases must not corrupt block boundaries."""
    result: PsseAuxiliaryFile = parse_sub("COM user's comment\nSUBSYSTEM s\nBUS 1\nEND\n")
    assert result.logger.error_count() == 0
    quoted: PsseAuxiliaryFile = parse_mon("'END'\nMONITOR ALL BRANCHES\n")
    assert quoted.records[0].command == PsseCommand.UNKNOWN
    assert len(quoted.records) == 2
    contingency: PsseAuxiliaryFile = parse_con("""CONTINGENCY c
ALTER BUS 1 LOAD BY 10 MW DISPATCH
BUS 2 1.0
END
RAISE BUS 1 GENERATION BY 10 MW DISPATCH
BUS 2 1.0
END
REDUCE BUS 1 LOAD BY 10 MW
END
""")
    assert contingency.logger.error_count() == 0
    assert contingency.logger.warning_count() == 0
    assert [record.command for record in contingency.records[0].children] == [
        PsseCommand.CHANGE, PsseCommand.INCREASE, PsseCommand.DECREASE]


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_shared_legacy_grammar_across_versions(version: int) -> None:
    """POM 33 section 8.1 examples remain readable by each major version."""
    subsystem: PsseAuxiliaryFile = parse_sub("""SUBSYSTEM 'MY COMPANY'
AREA 5
JOIN 'GROUP 1'
AREA 6
ZONES 8 10
END
SKIP BUS 567
PARTICIPATE
BUS 601 100.0
END
END
END
""", version=version)
    monitoring: PsseAuxiliaryFile = parse_mon("""MONITOR INTERFACE 'TRANSFER' RATINGS 100 110 120 MW
101 102 '01'
END
MONITOR BRANCHES IN AREA 5
MONITOR TIES FROM AREA 5 TO AREA 6
MONITOR VOLTAGE RANGE SUBSYSTEM 'MY COMPANY' .95 1.05
END
""", version=version)
    contingency: PsseAuxiliaryFile = parse_con("""CONTINGENCY 'LOSS OF LINE' .01 2
OPEN LINE FROM BUS 101 TO BUS 102 CKT '01'
CHANGE BUS 101 GENERATION BY -10 MW DISPATCH
BUS 102 100.0
END
END
SINGLE BRANCH IN AREA 5
END
""", version=version)
    dynamics: DyrFile = parse_dyr("""101 'GENCLS' '01' 3.5 0 /
101 'USRMDL' '01' 'CUSTOM' 1 1 0 2 1 0 3.5 0 /
101 'USRSWS' 'SHUNTMODEL' 1 1 0 2 1 0 3.5 0 /
""", version=version)
    for result in (subsystem, monitoring, contingency, dynamics):
        assert result.version is not None
        assert result.version == PsseVersion(version)
        assert result.logger.error_count() == 0
        assert result.logger.warning_count() == 0
    assert subsystem.records[0].children[1].command == PsseCommand.JOIN
    assert len(monitoring.records[0].children) == 1
    assert len(contingency.records[0].children[1].children) == 1
    assert dynamics.records[1].data[:2] == ('01', 'CUSTOM')
    assert dynamics.records[2].data[0] == 'SHUNTMODEL'


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_file_readers_forward_version(tmp_path: Path, version: int) -> None:
    """File readers must apply the requested profile rather than their default."""
    sub_path: Path = tmp_path / 'version.sub'
    mon_path: Path = tmp_path / 'version.mon'
    con_path: Path = tmp_path / 'version.con'
    dyr_path: Path = tmp_path / 'version.dyr'
    sub_path.write_text('SUBSYSTEM s\nAREA 1\nEND\n', encoding='utf-8')
    mon_path.write_text('MONITOR ALL BRANCHES\nEND\n', encoding='utf-8')
    con_path.write_text('CONTINGENCY c\nOPEN BUS 101\nEND\n', encoding='utf-8')
    dyr_path.write_text("101 'GENCLS' '1' 3.5 0 /\n", encoding='utf-8')
    for result in (read_sub(sub_path, version=version), read_mon(mon_path, version=version),
                   read_con(con_path, version=version), read_dyr(dyr_path, version=version)):
        assert result.version is not None
        assert result.version == PsseVersion(version)
        assert result.logger.error_count() == 0
        assert len(result.records) == 1


@pytest.mark.parametrize('version', tuple(PsseVersion))
def test_enum_versions_and_initial_bus_name_mode(version: PsseVersion) -> None:
    """Legacy bus name mode comes from the caller, without newer directives."""
    result: PsseAuxiliaryFile = parse_sub("SYSTEM names\nBUS 'ALPHA BETA 345'\nEND\n",
                                          bus_mode=BusInputMode.NAMES, version=version)
    assert result.version == version
    assert result.logger.error_count() == 0
    assert result.records[0].children[0].bus_mode == BusInputMode.NAMES
    assert parse_dyr("101 'GENCLS' '1' 3.5 0 /", version=version).version == version


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_versioned_bus_mode_directives(version: int) -> None:
    """ReleaseNotes 35.2 introduced dynamic bus input mode commands."""
    result: PsseAuxiliaryFile = parse_sub("BUSNAMES\nSYSTEM names\nBUS 'A 345'\nEND\n", version=version)
    assert len(result.records) == 2
    if version in (33, 34):
        assert result.logger.error_count() >= 1
        assert result.bus_mode == BusInputMode.NUMBERS
    else:
        assert result.logger.error_count() == 0
        assert result.bus_mode == BusInputMode.NAMES


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_versioned_mon_selectors(version: int) -> None:
    """Expanded selectors and singular TIE are documented 35.2 additions."""
    result: PsseAuxiliaryFile = parse_mon("""MONITOR BRANCHES IN AREAS 1 5
MONITOR TIES FROM AREA 1 TO AREA 2 IN KVRANGE 100 500
MONITOR VOLTAGE RANGE BUSES 101 110 .95 1.05
MONITOR TIE FROM AREA 1 TO AREA 2
""", version=version)
    assert len(result.records) == 4
    if version in (33, 34):
        assert result.logger.error_count() == 4
    else:
        assert result.logger.error_count() == 0


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_switched_shunt_dyr_header_versions(version: int) -> None:
    """USRSWS2 adds an ID in 35; USRSWS remains accepted without shifting data."""
    result: DyrFile = parse_dyr("101 'USRSWS2' '02' 'SHUNTMODEL' 1 1 0 2 1 0 3.5 0 /\n",
                               version=version)
    assert result.records[0].data[:2] == ('02', 'SHUNTMODEL')
    if version in (33, 34):
        assert result.logger.error_count() == 1
    else:
        assert result.logger.error_count() == 0


def test_psse33_limits_and_newer_syntax_are_diagnosed() -> None:
    """Retain incompatible records while exposing the documented 33 limits."""
    subsystem: PsseAuxiliaryFile = parse_sub("SYSTEM 'thirteenchars'\nAREA 1\nEND\n", version=33)
    assert subsystem.logger.error_count() == 1
    monitoring: PsseAuxiliaryFile = parse_mon("""MONITOR INTERFACE i RATINGS 1 2 3 4
101 102
END
MONITOR BREAKER SUBSTATION 1 FROM NODE 1 TO NODE 2
""", version=33)
    assert monitoring.logger.error_count() == 2
    contingency: PsseAuxiliaryFile = parse_con("CONTINGENCY c CATEGORY weather\nOPEN BUS 101\nEND\n",
                                              version=33)
    assert contingency.logger.error_count() == 1
    assert len(contingency.records[0].children) == 1


def test_keyword_labels_do_not_trigger_version_gates() -> None:
    """Legal unquoted names are data even if they spell newer keywords."""
    subsystem: PsseAuxiliaryFile = parse_sub('SYSTEM NODE\nAREA 1\nEND\n', version=33)
    monitoring: PsseAuxiliaryFile = parse_mon('MONITOR TIES FROM SUBSYSTEM KVRANGE TO SYSTEM AREAS\n',
                                             version=33)
    assert subsystem.logger.error_count() == 0
    assert monitoring.logger.error_count() == 0


@pytest.mark.parametrize('version', (32, 37))
def test_unsupported_versions_do_not_silently_fall_back(version: int) -> None:
    """No syntax tree should imply successful support for an unknown version."""
    for result in (parse_sub('SYSTEM s\nEND\n', version=version),
                   parse_mon('MONITOR ALL BRANCHES\n', version=version),
                   parse_con('CONTINGENCY c\nEND\n', version=version),
                   parse_dyr("101 'GENCLS' '1' 3.5 0 /", version=version)):
        assert result.version is None
        assert result.records == ()
        assert result.logger.error_count() == 1


@pytest.mark.parametrize('version', (33, 34))
def test_legacy_all_buses_and_primary_kv_selector(version: int) -> None:
    """POM 33 section 8.1.3 permits ALL BUSES and KV as primary selectors."""
    result: PsseAuxiliaryFile = parse_mon("""MONITOR VOLTAGE RANGE ALL BUSES .95 1.05
VOLTAGE RANGE KV 345 .95 1.05
MONITOR VOLTAGE LIMIT ALL BUSES
VOLTAGE LIMIT KV 345
MONITOR VOLTAGE DEVIATION KV 345 .05 .05
""", version=version)
    assert result.logger.error_count() == 0
    extra_filter: PsseAuxiliaryFile = parse_mon('MONITOR VOLTAGE RANGE AREA 1 KV 345 .95 1.05\n',
                                               version=version)
    assert extra_filter.logger.error_count() == 1
