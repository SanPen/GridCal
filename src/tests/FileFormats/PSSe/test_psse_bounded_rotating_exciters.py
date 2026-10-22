# SPDX-License-Identifier: MPL-2.0
"""Release-owned bounded rotating-exciter contracts, limiter selections and calibration restrictions."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def bounded_rotating_record(model: str, minimum: int = 1, maximum: int = 1, ke: float = 1., upper: float = 5.) -> str:
    """Build a direct seventeen-CON assignment with explicit OEL-then-UEL ICON order.

    :param model: Exact fixed or terminal-fed source identifier.
    :param minimum: UEL flag, one or two.
    :param maximum: OEL flag, one or two.
    :param ke: Explicit field coefficient or zero source calibration selector.
    :param upper: Explicit positive regulator capability or automatic selector.
    :return: Complete source record.
    """
    return f"1 '{model}' '01' {maximum} {minimum} .02 20 .05 .2 .1 {upper} -5 {ke} .5 .05 1 3 .1 4 .3 999 -999 /"


@pytest.mark.parametrize('model',('DC1C','DC2C'))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_bounded_rotating_release_layout(model: str, version: int) -> None:
    """The supplied modern layout is not inferred for earlier unverified source releases.

    :param model: Exact source identifier.
    :param version: Parser profile.
    """
    record: DyrRecord = parse_dyr(bounded_rotating_record(model,2,1),version=version).records[0]
    if version in (35,36):
        assert record.status == RecordStatus.VALID
        assert record.icons == (1,2)
        assert len(record.parameters) == 17
        assert tuple(parameter.name for parameter in record.parameters)[-2:] == ('VEMAX','VEMIN')
    else:
        assert record.status == RecordStatus.UNSUPPORTED


@pytest.mark.parametrize('model',('DC1C','DC2C'))
@pytest.mark.parametrize('minimum',(1,2))
@pytest.mark.parametrize('maximum',(1,2))
@pytest.mark.parametrize('runtime',(False,True))
def test_bounded_rotating_actual_machine_equilibrium(model: str, minimum: int, maximum: int, runtime: bool) -> None:
    """Both gate selections and regulator supplies preserve actual field equilibrium with absent OEL bypassed exactly.

    :param model: Exact source identity.
    :param minimum: UEL insertion flag.
    :param maximum: OEL insertion flag.
    :param runtime: Inspect runtime duplication or stored graph.
    """
    source: str = bounded_rotating_record(model,minimum,maximum)+"\n1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)


@pytest.mark.parametrize('model',('DC1C','DC2C'))
@pytest.mark.parametrize('ke,upper',((0.,5.),(1.,0.),(1.,-1.)))
def test_bounded_rotating_unreviewed_automatic_initialization(model: str, ke: float, upper: float) -> None:
    """Nonpositive source capability and zero field coefficient are calibration selectors, not direct physical settings.

    :param model: Source model identifier.
    :param ke: Source field coefficient or calibration selector.
    :param upper: Source regulator capability or automatic selector.
    """
    record: DyrRecord = parse_dyr(bounded_rotating_record(model,ke=ke,upper=upper),version=35).records[0]
    with pytest.raises(ValueError,match='calibration has not been reviewed'):
        validate_dynamic_parameters(record)
