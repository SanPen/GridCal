# SPDX-License-Identifier: MPL-2.0
"""Release-owned static cascaded-PI excitation with actual phasors and auxiliary bias."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case, test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def filtered_compound_record(pss: int = 1, minimum: int = 1, maximum: int = 1, source: int = 1) -> str:
    """Build five explicit ICONs and twenty-one ordered CONs.

    :param pss: Supplement insertion.
    :param minimum: Minimum-limiter insertion.
    :param maximum: Maximum-limiter insertion.
    :param source: Terminal or independent potential supply.
    :return: Complete direct source assignment.
    """
    return f"1 'ST4C' '01' {pss} {maximum} {minimum} 1 {source} .02 20 10 5 -5 1 1 5 -5 .02 5 -5 1 .1 5 2 .1 .1 10 .1 5 /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_filtered_compound_release_contract(version: int) -> None:
    """A modern twenty-one-CON/five-ICON layout is not backfilled into unsupported profiles.

    :param version: Explicit parser release.
    """
    record: DyrRecord = parse_dyr(filtered_compound_record(),version=version).records[0]
    if version < 35:
        assert record.parameters == ()
    else:
        assert record.status == RecordStatus.VALID and len(record.parameters) == 21
        assert record.icons == (1,1,1,1,1)


@pytest.mark.parametrize('minimum,maximum,pss,source',((1,1,1,1),(2,3,2,1),(3,2,1,2),(1,3,2,2)))
@pytest.mark.parametrize('runtime',(False,True))
def test_filtered_compound_actual_machine_equilibrium(minimum: int, maximum: int, pss: int, source: int, runtime: bool) -> None:
    """Selected gates bypass absent controllers exactly and supplement bias initializes all five memories.

    :param minimum: Minimum-limiter insertion.
    :param maximum: Maximum-limiter insertion.
    :param pss: Supplement insertion.
    :param source: Potential-source selection.
    :param runtime: Stored or cloned graph.
    """
    auxiliary: str = filtered_compound_record(pss,minimum,maximum,source)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /"
    auxiliary += "\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',auxiliary,runtime)


def test_filtered_compound_takeover_controller_is_retained_in_assembly() -> None:
    """A compatible actual minimum limiter remains part of the converted take-over chain."""
    case: PsseCircuit = make_raw_case()
    source: str = ("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+
        filtered_compound_record(pss=2,minimum=2)+
        "\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /")
    assert case.add_auxiliary(parse_dyr(source,version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is not None
    assert len(case.conversion_report.entries) == 4
