# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Shared configuration and reproducible fixtures for the FMI test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.FMI.fmi_three_compiled_fixture import (
    FmiThreeCompiledFixtureProfile,
    build_fmi_three_co_simulation_fmu,
    derive_fmi_three_model_exchange_fmu_without_checkpoint,
    resolve_fmi_three_test_cmake_executable,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the CI gate for mandatory host-native FMI builds.

    Developer machines may omit the native smoke test when the CMake package
    or a usable compiler is unavailable. The FMI workflow enables this option
    so loss of any Windows, Linux, or macOS toolchain fails the job instead of
    producing a misleading green skip.

    :param parser: Pytest command-line parser for the current test session.
    :return: None.
    """

    fmi_option_group: pytest.OptionGroup = parser.getgroup("FMI")
    compiler_name: str
    for compiler_name in ("gcc", "clang", "msvc"):
        fmi_option_group.addoption(
            "--fmi-test-" + compiler_name,
            default=None,
            help="Use an already installed " + compiler_name + " executable for builtin FMU qualification.",
        )
    fmi_option_group.addoption(
        "--require-fmi-three-native-build",
        action="store_true",
        default=False,
        help="Fail when the host cannot compile the generated FMI 3 test FMU.",
    )


def _build_compiled_fmi_three_fixture(
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
    fixture_profile: FmiThreeCompiledFixtureProfile,
    temporary_directory_prefix: str,
) -> Path:
    """Build one selected host-native FMI 3 FMU for session fixtures.

    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :param pytestconfig: Active pytest configuration containing the CI build gate.
    :param fixture_profile: Deterministic behavior selected for compilation.
    :param temporary_directory_prefix: Distinct pytest build-directory prefix.
    :return: Temporary source-bearing FMU with the current-host binary inside.
    """

    work_directory: Path = tmp_path_factory.mktemp(temporary_directory_prefix)
    native_build_required: bool = bool(
        pytestconfig.getoption("require_fmi_three_native_build")
    )
    cmake_executable: Path | None = resolve_fmi_three_test_cmake_executable()
    if cmake_executable is not None:
        pass
    else:
        if native_build_required:
            raise AssertionError(
                "The FMI workflow requires the environment-owned CMake "
                "executable used by the FMI fixture"
            )
        else:
            pytest.skip(
                "The local Python environment does not contain the FMI fixture CMake executable"
            )
    compiled_fmu_path: Path | None
    configure_diagnostic: str | None
    # Each native phase receives five minutes, leaving half of the twenty-minute
    # CI job for setup, process teardown, packaging, and the Python test suite.
    cmake_command_timeout_seconds: float = 300.0
    termination_grace_seconds: float = 10.0
    compiled_fmu_path, configure_diagnostic = build_fmi_three_co_simulation_fmu(
        work_directory=work_directory,
        cmake_executable=cmake_executable,
        cmake_command_timeout_seconds=cmake_command_timeout_seconds,
        termination_grace_seconds=termination_grace_seconds,
        fixture_profile=fixture_profile,
    )
    if compiled_fmu_path is not None:
        if configure_diagnostic is None:
            pass
        else:
            raise AssertionError(
                "The FMI 3 fixture returned an unexpected configure diagnostic after success"
            )
        return compiled_fmu_path
    else:
        if configure_diagnostic is not None:
            pass
        else:
            raise AssertionError(
                "The FMI 3 fixture returned no FMU and no configure diagnostic"
            )
        if native_build_required:
            raise AssertionError(
                "The FMI workflow could not configure its required C compiler:\n"
                f"{configure_diagnostic}"
            )
        else:
            pytest.skip(
                "The local C compiler could not be configured:\n"
                f"{configure_diagnostic}"
            )


@pytest.fixture(scope="session")
def compiled_fmi_three_scalar_co_simulation_fmu(
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
) -> Path:
    """Build the scalar host-native FMI 3 fixture once per test session.

    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :param pytestconfig: Active pytest configuration containing the CI build gate.
    :return: Temporary scalar FMU with the current-host binary inside.
    """

    return _build_compiled_fmi_three_fixture(
        tmp_path_factory=tmp_path_factory,
        pytestconfig=pytestconfig,
        fixture_profile=FmiThreeCompiledFixtureProfile.SCALAR,
        temporary_directory_prefix="fmi-three-native-scalar-fixture",
    )


@pytest.fixture(scope="session")
def compiled_fmi_three_scalar_model_exchange_without_checkpoint_fmu(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Derive the scalar fixture without optional ME checkpoint capability.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Compiled scalar source
        whose native equations remain unchanged.
    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :return: Scalar Model Exchange FMU declaring no state checkpoints.
    """

    work_directory: Path = tmp_path_factory.mktemp(
        "fmi-three-scalar-me-no-checkpoint"
    )
    return derive_fmi_three_model_exchange_fmu_without_checkpoint(
        source_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        work_directory=work_directory,
    )


@pytest.fixture(scope="session")
def compiled_fmi_three_state_leak_model_exchange_fmu(
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
) -> Path:
    """Build the adversarial scalar ME fixture without checkpoint support.

    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :param pytestconfig: Active pytest configuration containing the CI build gate.
    :return: Native Model Exchange FMU with observable hidden-state leakage.
    """

    compiled_source_fmu_path: Path = _build_compiled_fmi_three_fixture(
        tmp_path_factory=tmp_path_factory,
        pytestconfig=pytestconfig,
        fixture_profile=(
            FmiThreeCompiledFixtureProfile.SCALAR_OBSERVABLE_STATE_LEAK
        ),
        temporary_directory_prefix="fmi-three-native-state-leak-fixture",
    )
    work_directory: Path = tmp_path_factory.mktemp(
        "fmi-three-state-leak-me-no-checkpoint"
    )
    return derive_fmi_three_model_exchange_fmu_without_checkpoint(
        source_fmu_path=compiled_source_fmu_path,
        work_directory=work_directory,
    )


@pytest.fixture(scope="session")
def compiled_fmi_three_constant_array_co_simulation_fmu(
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
) -> Path:
    """Build the constant-array host-native FMI 3 fixture once per session.

    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :param pytestconfig: Active pytest configuration containing the CI build gate.
    :return: Temporary array FMU with the current-host binary inside.
    """

    return _build_compiled_fmi_three_fixture(
        tmp_path_factory=tmp_path_factory,
        pytestconfig=pytestconfig,
        fixture_profile=FmiThreeCompiledFixtureProfile.CONSTANT_ARRAY,
        temporary_directory_prefix="fmi-three-native-array-fixture",
    )


@pytest.fixture(scope="session")
def compiled_fmi_three_configurable_array_co_simulation_fmu(
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
) -> Path:
    """Build the configurable-array FMI 3 fixture once per test session.

    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :param pytestconfig: Active pytest configuration containing the CI build gate.
    :return: Temporary configurable-array FMU with the current-host binary.
    """

    return _build_compiled_fmi_three_fixture(
        tmp_path_factory=tmp_path_factory,
        pytestconfig=pytestconfig,
        fixture_profile=FmiThreeCompiledFixtureProfile.CONFIGURABLE_ARRAY,
        temporary_directory_prefix="fmi-three-native-configurable-array-fixture",
    )


@pytest.fixture(scope="session")
def compiled_fmi_three_parameterized_configurable_array_fmu(
    tmp_path_factory: pytest.TempPathFactory,
    pytestconfig: pytest.Config,
) -> Path:
    """Build the parameterized configurable-array FMI 3 fixture once.

    :param tmp_path_factory: Session-scoped pytest temporary-directory factory.
    :param pytestconfig: Active pytest configuration containing the CI build gate.
    :return: Temporary dual-interface FMU with observable scalar parameters.
    """

    return _build_compiled_fmi_three_fixture(
        tmp_path_factory=tmp_path_factory,
        pytestconfig=pytestconfig,
        fixture_profile=(
            FmiThreeCompiledFixtureProfile.PARAMETERIZED_CONFIGURABLE_ARRAY
        ),
        temporary_directory_prefix=(
            "fmi-three-native-parameterized-configurable-array-fixture"
        ),
    )
