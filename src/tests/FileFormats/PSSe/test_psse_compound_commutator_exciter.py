# SPDX-License-Identifier: MPL-2.0
"""Modern commutator PID layout, actual winding initialization and limiter wiring."""
from __future__ import annotations
import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import named_parameter
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def compound_commutator_record(minimum: int = 1, maximum: int = 1, source: int = 2) -> str:
    """Return the literal modern layout, including the supplied KJR integral label.

    :param minimum: Minimum insertion selector.
    :param maximum: Maximum insertion selector.
    :param source: Physical potential selector.
    :return: Complete twenty-four-CON/four-ICON source assignment.
    """
    return f"1 'DC4C' '01' {maximum} {minimum} 1 {source} .02 4 2 .1 .05 5 -5 3 .08 1.4 .7 .2 .4 0 3 .1 4 .3 2 .1 .2 10 .1 5 /"


@pytest.mark.parametrize('minimum',(1,2))
@pytest.mark.parametrize('maximum',(1,2))
@pytest.mark.parametrize('source',(1,2))
@pytest.mark.parametrize('runtime',(False,True))
def test_compound_commutator_machine_equilibrium(minimum: int, maximum: int, source: int, runtime: bool) -> None:
    """All source/gate configurations balance actual phasors, magnetic loss and supplement bias.

    :param minimum: Minimum insertion selector.
    :param maximum: Maximum insertion selector.
    :param source: Physical potential selector.
    :param runtime: Stored or cloned assembly.
    """
    record: str = compound_commutator_record(minimum,maximum,source)
    record += "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',record,runtime,version=35)


@pytest.mark.parametrize('minimum',(1,2))
def test_compound_commutator_actual_minimum_limiter(minimum: int) -> None:
    """A compatible actual minimum controller reaches the selected sum or takeover port.

    :param minimum: Minimum insertion selector.
    """
    record: str = compound_commutator_record(minimum)
    record += "\n1 'MNLEX1' '01' .001 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',record,True,version=35)


@pytest.mark.parametrize('version',(35,36))
def test_compound_commutator_release_contract(version: int) -> None:
    """The modern layout does not leak into earlier version contracts.

    :param version: Modern source profile.
    """
    record: DyrRecord = parse_dyr(compound_commutator_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 24 and record.icons == (1,1,1,2)
    assert named_parameter(record,'KJR') == 2.
    assert RawDyrV33().get_model_schema('DC4C') is None and RawDyrV34().get_model_schema('DC4C') is None


@pytest.mark.parametrize('record',(compound_commutator_record(3),compound_commutator_record().replace('.08 1.4 .7','.08 0 .7')))
def test_compound_commutator_unreviewed_source_blocks_machine(record: str) -> None:
    """Unknown selectors and automatic resistance calibration cannot activate a partial assembly.

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
