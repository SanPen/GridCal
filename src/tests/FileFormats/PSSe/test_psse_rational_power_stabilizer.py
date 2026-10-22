# SPDX-License-Identifier: MPL-2.0
"""Explicit early/modern rational stabilizer fields and actual host auxiliary initialization."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import make_raw_case, test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('version',(33,34,35,36))
def test_rational_stabilizer_release_contract(version: int) -> None:
    """Twenty-one coefficients retain all three rational numerators, denominators and bounds.

    :param version: Explicit source profile.
    """
    record: DyrRecord = parse_dyr("1 'IVOST' '01' 1 0 1 1 2 1 -1 1 1 1 .1 .2 1 -1 1 1 1 .1 .2 1 -1 /",version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 21 and record.icons == ()


@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('version',(33,35))
@pytest.mark.parametrize('numerator',(0,1))
def test_rational_stabilizer_actual_machine_equilibrium(runtime: bool, version: int, numerator: int) -> None:
    """Washout and nonzero-DC cases initialize measured electrical power and the exciter's actual bias.

    :param runtime: Stored or cloned graph.
    :param version: Supplied early or modern profile.
    :param numerator: First-stage washout or positive DC gain.
    """
    source: str = (f"1 'IVOST' '01' 1 {numerator} 1 1 2 2 -2 1 1 1 .1 .2 2 -2 1 1 1 .1 .2 2 -2 /\n"
        "1 'EXST1' '01' .02 .5 -.5 .1 .2 20 .05 5 -5 .1 .05 1 /")
    check_equilibrium('GENROU','8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38',source,runtime,version=version)


@pytest.mark.parametrize('source',(
    "1 'IVOST' '01' 1 0 0 1 2 1 -1 1 1 1 .1 .2 1 -1 1 1 1 .1 .2 1 -1 /",
    "1 'IVOST' '01' 1 1 0 1 2 1 -1 1 1 1 .1 .2 1 -1 1 1 1 .1 .2 1 -1 /",
    "1 'IVOST' '01' 1 0 1 1 2 1 -1 0 1 0 0 .2 1 -1 1 1 1 .1 .2 1 -1 /",
))
def test_rational_unreviewed_degenerate_source_blocks_machine(source: str) -> None:
    """A physically implementable degeneration is not claimed source-compatible without its initialization/limiter convention.

    :param source: Unreviewed zero-origin, bounded PI or free zero-gain integral configuration.
    """
    record: DyrRecord = parse_dyr(source,version=35).records[0]
    assert record.status == RecordStatus.VALID
    with pytest.raises(ValueError,match='Source'):
        validate_dynamic_parameters(record)
    case: PsseCircuit = make_raw_case()
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+
        source+"\n1 'EXST1' '01' .02 .5 -.5 .1 .2 20 .05 5 -5 .1 .05 1 /",version=35))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None and len(case.conversion_report.entries) == 3
