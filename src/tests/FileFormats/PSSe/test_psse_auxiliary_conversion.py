# SPDX-License-Identifier: MPL-2.0
"""Native object values and dynamic-template bindings, beyond successful parsing."""
from pathlib import Path
import numpy as np
import pytest
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.IO.raw.sub_parser import parse_sub
from VeraGridEngine.IO.raw.mon_parser import parse_mon
from VeraGridEngine.IO.raw.con_parser import parse_con
from VeraGridEngine.IO.raw.seq_parser import parse_seq
from VeraGridEngine.IO.raw.rop_parser import parse_rop
from VeraGridEngine.IO.raw.gcp_parser import parse_gcp
from VeraGridEngine.IO.raw.loc_parser import parse_loc
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.psse_conversion_report import PsseConversionStatus
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType
from VeraGridEngine.IO.raw.versioned.base.rop import RopSection
from VeraGridEngine.IO.raw.versioned.base.dyr import RawDyr
from VeraGridEngine.IO.raw.versioned.v35.bus import RawBusV35
from VeraGridEngine.IO.raw.versioned.v35.branch import RawBranchV35
from VeraGridEngine.IO.raw.versioned.v35.generator import RawGeneratorV35
from VeraGridEngine.IO.raw.versioned.v35.transformer import RawTransformerV35
from VeraGridEngine.enumerations import WindingsConnection
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.basic_structures import Logger


def make_raw_case() -> PsseCircuit:
    """Create a two-bus RAW case with nontrivial system/machine base ratio.

    :return: Concrete version-35 RAW objects and no auxiliary input.
    """
    case: PsseCircuit = PsseCircuit()
    case.REV = 35
    case.SBASE = 100
    case.BASFRQ = 60
    for number in (1,2):
        bus: RawBusV35 = RawBusV35()
        bus.I = number
        bus.NAME = f'BUS{number}'
        bus.BASKV = 230
        bus.IDE = 3 if number == 1 else 1
        bus.AREA = 1
        bus.ZONE = 1
        case.buses.append(bus)
    generator: RawGeneratorV35 = RawGeneratorV35()
    generator.I = 1
    generator.ID = '01'
    generator.MBASE = 50
    generator.ZR = .01
    generator.ZX = .2
    generator.PG = 20
    generator.QG = 5
    generator.QT = 30
    generator.QB = -20
    generator.PT = 80
    generator.PB = 0
    generator.STAT = 1
    case.generators.append(generator)
    branch: RawBranchV35 = RawBranchV35()
    branch.I = 1
    branch.J = 2
    branch.CKT = 'A'
    branch.R = .01
    branch.X = .1
    branch.RATE1 = 100
    branch.ST = 1
    case.branches.append(branch)
    return case


def event_values(block: Block) -> dict[str,float]:
    """Read literal event constants for exact unit-conversion assertions.

    :param block: Runtime/template block.
    :return: Named scalar event constants.
    """
    return dict((var.name, expression.value) for var, expression in block.event_dict.items() if isinstance(expression, Const))


def test_native_static_values_and_source_report() -> None:
    """Source values reach native bus/branch/generator/contingency objects."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_sub('SYSTEM s\nAREA 1\nSKIP BUS 2\nEND',version=35))
    assert case.add_auxiliary(parse_mon('MONITOR BRANCH FROM BUS 1 TO BUS 2 CIRCUIT A',version=35))
    assert case.add_auxiliary(parse_con('CONTINGENCY outage\nOPEN BRANCH FROM BUS 2 TO BUS 1 CIRCUIT A\nEND',version=35))
    assert case.add_auxiliary(parse_seq('0,35\n0\n1,01,.01,.2,,,.02,.21,.03,.22,1,0,0\n0\n0\n1,2,A,.04,.4,.02\nQ',version=35))
    assert case.add_auxiliary(parse_gcp('0,35\n1,01,0,20,-10,40,30,-15\n0',version=35))
    assert case.add_auxiliary(parse_loc('1,-79,40',version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    generator = grid.generators[0]
    assert generator.R1 == .02 and generator.X1 == .4
    assert generator.R2 == .04 and generator.X2 == .42
    assert generator.R0 == .06 and generator.X0 == .44
    assert grid.lines[0].R0 == .04 and grid.lines[0].X0 == .4
    assert grid.lines[0].B0 == .02
    assert generator.use_reactive_power_curve
    np.testing.assert_allclose(generator.q_curve.get_data(), [[0,-10,20],[40,-15,30]])
    assert grid.buses[0].longitude == -79 and grid.buses[0].latitude == 40
    assert grid.lines[0].monitor_loading
    assert grid.lines[0].active
    assert len(grid.contingencies) == 1 and grid.contingencies[0].device is grid.lines[0]
    assert grid.contingencies[0].value == 0
    assert case.conversion_report is not None
    assert case.conversion_report.documents == case.get_auxiliary_documents()
    assert case.conversion_report.subsystems[0].bus_ids == (grid.buses[0].idtag,)


def test_opf_tables_resolve_native_limits_and_costs() -> None:
    """Dispatch/cost references resolve after the complete ROP file is indexed."""
    case: PsseCircuit = make_raw_case()
    sections: dict[RopSection,str] = dict([
        (RopSection.BUS_VOLTAGE,'1,1.05,.95'),
        (RopSection.GENERATOR_DISPATCH,'1,01,1,1'),
        (RopSection.ACTIVE_DISPATCH,'1,70,10,2,1,1,1'),
        (RopSection.POLYNOMIAL_COST,"1,'fuel',5,2,3,0,1"),
    ])
    text: str = '0\n'
    for section in RopSection:
        payload: str = sections.get(section,'')
        text += (payload+'\n' if payload else '')+'0\n'
    assert case.add_auxiliary(parse_rop(text+'Q',version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.buses[0].Vmax == 1.05 and grid.buses[0].Vmin == .95
    assert grid.generators[0].Pmax == 70 and grid.generators[0].Pmin == 10
    assert grid.generators[0].Cost0 == 10
    assert grid.generators[0].Cost == 4
    assert grid.generators[0].Cost2 == 6


def test_contingency_group_is_atomic_when_an_event_is_unsupported() -> None:
    """An incomplete source contingency must never become a smaller native outage."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_con('CONTINGENCY bad\nOPEN BRANCH FROM BUS 1 TO BUS 2 CIRCUIT A\nINCREASE BUS 1 GENERATION BY 10 MW\nEND',version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.contingencies == [] and grid.contingency_groups == []
    assert any(entry.status == PsseConversionStatus.UNSUPPORTED for entry in case.conversion_report.entries)
    assert grid.lines[0].active


def test_cartesian_locations_copy_without_source_specific_metadata() -> None:
    """Drawing units stay separate from GIS, including in copied circuits."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_loc('CARTESIAN\n1,2,3,90,1', version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert len(grid.diagrams) == 1
    point = grid.diagrams[0].query_point(grid.buses[0])
    assert point is not None
    assert (point.x, point.y, point.r, point.w) == (192,288,90,96)
    copied: MultiCircuit = grid.copy()
    assert case.conversion_report is not None
    assert case.conversion_report.entries[0].target_ids == (copied.buses[0].idtag,)
    assert all("psse" not in name.lower() for name in MultiCircuit.__slots__)
    assert copied.diagrams[0].query_point(copied.buses[0]) is not point


def test_neutral_sequence_update_does_not_add_grounding_twice() -> None:
    """UPDATE retains machine-base neutral data but replaces supplied series fields."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_seq('0,35\n0\n1,01,.01,.2,,,.02,.21,.03,.22,1,.04,.05\nQ', version=35))
    assert case.add_auxiliary(parse_seq('1,35\n0\n1,01,,,,,,,.06\nQ', version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].R0 == pytest.approx(.06*2+3*.04*2)
    assert grid.generators[0].X0 == pytest.approx(.22*2+3*.05*2)


@pytest.mark.parametrize('code,connection', ((1,WindingsConnection.GG),(2,WindingsConnection.GD),
                                           (14,WindingsConnection.DD)))
def test_simple_transformer_sequence_topology_and_base(code: int, connection: WindingsConnection) -> None:
    """Each supported zero-sequence topology keeps its grounded winding orientation."""
    case: PsseCircuit = make_raw_case()
    transformer: RawTransformerV35 = RawTransformerV35()
    transformer.I = 1
    transformer.J = 2
    transformer.K = 0
    transformer.CKT = 'T'
    transformer.windings = 2
    transformer.R1_2 = .01
    transformer.X1_2 = .1
    transformer.SBASE1_2 = 50
    transformer.NOMV1 = 230
    transformer.NOMV2 = 230
    case.transformers.append(transformer)
    text: str = '0,35\n'+'0\n'*5+f'1,2,0,T,2,1,{code},0,0,.03,.2,0,0,0,0,0,0\nQ'
    assert case.add_auxiliary(parse_seq(text, version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.transformers2w[0].conn == connection
    assert grid.transformers2w[0].R0 == pytest.approx(.06)
    assert grid.transformers2w[0].X0 == pytest.approx(.4)


@pytest.mark.parametrize('constants', ('-1 0', '4 0'))
def test_invalid_or_unsupported_machine_domains_do_not_activate(constants: str) -> None:
    """Invalid inertia and unsupported controller structures do not activate a host."""
    case: PsseCircuit = make_raw_case()
    text: str = "1 'GENCLS' '01' "+constants+' /'
    if constants == '4 0':
        text += "\n1 'ESST3A' '01' .02 .2 -.2 10 1 5 20 .1 5 -5 1 1 1 5 .1 .1 5 0 .1 5 0 /"
    else:
        pass
    assert case.add_auxiliary(parse_dyr(text, version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is None
    assert grid.rms_models == []
    assert any(entry.status != PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('controller', ('', "1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /"))
def test_gencls_uses_native_template_with_system_base_parameters(controller: str) -> None:
    """GENCLS H/D and source impedance convert from machine to system base."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENCLS' '01' 4 2 /\n"+controller,version=35))
    logger: Logger = Logger()
    grid: MultiCircuit = psse_to_veragrid(case,logger=logger)
    assert grid.generators[0].rms_template is not None, str(logger)
    template = grid.generators[0].rms_template
    assert len(grid.rms_models) == 1
    values: dict[str,float] = event_values(template.block.children[0])
    assert values['M'] == 4
    assert values['D'] == 1
    assert values['Ra'] == .02
    assert values['Xd_prime'] == .4
    if controller:
        governor_values: dict[str,float] = event_values(template.block.children[1])
        assert governor_values['R'] == .1
        assert governor_values['VMAX'] == .6
    else:
        assert len(template.block.children) == 1
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('model,constants,state_count', (
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',6),
    ('GENROE','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',6),
    ('GENSAL','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 0 0',5),
    ('GENTRA','8 4 2 1.8 1.7 .3 0 0 .3',3),
))
def test_rotor_models_reuse_native_equations_with_real_state_counts(model: str, constants: str, state_count: int) -> None:
    """GENSAL keeps its five-state equations and is never replaced by GENROU."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr(f"1 '{model}' '01' {constants} /",version=35))
    logger: Logger = Logger()
    grid: MultiCircuit = psse_to_veragrid(case,logger=logger)
    assert grid.generators[0].rms_template is not None, str(logger)
    machine: Block = grid.generators[0].rms_template.block.children[0]
    if model == 'GENSAL':
        machine = machine.children[0]
    else:
        pass
    assert len(machine.state_vars) == state_count
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('controller', (
    "1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /",
    "1 'HYGOV' '01' .05 .3 5 .05 .5 .2 1 0 1 1 0 .08 /",
    "1 'GAST' '01' .05 .1 .4 3 1 2 1.2 0 .1 /",
    "1 'IEESGO' '01' .2 .07 .2 .3 5 .5 20 .6 .5 1.2 0 /",
    "1 'IEEEG2' '01' 20 .2 .07 .3 1.2 0 1 /",
    "1 'SEXS' '01' .1 .1 100 .5 0 5 /",
    "1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /",
    "1 'EXST1' '01' 0 .2 -.2 0 0 20 0 5 -5 .01 0 0 /",
    "1 'ESST3A' '01' .02 .2 -.2 10 1 5 20 0 5 -5 1 1 1 5 .1 .1 5 0 .1 5 0 /",
    "1 'EXAC1' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 1 2 .1 3 .3 /",
))
def test_genrou_controller_assembly_uses_existing_standard_components(controller: str) -> None:
    """Controllers become connected generator children, not disconnected host templates."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0 /\n"+controller,version=35))
    logger: Logger = Logger()
    grid: MultiCircuit = psse_to_veragrid(case,logger=logger)
    assert grid.generators[0].rms_template is not None, str(logger)
    assert len(grid.generators[0].rms_template.block.children) == 2
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


def test_unknown_controller_blocks_unsafe_partial_generator_activation() -> None:
    """Unknown neighboring records cannot silently turn a controlled plant into constant-input dynamics."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENCLS' '01' 4 0 /\n1 'UNREVIEWED' '01' 1 2 /",version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
    assert grid.rms_models == []
    assert len(case.conversion_report.documents[0].records) == 2


def test_zero_inertia_classical_machine_imports_as_fixed_rotor() -> None:
    """A prescribed source keeps network equations and never divides by zero inertia."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENCLS' '01' 0 0 /",version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    block: Block = grid.generators[0].rms_template.block.children[0]
    assert all(isinstance(equation,Const) and equation.value == 0 for equation in block.state_eqs)
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


def test_source_circuit_and_templates_are_not_mutated_by_conversion() -> None:
    """Repeated conversion creates distinct native graphs with identical source constants."""
    case: PsseCircuit = make_raw_case()
    document = parse_dyr("1 'GENCLS' '01' 4 2 /",version=35)
    assert case.add_auxiliary(document)
    first: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    second: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert first.generators[0].rms_template is not second.generators[0].rms_template
    assert first.generators[0].rms_template.block is not second.generators[0].rms_template.block
    assert document.records[0].constants == (4,2)
    assert case.generators[0].ZR == .01 and case.generators[0].MBASE == 50


def test_remote_voltage_sensing_runtime_connection_survives_native_copy() -> None:
    """Runtime duplication must retain the actual remote bus, including circuit copies."""
    from VeraGridEngine.enumerations import VarPowerFlowReferenceType
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0 /\n"
        "1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'REMCMP' '01' 2 /",version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    copied: MultiCircuit = grid.copy()
    for native in (grid,copied):
        blocks: list[Block] = [child for child in native.generators[0].rms_model.children if 'REMCMP' in child.name]
        assert len(blocks) == 1
        assert blocks[0].in_vars[0].uid == native.buses[1].rms_model.external_mapping[VarPowerFlowReferenceType.Vm].uid


@pytest.mark.parametrize('filter_time',(0,.2))
@pytest.mark.parametrize('frequency',(.01,.3,2.0))
def test_hydro_binding_retains_speed_response_and_water_starting_zero(filter_time: float,frequency: float) -> None:
    """Actual mapped equations must retain droop gain and the inverse turbine response."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response
    document = parse_dyr(f"1 'IEEEG2' '01' 20 {filter_time} .07 .3 1.2 0 1 /",version=35)
    record = document.records[0]
    binding = dynamic_binding(record.model)
    assert binding is not None
    block: Block = build_controller(record,binding,VarFactory(),'hydro',.5).block
    values: dict[int,float] = initialized_values(block)
    response: complex = linearized_response(block,values,1.0,frequency)
    s: complex = 2j*np.pi*frequency
    expected: complex = -20*(1+.07*s)/((1+filter_time*s)*(1+.3*s))*(1-s)/(1+.5*s)
    assert response == pytest.approx(expected,rel=1e-6,abs=1e-8)


@pytest.mark.parametrize('revision', (33,34,35,36))
@pytest.mark.parametrize('acceleration',(.15,.7))
def test_transient_machine_uses_common_layout_without_source_solver_parameters(revision: int,
                                                                               acceleration: float) -> None:
    """The three-state machine maps the common schema but retains AF only at source.

    :param revision: Explicit source revision selecting the document class.
    :param acceleration: Source network-iteration relaxation factor.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    document: RawDyr = parse_dyr(f"1 'GENTRA' '01' 8 4 2 1.8 1.7 .3 .09 .38 {acceleration} /",version=revision)
    assert document.records[0].parameters[-1].name == 'AF'
    assert document.records[0].parameters[-1].value == acceleration
    assert case.add_auxiliary(document)
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    block: Block = grid.generators[0].rms_template.block.children[0]
    parameters: dict[str,float] = event_values(block)
    assert len(block.state_vars) == 3
    assert parameters['H_PSSE_1_01_GENTRA'] == 2
    assert parameters['XdPu_PSSE_1_01_GENTRA'] == 3.6
    assert not any(name.startswith('AF') for name in parameters)
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('revision', (33,34,35,36))
def test_common_dynamic_binding_accepts_versioned_source_documents(revision: int) -> None:
    """Reviewed common CON orders work through each revision's document schema."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENCLS' '01' 4 2 /\n1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert event_values(grid.generators[0].rms_template.block.children[0])['M'] == 4
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('revision',(33,34,35))
@pytest.mark.parametrize('model,constants',(
    ('IEEET1','.02 100 .05 5 -5 1 .5 .05 1 0 3 .1 4 .3'),
    ('IEEEX1','.02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3'),
    ('ESDC1A','.02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3'),
    ('ESDC2A','.02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3'),
    ('EXDC2','.02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3'),
    ('IEEET2','.02 100 .05 5 -5 1 .5 .05 1 .3 3 .1 4 .3'),
    ('IEEEX2','.02 100 .05 .2 .1 5 -5 1 .5 .05 1 .3 3 .1 4 .3'),
    ('IEEX2A','.02 100 .05 .2 .1 5 -5 1 .5 .05 1 3 .1 4 .3'),
    ('GENROE','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38'),
))
def test_new_dynamic_families_use_versioned_documents(revision: int, model: str, constants: str) -> None:
    """Reviewed constant orders activate through each requested version's document class.

    :param revision: Explicit source major version.
    :param model: Reviewed machine or excitation-system identifier.
    :param constants: Numeric constants in documented source order.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    machine: str = '' if model == 'GENROE' else "1 'GENTRA' '01' 8 4 2 1.8 1.7 .3 .09 .38 .3 /\n"
    document: RawDyr = parse_dyr(machine+f"1 '{model}' '01' {constants} /",version=revision)
    assert all(record.parameters for record in document.records)
    assert case.add_auxiliary(document)
    logger: Logger = Logger()
    grid: MultiCircuit = psse_to_veragrid(case,logger=logger)
    assert grid.generators[0].rms_template is not None, str(logger)
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime',(False,True))
@pytest.mark.parametrize('model,constants,controller', (
    ('GENSAL','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 0 0',''),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',''),
    ('GENROE','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',"1 'IEEEX1' '01' .02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3 /"),
    ('GENROE','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'HYGOV' '01' .05 .3 5 .05 .5 .2 1 0 1 1 0 .08 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'GAST' '01' .05 .1 .4 3 1 2 1.2 0 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEESGO' '01' .2 .07 .2 .3 5 .5 20 .6 .5 1.2 0 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEESGO' '01' 0 0 .2 0 0 0 20 .6 .5 1.2 0 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEEG2' '01' 20 .2 .07 .3 1.2 0 1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEEG2' '01' 20 0 .07 .3 1.2 0 1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'SEXS' '01' .1 .1 100 .5 0 5 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEET1' '01' .02 100 .05 5 -5 1 .5 .05 1 0 3 .1 4 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEET1' '01' 0 100 0 0 0 0 .5 .05 1 0 3 .1 4 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEEX1' '01' .02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3 /\n1 'STAB1' '01' 2 10 3 .1 3 .1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'ESDC1A' '01' 0 100 0 0 0 0 0 0 .5 .05 1 0 3 .1 4 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'ESDC2A' '01' 0 100 0 0 0 0 0 0 .5 .05 1 0 3 .1 4 .3 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXDC2' '01' .02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEET2' '01' .02 100 .05 5 -5 1 .5 .05 1 .3 3 .1 4 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEEX2' '01' 0 100 0 0 0 0 0 0 .5 .05 1 .3 3 .1 4 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'IEEX2A' '01' .02 100 .05 .2 .1 5 -5 1 .5 .05 1 3 .1 4 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXAC1' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 1 2 .1 3 .3 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' 0 .2 -.2 0 0 20 0 5 -5 .01 0 0 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'ESST3A' '01' .02 .2 -.2 10 1 5 20 0 5 -5 1 1 1 5 .1 .1 5 0 .1 5 0 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'STAB1' '01' 2 10 3 .1 3 .1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'COMP' '01' .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'IEEEVC' '01' .01 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'REMCMP' '01' 2 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'STAB2A' '01' 1 1 1 .1 1 1 .1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'STAB3' '01' .02 .1 1 1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'STAB4' '01' 1 .02 .1 1 .2 .2 .1 .05 .05 -.1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'STABNI' '01' 1 .2 .1 1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'MNLEX1' '01' .1 1 1 .1 .2 1 /"),
    ('GENTRA','8 4 2 1.8 1.7 .3 0 0 .3',"1 'EXST2' '01' .02 20 .05 5 -5 1 .5 .05 1 1 .1 .1 5 /"),
    ('GENTRA','8 4 2 1.8 1.7 .3 .09 .38 .3',"1 'SCRX' '01' .2 .1 100 .5 -5 5 0 0 /"),
    ('GENTRA','8 4 2 1.8 1.7 .3 .09 .38 .3',"1 'SCRX' '01' .2 .1 100 0 -5 5 0 0 /"),
    ('GENSAL','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 0 0',"1 'SCRX' '01' .2 .1 100 .5 -5 5 1 10 /\n1 'STAB1' '01' 2 10 3 .1 3 .1 .1 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 .1 /"),
    ('GENTRA','8 4 2 1.8 1.7 .3 .09 .38 .3',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /\n1 'STAB1' '01' 2 10 3 .1 3 .1 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST2' '01' .02 20 .05 5 -5 1 .5 .05 1 1 .1 .1 5 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST2' '01' 0 20 0 5 -5 1 .5 .05 1 0 0 .1 5 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'MNLEX3' '01' .1 1 1 .1 .2 -.2 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'MNLEX2' '01' .1 1 1 0 .2 0 .1 /"),
    ('GENSAL','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'MNLEX1' '01' .1 1 1 .1 .2 1 /"),
    ('GENSAL','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 0 0',"1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n1 'MNLEX3' '01' .1 1 1 .1 .2 -.2 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'SEXS' '01' .1 .1 100 .5 0 5 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'ESST3A' '01' .02 .2 -.2 10 1 5 20 0 5 -5 1 1 1 5 .1 .1 5 0 .1 5 0 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXAC1' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 1 2 .1 3 .3 /\n1 'STAB1' '01' 2 10 3 .1 3 .1 .1 /\n1 'MNLEX2' '01' .1 1 1 .1 .2 0 .1 /"),
    ('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0',"1 'EXAC1' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 1 2 .1 3 .3 /\n1 'TGOV1' '01' .05 .1 1.2 0 .2 10 0 /\n1 'STAB4' '01' 1 .02 .1 1 .2 .2 .1 .05 .05 -.1 .1 /"),
))
def test_adapter_initializes_at_a_real_power_flow_equilibrium(model: str, constants: str,
                                                            controller: str, use_runtime: bool,
                                                            operating_power: tuple[float, float] = (.2, .05),
                                                            version: int = 35) -> None:
    """The new stator bridge must satisfy both network and five-state equations."""
    from VeraGridEngine.Utils.Symbolic.block import flatten_block
    from VeraGridEngine.enumerations import VarPowerFlowReferenceType
    from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
    from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import collect_direct_algebraic_initializers
    case: PsseCircuit = make_raw_case()
    case.REV = version
    case.generators[0].PG = operating_power[0]*case.SBASE
    case.generators[0].QG = operating_power[1]*case.SBASE
    assert case.add_auxiliary(parse_dyr(f"1 '{model}' '01' {constants} /\n"+controller,version=version))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    template = grid.generators[0].rms_template
    assert template is not None
    actual_block: Block = grid.generators[0].rms_model if use_runtime else template.block
    flat: Block = flatten_block(actual_block)
    bindings: dict[int,float] = dict()
    for reference, value in ((VarPowerFlowReferenceType.Vm,1.03),(VarPowerFlowReferenceType.Va,.11),
                             (VarPowerFlowReferenceType.P,operating_power[0]),(VarPowerFlowReferenceType.Q,operating_power[1])):
        bindings[actual_block.external_mapping[reference].uid] = value
    # A remote measurement is an independent network input, not a local bus alias.
    for bus in grid.buses:
        remote_voltage: Var | None = bus.rms_model.external_mapping.get(VarPowerFlowReferenceType.Vm,None)
        if remote_voltage is not None and remote_voltage.uid not in bindings:
            bindings[remote_voltage.uid] = .97
        else:
            pass
    expressions: dict[Var,Expr] = dict()
    collect_direct_algebraic_initializers(flat, expressions)
    expressions.update(flat.parameters)
    expressions.update(flat.event_dict)
    expressions.update(flat.init_eqs)
    for _ in range(len(expressions)+1):
        for variable, expression in expressions.items():
            if variable.uid not in bindings:
                try:
                    value = expression.eval_uid(bindings)
                except ValueError:
                    value = None
                if value is not None:
                    bindings[variable.uid] = value
                else:
                    pass
            else:
                pass
    missing: list[str] = [variable.name + ' = ' + str(expression) for variable, expression in expressions.items() if variable.uid not in bindings]
    assert not missing, missing
    residual: np.ndarray = np.asarray([equation.eval_uid(bindings) for equation in flat.algebraic_eqs],dtype=float)
    derivative: np.ndarray = np.asarray([equation.eval_uid(bindings) for equation in flat.state_eqs],dtype=float)
    np.testing.assert_allclose(residual,0,atol=1e-10,
        err_msg='\n'.join(str(flat.algebraic_eqs[index]) for index,value in enumerate(residual) if abs(value)>1e-10))
    np.testing.assert_allclose(derivative,0,atol=1e-10)
    assert len(flat.state_vars) >= (3 if model == 'GENTRA' else (5 if model in ('GENSAL','GENSAE') else 6))
    assert len(flat.algebraic_vars) == len(flat.algebraic_eqs)


@pytest.mark.parametrize('selection,remote', ((1, 0), (3, 0), (5, 0), (5, 2)))
@pytest.mark.parametrize('reset', (0, 5))
@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('exciter', (
    "1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /",
    "1 'IEEET1' '01' .02 20 .02 5 -5 1 .5 .05 1 0 2 .1 3 .3 /",
    "1 'SEXS' '01' .1 .1 100 .5 0 5 /",
    "1 'EXAC1' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 1 2 .1 3 .3 /",
    "1 'EXST2' '01' .02 20 .02 5 -5 1 .5 .05 1 0 0 .1 5 /",
    "1 'SCRX' '01' .1 .1 100 .02 -5 5 0 10 /",
))
def test_polynomial_stabilizer_connected_equilibrium(selection: int, remote: int, reset: int,
                                                     use_runtime: bool, exciter: str) -> None:
    """Source measurements, remote connections and nonzero steady signals initialize the whole assembly."""
    controller: str = (exciter+f"\n1 'IEEEST' '01' {selection} {remote} "
                       f".3 .02 .4 .03 .2 .01 .2 .05 .2 .05 {reset} 5 .01 .1 -.1 1.1 .9 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENROU',
        '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0', controller, use_runtime)


@pytest.mark.parametrize('selection,remote', ((0, 0), (7, 0), (2, 0), (4, 0), (6, 0), (1, 2), (3, 2), (5, 99)))
def test_unreviewed_stabilizer_measurement_blocks_host(selection: int, remote: int) -> None:
    """Unsupported or unresolved measurements retain source records and prevent partial activation."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0 /\n"
        "1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n"
        f"1 'IEEEST' '01' {selection} {remote} .3 .02 .4 .03 .2 .01 .2 .05 .2 .05 5 5 1 .1 -.1 1.1 .9 /", version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is None
    assert all(outcome.status != PsseConversionStatus.CONVERTED for outcome in case.conversion_report.entries
               if outcome.file_type == PsseFileType.DYR)


@pytest.mark.parametrize('selectors', ('1 0 3 0', '3 0 5 2', '5 2 5 0', '5 2 5 2'))
@pytest.mark.parametrize('reset', (0, 5))
@pytest.mark.parametrize('use_runtime', (False, True))
def test_dual_input_stabilizer_connected_equilibrium(selectors: str, reset: int, use_runtime: bool) -> None:
    """Both selected measurements remain connected through saved-template runtime duplication."""
    controller: str = ("1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n"
                       f"1 'IEE2ST' '01' {selectors} .01 -.02 .02 .1 {reset} 5 .2 .05 .3 .1 .1 .05 .1 -.1 1.1 .9 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENROU',
        '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0', controller, use_runtime)


@pytest.mark.parametrize('model,header,constants', (
    ('IEEEST', '5 0', '.3 .02 .4 .03 .2 .01 .2 .05 .2 .05 0 5 .01 .1 -.1 1 .9'),
    ('IEE2ST', '0 0 5 2', '.01 -.02 .02 .1 0 5 .2 .05 .3 .1 .1 .05 .1 -.1 1 .9'),
))
@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_stabilizer_compensated_supervision(model: str, header: str, constants: str, revision: int) -> None:
    """Supervision follows compensated voltage in both templates and duplicated/copy runtime graphs."""
    from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0 /\n"
        "1 'EXST1' '01' .02 .2 -.2 1 5 20 .02 5 -5 .01 .1 1 /\n"
        "1 'REMCMP' '01' 2 /\n"+f"1 '{model}' '01' {header} {constants} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    copied: MultiCircuit = grid.copy()
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)
    for root in (grid.generators[0].rms_template.block, grid.generators[0].rms_model, copied.generators[0].rms_model):
        stabilizer: Block = next(child for child in root.children if model in child.name)
        compensator: Block = next(child for child in root.children if 'REMCMP' in child.name)
        equations: list[BinOp] = [equation for equation in root.algebraic_eqs
            if isinstance(equation, BinOp) and equation.left == stabilizer.in_vars[-1]]
        assert len(equations) == 1
        assert equations[0].right == compensator.out_vars[0]
        assert equations[0].right.eval_uid(dict(((compensator.out_vars[0].uid, .97),))) == .97


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('constants', (
    '.02 20 .02 5 -5 1 .5 .05 1 .3 .1 2 .1 3 .3',
    '0 20 0 5 -5 1 .5 .05 1 0 .7 2 .1 3 .3',
    '.02 20 .02 0 -5 0 .5 .05 1 .3 .1 2 .1 3 .3',
))
def test_brushless_exciter_versioned_binding(revision: int, constants: str) -> None:
    """Reviewed common brushless layout activates through all concrete document versions."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0 /\n"
        f"1 'ESAC5A' '01' {constants} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('constants', (
    '.02 20 .02 5 -5 1 .5 .05 1 .3 .1 2 .1 3 .3',
    '0 20 0 5 -5 1 .5 .05 1 0 .7 2 .1 3 .3',
    '.02 20 .02 0 -5 0 .5 .05 1 .3 .1 2 .1 3 .3',
))
def test_brushless_exciter_connected_equilibrium(constants: str, use_runtime: bool) -> None:
    """Field calibration, loaded saturation, additive limiter and steady stabilizer bias coexist."""
    controller: str = (f"1 'ESAC5A' '01' {constants} /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .2 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENROU',
        '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0', controller, use_runtime)


@pytest.mark.parametrize('model', ('EXAC4', 'ESAC4A'))
@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_alternator_rectifier_versioned_binding(model: str, revision: int) -> None:
    """Equal source constant orders select explicitly different native regulator structures."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0 /\n"
        f"1 '{model}' '01' .02 .2 -.2 .1 .2 100 .05 5 -5 .1 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('model', ('EXAC4', 'ESAC4A'))
@pytest.mark.parametrize('constants', ('.02 .2 -.2 .1 .2 100 .05 5 -5 .1', '0 .2 -.2 0 0 100 0 5 -5 .1'))
@pytest.mark.parametrize('use_runtime', (False, True))
def test_alternator_rectifier_connected_equilibrium(model: str, constants: str, use_runtime: bool) -> None:
    """Live field current, compensated sensing, stabilizer bias and limiter gates coexist."""
    # A high-value gate cannot initialize at the requested forcing if its lower
    # excitation demand already exceeds that operating point.
    controller: str = (f"1 '{model}' '01' {constants} /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /\n"
        "1 'IEEEVC' '01' 0 .05 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENROU',
        '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 0 0', controller, use_runtime)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('saturation', ('0 0', '.09 .38'))
def test_saturated_salient_versioned_binding(revision: int, saturation: str) -> None:
    """The twelve-constant salient layout selects five genuine differential states."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr(f"1 'GENSAE' '01' 8 .03 .05 4 2 1.8 1.7 .3 .25 .2 {saturation} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert len(grid.generators[0].rms_template.block.children[0].state_vars) == 5
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('saturation', ('0 0', '.09 .38'))
@pytest.mark.parametrize('controller', (
    "1 'IEEEX1' '01' .02 100 .05 .2 .1 5 -5 1 .5 .05 1 0 3 .1 4 .3 /",
    "1 'ESAC4A' '01' .02 .2 -.2 .1 .2 100 .05 5 -5 .1 /\n1 'IEE2ST' '01' 1 0 3 0 .01 -.01 .02 .1 5 5 .2 .05 .3 .1 .1 .05 .1 -.1 0 0 /\n1 'MNLEX3' '01' .1 1 1 .1 .001 -.2 .1 /",
))
def test_saturated_salient_connected_equilibrium(use_runtime: bool, saturation: str, controller: str) -> None:
    """Saturated load angle, direct winding and single quadrature damper balance at nonflat P/Q."""
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 '+saturation, controller, use_runtime)


@pytest.mark.parametrize('model,constants', (
    ('GENROU', '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38'),
    ('GENROE', '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38'),
    ('GENSAE', '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38'),
))
@pytest.mark.parametrize('operating_power', ((0.0, 0.0), (0.0, .05), (.2, 0.0)))
@pytest.mark.parametrize('use_runtime', (False, True))
def test_saturated_machine_zero_component_initialization(model: str, constants: str,
                                                         operating_power: tuple[float, float], use_runtime: bool) -> None:
    """Zero stator current has a valid saturated rotor equilibrium without a current-phase logarithm."""
    test_adapter_initializes_at_a_real_power_flow_equilibrium(model, constants,
        "1 'IEEET1' '01' .02 100 .05 5 -5 1 .5 .05 1 0 3 .1 4 .3 /", use_runtime, operating_power)


@pytest.mark.parametrize('model', ('EXAC1', 'EXAC1A', 'ESAC1A'))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
def test_ac_exciter_distinct_feedback_measurement(model: str, frequency: float) -> None:
    """Identical forward paths have different closed-loop gain when the rate sensor changes."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response
    downstream_limits: str = ' 5 -5' if model == 'ESAC1A' else ''
    document: RawDyr = parse_dyr(f"1 '{model}' '01' .03 .2 .2 4 .07 5 -5 .5 .06 .8 0 0 2 2 .1 3 .3{downstream_limits} /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding(model),VarFactory(),'feedback',.5).block
    values: dict[int,float] = initialized_values(block)
    if model == 'ESAC1A':
        values[block.in_vars[1].uid] = 10
        values[block.in_vars[5].uid] = 0
    else:
        pass
    # Select sensed voltage as the perturbed input while retaining the native
    # field-current and limiter ports at their independent steady values.
    block.in_vars[0], block.in_vars[3] = block.in_vars[3], block.in_vars[0]
    s: complex = 2j*np.pi*frequency
    amplifier: complex = 4/(1+.07*s)
    field: complex = 1/(2+.5*s)
    feedback: complex = .06*s/(1+.8*s)
    expected: complex = -amplifier*field/((1+amplifier*field*feedback*(1 if model == 'EXAC1A' else 2))*(1+.03*s))
    assert linearized_response(block,values,1.0,frequency) == pytest.approx(expected,rel=1e-7,abs=1e-8)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_rectified_field_feedback_versioned_binding(revision: int) -> None:
    """The modified feedback source uses its own reviewed binding through each versioned document."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'EXAC1A' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 1 2 .1 3 .3 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('model,constants', (
    ('GENROU', '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38'),
    ('GENSAE', '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38'),
))
def test_rectified_field_feedback_connected_equilibrium(use_runtime: bool, model: str, constants: str) -> None:
    """Rectified-voltage feedback starts at the host field voltage with live current loading and biases."""
    controller: str = ("1 'EXAC1A' '01' .02 1 1 200 .02 5 -5 .5 .05 1 .1 .1 2 2 .1 3 .3 /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium(model, constants, controller, use_runtime)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_gated_brushless_versioned_binding(revision: int) -> None:
    """Nineteen constants preserve distinct amplifier and downstream forcing bounds."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'ESAC1A' '01' .02 1 1 200 .02 8 -8 .5 .05 1 .1 .1 1 2 .1 3 .3 5 -5 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    block: Block = grid.generators[0].rms_template.block.children[-1]
    values: dict[str,float] = event_values(block)
    assert values['avr_VrMaxPu_'+block.name] == 8
    assert values['BridgeVRMAX_'+block.name] == 5
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('limiter', ('', "\n1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /"))
def test_gated_brushless_connected_equilibrium(use_runtime: bool, limiter: str) -> None:
    """Absent gates bypass live demand; an explicit limiter retains its downstream location."""
    controller: str = ("1 'ESAC1A' '01' .02 1 1 200 .02 8 -8 .5 .05 1 .1 .1 2 2 .1 3 .3 5 -5 /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /"+limiter)
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', controller, use_runtime)


@pytest.mark.parametrize('amplifier,uel,oel,forcing', (
    (4.0, 0.0, 10.0, 3.0), (.5, 2.0, 10.0, 2.0), (4.0, 2.0, 2.5, 2.5),
    (.5, 4.0, 2.0, 2.0), (-4.0, -10.0, 10.0, -3.0),
))
def test_brushless_gate_order_and_separate_limits(amplifier: float, uel: float, oel: float, forcing: float) -> None:
    """Capability gates and downstream clips do not replace the amplifier state bounds."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    document: RawDyr = parse_dyr("1 'ESAC1A' '01' .02 1 1 20 .1 10 -10 .5 .05 1 0 0 1 2 .1 3 .3 3 -3 /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding('ESAC1A'),VarFactory(),'gates',.5).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = oel
    values[block.in_vars[5].uid] = uel
    states: np.ndarray = np.asarray([amplifier if variable.name == 'avr_limitedFirstOrder_I_y_gates'
        else values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert output == pytest.approx(1.0)
    assert derivative[0] == pytest.approx((forcing-1.0)/.5)


@pytest.mark.parametrize('model', ('EXAC1', 'EXAC1A', 'ESAC1A'))
@pytest.mark.parametrize('use_runtime', (False, True))
def test_brushless_disabled_saturation(model: str, use_runtime: bool) -> None:
    """Two zero saturation factors select a finite linear field circuit even with zero sample voltages."""
    downstream_limits: str = ' 5 -5' if model == 'ESAC1A' else ''
    controller: str = f"1 '{model}' '01' .02 1 1 200 .02 8 -8 .5 .05 1 .1 .1 2 0 0 0 0{downstream_limits} /"
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 0 0', controller, use_runtime)


@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('inner_gain,direct_feedback', ((1.0, 0.0), (3.0, .2), (20.0, .2)))
def test_high_response_brushless_transfer(frequency: float, inner_gain: float, direct_feedback: float) -> None:
    """The independently derived closed-loop response includes proportional and rate field feedback."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response
    document: RawDyr = parse_dyr(f"1 'EXAC2' '01' .03 .2 .2 4 .07 8 -8 {inner_gain} 5 -5 .5 1 {direct_feedback} .06 .8 0 0 2 10 2 .1 3 .3 /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding('EXAC2'),VarFactory(),'inner',.5).block
    values: dict[int,float] = initialized_values(block)
    block.in_vars[0], block.in_vars[3] = block.in_vars[3], block.in_vars[0]
    s: complex = 2j*np.pi*frequency
    amplifier: complex = 4/(1+.07*s)
    field: complex = 1/(2+.5*s)
    rate: complex = .06*s/(1+.8*s)
    expected: complex = -inner_gain*amplifier*field/(
        (1+inner_gain*field*2*(direct_feedback+amplifier*rate))*(1+.03*s))
    assert linearized_response(block,values,1.0,frequency) == pytest.approx(expected,rel=1e-7,abs=1e-8)


@pytest.mark.parametrize('amplifier,field,forcing', (
    (4.0, 1.0, 5.0), (.5, 1.0, .9), (4.0, 1.8, 1.2),
    (4.0, 3.0, -5.0), (-4.0, 1.0, -5.0),
))
def test_high_response_brushless_current_override(amplifier: float, field: float, forcing: float) -> None:
    """The finite-gain current override precedes high gain and independent forcing clipping."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    document: RawDyr = parse_dyr("1 'EXAC2' '01' .03 1 1 20 .1 10 -10 3 5 -5 .5 2 .2 .05 1 0 0 1 2 0 0 0 0 /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding('EXAC2'),VarFactory(),'override',.5).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([field if variable.name == 'avr_integrator_y_override' else
        (amplifier if variable.name == 'avr_limitedFirstOrder_I_y_override' else values[variable.uid])
        for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert output == pytest.approx(field)
    assert derivative[0] == pytest.approx((forcing-field)/.5)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_high_response_brushless_versioned_binding(revision: int) -> None:
    """All twenty-three constants remain named through the concrete source-version document."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'EXAC2' '01' .02 1 1 200 .02 8 -8 10 5 -5 .5 1 .2 .05 1 .1 .1 1 10 2 .1 3 .3 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('machine,constants', (
    ('GENROU', '8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38'),
    ('GENSAE', '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38'),
))
def test_high_response_brushless_connected_equilibrium(use_runtime: bool, machine: str, constants: str) -> None:
    """Inner-loop amplifier initialization agrees with saturated hosts and additive controls."""
    controller: str = ("1 'EXAC2' '01' .02 1 1 200 .02 8 -8 10 5 -5 .5 1 .2 .05 1 .1 .1 2 10 2 .1 3 .3 /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium(machine, constants, controller, use_runtime)


@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('supply_gain', (.5, 1.6))
@pytest.mark.parametrize('knee,rate_gain', ((2.0, .06), (.5, .2)))
def test_self_excited_brushless_transfer(frequency: float, supply_gain: float, knee: float, rate_gain: float) -> None:
    """Self-excitation cancels the steady resistive pole and uses the local nonlinear feedback slope."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response
    document: RawDyr = parse_dyr(f"1 'EXAC3' '01' .03 .2 .2 4 .07 10 -10 .5 .1 {supply_gain} .06 .8 .2 {knee} 0 0 2 .2 0 0 0 0 /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding('EXAC3'),VarFactory(),'self_excited',.5).block
    values: dict[int,float] = initialized_values(block)
    block.in_vars[0], block.in_vars[3] = block.in_vars[3], block.in_vars[0]
    s: complex = 2j*np.pi*frequency
    amplifier: complex = 4/(1+.07*s)
    field: complex = supply_gain/(.5*s)
    feedback: complex = rate_gain*s/(1+.8*s)
    expected: complex = -amplifier*field/((1+amplifier*field*feedback)*(1+.03*s))
    assert linearized_response(block,values,1.0,frequency) == pytest.approx(expected,rel=1e-7,abs=1e-8)


@pytest.mark.parametrize('field,expected_amplifier_rate', ((.2, 80.0), (1.2, -20.0)))
def test_self_excited_minimum_voltage_gate(field: float, expected_amplifier_rate: float) -> None:
    """The minimum-voltage demand overrides phase output before amplifier gain and lag."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    document: RawDyr = parse_dyr("1 'EXAC3' '01' .03 1 1 20 .1 10 -10 .5 .5 1 .05 1 .2 2 0 0 1 1 0 0 0 0 /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding('EXAC3'),VarFactory(),'minimum',.5).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = 0
    states: np.ndarray = np.asarray([field if variable.name == 'avr_integrator_y_minimum' else
        (0 if variable.name == 'avr_limitedFirstOrder_I_y_minimum' else values[variable.uid])
        for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.0)
    amplifier_index: int = next(index for index, variable in enumerate(block.state_vars)
                               if variable.name == 'avr_limitedFirstOrder_I_y_minimum')
    assert derivative[amplifier_index] == pytest.approx(expected_amplifier_rate)


def test_self_excited_supply_uses_rectified_voltage() -> None:
    """Nonzero commutation distinguishes the regulator's supply from internal alternator voltage."""
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    document: RawDyr = parse_dyr("1 'EXAC3' '01' .03 1 1 20 .1 10 -10 .5 .1 1.6 .05 1 .2 2 .2 .1 1 .2 0 0 0 0 /", version=35)
    block: Block = build_controller(document.records[0],dynamic_binding('EXAC3'),VarFactory(),'supply',.5).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([1 if variable.name == 'avr_integrator_y_supply' else
        (2 if variable.name == 'avr_limitedFirstOrder_I_y_supply' else values[variable.uid])
        for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.0)
    coefficient: float = next(values[variable.uid] for variable in block.event_dict if variable.name == 'avr_A1_supply')
    expected_output: float = 1-coefficient*.2
    assert output == pytest.approx(expected_output)
    assert derivative[0] == pytest.approx((1.6*expected_output*2-1.1)/.5)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_self_excited_brushless_versioned_binding(revision: int) -> None:
    """The twenty-two-constant self-excited layout remains distinct from other brushless records."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'EXAC3' '01' .02 1 1 200 .02 8 -8 .5 .1 1 .05 1 .2 2 .1 .1 1 .2 2 .1 3 .3 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('knee', (.5, 2.0))
def test_self_excited_brushless_connected_equilibrium(use_runtime: bool, knee: float) -> None:
    """Self-excited power and both nonlinear feedback segments initialize with a saturated host."""
    controller: str = (f"1 'EXAC3' '01' .02 1 1 200 .02 8 -8 .5 .1 1 .05 1 .2 {knee} .1 .1 2 .2 2 .1 3 .3 /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', controller, use_runtime)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('constants', (
    '20 .05 5 -5 1 .5 .1 1 0 2 .1 3 .3',
    '20 0 5 -5 1 .5 .1 1 0 0 0 3 0',
    '20 .05 0 0 0 .5 .1 1 0 2 .1 3 .3',
))
def test_external_field_limit_versioned_binding(revision: int, constants: str) -> None:
    """The thirteen-constant layout has no sensing/phase time fields and shares its ceiling with saturation."""
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        f"1 'IEET1A' '01' {constants} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('constants', (
    '20 .05 5 -5 1 .5 .1 1 0 2 .1 3 .3',
    '20 0 5 -5 1 .5 .1 1 0 0 0 3 0',
    '20 .05 0 0 0 .5 .1 1 0 2 .1 3 .3',
))
def test_external_field_limit_connected_equilibrium(use_runtime: bool, constants: str) -> None:
    """Internal and delivered field values agree at a valid host point, including calibrated and zero-TA variants."""
    controller: str = (f"1 'IEET1A' '01' {constants} /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', controller, use_runtime)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('controller', (
    "IEEET4' '01' .01 2 .05 5 -5 .5 1 2 .1 3 .3",
    "IEEET5' '01' 2 .05 5 -5 .5 1 2 .1 3 .3",
    "IEEEX4' '01' .02 2 .05 5 -5 .5 1 2 .1 3 .3",
    "IEEEX4' '01' 0 2 .05 0 0 .5 0 2 .1 3 .3",
    "IEET5A' '01' 20 2 .05 5 -5 .5 1 2 .1 3 .3 8 0",
    "IEET5A' '01' 20 0 .05 0 0 .5 0 2 .1 3 .3 8 0",
))
def test_electromechanical_versioned_binding(revision: int, controller: str) -> None:
    """Explicit layouts support documented calibration and structural zero-time cases.

    :param revision: Explicit source parser profile.
    :param controller: Exact model identifier, machine identity and CON layout.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        f"1 '{controller} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('controller', (
    "IEEET4' '01' .01 2 .05 5 -5 .5 1 2 .1 3 .3",
    "IEEET5' '01' 2 .05 0 0 .5 0 2 .1 3 .3",
    "IEEEX4' '01' .02 2 .05 5 -5 .5 1 2 .1 3 .3",
    "IEET5A' '01' 20 2 .05 5 -5 .5 1 2 .1 3 .3 8 0",
    "IEET5A' '01' 20 0 .05 0 0 .5 0 2 .1 3 .3 8 0",
))
def test_electromechanical_connected_equilibrium(use_runtime: bool, controller: str) -> None:
    """Independent reset paths initialize with a saturated host, biased stabilizer and minimum-excitation limiter.

    :param use_runtime: Materialize the attached runtime instead of the stored graph.
    :param controller: Exact controller model and constants.
    """
    records: str = (f"1 '{controller} /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', records, use_runtime)


def test_zero_deadband_relay_is_not_silently_substituted() -> None:
    """An unreviewed special-case interpretation remains inspectable and blocks partial activation."""
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'IEEET4' '01' 0 2 .05 5 -5 .5 1 2 .1 3 .3 /", version=case.REV))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is None
    assert any(entry.status != PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('controller', (
    "ESAC2A' '01' .02 1 1 200 .02 8 -8 10 5 -5 .5 10 .2 .05 1 .1 .1 1 2 .1 3 .3",
    "ESAC3A' '01' .02 1 1 200 .02 8 -8 .5 0 1 .05 1 .2 2 .1 .1 1 10 2 .1 3 .3",
))
def test_takeover_brushless_versioned_binding(revision: int, controller: str) -> None:
    """Independent twenty-two-constant layouts retain current ceilings and gate locations.

    :param revision: Explicit source parser profile.
    :param controller: Exact source identifier, identity and constants.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        f"1 '{controller} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('with_limiter', (False, True))
@pytest.mark.parametrize('controller', (
    "ESAC2A' '01' .02 1 1 200 .02 8 -8 10 5 -5 .5 10 .2 .05 1 .1 .1 1 2 .1 3 .3",
    "ESAC3A' '01' .02 1 1 200 .02 8 -8 .5 .1 1 .05 1 .2 2 .1 .1 1 10 2 .1 3 .3",
))
def test_takeover_brushless_connected_equilibrium(use_runtime: bool, with_limiter: bool, controller: str) -> None:
    """Gate bypasses and active limiter connections initialize with a saturated generator and biased stabilizer.

    :param use_runtime: Materialize attached runtime instead of stored graph.
    :param with_limiter: Connect a minimum-excitation model instead of the live bypass.
    :param controller: Exact source controller and constants.
    """
    records: str = (f"1 '{controller} /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        +("1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /" if with_limiter else ''))
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', records, use_runtime)


@pytest.mark.parametrize('model', ('ESAC2A', 'ESAC3A'))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
def test_takeover_brushless_transfer(model: str, frequency: float) -> None:
    """Inner proportional feedback and self-excited power have distinct independent transfer functions.

    :param model: Explicit source model under test.
    :param frequency: Perturbation frequency in hertz.
    """
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response
    constants: str = ('.03 .2 .2 4 .07 8 -8 3 5 -5 .5 10 .2 .06 .8 0 0 2 0 0 0 0'
        if model == 'ESAC2A' else '.03 .2 .2 4 .07 8 -8 .5 0 1.5 .06 .8 .2 2 0 0 2 10 0 0 0 0')
    document: RawDyr = parse_dyr(f"1 '{model}' '01' {constants} /", version=35)
    block: Block = build_controller(document.records[0], dynamic_binding(model), VarFactory(), 'takeover', .5).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[1].uid] = 100 if model == 'ESAC2A' else 0
    values[block.in_vars[5].uid] = -100
    block.in_vars[0], block.in_vars[3] = block.in_vars[3], block.in_vars[0]
    s: complex = 2j*np.pi*frequency
    amplifier: complex = 4/(1+.07*s)
    feedback: complex = .06*s/(1+.8*s)
    expected: complex
    if model == 'ESAC2A':
        field: complex = 1/(2+.5*s)
        expected = -3*amplifier*field/((1+3*field*2*(.2+amplifier*feedback))*(1+.03*s))
    else:
        field = 1.5/(.5*s)
        expected = -amplifier*field/((1+amplifier*field*feedback)*(1+.03*s))
    assert linearized_response(block, values, 1, frequency) == pytest.approx(expected, rel=1e-7, abs=1e-8)


@pytest.mark.parametrize('model', ('ESAC2A', 'ESAC3A'))
@pytest.mark.parametrize('field_current', (1.0, 2.0))
@pytest.mark.parametrize('outward', (False, True))
def test_takeover_field_current_stop_and_recovery(model: str, field_current: float, outward: bool) -> None:
    """A live current-dependent ceiling blocks increasing field voltage and permits inward recovery.

    :param model: Explicit source model under test.
    :param field_current: Generator field current, including a moving-ceiling perturbation.
    :param outward: Demand increasing field voltage instead of inward discharge.
    """
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    constants: str = ('.03 1 1 20 .1 10 -10 3 5 -5 .5 4.25 .2 .05 1 0 .25 2 0 0 0 0'
        if model == 'ESAC2A' else '.03 1 1 20 .1 10 -10 .5 .2 1 .05 1 .2 2 0 .25 2 4.25 0 0 0 0')
    document: RawDyr = parse_dyr(f"1 '{model}' '01' {constants} /", version=35)
    block: Block = build_controller(document.records[0], dynamic_binding(model), VarFactory(), 'stop', .5).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[1].uid] = 100 if model == 'ESAC2A' else 0
    values[block.in_vars[5].uid] = -100
    states: np.ndarray = np.asarray([2 if variable.name == 'avr_integrator_y_stop' else
        ((10 if outward else 0) if variable.name == 'avr_limitedFirstOrder_I_y_stop' else values[variable.uid])
        for variable in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, field_current)
    if outward:
        assert derivative[0] == 0
    else:
        assert derivative[0] < 0
    assert output == 2


@pytest.mark.parametrize('model', ('ESAC2A', 'ESAC3A'))
def test_takeover_brushless_gate_locations(model: str) -> None:
    """Minimum-excitation demand acts in forcing units for one model and before amplifier gain for the other.

    :param model: Explicit source model under test.
    """
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    constants: str = ('.03 1 1 20 .1 10 -10 3 5 -5 .5 10 .2 .05 1 0 0 1 0 0 0 0'
        if model == 'ESAC2A' else '.03 1 1 20 .1 10 -10 .5 0 1 .05 1 .2 2 0 0 1 10 0 0 0 0')
    document: RawDyr = parse_dyr(f"1 '{model}' '01' {constants} /", version=35)
    block: Block = build_controller(document.records[0], dynamic_binding(model), VarFactory(), 'gates', .5).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[1].uid] = 100 if model == 'ESAC2A' else 0
    values[block.in_vars[5].uid] = 2
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1)
    assert output == 1
    if model == 'ESAC2A':
        assert derivative[0] == pytest.approx(2)
        assert derivative[2] == pytest.approx(0, abs=1e-12)
        values[block.in_vars[1].uid] = 1.5
        derivative, output = evaluate_controller(block, values, states, 1)
        assert derivative[0] == pytest.approx(1)
    else:
        assert derivative[0] == pytest.approx(0, abs=1e-12)
        assert derivative[2] == pytest.approx(390)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_hydraulic_pilot_governor_versioned_binding(revision: int) -> None:
    """The fourteen-constant baseline is shared by both supplied model-library snapshots.

    :param revision: Explicit parser profile.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'IEEEG3' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 1 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('controller', (
    "IEEEG3' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 .8",
    "IEEEG3D' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 .8 .001 -.002 0",
    "IEEEG3D' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 .8 .001 -.002 25",
    "IEEEG3D' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 .8 0 0 80",
))
def test_hydraulic_pilot_connected_equilibrium(use_runtime: bool, controller: str) -> None:
    """Nonunit turbine gains and turbine/machine bases initialize every hydraulic memory consistently.

    :param use_runtime: Materialize runtime instead of using stored graph.
    :param controller: Explicit source governor and constants.
    """
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', f"1 '{controller} /", use_runtime)


@pytest.mark.parametrize('system_base', (100.0, 200.0))
@pytest.mark.parametrize('rating', (0.0, 25.0, 80.0))
def test_hydraulic_governor_explicit_power_base(system_base: float, rating: float) -> None:
    """TRATE overrides the machine rating exactly once at the governor/network boundary.

    :param system_base: Network MVA base.
    :param rating: Explicit turbine MW rating, or zero to select machine MVA base.
    """
    case: PsseCircuit = make_raw_case()
    case.SBASE = system_base
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        f"1 'IEEEG3D' '01' .2 .05 .1 -.1 1.2 0 .05 .4 5 1 .5 1 1.5 1 .001 -.002 {rating} /", version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    template = grid.generators[0].rms_template
    assert template is not None
    governor: Block = template.block.children[1]
    power = governor.out_vars[0]
    scaling = next(eq for eq in template.block.algebraic_eqs if power in eq.get_vars())
    values: dict[int, float] = dict((variable.uid, 0.0) for variable in scaling.get_vars())
    values[power.uid] = 1
    expected_ratio: float = (rating if rating > 0 else 50)/system_base
    assert scaling.eval_uid(values) == pytest.approx(-expected_ratio)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_pi_brushless_versioned_binding(revision: int) -> None:
    """The supplied libraries share a twenty-one-constant PI/shaped-feedback layout.

    :param revision: Explicit parser profile under review.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'EXBAS' '01' .02 1 1 200 .02 1 1 5 0 .05 1 .1 .5 1 .5 .1 .1 2 .1 3 .3 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('proportional_gain', (0.0, 1.0))
def test_pi_brushless_connected_equilibrium(use_runtime: bool, proportional_gain: float) -> None:
    """Integral memory initializes loaded field demand while the reference cancels steady additive controllers.

    :param use_runtime: Materialize runtime instead of using the stored graph.
    :param proportional_gain: Select integral-only or PI voltage-error control.
    """
    controller: str = (f"1 'EXBAS' '01' .02 {proportional_gain} 1 200 .02 1 1 5 0 .05 1 .1 .5 2 .5 .1 .1 2 .1 3 .3 /\n"
        "1 'IEEEST' '01' 3 0 0 0 0 0 0 0 0 0 0 0 0 5 .01 .1 -.1 0 0 /\n"
        "1 'MNLEX2' '01' .1 1 1 .1 .001 0 .1 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', controller, use_runtime)


@pytest.mark.parametrize('model', ('ESAC2A', 'ESAC3A'))
def test_takeover_field_voltage_lower_stop_and_recovery(model: str) -> None:
    """A zero or nonzero lower field-voltage stop blocks discharge and releases positive forcing.

    :param model: Explicit source model with a fixed-zero or configurable lower stop.
    """
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding
    from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller
    constants: str = ('.03 1 1 20 .1 10 -10 3 5 -5 .5 4.25 .2 .05 1 0 .25 2 0 0 0 0'
        if model == 'ESAC2A' else '.03 1 1 20 .1 10 -10 .5 .2 1 .05 1 .2 2 0 .25 2 4.25 0 0 0 0')
    document: RawDyr = parse_dyr(f"1 '{model}' '01' {constants} /", version=35)
    block: Block = build_controller(document.records[0], dynamic_binding(model), VarFactory(), 'floor', .5).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[1].uid] = 100 if model == 'ESAC2A' else 0
    values[block.in_vars[5].uid] = -100
    lower: float = 0 if model == 'ESAC2A' else .2
    states: np.ndarray = np.asarray([lower if var.name == 'avr_integrator_y_floor' else
        (-10 if var.name == 'avr_limitedFirstOrder_I_y_floor' else values[var.uid]) for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[0] == 0
    assert output == lower
    states[2] = 10
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[0] > 0
    assert output == lower


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('controller', (
    "PSS2A' '01' 1 0 3 0 2 2 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .1 -.1",
    "PSS2B' '01' 1 0 3 0 4 2 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .04 .02 2 -2 2 -2 .1 -.1",
))
def test_ramp_tracking_stabilizer_versioned_binding(revision: int, controller: str) -> None:
    """All reviewed source profiles connect two selected measurements without treating orders as a third input.

    :param revision: Explicit parser profile.
    :param controller: Exact six-ICON stabilizer and constants.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'SEXS' '01' .1 1 100 .1 0 10 /\n"+f"1 '{controller} /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
    from VeraGridEngine.Utils.Symbolic.symbolic import Expr
    template: RmsModelTemplate | None = grid.generators[0].rms_template
    assert template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)
    stabilizer: Block = template.block.children[1]
    assert len(stabilizer.in_vars) == 2
    # A unit of machine-base measured power corresponds to MBASE/SBASE
    # units at the native machine's system-base electrical-power output.
    machine: Block = template.block.children[0]
    power_equation: Expr = next(eq for eq in template.block.algebraic_eqs if stabilizer.in_vars[1] in eq.get_vars())
    values: dict[int, float] = dict((var.uid, 0.0) for var in power_equation.get_vars())
    values[stabilizer.in_vars[1].uid] = 1
    values[machine.out_vars[0].uid] = .5
    assert power_equation.eval_uid(values) == pytest.approx(0)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('controller', (
    "PSS2A' '01' 1 0 3 0 2 2 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .1 -.1",
    "PSS2A' '01' 5 2 3 0 0 5 3 0 0 4 0 0 .4 .7 .1 .2 5 0 0 0 0 .1 -.1",
    "PSS2B' '01' 1 0 3 0 4 2 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .04 .02 2 -2 2 -2 .1 -.1",
    "PSS2B' '01' 5 2 3 0 0 0 3 0 0 4 0 0 .4 .7 .1 .2 5 0 0 0 0 0 0 2 -2 2 -2 .1 -.1",
))
def test_ramp_tracking_stabilizer_connected_equilibrium(use_runtime: bool, controller: str) -> None:
    """Nonzero power and remote voltage initialize washouts, including bypassed and maximum-order variants.

    :param use_runtime: Materialize the attached runtime instead of the stored graph.
    :param controller: Exact source stabilizer selector/order/settings record.
    """
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38',
        "1 'SEXS' '01' .1 1 100 .1 0 10 /\n"+f"1 '{controller} /", use_runtime)


@pytest.mark.parametrize('header', ('1 0 3 0 3 3', '2 0 3 0 1 1', '1 2 3 0 1 1', '0 0 3 0 1 1'))
def test_ramp_tracking_unreviewed_configuration_blocks_activation(header: str) -> None:
    """Excess filter order and unreviewed measurements remain explicit and cannot install a partial host.

    :param header: Invalid or unreviewed selector/remote/order combination.
    """
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'SEXS' '01' .1 1 100 .1 0 10 /\n"
        f"1 'PSS2A' '01' {header} 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .1 -.1 /", version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is None
    assert any(entry.status != PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
def test_multistage_steam_governor_versioned_binding(revision: int) -> None:
    """The single-shaft governor consumes two header fields and twenty physical constants.

    :param revision: Explicit parser profile.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('controller', (
    "IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0",
    "IEEEG1' '01' 0 0 20 0 0 .2 .1 -.1 1.2 0 0 .3 0 0 .3 0 0 .2 0 0 .2 0",
    "IEEEG1D' '01' 0 '00' 20 .1 .03 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 .001 -.002 25",
    "IEEEG1D' '01' 0 0 20 0 0 .2 .1 -.1 1.2 0 0 .3 0 0 .3 0 0 .2 0 0 .2 0 0 0 0",
))
def test_multistage_steam_connected_equilibrium(use_runtime: bool, controller: str) -> None:
    """Steam memories and mechanical power initialize with the correct turbine and network bases.

    :param use_runtime: Use the attached runtime instead of the stored graph.
    :param controller: Exact source governor, header and constants.
    """
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', f"1 '{controller} /", use_runtime)


@pytest.mark.parametrize('header,weights', (("0 '0'", '.3 .1'), ("2 '02'", '.3 0')))
def test_cross_compound_steam_is_not_summed_into_one_machine(header: str, weights: str) -> None:
    """A second shaft or target stays explicit instead of silently adding its power to the first machine.

    :param header: Source secondary bus and equipment identity.
    :param weights: First-stage first- and second-shaft fractions.
    """
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        f"1 'IEEEG1' '01' {header} 20 .1 0 .2 .1 -.1 1.2 0 .3 {weights} 5 .3 0 .5 .2 0 .1 .2 0 /", version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is None
    assert any(entry.status != PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


def test_unreviewed_cross_compound_governor_inhibits_both_named_machines() -> None:
    """Both referenced machines are blocked while another unit on the same secondary bus remains independent."""
    case: PsseCircuit = make_raw_case()
    for identity in ('02', '03'):
        raw: RawGeneratorV35 = RawGeneratorV35()
        raw.I = 2
        raw.ID = identity
        raw.MBASE = 50
        raw.ZR = .01
        raw.ZX = .2
        raw.PG = 20
        raw.QG = 5
        case.generators.append(raw)
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "2 'GENROU' '02' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "2 'GENROU' '03' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'IEEEG1' '01' 2 '02' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 /", version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    by_code: dict[str, Generator] = dict((generator.code, generator) for generator in grid.generators)
    assert by_code['1_01'].rms_template is None
    assert by_code['2_02'].rms_template is None
    assert by_code['2_03'].rms_template is not None


@pytest.mark.parametrize('revision', (33, 34, 35, 36))
@pytest.mark.parametrize('frequency_flag', (0, 1))
def test_outer_load_controller_versioned_binding(revision: int, frequency_flag: int) -> None:
    """Enabled power feedback connects to the governor rather than becoming a disconnected model.

    :param revision: Explicit parser profile.
    :param frequency_flag: Disable or enable source frequency bias.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        "1 'IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 /\n"
        f"1 'LCFB1' '01' {frequency_flag} 1 2 2 0 .1 .3 .05 .05 /", version=revision))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)
    assert len(grid.generators[0].rms_template.block.children) == 3


@pytest.mark.parametrize('use_runtime', (False, True))
@pytest.mark.parametrize('frequency_flag', (0, 1))
@pytest.mark.parametrize('gains,measurement_time', (('.3 0 5 .3 0 .5 .2 0 .1 .2 0', 2),
    ('.2 0 5 .2 0 .5 .2 0 .1 .2 0', 0)))
def test_outer_load_controller_connected_equilibrium(use_runtime: bool, frequency_flag: int,
                                                    gains: str, measurement_time: float) -> None:
    """Power setpoint and governor reference retain different loss/gain offsets at a real power-flow point.

    :param use_runtime: Use attached runtime instead of the stored graph.
    :param frequency_flag: Source frequency-bias selector.
    :param gains: Unit or nonunit total turbine fractions and downstream times.
    :param measurement_time: Positive measurement time or exact algebraic reduction.
    """
    controller: str = (f"1 'IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 {gains} /\n"
        f"1 'LCFB1' '01' {frequency_flag} 1 2 {measurement_time} 0 .1 .3 .05 .05 /")
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38', controller, use_runtime)


@pytest.mark.parametrize('records', (
    "1 'LCFB1' '01' 0 1 2 2 0 .1 .3 .05 .05 /",
    "1 'IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 /\n1 'LCFB1' '01' 0 0 2 2 0 .1 .3 .05 .05 /",
    "1 'IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 .3 0 5 .3 0 .5 .2 0 .1 .2 0 /\n1 'LCFB1' '01' 2 1 2 2 0 .1 .3 .05 .05 /",
))
def test_outer_load_controller_missing_host_or_unreviewed_flags(records: str) -> None:
    """An unsupported outer-loop combination cannot activate a partly wired generator.

    :param records: Missing governor or unreviewed flag configuration.
    """
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+records, version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    assert grid.generators[0].rms_template is None


@pytest.mark.parametrize('first_fraction', (.1, .6))
def test_outer_load_correction_reaches_governor_with_stage_gain(first_fraction: float) -> None:
    """A live outer-loop command reaches the valve-reference path with its actual nonunit steam gain.

    :param first_fraction: First turbine-stage fraction; remaining fractions sum to 0.7.
    """
    from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
    from VeraGridEngine.Utils.Symbolic.symbolic import Expr
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        f"1 'IEEEG1' '01' 0 '0' 20 .1 0 .2 .1 -.1 1.2 0 .3 {first_fraction} 0 5 .3 0 .5 .2 0 .1 .2 0 /\n"
        "1 'LCFB1' '01' 1 1 2 2 0 .1 .3 .05 .05 /", version=35))
    grid: MultiCircuit = psse_to_veragrid(case, logger=Logger())
    template: RmsModelTemplate | None = grid.generators[0].rms_template
    assert template is not None
    load: Block = template.block.children[1]
    governor: Block = template.block.children[2]
    coupling: Expr = next(equation for equation in template.block.algebraic_eqs
                          if governor.in_vars[2] in equation.get_vars())
    values: dict[int, float] = dict((variable.uid, 0.0) for variable in coupling.get_vars())
    values[governor.in_vars[2].uid] = first_fraction + .7
    values[load.out_vars[0].uid] = 1.0
    assert coupling.eval_uid(values) == pytest.approx(0.0)
    # A changed outer-loop command must alter the governor equation immediately.
    values[load.out_vars[0].uid] = 2.0
    assert abs(coupling.eval_uid(values)) == pytest.approx(first_fraction + .7)


def fuel_governor_record(model: str, selector: int = 1, flag: int = 0,
                         rating: float = 0., integral: float = 2.) -> str:
    """Provide a documented fuel-governor record with active load limiting and disabled acceleration/delay.

    :param model: Exact direct source identifier.
    :param selector: Signed droop-measurement selector.
    :param flag: Fuel-flow characteristic.
    :param rating: Turbine MW rating, zero selecting machine MVA.
    :param integral: Speed-controller integral gain.
    :return: One complete slash-terminated assignment.
    """
    deadbands: str = ' .001 -.002' if model == 'GGOV1D' else ''
    return (f"1 '{model}' '01' {selector} {flag} .05 .1 .1 -.1 10 {integral} .1 .1 1 0 .2 1.2 .1 "
        f".5 .02 0 3 1 1 1 .1 .1 -.1 .01 .01 0 0 {rating} 0 .02 1 .04 -.03{deadbands} /")


@pytest.mark.parametrize('revision', (33,34,35,36))
@pytest.mark.parametrize('selector', (-2,-1,0,1))
@pytest.mark.parametrize('flag', (0,1))
def test_tracked_fuel_governor_versioned_binding(revision: int, selector: int, flag: int) -> None:
    """Signed droop selectors preserve explicit physical feedback choices in every reviewed parser profile.

    :param revision: Explicit source grammar profile.
    :param selector: Droop feedback code, including negative selector values.
    :param flag: Fuel-flow characteristic.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = revision
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        +fuel_governor_record('GGOV1',selector,flag),version=revision))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert all(entry.status == PsseConversionStatus.CONVERTED for entry in case.conversion_report.entries)


@pytest.mark.parametrize('use_runtime', (False,True))
@pytest.mark.parametrize('model', ('GGOV1','GGOV1D'))
@pytest.mark.parametrize('rating,integral', ((0.,2.),(75.,0.)))
@pytest.mark.parametrize('selector,flag', ((1,0),(-1,1),(-2,1),(0,0)))
def test_tracked_fuel_governor_connected_equilibrium(use_runtime: bool, model: str,
        rating: float, integral: float, selector: int, flag: int) -> None:
    """Loss-adjusted fuel/reference memories and the electrical reset setpoint initialize on the declared base.

    :param use_runtime: Check the duplicated runtime rather than stored graph.
    :param model: Direct source governor identifier.
    :param rating: Turbine power base or zero for machine MVA.
    :param integral: Positive or zero speed-integral gain.
    :param selector: Physical droop feedback choice.
    :param flag: Fuel-flow characteristic.
    """
    test_adapter_initializes_at_a_real_power_flow_equilibrium('GENSAE',
        '8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38',
        fuel_governor_record(model,selector,flag,rating,integral),use_runtime)


@pytest.mark.parametrize('position,value', ((0,'2'),(1,'2'),(17,'.1'),(27,'.1'),(29,'-1'),(19,'0'),(34,'0')))
def test_unreviewed_fuel_governor_options_block_activation(position: int, value: str) -> None:
    """Unreviewed modes, delay, acceleration and invalid load settings cannot install a partial host.

    :param position: Payload token index after the model/equipment prefix.
    :param value: Invalid or unsupported replacement token.
    """
    case: PsseCircuit = make_raw_case()
    tokens: list[str] = fuel_governor_record('GGOV1').split()
    tokens[3+position] = value
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
        +' '.join(tokens),version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
