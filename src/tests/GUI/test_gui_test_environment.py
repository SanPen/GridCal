from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest


def test_gui_collection_preserves_process_temp_configuration(
        request: pytest.FixtureRequest,
        tmp_path: Path,
) -> None:
    """
    Verify that GUI collection does not claim process-wide temporary paths.

    :param request: Pytest request exposing the final session configuration.
    :param tmp_path: Per-test path used to leave an ownership sentinel.
    :return: None.
    """
    gui_owner_marker: str = "veragrid-pytest-gui"
    protected_variable_names: tuple[str, ...] = (
        "TMP", "TEMP", "HOME", "USERPROFILE",
    )
    observed_paths: list[str] = list()

    # Missing host variables are valid; present values must remain outside the
    # retired GUI-owned test directory.
    variable_name: str
    for variable_name in protected_variable_names:
        variable_value: str | None = os.environ.get(variable_name, None)
        if variable_value is None:
            pass
        else:
            observed_paths.append(variable_value)

    process_temp_path: str = tempfile.gettempdir()
    observed_paths.append(process_temp_path)

    configured_base_temp: str | None = request.config.option.basetemp
    if sys.platform.startswith("win"):
        assert configured_base_temp is not None
        repository_anchor: str = Path(request.config.rootpath).resolve().anchor.casefold()
        configured_anchor: str = Path(configured_base_temp).resolve().anchor.casefold()
        assert configured_anchor == repository_anchor
    else:
        pass

    if configured_base_temp is None:
        pass
    else:
        observed_paths.append(configured_base_temp)
        sentinel_path: Path = tmp_path / "owner-sentinel.txt"
        sentinel_path.touch()
        print(
            f"veragrid_pytest_basetemp pid={os.getpid()} path={configured_base_temp} sentinel={sentinel_path}"
        )

    observed_path: str
    for observed_path in observed_paths:
        assert gui_owner_marker not in observed_path.casefold()
