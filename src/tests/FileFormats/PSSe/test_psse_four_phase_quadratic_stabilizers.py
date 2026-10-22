# SPDX-License-Identifier: MPL-2.0
"""Version-specific four-phase and quadratic dual-input stabilizer conversion contracts."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def additional_stabilizer_record(model: str, bypass: bool = False) -> str:
    """Build the exact source ICON/CON contract for the added physical structure.

    :param model: Four-phase ramp-tracking or quadratic dual-input identity.
    :param bypass: Bypass all channel dynamics for the quadratic family.
    :return: Complete source assignment.
    """
    if model == 'PSS2C':
        return "1 'PSS2C' '01' 1 0 3 0 2 2 3 0 .02 4 0 .03 .4 .7 .1 .2 5 .2 .05 .1 .03 .04 .02 2 -2 2 -2 .1 -.1 .08 .04 -1 0 0 .1 /"
    else:
        times: str = '0 0' if bypass else '.02 10'
        second_times: str = '0 0 0' if bypass else '.03 12 .5'
        return "1 'PSS3B' '01' 1 0 3 0 1 "+times+' -.5 '+second_times+' .1 .01 .2 .02 .1 .01 .2 .02 .1 -.1 /'


@pytest.mark.parametrize('model',('PSS2C','PSS3B'))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_added_stabilizer_profile_contracts(model: str, version: int) -> None:
    """The new four-phase source layout is release-owned while the quadratic layout matches both supplied snapshots.

    :param model: Exact source identifier.
    :param version: Parser release profile.
    """
    record: DyrRecord = parse_dyr(additional_stabilizer_record(model),version=version).records[0]
    if model == 'PSS2C' and version in (33,34):
        assert record.status == RecordStatus.UNSUPPORTED
    else:
        assert record.status == RecordStatus.VALID
        assert len(record.parameters) == (29 if model == 'PSS2C' else 17)
        assert len(record.icons) == (6 if model == 'PSS2C' else 4)


@pytest.mark.parametrize('model,version,bypass',(('PSS2C',35,False),('PSS2C',36,False),
    ('PSS3B',33,False),('PSS3B',34,False),('PSS3B',35,False),('PSS3B',36,False),('PSS3B',35,True)))
@pytest.mark.parametrize('runtime',(False,True))
def test_added_stabilizer_machine_equilibrium(model: str, version: int, bypass: bool, runtime: bool) -> None:
    """Selected speed/power measurements initialize both stored/runtime paths, including nonzero fully bypassed bias.

    :param model: Exact source stabilizer identifier.
    :param version: Reviewed source profile.
    :param bypass: Remove optional quadratic-family channel memories.
    :param runtime: Inspect runtime duplication or stored graph.
    """
    controller: str = "1 'SEXS' '01' .1 1 20 .05 0 5 /\n"+additional_stabilizer_record(model,bypass)
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',controller,runtime,version=version)


@pytest.mark.parametrize('threshold',(0.,.1))
def test_unreviewed_power_hysteresis_is_not_silently_disabled(threshold: float) -> None:
    """The source enable selector must explicitly request continuously enabled output.

    :param threshold: Zero/positive ambiguous or enabled source output logic.
    """
    record: DyrRecord = parse_dyr(additional_stabilizer_record('PSS2C').replace(' -1 0 0 .1 /',f' {threshold} 0 0 .1 /'),version=35).records[0]
    with pytest.raises(ValueError,match='hysteresis'):
        validate_dynamic_parameters(record)
