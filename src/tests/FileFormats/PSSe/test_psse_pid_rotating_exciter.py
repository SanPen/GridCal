# SPDX-License-Identifier: MPL-2.0
"""Reviewed PID rotating-exciter source contract and machine operating-point integration."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('ki',(0.,2.))
@pytest.mark.parametrize('runtime',(False,True))
def test_pid_exciter_release_layout_and_machine_equilibrium(version: int, ki: float, runtime: bool) -> None:
    """Every reviewed profile preserves the ordered fifteen constants and actual initial machine field forcing.

    :param version: Parser release profile.
    :param ki: Integral gain, including proportional-only initialization.
    :param runtime: Validate duplicated runtime equations or persisted graph.
    """
    source: str = f"1 'ESAC8B' '01' .03 4 {ki} .3 .12 3 .08 8 -8 .7 1.4 .8 .1 1.2 .4 /"
    record: DyrRecord = parse_dyr(source,version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert tuple(parameter.name for parameter in record.parameters) == ('TR','KP','KI','KD','TD','KA','TA','VRMAX','VRMIN','TE','KE','E1','SE1','E2','SE2')
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime,version=version)


@pytest.mark.parametrize('ke,vrmax',((0.,8.),(1.4,0.)))
def test_pid_unreviewed_automatic_calibration_is_rejected(ke: float, vrmax: float) -> None:
    """Source zero selectors never silently become physical zero resistance or capability.

    :param ke: Explicit field coefficient or source calibration selector.
    :param vrmax: Explicit capability or source calibration selector.
    """
    from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding, PsseDynamicBinding
    from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
    source: str = f"1 'ESAC8B' '01' .03 4 2 .3 .12 3 .08 {vrmax} -8 .7 {ke} .8 .1 1.2 .4 /"
    record: DyrRecord = parse_dyr(source,version=35).records[0]
    binding: PsseDynamicBinding | None = dynamic_binding('ESAC8B')
    assert binding is not None
    with pytest.raises(ValueError,match='calibration has not been reviewed'):
        build_controller(record,binding,VarFactory(),'pid',.5)
