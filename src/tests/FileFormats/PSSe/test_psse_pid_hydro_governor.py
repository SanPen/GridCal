# SPDX-License-Identifier: MPL-2.0
"""Direct/legacy hydraulic PID contracts, both feedback modes and independent mechanical/electrical bases."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


def pid_hydro_record(model: str, feedback: int, rating: float = 0.) -> str:
    """Build one exact source assignment with a monotone turbine curve and nonzero machine-loss sensitivity.

    :param model: Exact built-in or reviewed legacy subroutine name.
    :param feedback: Zero for electrical power, one for gate position.
    :param rating: Turbine rating; zero selects machine MVA.
    :return: Complete slash-terminated source record.
    """
    header: str = f"1 'USRMDL' '01' '{model}' 5 0 1 23 7 2 {feedback}" if model == 'PIDGOVDU' else f"1 '{model}' '01' {feedback}"
    payload: str = header+' .05 .02 2 1 .1 .1 .2 .5 .08 .4 .3 .7 .65 1 1 0 1 1 .2 -.15'
    return payload+(' /' if model == 'PIDGOV' else f' .002 -.003 {rating} /')


@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('model',('PIDGOV','PIDGOVD','PIDGOVDU'))
def test_pid_hydro_release_contracts(model: str, version: int) -> None:
    """The direct deadband layout keeps its feedback ICON; the legacy wrapper owns its NI/NC/NS/NV contract.

    :param model: Exact source identity.
    :param version: Explicit parser release.
    """
    record: DyrRecord = parse_dyr(pid_hydro_record(model,1),version=version).records[0]
    if model == 'PIDGOVDU':
        assert record.status == RecordStatus.VALID
        assert record.user_header is not None and record.user_header.state_count == 7
        assert record.user_header.variable_count == 2 and record.user_header.icon_count == 1
        assert (record.user_schema is not None) == (version == 33)
    elif model == 'PIDGOVD' and version in (33,34):
        assert record.status == RecordStatus.UNSUPPORTED
    else:
        assert record.status == RecordStatus.VALID
        assert record.icons == (1,)
        assert len(record.parameters) == (20 if model == 'PIDGOV' else 23)


@pytest.mark.parametrize('model,version',(('PIDGOV',33),('PIDGOV',34),('PIDGOV',35),('PIDGOV',36),('PIDGOVD',35),('PIDGOVD',36),('PIDGOVDU',33)))
@pytest.mark.parametrize('feedback',(0,1))
@pytest.mark.parametrize('runtime',(False,True))
def test_pid_hydro_actual_machine_equilibrium(model: str, version: int, feedback: int, runtime: bool) -> None:
    """Both feedback modes preserve separate loss-adjusted mechanical and electrical operating points on the selected turbine base.

    :param model: Exact source identifier.
    :param version: Reviewed source release.
    :param feedback: Physical droop feedback selection.
    :param runtime: Inspect runtime duplication or stored graph.
    """
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',
        pid_hydro_record(model,feedback,0. if model == 'PIDGOV' else 75.),runtime,version=version)
