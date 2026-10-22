# SPDX-License-Identifier: MPL-2.0
"""Rheostat excitation contracts and actual machine initialization."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('version',(33,34,35,36))
def test_rheostat_exciter_layout(version: int) -> None:
    """Matching supplied early/modern sheets share twelve ordered physical constants.

    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr("1 'DC3A' '01' .02 .05 5 -5 2 .5 1 0 3 .1 4 .3 /",version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert tuple(parameter.name for parameter in record.parameters) == ('TR','KV','VRMAX','VRMIN','TRH','TE','KE','VEMIN','E1','SE1','E2','SE2')


@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('sensing_time',(0.,.02))
def test_rheostat_exciter_host_equilibrium(runtime: bool, sensing_time: float) -> None:
    """Actual host field losses and auxiliary biases initialize both dynamic sensing variants.

    :param runtime: Stored graph or duplicated runtime assembly.
    :param sensing_time: Algebraic or positive measurement lag.
    """
    source: str = f"1 'DC3A' '01' {sensing_time} .05 5 -5 2 .5 1 0 3 .1 4 .3 /\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)
