# SPDX-License-Identifier: MPL-2.0
"""Compound-source cascaded PI source contracts and actual operating-point initialization."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def compound_pi_record(kir: float = 1., kim: float = 1.) -> str:
    """Construct the seventeen-CON compound-source assignment.

    :param kir: Voltage-loop integral gain.
    :param kim: Field-loop integral gain.
    :return: Complete direct source assignment.
    """
    return f"1 'ESST4B' '01' .02 2 {kir} 8 -8 .05 1 {kim} 2 -2 1 2 .1 5 .1 .1 10 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_compound_pi_source_layout(version: int) -> None:
    """Matching supplied layouts preserve transformer phase and all regulator gains.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr(compound_pi_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 17
    assert record.parameters[-1].name == 'THETAP' and record.parameters[-1].value == 10.


@pytest.mark.parametrize('kir',(0.,1.))
@pytest.mark.parametrize('kim',(0.,1.))
@pytest.mark.parametrize('runtime',(False,True))
def test_compound_pi_machine_equilibrium(kir: float, kim: float, runtime: bool) -> None:
    """Both proportional-only variants initialize actual loaded supply and auxiliary biases.

    :param kir: Voltage integral gain.
    :param kim: Field integral gain.
    :param runtime: Stored or duplicated graph.
    """
    source: str = compound_pi_record(kir,kim)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


def test_compound_pi_potential_only_source() -> None:
    """An explicit potential-only transformer uses KI=0 without borrowing another model's calibration rule."""
    source: str = "1 'ESST4B' '01' .02 0 1 8 -8 .05 0 1 2 -2 1 2 0 5 .1 .1 10 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,True)
