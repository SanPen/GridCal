# SPDX-License-Identifier: MPL-2.0
"""Compiled loaded-network execution of reviewed compound excitation controllers."""
from __future__ import annotations
import numpy as np
import pytest
import VeraGridEngine.api as gce
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import RmsInitializationMethod, RmsProblemTypes, InternationalStandardModel
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case
from tests.FileFormats.PSSe.test_psse_selectable_cascaded_brushless import selectable_cascaded_record
from tests.FileFormats.PSSe.test_psse_cascaded_brushless_exciter import cascaded_brushless_record
from tests.FileFormats.PSSe.test_psse_compound_commutator_exciter import compound_commutator_record
from tests.FileFormats.PSSe.test_psse_current_limited_field_exciter import current_limited_field_record


@pytest.mark.parametrize('model,self_excited',((InternationalStandardModel.DC4C,False),(InternationalStandardModel.ST6C,False),
    (InternationalStandardModel.AC7B,False),(InternationalStandardModel.AC7C,False),(InternationalStandardModel.AC7C,True)))
def test_loaded_compound_exciter_runs_vectorized(model: InternationalStandardModel, self_excited: bool) -> None:
    """A real power-flow initialized network retains its field through compiled RMS execution.

    :param model: Reviewed excitation controller.
    :param self_excited: Select delivered-field power for the modern cascaded controller.
    """
    case: PsseCircuit = make_raw_case()
    source: str
    if model == InternationalStandardModel.DC4C:
        source = compound_commutator_record(source=1)
    elif model == InternationalStandardModel.ST6C:
        source = current_limited_field_record(source=1)
    elif model == InternationalStandardModel.AC7B:
        source = cascaded_brushless_record()
    else:
        source = selectable_cascaded_record(power_supply=2 if self_excited else 1)
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+source,version=35))
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
    exciter: Block = grid.generators[0].rms_model.children[-1]
    field: np.ndarray = driver.results.get_vars_data([exciter.out_vars[0]])[:,0]
    assert field.size == 31 and np.all(np.isfinite(field)) and field[0] > 0.
    np.testing.assert_allclose(field,field[0],atol=1e-7,rtol=0.)
