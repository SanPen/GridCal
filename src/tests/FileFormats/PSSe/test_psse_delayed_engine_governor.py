# SPDX-License-Identifier: MPL-2.0
"""Version-owned diesel governor records and real-machine torque initialization."""
from __future__ import annotations

import pytest
import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import RmsInitializationMethod, RmsProblemTypes
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case, test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def engine_record(model: str, feedback: int = 0) -> str:
    """Build an explicit direct assignment including the modern/legacy common selector.

    :param model: Reviewed engine governor name.
    :param feedback: Throttle or measured electrical power.
    :return: Complete source assignment.
    """
    selector: str = str(feedback)+' ' if model != 'DEGOV' else ''
    extra: str = ' .05 .1' if model != 'DEGOV' else ''
    extra += ' .001 -.002 80' if model == 'DEGOV1D' else ''
    return f"1 '{model}' '01' {selector}.01 .02 .2 20 .25 .009 .0384 .01 1.1 0{extra} /"


@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('model',('DEGOV','DEGOV1'))
def test_engine_release_contract(version: int, model: str) -> None:
    """Supplied early and modern sheets agree on ordered constants and ICON placement.

    :param version: Explicit parser profile.
    :param model: Reviewed source identifier.
    """
    record: DyrRecord = parse_dyr(engine_record(model),version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert len(record.parameters) == (12 if model != 'DEGOV' else 10)
    assert record.icons == ((0,) if model != 'DEGOV' else ())


@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('model,feedback',(('DEGOV',0),('DEGOV1',0),('DEGOV1',1),('DEGOV1D',0),('DEGOV1D',1)))
def test_engine_machine_torque_equilibrium(runtime: bool, model: str, feedback: int) -> None:
    """Machine losses preserve distinct electrical-feedback and mechanical-torque seeds.

    :param runtime: Original or materialized graph.
    :param model: Isochronous or droop source assignment.
    :param feedback: Physical droop measurement.
    """
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',
        engine_record(model,feedback),runtime)


@pytest.mark.parametrize('version',(33,34,35,36))
def test_engine_deadband_release_grammar(version: int) -> None:
    """The direct modern assignment never replaces the older user-subroutine contract.

    :param version: Explicit parser release.
    """
    direct: DyrRecord = parse_dyr(engine_record('DEGOV1D'),version=version).records[0]
    if version < 35:
        assert direct.parameters == ()
    else:
        assert direct.status == RecordStatus.VALID and len(direct.parameters) == 15
    legacy: str = "1 'USRMDL' '01' 'DEGOV1DU' 5 0 1 15 6 15 1 .01 .02 .2 20 .25 .009 .0384 .01 1.1 0 .05 .1 .001 -.002 80 /"
    wrapped: DyrRecord = parse_dyr(legacy,version=version).records[0]
    if version == 33:
        assert wrapped.status == RecordStatus.VALID and len(wrapped.parameters) == 15
        assert wrapped.icons == (1,)
    else:
        assert wrapped.parameters == () and wrapped.user_schema is None


@pytest.mark.parametrize('runtime',(False,True))
def test_engine_legacy_turbine_base_equilibrium(runtime: bool) -> None:
    """A distinct turbine rating scales both feedback and torque in the actual wrapper assembly.

    :param runtime: Stored or materialized symbolic graph.
    """
    source: str = "1 'USRMDL' '01' 'DEGOV1DU' 5 0 1 15 6 15 1 .01 .02 .2 20 .25 .009 .0384 .01 1.1 0 .05 .1 .001 -.002 80 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=33)


def test_governor_runs_in_vectorized_rms_driver(governor_source: str | None = None) -> None:
    """A loaded network keeps actual power through compiled governor startup.

    :param governor_source: Optional explicit assignment reused by other reviewed governor-family checks.
    """
    case: PsseCircuit = make_raw_case()
    source: str = engine_record('DEGOV1',1) if governor_source is None else governor_source
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+
        source,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    grid.add_rms_events_group(gce.RmsEventsGroup(name='baseline'))
    grid.add_load(grid.buses[1],gce.Load(name='load',P=10.,Q=2.))
    initialize_bus_rms(grid.buses[1],vf=grid.var_factory)
    set_rms_model(grid.lines[0],get_line_rms_template(grid.var_factory).block,grid.var_factory)
    set_rms_model(grid.loads[0],get_load_rms_template(grid.var_factory).block,grid.var_factory)
    power_flow: gce.PowerFlowResults = gce.power_flow(grid,gce.PowerFlowOptions())
    assert power_flow.converged
    driver: RmsSimulationDriver = RmsSimulationDriver(grid,gce.RmsOptions(time_step=.001,simulation_time=.03,
        initialization_method=RmsInitializationMethod.Explicit,problem_type=RmsProblemTypes.PowerBalanceVectorized,
        verbose=0),pf_results=power_flow)
    driver.run()
    assert driver.logger.error_count() == 0
    governor: Block = grid.generators[0].rms_model.children[-1]
    power: np.ndarray = driver.results.get_vars_data([governor.out_vars[0]])[:,0]
    assert power.size == 31 and np.all(np.isfinite(power))
    assert .2 < power[0] < .22
    np.testing.assert_allclose(power,power[0],atol=1e-7,rtol=0.)


@pytest.mark.parametrize('bad_record',(
    "1 'DEGOV1' '01' 2 .01 .02 .2 20 .25 .009 .0384 .01 1.1 0 .05 .1 /",
    "1 'DEGOV1' '01' 0 .01 .02 .2 20 .25 .009 .0384 0 1.1 0 .05 .1 /",
    "1 'DEGOV1' '01' 1 .01 .02 .2 20 .25 .009 .0384 .01 1.1 0 .05 -.1 /",
    "1 'DEGOV1D' '01' 1 .01 .02 .2 20 .25 .009 .0384 .01 1.1 0 .05 .1 .001 -.002 -80 /",
))
def test_engine_invalid_source_does_not_activate_partial_machine(bad_record: str) -> None:
    """Invalid selectors, delay, sensing and rating retain the source while blocking the assembly.

    :param bad_record: Source assignment outside the reviewed parameter domain.
    """
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+
        bad_record,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
    assert len(case.conversion_report.entries) == 2
