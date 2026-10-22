# SPDX-License-Identifier: MPL-2.0
"""PI compound-field excitation source contracts and algebraic-field special case."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def pi_compound_record(field_time: float = .5, potential: float = 0., current: float = 0.) -> str:
    """Construct the twenty-four-CON direct assignment.

    :param field_time: Positive rotating field time or exact zero bypass.
    :param potential: Potential-source ratio or zero.
    :param current: Current-compounding ratio or zero.
    :return: Complete direct source assignment.
    """
    return f"1 'EXPIC1' '01' .02 20 .1 5 -5 .05 .02 .03 5 -5 .05 1 .1 5 -5 1 {field_time} 3 .1 4 .3 {potential} {current} .1 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_pi_compound_field_release_contract(version: int) -> None:
    """Matching supplied early/modern layouts retain all independent capability and source constants.

    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(pi_compound_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 24
    assert tuple(parameter.name for parameter in record.parameters)[-3:] == ('KP','KI','KC')


@pytest.mark.parametrize('field_time',(0.,.5))
@pytest.mark.parametrize('potential,current',((0.,0.),(2.,0.),(2.,.1)))
@pytest.mark.parametrize('runtime',(False,True))
def test_pi_compound_field_machine_equilibrium(field_time: float, potential: float, current: float, runtime: bool) -> None:
    """Unit, potential and compound supplies initialize actual auxiliary biases with dynamic or direct field forcing.

    :param field_time: Positive dynamic time or direct forcing.
    :param potential: Potential-source ratio.
    :param current: Current-source ratio.
    :param runtime: Stored or duplicated graph.
    """
    source: str = pi_compound_record(field_time,potential,current)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)
