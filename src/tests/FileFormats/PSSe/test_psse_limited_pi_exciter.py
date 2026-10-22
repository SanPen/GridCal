# SPDX-License-Identifier: MPL-2.0
"""Explicitly reversed actuator/exciter source ordering across supplied releases."""
from __future__ import annotations

import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding, PsseDynamicBinding
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('version',(33,34,35,36))
def test_limited_pi_release_order_is_explicit(version: int) -> None:
    """Known releases preserve different TA/TE positions; an unverified intermediate release stays unsupported.

    :param version: Concrete source release profile.
    """
    times: str = '.1 .4' if version == 33 else '.4 .1'
    record: DyrRecord = parse_dyr("1 'BUDCZT' '01' 5 2 1.5 .02 1 "+times+' 5 -5 5 -5 /',version=version).records[0]
    if version == 34:
        assert record.status == RecordStatus.UNSUPPORTED
        assert not record.parameters
    else:
        assert record.status == RecordStatus.VALID
        assert tuple(parameter.name for parameter in record.parameters)[5:7] == (('TA','TE') if version == 33 else ('TE','TA'))
        binding: PsseDynamicBinding | None = dynamic_binding('BUDCZT')
        assert binding is not None
        block: Block = build_controller(record,binding,VarFactory(),'pi',1.).block
        values: dict[int,float] = initialized_values(block)
        ta: float = next(values[var.uid] for var in block.event_dict if var.name == 'TA_pi')
        te: float = next(values[var.uid] for var in block.event_dict if var.name == 'TE_pi')
        assert ta == .1 and te == .4


@pytest.mark.parametrize('version',(33,35,36))
@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('auxiliary',(False,True))
def test_limited_pi_machine_and_auxiliary_equilibrium(version: int, runtime: bool, auxiliary: bool) -> None:
    """Both release layouts initialize stored/runtime equations from the actual host field and auxiliary signals.

    :param version: Reviewed source profile.
    :param runtime: Inspect duplicated runtime or stored graph.
    :param auxiliary: Connect a stabilizer and minimum-excitation limiter.
    """
    times: str = '.1 .4' if version == 33 else '.4 .1'
    source: str = "1 'BUDCZT' '01' 5 2 1.5 .02 1 "+times+' 5 -5 5 -5 /'
    if auxiliary:
        source += "\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    else:
        pass
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime,version=version)
