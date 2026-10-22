# SPDX-License-Identifier: MPL-2.0
"""Release-owned static maximum-limiter locations and host assembly."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def static_maximum_record(minimum: int, stabilizer: int, maximum: int) -> str:
    """Construct the three-ICON/eighteen-CON direct assignment.

    :param minimum: UEL location.
    :param stabilizer: Stabilizing-voltage location.
    :param maximum: OEL location.
    :return: Complete source record.
    """
    return f"1 'ST1C' '01' {minimum} {stabilizer} {maximum} .02 .5 -.5 .05 .2 .03 .1 20 .05 5 -5 5 -5 .1 .05 1 1 2 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_static_maximum_release_contract(version: int) -> None:
    """The modern OEL selector is not inferred from the earlier two-ICON static model.

    :param version: Parser profile.
    """
    record: DyrRecord = parse_dyr(static_maximum_record(2,1,3),version=version).records[0]
    if version in (35,36):
        assert record.status == RecordStatus.VALID and record.icons == (2,1,3)
        assert len(record.parameters) == 18
    else:
        assert record.status == RecordStatus.UNSUPPORTED


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('stabilizer',(1,2))
@pytest.mark.parametrize('maximum',(1,2,3))
@pytest.mark.parametrize('runtime',(False,True))
def test_static_maximum_host_equilibrium(minimum: int, stabilizer: int, maximum: int, runtime: bool) -> None:
    """Each topology preserves actual machine and auxiliary equilibrium with absent OEL bypassed exactly.

    :param minimum: UEL insertion.
    :param stabilizer: Supplementary insertion.
    :param maximum: OEL insertion.
    :param runtime: Stored or duplicated runtime graph.
    """
    source: str = static_maximum_record(minimum,stabilizer,maximum)+"\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)
