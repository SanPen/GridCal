# SPDX-License-Identifier: MPL-2.0
"""Modern cascaded brushless source selectors, power arrangements and retained boundaries."""
from __future__ import annotations
import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from tests.FileFormats.PSSe.test_psse_cascaded_brushless_exciter import cascaded_brushless_record
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def selectable_cascaded_record(minimum: int = 1, maximum: int = 1, supplement: int = 1,
                               source: int = 1, power_supply: int = 1, potential: float = 2.) -> str:
    """Return thirty-three CONs with the six modern selectors in documented order.

    :param minimum: Minimum location.
    :param maximum: Maximum location.
    :param supplement: Supplement location.
    :param source: Terminal or independent potential.
    :param power_supply: Rectified potential or self-excited supply.
    :param potential: Potential voltage gain.
    :return: Complete modern direct assignment.
    """
    return cascaded_brushless_record(potential).replace("'AC7B' '01'",f"'AC7C' '01' {maximum} {minimum} 1 {supplement} {source} {power_supply}").replace(' /',' .1 .2 10 .1 5 2 /')


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('maximum',(1,2,3,4))
@pytest.mark.parametrize('supplement',(1,2))
@pytest.mark.parametrize('power_supply',(1,2))
def test_selectable_cascaded_machine_equilibrium(minimum: int, maximum: int, supplement: int, power_supply: int) -> None:
    """Each independently selected signal location initializes against live phasors and actual source power.

    :param minimum: Minimum location.
    :param maximum: Maximum location.
    :param supplement: Supplement location.
    :param power_supply: Physical field-power arrangement.
    """
    source: str = selectable_cascaded_record(minimum,maximum,supplement,power_supply=power_supply)
    source += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,True,version=35)


@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('power_supply',(1,2))
def test_selectable_cascaded_actual_minimum_limiter(minimum: int, power_supply: int) -> None:
    """Actual minimum excitation reaches error, input-gate or post-PID location with compatible operating bias.

    :param minimum: Minimum location.
    :param power_supply: Physical field-power arrangement.
    """
    source: str = selectable_cascaded_record(minimum,4,2,source=2,power_supply=power_supply)
    source += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .001 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,True,version=35)


@pytest.mark.parametrize('version',(35,36))
def test_selectable_cascaded_release_contract(version: int) -> None:
    """The six-ICON modern contract is not silently imported under an older grammar.

    :param version: Modern source profile.
    """
    record: DyrRecord = parse_dyr(selectable_cascaded_record(3,4,2),version=version).records[0]
    assert record.status == RecordStatus.VALID and record.icons == (4,3,1,2,1,1) and len(record.parameters) == 33
    assert RawDyrV33().get_model_schema('AC7C') is None and RawDyrV34().get_model_schema('AC7C') is None


@pytest.mark.parametrize('source',(selectable_cascaded_record(potential=0.),selectable_cascaded_record(maximum=5)))
def test_selectable_cascaded_unreviewed_source_blocks_machine(source: str) -> None:
    """Ambiguous zero-potential source conventions and unknown locations retain data without partial activation.

    :param source: Unreviewed source assignment.
    """
    from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
    from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.basic_structures import Logger
    from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+source,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
