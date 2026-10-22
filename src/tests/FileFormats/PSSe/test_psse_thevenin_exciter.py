# SPDX-License-Identifier: MPL-2.0
"""Distinct classical compound-transformer source layouts, calibration restrictions and machine integration."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('model',('IEEET3','IEEEX3'))
@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('runtime',(False,True))
def test_thevenin_source_layout_and_actual_equilibrium(model: str, version: int, runtime: bool) -> None:
    """Both explicit twelve-CON identities initialize actual transformer loading, field forcing and stator-current bases.

    :param model: Exact source capability-placement identity.
    :param version: Concrete parser profile.
    :param runtime: Inspect runtime duplication or stored graph.
    """
    source: str = f"1 '{model}' '01' .02 20 .05 5 -5 .5 .05 1 1 .5 4 1 /"
    record: DyrRecord = parse_dyr(source,version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert tuple(parameter.name for parameter in record.parameters) == ('TR','KA','TA','VRMAX','VRMIN','TE','KF','TF','KP','KI','VBMAX','KE')
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime,version=version)


@pytest.mark.parametrize('model',('IEEET3','IEEEX3'))
def test_thevenin_source_auxiliary_connections(model: str) -> None:
    """A live stabilizer and minimum-excitation signal connect additively without corrupting initial field balance.

    :param model: Exact source identity.
    """
    source: str = f"1 '{model}' '01' .02 20 .05 5 -5 .5 .05 1 1 .5 4 1 /\n"+"1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,False)


@pytest.mark.parametrize('model',('IEEET3','IEEEX3'))
def test_thevenin_automatic_current_gain_is_not_silently_zeroed(model: str) -> None:
    """The source zero selector requests a design calibration rather than a physical zero current-compounding gain.

    :param model: Exact source model identity.
    """
    record: DyrRecord = parse_dyr(f"1 '{model}' '01' .02 20 .05 5 -5 .5 .05 1 1 0 4 1 /",version=35).records[0]
    with pytest.raises(ValueError,match='calibration has not been reviewed'):
        validate_dynamic_parameters(record)
