# SPDX-License-Identifier: MPL-2.0
"""Matching early/modern three-channel excitation layouts and moving absent-gate bypasses."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case, test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def parallel_channel_record() -> str:
    """Return the eighteen-CON fixed take-over assignment.

    :return: Complete source record.
    """
    return "1 'ST5B' '01' .02 .1 .2 .05 .1 20 5 -5 .05 .1 .2 .3 .1 .2 .05 .15 .04 .08 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_parallel_channel_release_contract(version: int) -> None:
    """The supplied matching fixed-gate layout does not invent modern selector ICONs.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr(parallel_channel_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 18 and record.icons == ()


@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('version',(33,35))
def test_parallel_channel_actual_machine_equilibrium(runtime: bool, version: int) -> None:
    """Eight continuous memories initialize actual field/current and nonzero supplementary bias with exact gate bypass.

    :param runtime: Stored or cloned graph.
    :param version: Supplied early or modern profile.
    """
    source: str = parallel_channel_record()+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=version)


def test_parallel_channel_actual_minimum_limiter_equilibrium() -> None:
    """An actual compatible minimum limiter connects at the specified take-over point."""
    case: PsseCircuit = make_raw_case()
    source: str = ("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+
        parallel_channel_record()+
        "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /")
    assert case.add_auxiliary(parse_dyr(source,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None and len(case.conversion_report.entries) == 4
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',
        source.split('\n',1)[1],True)
