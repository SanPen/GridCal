# SPDX-License-Identifier: MPL-2.0
"""Two-ICON terminal-fed PID source contracts and actual machine assembly."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def terminal_pid_record(minimum: int, maximum: int, ki: float = 1.) -> str:
    """Construct the eighteen-CON layout with OEL preceding UEL.

    :param minimum: Minimum-excitation insertion selector.
    :param maximum: Maximum-excitation insertion selector.
    :param ki: Integral regulation gain.
    :return: Complete direct source assignment.
    """
    return f"1 'DC4B' '01' {maximum} {minimum} .02 2 {ki} .1 .05 5 -5 20 .05 1 .5 .05 1 0 3 .1 4 .3 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_terminal_pid_layout(version: int) -> None:
    """Matching supplied early/modern layouts preserve eighteen constants and limiter flags.

    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(terminal_pid_record(2,1),version=version).records[0]
    assert record.status == RecordStatus.VALID and record.icons == (1,2)
    assert len(record.parameters) == 18
    assert tuple(parameter.name for parameter in record.parameters)[-5:] == ('VEMIN','E1','SE1','E2','SE2')


@pytest.mark.parametrize('minimum',(1,2))
@pytest.mark.parametrize('maximum',(1,2))
@pytest.mark.parametrize('ki',(0.,1.))
@pytest.mark.parametrize('runtime',(False,True))
def test_terminal_pid_host_equilibrium(minimum: int, maximum: int, ki: float, runtime: bool) -> None:
    """All gates and the zero-integral variant initialize actual machine and auxiliary signals.

    :param minimum: Minimum limiter insertion.
    :param maximum: Maximum limiter insertion.
    :param ki: Integral regulation gain.
    :param runtime: Stored or duplicated runtime assembly.
    """
    source: str = terminal_pid_record(minimum,maximum,ki)+"\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


def test_terminal_pid_unknown_selector() -> None:
    """Unknown limiter flags do not become an additive default."""
    record: DyrRecord = parse_dyr(terminal_pid_record(3,1),version=35).records[0]
    with pytest.raises(ValueError,match='selectors'):
        validate_dynamic_parameters(record)
