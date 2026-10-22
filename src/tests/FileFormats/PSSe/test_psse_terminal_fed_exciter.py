# SPDX-License-Identifier: MPL-2.0
"""Static excitation ICON topology and actual-machine initialization across supplied releases."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def terminal_fed_record(minimum: int, stabilizer: int) -> str:
    """Build an exact eighteen-CON source assignment with two explicit topology ICONs.

    :param minimum: Source UEL flag one, two or three.
    :param stabilizer: Source VOS flag one or two.
    :return: Complete source record.
    """
    return f"1 'ESST1A' '01' {minimum} {stabilizer} .02 .5 -.5 .05 .2 .03 .1 20 .05 5 -5 5 -5 .1 .05 1 1 2 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_terminal_fed_release_layout(version: int) -> None:
    """Both supplied releases use the same explicit UEL/VOS header and ordered eighteen constants.

    :param version: Concrete parser profile.
    """
    record: DyrRecord = parse_dyr(terminal_fed_record(3,2),version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert record.icons == (3,2)
    assert len(record.parameters) == 18
    assert tuple(parameter.name for parameter in record.parameters)[-5:] == ('KC','KF','TF','KLR','ILR')


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('stabilizer',(1,2))
@pytest.mark.parametrize('version',(33,35))
@pytest.mark.parametrize('runtime',(False,True))
def test_terminal_fed_machine_equilibrium(minimum: int, stabilizer: int, version: int, runtime: bool) -> None:
    """Every topology initializes stored/runtime equations from the actual field current and field voltage.

    :param minimum: Source UEL insertion flag.
    :param stabilizer: Source stabilizer insertion flag.
    :param version: Reviewed supplied release.
    :param runtime: Inspect runtime duplication or stored graph.
    """
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',terminal_fed_record(minimum,stabilizer),runtime,version=version)


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('stabilizer',(1,2))
def test_terminal_fed_nonzero_stabilizer_and_minimum_excitation(minimum: int, stabilizer: int) -> None:
    """A nonzero steady stabilizer bias is initialized at its selected summation point without double subtraction.

    :param minimum: UEL insertion flag.
    :param stabilizer: Stabilizer insertion flag.
    """
    source: str = terminal_fed_record(minimum,stabilizer)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,False)
