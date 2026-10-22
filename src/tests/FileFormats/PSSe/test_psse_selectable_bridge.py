# SPDX-License-Identifier: MPL-2.0
"""Release-owned controlled-bridge selectors and host equilibrium."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def bridge_record(minimum: int, maximum: int) -> str:
    """Construct the documented OEL-then-UEL layout.

    :param minimum: Minimum-excitation insertion selector.
    :param maximum: Maximum-excitation insertion selector.
    :return: Direct controlled-bridge assignment.
    """
    return f"1 'AC4C' '01' {maximum} {minimum} .02 .2 -.2 .1 .2 100 .05 5 -5 .1 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_selectable_bridge_release_contract(version: int) -> None:
    """Earlier profiles do not infer a later two-ICON source layout.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr(bridge_record(2,1),version=version).records[0]
    if version in (35,36):
        assert record.status == RecordStatus.VALID
        assert record.icons == (1,2)
        assert len(record.parameters) == 10
    else:
        assert record.status == RecordStatus.UNSUPPORTED


@pytest.mark.parametrize('minimum',(1,2))
@pytest.mark.parametrize('maximum',(1,2))
@pytest.mark.parametrize('runtime',(False,True))
def test_selectable_bridge_host_equilibrium(minimum: int, maximum: int, runtime: bool) -> None:
    """Each selector pair connects the actual host field, stabilizer and minimum limiter.

    :param minimum: Minimum-excitation insertion.
    :param maximum: Maximum-excitation insertion.
    :param runtime: Stored or duplicated runtime graph.
    """
    source: str = bridge_record(minimum,maximum)+"\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


def test_selectable_bridge_rejects_unknown_gate() -> None:
    """An unknown source selector cannot silently choose an additive input."""
    record: DyrRecord = parse_dyr(bridge_record(3,1),version=35).records[0]
    with pytest.raises(ValueError,match='selectors'):
        validate_dynamic_parameters(record)
