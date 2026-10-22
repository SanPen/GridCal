# SPDX-License-Identifier: MPL-2.0
"""Release-owned output-feedback excitation contracts and actual host assembly."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def self_feedback_record(model: str, minimum: int = 1, maximum: int = 1) -> str:
    """Construct the documented two-ICON layout with optional firing time.

    :param model: Explicit source identity.
    :param minimum: Minimum-excitation insertion.
    :param maximum: Maximum-excitation insertion.
    :return: Complete direct assignment.
    """
    firing: str = ' .03' if model == 'ST7C' else ''
    return f"1 '{model}' '01' {maximum} {minimum} .02 .1 .2 1.5 .5 20 5 -5 1 1 .1 .2 1 .5{firing} /"


@pytest.mark.parametrize('model',('ST7B','ST7C'))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_self_feedback_release_layout(model: str, version: int) -> None:
    """Only matching documented early layouts are inherited by earlier profiles.

    :param model: Source identity.
    :param version: Explicit release profile.
    """
    record: DyrRecord = parse_dyr(self_feedback_record(model,2,3),version=version).records[0]
    if model == 'ST7B' or version in (35,36):
        assert record.status == RecordStatus.VALID and record.icons == (3,2)
        assert len(record.parameters) == (14 if model == 'ST7B' else 15)
    else:
        assert record.status == RecordStatus.UNSUPPORTED


@pytest.mark.parametrize('model',('ST7B','ST7C'))
@pytest.mark.parametrize('minimum',(1,2,3))
@pytest.mark.parametrize('maximum',(1,2,3))
@pytest.mark.parametrize('runtime',(False,True))
def test_self_feedback_machine_equilibrium(model: str, minimum: int, maximum: int, runtime: bool) -> None:
    """All reference/output takeover selections preserve actual machine and auxiliary equilibrium.

    :param model: Source identity.
    :param minimum: Minimum-excitation insertion.
    :param maximum: Maximum-excitation insertion.
    :param runtime: Stored or duplicated runtime graph.
    """
    source: str = self_feedback_record(model,minimum,maximum)+"\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


@pytest.mark.parametrize('model',('ST7B','ST7C'))
def test_self_feedback_nonzero_stabilizer_bias(model: str) -> None:
    """An actual nonzero stabilizer equilibrium is subtracted exactly once in reference initialization.

    :param model: Explicit source identity.
    """
    source: str = self_feedback_record(model)+"\n1 'PSS3B' '01' 1 0 3 0 1 0 0 -.5 0 0 0 0 0 0 0 0 0 0 0 .1 -.1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,True)
