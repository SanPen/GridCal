# SPDX-License-Identifier: MPL-2.0
"""Distinct direct and legacy cascaded hydraulic governor contracts and turbine-base initialization."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def cascaded_hydro_record(model: str, droop: float = .05, rating: float = 0.) -> str:
    """Build an exact source assignment with distinct physical cascade coefficients.

    :param model: Direct built-in or reviewed legacy subroutine name.
    :param droop: Permanent gate-feedback gain, including zero.
    :param rating: Optional turbine rating; zero selects machine MVA.
    :return: Complete slash-terminated assignment.
    """
    header: str = f"1 'USRMDL' '01' '{model}' 5 0 0 19 6 2" if model == 'HYGOV2DU' else f"1 '{model}' '01'"
    payload: str = header+f' 1 .1 1 .1 .05 1 .1 1 .5 5 .3 {droop} .2 1.2 0 1.3'
    return payload+(' /' if model == 'HYGOV2' else f' .002 -.003 {rating} /')


@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('model',('HYGOV2','HYGOV2D','HYGOV2DU'))
def test_cascaded_hydro_profile_contracts(model: str, version: int) -> None:
    """Direct and user-model assignments have separate release-owned layouts and allocation checks.

    :param model: Exact source built-in or user-subroutine name.
    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(cascaded_hydro_record(model),version=version).records[0]
    if model == 'HYGOV2DU':
        assert record.status == RecordStatus.VALID
        assert record.user_header is not None and record.user_header.name == model
        assert record.user_header.state_count == 6 and record.user_header.variable_count == 2
        assert (record.user_schema is not None) == (version == 33)
    elif model == 'HYGOV2D' and version in (33,34):
        assert record.status == RecordStatus.UNSUPPORTED
    else:
        assert record.status == RecordStatus.VALID
        assert len(record.parameters) == (16 if model == 'HYGOV2' else 19)


@pytest.mark.parametrize('model,version',(('HYGOV2',33),('HYGOV2',34),('HYGOV2',35),('HYGOV2',36),('HYGOV2D',35),('HYGOV2D',36),('HYGOV2DU',33)))
@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('droop',(0.,.05))
def test_cascaded_hydro_machine_base_equilibrium(model: str, version: int, runtime: bool, droop: float) -> None:
    """Actual host power initializes gate, water and reference without dividing by zero droop or double scaling turbine rating.

    :param model: Exact source identity.
    :param version: Reviewed profile.
    :param runtime: Inspect duplicated runtime or stored graph.
    :param droop: Permanent droop, including isochronous control.
    """
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',
        cascaded_hydro_record(model,droop,0. if model == 'HYGOV2' else 75.),runtime,version=version)
