# SPDX-License-Identifier: MPL-2.0
"""Release-owned static feedback-exciter layout, routing and actual-machine equilibrium."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('selection',(0.,1.,-1.))
@pytest.mark.parametrize('runtime',(False,True))
def test_static_feedback_exciter_layout_and_equilibrium(version: int, selection: float, runtime: bool) -> None:
    """Zero and nonzero source switch values preserve distinct physical routing without source-name aliases.

    :param version: Parser release profile.
    :param selection: Source routing selector; any nonzero value selects the voltage-error summation.
    :param runtime: Inspect duplicated runtime or saved graph.
    """
    source: str = f"1 'BBSEX1' '01' .02 20 .2 .1 .05 .1 5 -5 5 -5 {selection} /"
    record: DyrRecord = parse_dyr(source,version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert tuple(parameter.name for parameter in record.parameters) == ('TF','K','T1','T2','T3','T4','VRMAX','VRMIN','EFDMAX','EFDMIN','Switch')
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime,version=version)


@pytest.mark.parametrize('selection',(0.,1.))
@pytest.mark.parametrize('runtime',(False,True))
def test_static_feedback_exciter_connected_auxiliary_equilibrium(selection: float, runtime: bool) -> None:
    """Both insertion points initialize with the actual connected stabilizer and minimum-excitation output.

    :param selection: Source auxiliary routing switch.
    :param runtime: Inspect duplicated runtime or stored graph.
    """
    source: str = f"1 'BBSEX1' '01' .02 20 .2 .1 .05 .1 5 -5 5 -5 {selection} /\n"+"1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)
