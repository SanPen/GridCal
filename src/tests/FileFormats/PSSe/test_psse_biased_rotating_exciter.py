# SPDX-License-Identifier: MPL-2.0
"""Biased rotating excitation source contracts, current bases and auxiliary initialization."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import build_controller, dynamic_binding, PsseDynamicBinding
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def biased_rotating_record(feedback: int = 0, compensation: float = .1, ke: float = 1., upper: float = 5.) -> str:
    """Construct the eighteen-CON layout without integer-header reinterpretation.

    :param feedback: Numeric feedback switch inside the constant array.
    :param compensation: Explicit current-magnitude compensation reactance.
    :param ke: Explicit field coefficient or source calibration selector.
    :param upper: Explicit amplifier capability or source calibration selector.
    :return: Complete direct source assignment.
    """
    return f"1 'IEET1B' '01' .02 .5 -.5 20 .05 {upper} -5 .07 .05 1 {ke} .5 3 .1 4 .3 {feedback} {compensation} /"


@pytest.mark.parametrize('version',(33,34,35,36))
def test_biased_rotating_source_layout(version: int) -> None:
    """Matching early/modern layouts preserve the switch and compensation constant positions.

    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(biased_rotating_record(),version=version).records[0]
    assert record.status == RecordStatus.VALID and len(record.parameters) == 18
    assert tuple(parameter.name for parameter in record.parameters)[-2:] == ('Switch','Xe')


@pytest.mark.parametrize('feedback',(0,1))
@pytest.mark.parametrize('compensation',(0.,.1))
@pytest.mark.parametrize('runtime',(False,True))
def test_biased_rotating_machine_equilibrium(feedback: int, compensation: float, runtime: bool) -> None:
    """Actual machine-base current magnitude and nonzero auxiliary bias initialize both feedback selections.

    :param feedback: Second-regulator or field-voltage feedback.
    :param compensation: Disable or enable explicit transformer compensation.
    :param runtime: Stored or duplicated graph.
    """
    source: str = biased_rotating_record(feedback,compensation)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


@pytest.mark.parametrize('ke,upper',((0.,5.),(1.,0.)))
def test_biased_rotating_automatic_calibration_rejected(ke: float, upper: float) -> None:
    """Source automatic coefficients are never silently substituted as physical zeros.

    :param ke: Source resistance or calibration selector.
    :param upper: Source capability or calibration selector.
    """
    record: DyrRecord = parse_dyr(biased_rotating_record(ke=ke,upper=upper),version=35).records[0]
    binding: PsseDynamicBinding | None = dynamic_binding('IEET1B')
    assert binding is not None
    with pytest.raises(ValueError,match='calibration has not been reviewed'):
        build_controller(record,binding,VarFactory(),'biased',.5)
