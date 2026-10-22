# SPDX-License-Identifier: MPL-2.0
"""Modern compound PID source contract and actual machine equilibrium."""
import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('maximum',(1,2,3))
@pytest.mark.parametrize('supplement',(1,2))
@pytest.mark.parametrize('source',(1,2))
def test_compound_pid_actual_machine_equilibrium(minimum: int, maximum: int, supplement: int, source: int) -> None:
    """Live phasors, winding current and auxiliary bias initialize each reviewed selector combination.

    :param minimum: Minimum limiter location.
    :param maximum: Maximum limiter location.
    :param supplement: Supplement location.
    :param source: Excitation source selection.
    """
    record: str = f"1 'AC8C' '01' {maximum} {minimum} 1 {supplement} {source} .02 20 10 .05 .05 5 -5 20 .05 5 -5 .1 .1 1 .5 5 .01 3 .1 4 .3 2 .1 .1 15 .1 5 /"
    record += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',record,True,version=35)


@pytest.mark.parametrize('version',(35,36))
def test_compound_pid_release_contract(version: int) -> None:
    """Preserve five ICONs and twenty-seven CONs without old-release backfill.

    :param version: Modern source profile.
    """
    record: DyrRecord = parse_dyr("1 'AC8C' '01' 1 2 3 2 1 .02 20 10 .05 .05 5 -5 20 .05 5 -5 .1 .1 1 .5 5 .01 3 .1 4 .3 2 .1 .1 15 .1 5 /",version=version).records[0]
    assert record.status == RecordStatus.VALID and record.icons == (1,2,3,2,1) and len(record.parameters) == 27
    assert RawDyrV33().get_model_schema('AC8C') is None and RawDyrV34().get_model_schema('AC8C') is None


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('runtime',(False,True))
def test_compound_pid_actual_minimum_limiter(minimum: int, runtime: bool) -> None:
    """Compatible real limiter bias initializes additive, input-gate and post-PID connections.

    :param minimum: Minimum limiter location.
    :param runtime: Stored or cloned graph.
    """
    source: str = f"1 'AC8C' '01' 1 {minimum} 1 2 2 .02 20 10 .05 .05 5 -5 20 .05 5 -5 .1 .1 1 .5 5 .01 3 .1 4 .3 2 .1 .1 15 .1 5 /"
    source += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .001 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=35)
