# SPDX-License-Identifier: MPL-2.0
"""Modern field-current-limited excitation schema and complete machine initialization."""
from __future__ import annotations
import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import named_parameter
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def current_limited_field_record(minimum: int = 1, maximum: int = 1, source: int = 2) -> str:
    """Return the twenty-five-CON modern layout with physically ordered firing bounds.

    :param minimum: Minimum signal location.
    :param maximum: Maximum signal location.
    :param source: Potential circuit selection.
    :return: Complete direct assignment.
    """
    return f"1 'ST6C' '01' {maximum} {minimum} 1 {source} .02 20 10 .05 .05 5 -5 1 2 1 10 5 5 -5 .1 .1 5 -5 .05 2 .1 .2 10 .1 5 /"


@pytest.mark.parametrize('minimum',(1,2,3,4))
@pytest.mark.parametrize('maximum',(1,2,3,4))
@pytest.mark.parametrize('source',(1,2))
@pytest.mark.parametrize('runtime',(False,True))
def test_current_limited_field_machine_equilibrium(minimum: int, maximum: int, source: int, runtime: bool) -> None:
    """Actual phasors, current and supplement bias initialize every independent limiter/source choice.

    :param minimum: Minimum signal location.
    :param maximum: Maximum signal location.
    :param source: Potential source selection.
    :param runtime: Stored or cloned graph.
    """
    record: str = current_limited_field_record(minimum,maximum,source)
    record += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',record,runtime,version=35)


@pytest.mark.parametrize('minimum',(1,2,3,4))
def test_current_limited_field_actual_minimum_limiter(minimum: int) -> None:
    """Actual minimum controllers retain their chosen summed or takeover connection.

    :param minimum: Minimum signal location.
    """
    record: str = current_limited_field_record(minimum)
    record += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .001 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',record,True,version=35)


@pytest.mark.parametrize('version',(35,36))
def test_current_limited_field_release_contract(version: int) -> None:
    """The documented modern contract does not invent a matching older layout.

    :param version: Modern source release.
    """
    record: DyrRecord = parse_dyr(current_limited_field_record(4,3),version=version).records[0]
    assert record.status == RecordStatus.VALID and record.icons == (3,4,1,2) and len(record.parameters) == 25
    assert named_parameter(record,'VMMIN') == -5.
    assert RawDyrV33().get_model_schema('ST6C') is None and RawDyrV34().get_model_schema('ST6C') is None


@pytest.mark.parametrize('record',(current_limited_field_record(5),current_limited_field_record().replace('.05 .05 5 -5','.05 0 5 -5')))
def test_current_limited_field_unreviewed_source_blocks_machine(record: str) -> None:
    """Unknown locations and an improper derivative preserve source without an approximate assembly.

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
