# SPDX-License-Identifier: MPL-2.0
"""Separate source contracts for additive, multiplicative and gated compound excitation."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import validate_dynamic_parameters
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium


@pytest.mark.parametrize('model',('EXST2','EXST2A','ESST2A'))
@pytest.mark.parametrize('version',(33,34,35,36))
@pytest.mark.parametrize('runtime',(False,True))
@pytest.mark.parametrize('independent',(False,True))
def test_compound_family_release_layout_and_equilibrium(model: str, version: int, runtime: bool, independent: bool) -> None:
    """Every distinct identity initializes its coupling from actual machine field and terminal phasors.

    :param model: Explicit source identifier.
    :param version: Parser profile.
    :param runtime: Inspect duplicated runtime rather than stored graph.
    :param independent: Select the documented KP=KI=0 unit supply.
    """
    source: str = f"1 '{model}' '01' .02 20 .05 5 -5 1 .5 .05 1 "+('0 0' if independent else '1 .1')+' .1 5 /'
    record: DyrRecord = parse_dyr(source,version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert tuple(parameter.name for parameter in record.parameters) == ('TR','KA','TA','VRMAX','VRMIN','KE','TE','KF','TF','KP','KI','KC','EFDMAX')
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime,version=version)


@pytest.mark.parametrize('model',('EXST2','EXST2A','ESST2A'))
def test_unreviewed_compound_source_calibration_is_rejected(model: str) -> None:
    """A zero current-gain selector with enabled potential supply must not become a physical zero gain.

    :param model: Source model whose automatic compounding rule remains unreviewed.
    """
    record: DyrRecord = parse_dyr(f"1 '{model}' '01' .02 20 .05 5 -5 1 .5 .05 1 1 0 .1 5 /",version=35).records[0]
    with pytest.raises(ValueError,match='calibration has not been reviewed'):
        validate_dynamic_parameters(record)


@pytest.mark.parametrize('model',('EXST2','EXST2A','ESST2A'))
@pytest.mark.parametrize('runtime',(False,True))
def test_compound_family_connects_stabilizer_and_minimum_excitation(model: str, runtime: bool) -> None:
    """Source additive and gated minimum-excitation paths preserve host equilibrium with a live stabilizer.

    :param model: Explicit source bridge/limiter identity.
    :param runtime: Inspect duplicated runtime or stored equations.
    """
    source: str = f"1 '{model}' '01' .02 20 .05 5 -5 1 .5 .05 1 1 .1 .1 5 /\n"+"1 'STABNI' '01' 1 .1 .2 .01 .1 /\n1 'MNLEX1' '01' .1 1 2 .2 .1 1 /"
    check_equilibrium('GENROU','8 .03 .4 .05 4 0 1.8 1.7 .3 .55 .2 .15 .08 .3',source,runtime)
