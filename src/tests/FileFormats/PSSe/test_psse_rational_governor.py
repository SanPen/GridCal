# SPDX-License-Identifier: MPL-2.0
"""Ordered rational governor records and live machine/turbine operating points."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium
from tests.FileFormats.PSSe.test_psse_delayed_engine_governor import test_governor_runs_in_vectorized_rms_driver as check_runtime


@pytest.mark.parametrize('version',(33,34,35,36))
def test_rational_governor_release_contract(version: int) -> None:
    """All three independent rational stages retain their ordered twenty-one source constants.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr("1 'IVOGO' '01' 20 1 1 .1 .2 1 -1 1 1 0 0 1 1.2 0 1 1 1 0 .2 1.2 0 /",version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 21 and record.icons == ()


@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('version',(33,35))
@pytest.mark.parametrize('integral_denominator',(0,1))
def test_rational_governor_actual_machine_equilibrium(runtime: bool, version: int, integral_denominator: int) -> None:
    """Integral and finite-DC chains balance actual mechanical power on nonunit machine base.

    :param runtime: Stored or cloned graph.
    :param version: Supplied early/modern profile.
    :param integral_denominator: Free load-holding integral or stable middle lag.
    """
    source: str = f"1 'IVOGO' '01' 20 1 1 .1 .2 1 -1 1 1 {integral_denominator} 0 1 1.2 0 1 1 1 0 .2 1.2 0 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=version)


def test_rational_governor_deferred_initialization_in_real_rms_driver() -> None:
    """The three backward-balanced frozen initial demands compile and run against a loaded network."""
    check_runtime("1 'IVOGO' '01' 20 1 1 .1 .2 1 -1 1 1 0 0 1 1.2 0 1 1 1 0 .2 1.2 0 /")
