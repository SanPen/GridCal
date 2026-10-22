"""Exercise optional-backend startup in fresh interpreters without a native solver."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


def write_backend_fixture(folder: Path, version: str, licensed: bool, missing_api: bool) -> None:
    """Write a minimal backend with explicit enum exports and license discovery.

    :param folder: Isolated import directory.
    :param version: Reported backend version.
    :param licensed: Whether activation finds a license.
    :param missing_api: Omit the battery API to reproduce an incomplete installation.
    :return: None.
    """
    source: str = (
        'from enum import Enum\nfrom pathlib import Path\n'
        f'def get_version() -> str:\n    return {version!r}\n'
        'def search_license_and_activate(verbose: bool) -> None:\n'
        '    Path("activation_called").touch()\n'
        f'def isLicensed() -> bool:\n    return {licensed!r}\n'
    )
    # List the public API explicitly so successful startup tests real mapping construction.
    enums: tuple[str, ...] = (
        'BuildStatus Planned Commissioned Candidate Decommissioned PlannedDecommission',
        'TapModuleControl fixed Qf Qt Vm',
        'TapPhaseControl fixed Pf Pt',
        'GeneratorControlMode Q V QVDroop',
        'RemedialActionPropertyEnum Vmin Vmax Loading ContingencyLoading',
        'HvdcControlType type_0_free type_1_Pset',
        'BranchGroupTypes GenericGroup TransformerGroup LineSegmentsGroup',
        'ContingencyOperationTypes Active PowerPercentage',
        'ContingencyMethod PTDF PowerFlow HELM',
        'ConverterControlType Vm_dc Vm_ac Va_ac Q_ac P_dc P_ac P_dc_angle_droop P_dc_droop '
        'Q_droop P_droop Imax Fault1 Fault2',
        'BusMode PQ PV Slack P PQV',
        'ShuntConnectionType GroundedStar FloatingStar NeutralStar Delta',
        'WindingType GroundedStar NeutralStar Delta ZigZag',
        'WindingsConnection GG GS GD SS SD DD',
    )
    for definition in enums:
        name: str
        members: str
        name, members = definition.split(' ', 1)
        source += f'{name} = Enum({name!r}, {members!r})\n'
    if missing_api:
        pass
    else:
        source += (
            'BatteryDispatchMode = Enum("BatteryDispatchMode", '
            '"Grid PlantChargeGridDischarge PlantChargeAndDisCharge")\n'
        )
    (folder / 'pygslv.py').write_text(source)


@pytest.mark.parametrize(
    'scenario, version, licensed, missing_api, expected_reason, available',
    (
        ('absent', '', False, False, 'not installed', False),
        ('binary_failure', '', False, False, 'native library failed', False),
        ('old', '0.9.4', True, True, 'requires pygslv >= 1.0.0', False),
        ('prerelease', '1.0.0rc1', True, False, 'requires pygslv >= 1.0.0', False),
        ('invalid', 'broken', True, False, 'Invalid version', False),
        ('unlicensed', '1.0.0', False, True, 'no valid license', False),
        ('activation_failure', '1.0.0', False, False, 'license discovery failed', False),
        ('missing_api', '1.0.0', True, True, 'BatteryDispatchMode', False),
        ('compatible', '1.0.0', True, False, '', True),
        ('newer', '1.1.0', True, False, '', True),
    ),
)
def test_backend_startup(
        tmp_path: Path, scenario: str, version: str, licensed: bool,
        missing_api: bool, expected_reason: str, available: bool,
) -> None:
    """Import the complete engine against absent, old, and supported backend APIs.

    :param tmp_path: Isolated import directory.
    :param scenario: Backend installation condition.
    :param version: Backend version.
    :param licensed: License availability.
    :param missing_api: Whether required API symbols are absent.
    :param expected_reason: Required diagnostic fragment.
    :param available: Expected dispatch availability.
    :return: None.
    """
    if scenario == 'absent':
        (tmp_path / 'pygslv.py').write_text(
            'raise ModuleNotFoundError("No module named pygslv", name="pygslv")\n'
        )
    elif scenario == 'binary_failure':
        (tmp_path / 'pygslv.py').write_text('raise OSError("native library failed")\n')
    else:
        write_backend_fixture(tmp_path, version, licensed, missing_api)
        if scenario == 'activation_failure':
            with (tmp_path / 'pygslv.py').open('a') as fixture_file:
                fixture_file.write(
                    'def search_license_and_activate(verbose: bool) -> None:\n'
                    '    raise RuntimeError("license discovery failed")\n'
                )
        else:
            pass
    source_root: Path = Path(__file__).resolve().parents[2]
    script: str = (
        'import sys, json\n'
        f'sys.path.insert(0, {str(source_root)!r})\n'
        f'sys.path.insert(0, {str(tmp_path)!r})\n'
        'import VeraGridEngine.api\n'
        'from VeraGridEngine.Compilers.Gslv import activation as a\n'
        'if not a.GSLV_AVAILABLE:\n'
        '    assert a.pg is None\n'
        '    assert all(not value for name, value in vars(a).items() if name.endswith("_dict"))\n'
        '    try:\n'
        '        import VeraGridEngine.Utils.MIP.gslv_interface\n'
        '    except ImportError as error:\n'
        '        assert a.GSLV_UNAVAILABLE_REASON in str(error)\n'
        '    else:\n'
        '        raise AssertionError("Unavailable backend bypassed the activation gate")\n'
        'else:\n'
        '    assert len(a.battery_dispatch_mode_dict) == 3\n'
        'print(json.dumps([a.GSLV_AVAILABLE, a.GSLV_VERSION, a.GSLV_UNAVAILABLE_REASON]))\n'
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    status: list[object] = json.loads(result.stdout.splitlines()[-1])
    assert status[0] is available
    assert status[1] == version
    assert expected_reason in status[2]
    assert (tmp_path / 'activation_called').exists() == (
        scenario in ('unlicensed', 'missing_api', 'compatible', 'newer')
    )
    if scenario == 'absent':
        assert 'GSLV disabled' not in result.stderr
    elif available:
        assert status[2] == ''
        assert 'GSLV disabled' not in result.stderr
    else:
        assert 'GSLV disabled' in result.stderr
        assert expected_reason in result.stderr
