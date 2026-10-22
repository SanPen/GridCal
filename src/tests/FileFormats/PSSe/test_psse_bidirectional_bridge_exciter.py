# SPDX-License-Identifier: MPL-2.0
"""Bidirectional controlled-bridge source layouts and explicit unsupported current logic."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding, PsseDynamicBinding
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def bidirectional_bridge_record(supply: int = 0, resistance: float = 0.) -> str:
    """Construct the ten-CON direct source layout.

    :param supply: Zero terminal-fed or one independent supply.
    :param resistance: Zero selects bidirectional field current.
    :return: Complete source assignment.
    """
    return f"1 'EXNI' '01' .02 20 .05 5 -5 .05 1 .1 {supply} {resistance} /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_bidirectional_bridge_release_layout(version: int) -> None:
    """Matching early/modern source layouts preserve supply and current-capability selectors.

    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(bidirectional_bridge_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 10
    assert tuple(parameter.name for parameter in record.parameters)[-2:] == ('SWITCH','R')


@pytest.mark.parametrize('supply',(0,1))
@pytest.mark.parametrize('runtime',(False,True))
def test_bidirectional_bridge_host_equilibrium(supply: int, runtime: bool) -> None:
    """Both actual supply arrangements initialize actual host field and nonzero auxiliary biases.

    :param supply: Physical supply switch.
    :param runtime: Stored or duplicated graph.
    """
    source: str = bidirectional_bridge_record(supply)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


def test_bidirectional_bridge_unreviewed_current_logic() -> None:
    """A discharge-resistor setting cannot silently become a bidirectional bridge."""
    record: DyrRecord = parse_dyr(bidirectional_bridge_record(resistance=10.),version=35).records[0]
    binding: PsseDynamicBinding | None = dynamic_binding('EXNI')
    assert binding is not None
    with pytest.raises(ValueError,match='reverse-current logic'):
        build_controller(record,binding,VarFactory(),'bridge',.5)
