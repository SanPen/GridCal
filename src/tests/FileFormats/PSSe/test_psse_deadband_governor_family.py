# SPDX-License-Identifier: MPL-2.0
"""Direct and legacy gas, steam and nonlinear hydraulic deadband governor contracts."""
from __future__ import annotations

import pytest
from VeraGridEngine.IO.raw.dyr_parser import parse_dyr
from VeraGridEngine.IO.raw.dyr_to_veragrid import dynamic_record_name
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.raw_to_veragrid import psse_to_veragrid
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord, RawDyr
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from tests.FileFormats.PSSe.test_psse_auxiliary_conversion import (
    make_raw_case,test_adapter_initializes_at_a_real_power_flow_equilibrium as check_equilibrium)


def family_record(model: str, rating: float = 0.) -> str:
    """Build one exact direct or legacy allocation header with physical settings from the family sheets.

    :param model: Source model or user-subroutine identifier.
    :param rating: Positive turbine rating or zero machine-base selection.
    :return: Complete slash-terminated source assignment.
    """
    contracts: dict[str,tuple[str,str]] = dict(GASTD=('GAST',''),GASTDU=('GAST','5 0 0 12 3 2'),
        IEESGOD=('IEESGO',''),IEESGODU=('IEESGO','5 0 0 14 5 2'),
        HYGOVD=('HYGOV',''),HYGOVDU=('HYGOV','5 0 0 15 4 3'),
        TGOV1D=('TGOV1',''),TGOV1DU=('TGOV1','5 0 0 10 2 2'))
    family, allocation = contracts[model]
    constants: str
    if family == 'GAST':
        constants = '.05 .1 .4 3 1 2 1.2 0 2'
    elif family == 'IEESGO':
        constants = '.1 .02 .2 .3 5 .5 20 .6 .5 1.2 0'
    elif family == 'HYGOV':
        constants = '.05 .3 5 .05 .5 .2 1.2 0 1 1 .7 .08'
    else:
        constants = '.05 .1 1.2 0 .2 10 2'
    header: str = f"1 'USRMDL' '01' '{model}' {allocation}" if allocation else f"1 '{model}' '01'"
    return header+' '+constants+f' .002 -.003 {rating} /'


@pytest.mark.parametrize('model,count',(('GASTD',12),('IEESGOD',14),('HYGOVD',15),('TGOV1D',10)))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_direct_family_layouts_are_release_specific(model: str, count: int, version: int) -> None:
    """Direct built-ins use the supplied 35 layout without inventing equivalent older grammar.

    :param model: Direct source identifier.
    :param count: Exact CON allocation.
    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(family_record(model),version=version).records[0]
    assert record.status == (RecordStatus.VALID if version in (35,36) else RecordStatus.UNSUPPORTED)
    if version in (35,36):
        assert len(record.parameters) == count
        assert tuple(parameter.name for parameter in record.parameters)[-3:] == ('DBH','DBL','TRATE')
    else:
        assert not record.parameters


@pytest.mark.parametrize('model,states,variables',(('GASTDU',3,2),('IEESGODU',5,2),('HYGOVDU',4,3),('TGOV1DU',2,2)))
@pytest.mark.parametrize('version',(33,34,35,36))
def test_legacy_family_contracts_are_release_owned(model: str, states: int, variables: int, version: int) -> None:
    """Legacy headers preserve original identities and acquire a conversion schema only in the reviewed release.

    :param model: Source user-subroutine name.
    :param states: NS allocation.
    :param variables: NV allocation.
    :param version: Explicit parser profile.
    """
    record: DyrRecord = parse_dyr(family_record(model),version=version).records[0]
    assert record.status == RecordStatus.VALID
    assert record.model == 'USRMDL' and record.user_header is not None
    assert record.user_header.name == model
    assert record.user_header.state_count == states and record.user_header.variable_count == variables
    if version == 33:
        assert record.user_schema is not None
        assert dynamic_record_name(record) == model
    else:
        assert record.user_schema is None
        assert dynamic_record_name(record) == 'USRMDL'


@pytest.mark.parametrize('model,version',(('GASTD',35),('GASTDU',33),('IEESGOD',35),('IEESGODU',33),
    ('HYGOVD',35),('HYGOVDU',33),('TGOV1D',35),('TGOV1DU',33)))
@pytest.mark.parametrize('rating',(0.,75.))
@pytest.mark.parametrize('runtime',(False,True))
def test_family_machine_and_turbine_base_equilibrium(model: str, version: int, rating: float, runtime: bool) -> None:
    """Every family preserves actual loss-adjusted initial mechanical power, reference units and duplicated runtime equations.

    :param model: Source built-in or user-subroutine identity.
    :param version: Reviewed source profile.
    :param rating: Turbine rating or machine-base selection.
    :param runtime: Check runtime duplication instead of the stored graph.
    """
    check_equilibrium('GENSAE','8 .03 .05 4 2 1.8 1.7 .3 .25 .2 .09 .38',
        family_record(model,rating),runtime,version=version)


@pytest.mark.parametrize('model,version',(('GASTD',35),('GASTDU',33),('IEESGOD',35),('IEESGODU',33),
    ('HYGOVD',35),('HYGOVDU',33),('TGOV1D',35),('TGOV1DU',33)))
@pytest.mark.parametrize('bad_rating',(False,True))
def test_invalid_family_domain_blocks_whole_host(model: str, version: int, bad_rating: bool) -> None:
    """Invalid rating or reversed deadband signs remain inspectable and cannot install a partially governed machine.

    :param model: Source family member.
    :param version: Reviewed profile.
    :param bad_rating: Negative rating rather than positive underspeed threshold.
    """
    case: PsseCircuit = make_raw_case()
    case.REV = version
    record_text: str = family_record(model,-1. if bad_rating else 0.)
    if not bad_rating:
        record_text = record_text.replace('-.003','.003')
    else:
        pass
    assert case.add_auxiliary(parse_dyr("1 'GENROU' '01' 8 .03 .4 .05 4 2 1.8 1.7 .3 .55 .25 .2 .09 .38 /\n"+record_text,version=version))
    grid: MultiCircuit = psse_to_veragrid(case,logger=Logger())
    assert grid.generators[0].rms_template is None


@pytest.mark.parametrize('replacement',("'URSMDL'","'HYDGOVDU'"))
def test_printed_header_typos_do_not_become_automatic_aliases(replacement: str) -> None:
    """Known documentation spelling errors remain unreviewed rather than broadening the source grammar.

    :param replacement: Misspelled keyword or subroutine from older printed examples.
    """
    text: str = family_record('HYGOVDU')
    text = text.replace("'USRMDL'",replacement,1) if replacement == "'URSMDL'" else text.replace("'HYGOVDU'",replacement,1)
    document: RawDyr = parse_dyr(text,version=33)
    assert document.records[0].user_schema is None
