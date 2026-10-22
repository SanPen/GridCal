# SPDX-License-Identifier: MPL-2.0
"""Modern brushless excitation layouts, gate contracts and actual host equilibrium."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def selectable_brushless_record(model: str, minimum: int, maximum: int, field_minimum: float = 0.) -> str:
    """Construct explicit release-owned field-current-limited assignments.

    :param model: Reviewed direct source identity.
    :param minimum: Minimum-excitation insertion selector.
    :param maximum: Maximum-excitation insertion selector.
    :param field_minimum: Source brushless lower voltage setting.
    :return: Complete direct assignment.
    """
    coefficients: str = f'.02 .2 .1 20 .05 8 -8 .5 .05 1 .1 .1 1 3 .1 4 .3 5 -5 10 {field_minimum}' if model == 'AC1C' else f'.02 .2 .1 20 .05 8 -8 10 5 -5 .5 10 .2 .05 1 .1 .1 1 3 .1 4 .3 {field_minimum}'
    if model == 'AC5C':
        coefficients = f'.02 20 .05 8 -8 1 .5 .05 1 .2 .1 3 .1 4 .3 .1 .1 10 {field_minimum}'
    else:
        pass
    return f"1 '{model}' '01' {maximum} {minimum} {coefficients} /"


@pytest.mark.parametrize('model',('AC1C','AC2C','AC5C'))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_selectable_brushless_release_layout(model: str, version: int) -> None:
    """Modern model names do not imply layouts for unverified earlier releases.

    :param model: Source identity.
    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(selectable_brushless_record(model,2,1),version=version).records[0]
    if version in (35,36):
        assert record.status == RecordStatus.VALID and record.icons == (1,2)
        assert len(record.parameters) == (21 if model == 'AC1C' else (23 if model == 'AC2C' else 19))
        assert record.parameters[-1].name == 'VEMIN'
    else:
        assert record.status == RecordStatus.UNSUPPORTED


@pytest.mark.parametrize('model',('AC1C','AC2C','AC5C'))
@pytest.mark.parametrize('minimum',(1,2))
@pytest.mark.parametrize('maximum',(1,2))
@pytest.mark.parametrize('runtime',(False,True))
def test_selectable_brushless_machine_equilibrium(model: str, minimum: int, maximum: int, runtime: bool) -> None:
    """Gate selections preserve actual loaded rectifier equilibrium with stabilizer and minimum limiter.

    :param model: Source identity.
    :param minimum: Minimum-excitation insertion.
    :param maximum: Maximum-excitation insertion.
    :param runtime: Stored or duplicated graph.
    """
    source: str = selectable_brushless_record(model,minimum,maximum)+"\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


@pytest.mark.parametrize('model',('AC1C','AC2C','AC5C'))
def test_selectable_brushless_source_domain(model: str) -> None:
    """The documented brushless zero lower bound is enforced at the import boundary.

    :param model: Source identity.
    """
    record: DyrRecord = parse_dyr(selectable_brushless_record(model,1,1,-1.),version=35).records[0]
    with pytest.raises(ValueError,match='VEMIN=0'):
        validate_dynamic_parameters(record)
