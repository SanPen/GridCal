# SPDX-License-Identifier: MPL-2.0
"""Modern selectable excitation release layout and actual coupled equilibrium."""
import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from tests.FileFormats.PSSe.test_psse_parallel_channel_exciter import parallel_channel_record
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('minimum,maximum',((1,1),(1,2),(2,1),(2,2)))
@pytest.mark.parametrize('runtime',(False,True))
def test_selectable_parallel_equilibrium(minimum: int, maximum: int, runtime: bool) -> None:
    """Actual limiter bias and supplementary bias balance every topology.

    :param minimum: Underexcitation location.
    :param maximum: Overexcitation location.
    :param runtime: Stored or cloned assembly.
    """
    source: str = parallel_channel_record().replace("'ST5B' '01'",f"'ST5C' '01' {maximum} {minimum}")
    source += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=35)


@pytest.mark.parametrize('version',(35,36))
def test_selectable_parallel_schema(version: int) -> None:
    """Modern schema retains two selectors separately from eighteen constants.

    :param version: Modern release profile.
    """
    source: str = parallel_channel_record().replace("'ST5B' '01'","'ST5C' '01' 1 2")
    record: DyrRecord = parse_dyr(source,version=version).records[0]
    assert record.status == RecordStatus.VALID and record.icons == (1,2) and len(record.parameters) == 18


def test_selectable_parallel_earlier_profiles_are_not_backfilled() -> None:
    """A modern source layout must not silently activate in an earlier release."""
    assert RawDyrV33().get_model_schema('ST5C') is None
    assert RawDyrV34().get_model_schema('ST5C') is None


@pytest.mark.parametrize('flags',('0 1','1 3','3 2'))
def test_selectable_parallel_invalid_flags_block_conversion(flags: str) -> None:
    """Unreviewed selector values cannot produce an approximate machine assembly.

    :param flags: Invalid maximum/minimum selector pair.
    """
    from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
    from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.basic_structures import Logger
    from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case
    case: PsseCircuit = make_raw_case()
    source: str = "1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"
    source += parallel_channel_record().replace("'ST5B' '01'",f"'ST5C' '01' {flags}")
    assert case.add_auxiliary(parse_dyr(source,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None
