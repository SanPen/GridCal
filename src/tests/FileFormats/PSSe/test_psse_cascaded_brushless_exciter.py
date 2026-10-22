# SPDX-License-Identifier: MPL-2.0
"""Matching early/modern cascaded brushless layouts and real-machine initial conditions."""
from __future__ import annotations
import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def cascaded_brushless_record(potential: float = 1., outer_i: float = 10., inner_i: float = 5.) -> str:
    """Return the matching twenty-seven-CON cascaded PID/PI assignment.

    :param potential: Supply gain; zero bypasses terminal scaling.
    :param outer_i: Voltage integral gain.
    :param inner_i: Field integral gain.
    :return: Complete direct source assignment.
    """
    return f"1 'AC7B' '01' .02 20 {outer_i} .05 .05 5 -5 2 {inner_i} 5 -5 {potential} .2 .2 .1 .05 .1 .1 .1 1 .5 5 0 3 .1 4 .3 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_cascaded_brushless_release_contract(version: int) -> None:
    """Early and modern supplied layouts have the same named CON order without ICONs.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr(cascaded_brushless_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 27 and record.icons == ()


@pytest.mark.parametrize('version',(33,35))
@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('potential',(0.,2.))
@pytest.mark.parametrize('outer_i,inner_i',((0.,0.),(0.,5.),(10.,0.),(10.,5.)))
def test_cascaded_brushless_machine_equilibrium(version: int, runtime: bool, potential: float,
                                               outer_i: float, inner_i: float) -> None:
    """All integral/supply variants balance actual winding loss and real auxiliary biases.

    :param version: Supplied early or modern profile.
    :param runtime: Stored or cloned assembly.
    :param potential: Terminal supply gain or zero bypass.
    :param outer_i: Outer integral gain.
    :param inner_i: Inner integral gain.
    """
    record: str = cascaded_brushless_record(potential,outer_i,inner_i)
    record += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .001 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',record,runtime,version=version)


@pytest.mark.parametrize('record',(
    cascaded_brushless_record().replace('.1 .1 1 .5 5 0','.1 .1 0 .5 5 0'),
    cascaded_brushless_record().replace('20 10.0 .05 .05','20 10.0 .05 0'),
))
def test_cascaded_brushless_unreviewed_source_blocks_machine(record: str) -> None:
    """Automatic field calibration and an improper derivative do not produce a partial machine.

    :param record: Source assignment outside reviewed behavior.
    """
    from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
    from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.basic_structures import Logger
    from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+record,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
