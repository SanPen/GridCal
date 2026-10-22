# SPDX-License-Identifier: MPL-2.0
"""Manual-derived fixtures, not native PSS/E exports or simulator equivalence."""
import pytest
from VeraGridEngine.IO.raw.gcp_parser import parse_gcp, read_gcp
from VeraGridEngine.IO.raw.seq_parser import parse_seq
from VeraGridEngine.IO.raw.rop_parser import parse_rop
from VeraGridEngine.IO.raw.loc_parser import parse_loc
from VeraGridEngine.IO.raw.psse_data import split_data_row
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.seq import SequenceSection, SequenceSystem, SequenceCharacteristic, SequenceSwitchedShunt
from VeraGridEngine.IO.raw.versioned.base.seq_records import SequenceGenerator, SequenceTransformer, SequenceInduction
from VeraGridEngine.IO.raw.versioned.base.rop import RopSection, RopCostCurve, RopCoefficient
from VeraGridEngine.IO.raw.versioned.base.rop_records import RopAdjustableShunt, RopBranchFlow, RopVariable
from VeraGridEngine.IO.raw.versioned.base.loc import BranchLocationLayout, CoordinateSystem, LocationKind
from pathlib import Path


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_concrete_versions_and_early_quit(version: int) -> None:
    """Each public parser constructs the selected concrete version class."""
    seq = parse_seq(f'0,{version}\nQ', version=version)
    rop = parse_rop('0\nQ', version=version)
    gcp = parse_gcp((f'0,{version}\n' if version >= 35 else '') + '0', version=version)
    loc = parse_loc('1,-79,40', version=version)
    for result in (seq, rop, gcp, loc):
        assert type(result).__name__.endswith(f'V{version}')
        assert result.ended
        assert not result.logger.has_logs()


def test_numeric_lexer_preserves_omissions_and_quoted_slashes() -> None:
    """Blank CSV fields and string IDs must not shift numeric positions."""
    row = split_data_row(" ,1,, 'a/b''c', 3D-2, / comment", 8)
    assert [token.text for token in row.tokens] == ['', '1', '', "a/b'c", '3D-2', '']
    assert row.tokens[3].quoted
    assert split_data_row("1,'oops", 1).status == RecordStatus.INVALID


@pytest.mark.parametrize('sequence,text', [(True, '0,33\nQ'), (False, '0,33\n0')])
def test_revision_mismatch_is_not_silently_reinterpreted(sequence: bool, text: str) -> None:
    """An incompatible explicit REV prevents parsing with a guessed layout."""
    if sequence:
        result = parse_seq(text, version=36)
    else:
        result = parse_gcp(text, version=36)
    assert result.logger.has_logs()
    assert result.unsupported
    assert not result.ended


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_seq_named_fields_and_version_extensions(version: int) -> None:
    """Generator REFDEG is consumed only by the documented later layouts."""
    prefix = f'0,{version}\n' + ('0\n' if version >= 34 else '')
    fields = '1,01,.01,.2,.3,.4,.02,.21,.03,.22,1,.04,.23'
    fields += ',17' if version >= 34 else ''
    result = parse_seq(prefix + fields + '\nQ', version=version)
    entry = result.records[0].data
    assert isinstance(entry, SequenceGenerator)
    assert entry.machine_id == '01'
    assert entry.x_subtransient == .2
    assert entry.reference_angle == (17 if version >= 34 else None)
    assert entry.status == RecordStatus.VALID
    assert not result.logger.has_logs()


def test_seq_transformer_three_windings_and_omissions() -> None:
    """Winding three precedes neutral impedance; blank fields stay absent."""
    result = parse_seq('0,33\n' + '0\n' * 4 + '1,2,3,1,1,1,1,.1,.2,,.4,.5,.6,.7,.8,.9,1,1.1,1.2,1.3,1.4\nQ', version=33)
    entry = result.records[0].data
    assert isinstance(entry, SequenceTransformer)
    assert entry.r_zero_1 is None
    assert entry.r_ground_3 == .9
    assert entry.r_neutral == 1.3
    assert entry.x_neutral == 1.4
    assert entry.status == RecordStatus.VALID


@pytest.mark.parametrize('version', (33, 34, 35, 36))
def test_seq_shunt_layout_and_induction(version: int) -> None:
    """Modern switched-shunt IDs and induction additions have explicit layouts."""
    result = parse_seq(f'0,{version}\nQ', version=version)
    shunt_index = result.sections.index(SequenceSection.SWITCHED_SHUNT)
    induction_index = result.sections.index(SequenceSection.INDUCTION)
    shunt = "9,'02',.1,.2" if version >=35 else '9,.1,.2'
    induction = '9,1,1,1,5,10,.1,.2,.3,.4' + (',6,11,7,12' if version>=34 else '')
    text = f'0,{version}\n' + '0\n' * shunt_index + shunt + '\n' + '0\n' * (induction_index-shunt_index) + induction + '\nQ'
    result = parse_seq(text, version=version)
    first = result.records[0].data
    last = result.records[1].data
    assert isinstance(first, SequenceSwitchedShunt)
    assert first.shunt_id == ('02' if version>=35 else None)
    assert first.susceptances == (.1,.2,None,None,None,None,None,None)
    assert isinstance(last, SequenceInduction)
    assert last.locked_rotor_negative == (7 if version>=34 else None)
    assert not result.logger.has_logs()


def test_seq_system_options_and_continued_characteristic() -> None:
    """Named options, zero-valued first abscissa and triplet terminators coexist."""
    result = parse_seq('0,36\nMOV, TOLERANCE = .02, ITERATIONS=30\n' + '0\n' * 9 + "'CURVE',TIM,0,1,2\n.1,2,3,0,0,0\n0\n1,1,TIM,'CURVE',,1.2,.8,1.1\nQ")
    system = result.records[0].data
    curve = result.records[1].data
    assert isinstance(system, SequenceSystem)
    assert [option.value for option in system.options] == [.02,30]
    assert isinstance(curve, SequenceCharacteristic)
    assert [point.x for point in curve.points] == [0,.1]
    assert len(curve.rows) == 2
    assert len(result.records) == 3
    assert not result.logger.has_logs()


def test_seq_34_characteristics_are_single_records_without_sentinels() -> None:
    """Legacy curves have no nested zero-triplet framing."""
    result = parse_seq('0,34\n' + '0\n' * 9 + '1,1,0,1,2\n2,1,0,2,3\n0\n', version=34)
    entry = result.records[0].data
    assert isinstance(entry, SequenceCharacteristic)
    assert entry.status == RecordStatus.VALID
    assert len(result.records) == 2
    assert result.ended


@pytest.mark.parametrize('version', (33,34,35,36))
def test_gcp_generator_motor_and_legacy_origin(version: int) -> None:
    """A zero header must not be confused with legacy EOF or curve powers."""
    text = (f'1,{version}\n' if version>=35 else '') + "1,'01',10,20,-10,30,25,-12\n2,1,0,4,-4,-10,5,-5\n0"
    result = parse_gcp(text, version=version)
    assert result.curves[0].points[1].q_min == -12
    assert result.curves[0].implicit_origin == (version <35)
    assert not result.curves[1].implicit_origin
    assert all(curve.status == RecordStatus.VALID for curve in result.curves)
    assert not result.logger.has_logs()


@pytest.mark.parametrize('record', ('1,1,0,1,-1,0,2,-2', '1,1,0,-1,1,10,2,-2', '1,1,nan,1,-1,10,2,-2', '1,1,0,1,-1'))
def test_gcp_rejects_invalid_curves(record: str) -> None:
    """Ordering, finite values, minimum points and Q bounds are checked."""
    result = parse_gcp('0,36\n'+record+'\n0')
    assert result.curves[0].status == RecordStatus.INVALID
    assert result.curves[0].row.line_number == 2
    assert result.logger.has_logs()


def test_gcp_omitted_q_duplicate_and_encoded_file(tmp_path: Path) -> None:
    """Omissions remain distinct from zero and duplicate curves are rejected."""
    file_name = tmp_path / 'curves.gcp'
    file_name.write_text("0,36\n1,01,0,,,-10,2,-2\n1,01,0,1,-1,10,2,-2\n0\n2,1,0,1,-1", encoding='utf-8-sig')
    result = read_gcp(file_name)
    assert result.curves[0].points[0].q_max is None
    assert result.curves[1].status == RecordStatus.INVALID
    assert len(result.unsupported) == 1


@pytest.mark.parametrize('version', (33,34,35,36))
def test_rop_shunt_status_cost_column_swap(version: int) -> None:
    """The version-specific STATUS/CTYP swap must affect named values."""
    payload = '1,02,1,2,0,3,' + ('1,2,5' if version>=35 else '2,1,5')
    result = parse_rop('0\n0\n'+payload+'\nQ', version=version)
    entry = result.records[0].data
    assert isinstance(entry, RopAdjustableShunt)
    assert entry.status == 1
    assert entry.cost_type == 2
    assert entry.cost_table == 5
    assert entry.validity == RecordStatus.VALID
    assert not result.logger.has_logs()


def test_rop_counted_cost_points_and_zero_abscissa() -> None:
    """Zero-valued points in continued payloads are not section markers."""
    result = parse_rop('0\n'+'0\n'*9+"1,'cost',3,0,0\n10,2,20,3\n0\n2,'quad',5,2,0,0,10,2\nQ")
    first = result.records[0].data
    second = result.records[1].data
    assert isinstance(first, RopCostCurve)
    assert [point.x for point in first.points] == [0,10,20]
    assert len(first.rows) == 2
    assert isinstance(second, RopCostCurve)
    assert second.constant == 5
    assert second.validity == RecordStatus.VALID
    assert not result.logger.has_logs()


def test_rop_nested_zeros_and_linear_coefficient_identifiers() -> None:
    """Inner zeros cannot advance sections; KBUS follows COEFF for VTYP 5/6."""
    text = '0\n'+'0\n'*12+'1,40,10,1\n9,01\n0\n0\n1,2,01,1,20,-20,25,-25,1,1,0,0\n0\n1,label,20,-20,1,1,0\n1,2,01,0\n0\n0\n1,eq,0,0\n5,1,2,01,2.5,3\n6,1,2,01,1,3.5,4\n0\n0\n'
    result = parse_rop(text)
    assert [record.section for record in result.records] == [RopSection.PERIOD_RESERVE,RopSection.BRANCH_FLOW,RopSection.INTERFACE_FLOW,RopSection.LINEAR_DEPENDENCY]
    assert len(result.records[0].data.members) == 1
    assert isinstance(result.records[1].data, RopBranchFlow)
    coefficient = result.records[3].data.members[0]
    assert isinstance(coefficient, RopCoefficient)
    assert coefficient.variable == RopVariable.TRANSFORMER_TAP
    assert coefficient.coefficient == 2.5
    assert coefficient.third_bus == 3
    assert result.records[3].data.members[1].third_bus == 4
    assert result.ended
    assert not result.logger.has_logs()


def test_rop_incomplete_curve_does_not_swallow_next_section() -> None:
    """Malformed counted payload retains its source and leaves outer markers."""
    result = parse_rop('0\n'+'0\n'*9+"1,label,2,0,0\n0\nQ")
    assert result.records[0].data.validity == RecordStatus.INVALID
    assert result.ended
    assert result.logger.has_logs()


@pytest.mark.parametrize('longitude', ("79°30'36W", '-79 -30 -36', '79.51W', '-79.51,,,'))
def test_loc_manual_dms_equivalents(longitude: str) -> None:
    """All four coordinate notations in the manuals yield the same angle."""
    result = parse_loc(f'1,{longitude},40,0,1')
    assert result.records[0].status == RecordStatus.VALID
    assert result.records[0].points[0].x == pytest.approx(-79.51)
    assert result.records[0].points[0].y == 40
    assert result.records[0].length == 1
    assert not result.logger.has_logs()


def test_loc_blocks_formats_offsets_and_names() -> None:
    """Block settings reset, offsets keep their frame and quoted buses survive."""
    text = "BUSES\nGEOPHYSICAL LATLON\n1,40N,79W,,2\nNODES\nCARTESIAN SCALE 2\n3,4,200,300,90,1\nBRANCHES\nCARTESIAN\n'FROM BUS','TO BUS',02,1,2,3,4,5,6\n"
    result = parse_loc(text)
    bus,node,branch = result.records
    assert bus.format.latitude_first
    assert bus.points[0].x == 40
    assert bus.rotation == 0
    assert node.kind == LocationKind.NODE
    assert node.format.system == CoordinateSystem.CARTESIAN
    assert node.format.scale == 2
    assert node.substation == 3 and node.node == 4
    assert node.points[0].x == 200
    assert branch.bus.name == 'FROM BUS'
    assert len(branch.points) == 3
    assert branch.branch_layout == BranchLocationLayout.REQUIRED_ENDPOINTS
    assert not result.logger.has_logs()


@pytest.mark.parametrize('version', (33,34,35,36))
def test_loc_endpoint_version_boundary(version: int) -> None:
    """Legacy knee-only paths remain distinct from 36's mandatory endpoints."""
    result = parse_loc('BRANCHES\nCARTESIAN\n1,2,1,3,4', version=version)
    assert result.records[0].status == (RecordStatus.INVALID if version==36 else RecordStatus.VALID)


@pytest.mark.parametrize('payload', ('1,181,0', '1,0,91', '1,-79E,40', "1,79°60'0W,40", '1,nan,40', '1,0,0,0,-1', '1,0'))
def test_loc_rejects_bad_coordinates(payload: str) -> None:
    """Ranges, hemisphere conflicts, scalar domains and missing fields fail."""
    result = parse_loc(payload)
    assert result.records[0].status == RecordStatus.INVALID
    assert result.logger.has_logs()


def test_unknown_location_blocks_are_retained_until_a_known_header() -> None:
    """Unknown block content cannot be interpreted as bus coordinates."""
    result = parse_loc('[UNKNOWN]\n1,2,3\nBUSES\n1,-79,40')
    assert len(result.unsupported) == 2
    assert len(result.records) == 1
    assert result.records[0].row.line_number == 4


def test_seq_35_minor_layout_is_explicit() -> None:
    """The major REV field cannot distinguish 35.0 curves from 35.2 tables."""
    from VeraGridEngine.IO.raw.versioned.base.seq import Sequence35Layout
    legacy = parse_seq('0,35\n' + '0\n' * 9 + '1,01,0,1,2\n0\nQ', version=35, layout_35=Sequence35Layout.V35_0)
    assert legacy.records[0].section == SequenceSection.LEGACY_NCS
    curve = legacy.records[0].data
    assert isinstance(curve, SequenceCharacteristic)
    assert curve.bus == 1 and curve.machine_id == '01'
    assert len(curve.points) == 1
    assert not legacy.logger.has_logs()
    modern = parse_seq('0,35\n' + '0\n' * 9 + '1,01,0,1,2,0,0,0\nQ', version=35)
    assert modern.records[0].data.status == RecordStatus.INVALID


@pytest.mark.parametrize('version', (33,34,35,36))
def test_complete_section_terminators_allow_final_q(version: int) -> None:
    """A normal final section zero followed by Q is one valid termination."""
    seq = parse_seq(f'0,{version}\nQ', version=version)
    seq = parse_seq(f'0,{version}\n' + '0\n' * len(seq.sections) + 'Q', version=version)
    rop = parse_rop('0\n' + '0\n' * 16 + 'Q', version=version)
    assert seq.ended and rop.ended
    assert not seq.unsupported and not rop.unsupported
    assert not seq.logger.has_logs() and not rop.logger.has_logs()


@pytest.mark.parametrize('section,payload', (
    (RopSection.BUS_VOLTAGE, '1,1.1,.9,1.2,.8,2,10'),
    (RopSection.BUS_LOAD, '1,01,2'),
    (RopSection.LOAD_TABLE, '1,1,2,0,1,2,0,1,1,1,0'),
    (RopSection.GENERATOR_DISPATCH, '1,01,.75,2'),
    (RopSection.ACTIVE_DISPATCH, '1,20,0,2,1,1,3'),
    (RopSection.GENERATION_RESERVE, '1,01,2.5,100'),
    (RopSection.REACTIVE_CAPABILITY, '1,01,1.2,1.5,.85,.9,.2,4'),
    (RopSection.BRANCH_REACTANCE, '1,2,01,1,2,0,1,1,1,3'),
    (RopSection.POLYNOMIAL_COST, '1,label,1,2,3,4,5'),
))
def test_rop_all_fixed_section_layouts(section: RopSection, payload: str) -> None:
    """Every fixed schema consumes the documented integer/real/text types."""
    result = parse_rop('0\n' + '0\n' * tuple(RopSection).index(section) + payload + '\nQ')
    assert result.records[0].section == section
    assert result.records[0].data.validity == RecordStatus.VALID
    assert not result.logger.has_logs()


@pytest.mark.parametrize('section,payload', (
    (RopSection.BUS_VOLTAGE, '1,.9,1.1,1.2,.8,2,10'),
    (RopSection.BUS_VOLTAGE, '1,1.1,.9,1.2,.8,7,10'),
    (RopSection.ADJUSTABLE_SHUNT, '1,1,0,1,0,1,9,1,1'),
    (RopSection.REACTIVE_CAPABILITY, '1,1,1,1,.8,.9,1,8'),
    (RopSection.PERIOD_RESERVE, '16,1,1,1\n0'),
))
def test_rop_invalid_domains(section: RopSection, payload: str) -> None:
    """Syntactically numeric values still need documented domain checks."""
    result = parse_rop('0\n' + '0\n' * tuple(RopSection).index(section) + payload + '\nQ')
    assert result.records[0].data.validity == RecordStatus.INVALID
    assert result.logger.has_logs()


def test_loc_whitespace_example_and_node_offsets() -> None:
    """Representative DataFormats 36 example coordinates and relative offsets."""
    result = parse_loc('BUSES\nGEOPHYSICAL\n101 73.971254W 42.533109N 90 1.20\nBRANCHES\nGEOPHYSICAL\n101 151 T1 73.970356W 42.533026N 73.970356W 42.528558N\nNODES\n1,2,300,200')
    assert result.records[0].points[0].x == -73.971254
    assert result.records[0].rotation == 90
    assert result.records[1].circuit == 'T1'
    assert len(result.records[1].points) == 2
    assert result.records[2].points[0].x == 300
    assert all(record.status == RecordStatus.VALID for record in result.records)
    assert not result.logger.has_logs()


@pytest.mark.parametrize('version', (32,37))
def test_unsupported_versions_do_not_fallback(version: int) -> None:
    """Unknown versions preserve a diagnostic instead of selecting latest."""
    for result in (parse_seq('0\nQ', version=version), parse_rop('0\nQ', version=version), parse_gcp('0', version=version), parse_loc('1,0,0', version=version)):
        assert result.version is None
        assert result.logger.has_logs()


def test_seq_mov_current_is_real_and_transformer_grounding_can_be_ohms() -> None:
    """IPR is rated current, and transformer CZG=3 means ohms."""
    result = parse_seq('0,34\n' + '0\n' * 3 + '1,2,01,.1,.2,.3,0,0,0,0,1.25,1\n0\n0\n1,2,0,01,1,3,14,1,2,3,4,5,6,7,8,9,10\nQ', version=34)
    from VeraGridEngine.IO.raw.versioned.base.seq_records import SequenceBranch
    branch = result.records[0].data
    transformer = result.records[1].data
    assert isinstance(branch, SequenceBranch)
    assert branch.rated_mov_current == 1.25
    assert isinstance(transformer, SequenceTransformer)
    assert transformer.grounding_code == 3
    assert all(record.data.status == RecordStatus.VALID for record in result.records)
    assert not result.logger.has_logs()


def test_rop_flow_identifier_is_text_and_equation_label_has_32_characters() -> None:
    """BFID is not a numeric flag; full equation labels must be preserved."""
    result = parse_rop('0\n' + '0\n' * 13 + '1,2,01,A,20,-20,25,-25,1,1,0,0\n0\n0\n1,\'a label longer than twelve\',0,0\n6,1,2,01,A,2.5,0\n0\nQ')
    branch = result.records[0].data
    assert isinstance(branch, RopBranchFlow)
    assert branch.flow_id == 'A'
    member = result.records[1].data.members[0]
    assert isinstance(member, RopCoefficient)
    assert member.flow_id == 'A'
    assert member.coefficient == 2.5
    assert not result.logger.has_logs()


def test_seq_named_table_missing_sentinel_keeps_next_section_marker() -> None:
    """Only modern tables need a zero triplet; an outer zero remains unconsumed."""
    result = parse_seq('0,36\n' + '0\n' * 9 + "'table',TIM,0,1,2\n0\n1,01,TIM,'table'\nQ")
    assert isinstance(result.records[0].data, SequenceCharacteristic)
    assert result.records[0].data.status == RecordStatus.INVALID
    assert result.records[1].section == SequenceSection.NCS_GENERATOR
    assert result.ended


@pytest.mark.parametrize('scale', ('2', 'SCALE 2'))
def test_loc_cartesian_scale_syntax(scale: str) -> None:
    """SCALE is a retained positive numeric factor, not an invented projection."""
    result = parse_loc(f'CARTESIAN {scale}\n1,200,300')
    assert result.records[0].format.scale == 2
    assert not result.logger.has_logs()


def test_loc_comma_dms_and_unit_markers() -> None:
    """Hemisphere/unit notation disambiguates DMS comma components."""
    result = parse_loc("1,79,30,36W,40°15'30\"N,90,2")
    assert result.records[0].points[0].x == pytest.approx(-79.51)
    assert result.records[0].points[0].y == pytest.approx(40.2583333333)
    assert result.records[0].status == RecordStatus.VALID
    assert not result.logger.has_logs()


def test_provisional_version_inheritance_is_queryable() -> None:
    """Documentation gaps must be visible to integration code, not hidden."""
    from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
    assert parse_gcp('0', version=34).format_support == FeatureSupport.UNVERIFIED
    assert parse_gcp('0', version=33).format_support == FeatureSupport.YES
    assert parse_gcp('0,35\n0', version=35).format_support == FeatureSupport.YES
    assert parse_loc('1,0,0', version=34).branch_layout_support == FeatureSupport.UNVERIFIED
    assert parse_loc('1,0,0', version=35).branch_layout_support == FeatureSupport.UNVERIFIED
    assert parse_loc('1,0,0', version=36).branch_layout_support == FeatureSupport.YES
