# SPDX-License-Identifier: MPL-2.0
"""Matching early/modern PID brushless layouts and actual auxiliary operating points."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('version',(33,34,35,36))
def test_pid_brushless_release_contract(version: int) -> None:
    """The twenty-one-CON record retains both PID and amplifier capabilities without ICON inference.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr("1 'AC8B' '01' .02 20 10 .05 .05 5 -5 20 .05 5 -5 .1 .1 1 .5 5 0 3 .1 4 .3 /",version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 21 and record.icons == ()


@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('version',(33,35))
def test_pid_brushless_actual_machine_equilibrium(runtime: bool, version: int) -> None:
    """Live rotor current, saturation and additive PSS/UEL bias initialize original and cloned graphs.

    :param runtime: Stored or materialized graph.
    :param version: Supplied early or modern source profile.
    """
    source: str = ("1 'AC8B' '01' .02 20 10 .05 .05 5 -5 20 .05 5 -5 .1 .1 1 .5 5 0 3 .1 4 .3 /\n"
        "1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n"
        "1 'MNLEX1' '01' .1 1 2 .2 .1 1 /")
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=version)
