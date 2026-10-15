# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Execute and verify the independent FMI.jl SMIB composition."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import TextIO
import uuid

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import matplotlib.image as mpimg
import numpy as np

from examples.fmi.evidence_identity import (
    verify_regular_file_identity,
)


class FmiJlComparisonConfig:
    """Own every explicit input and bound of one FMI.jl comparison."""

    __slots__ = (
        "output_directory", "source_branch", "source_revision",
        "source_tree_sha256", "wsl_executable_path",
        "wsl_executable_size_bytes", "wsl_executable_sha256",
        "wsl_distribution", "wsl_version", "wsl_distribution_pretty_name",
        "wsl_distribution_version_id", "wsl_architecture", "wsl_kernel",
        "wsl_glibc_version", "wsl_python_executable_path",
        "wsl_python_executable_size_bytes", "wsl_python_executable_sha256",
        "wsl_python_version", "julia_archive_path", "julia_archive_size_bytes",
        "julia_archive_sha256", "julia_executable_path",
        "julia_executable_size_bytes", "julia_executable_sha256",
        "julia_runtime_entry_count", "julia_runtime_regular_bytes",
        "julia_runtime_tree_sha256",
        "julia_project_path", "julia_project_size_bytes",
        "julia_project_sha256", "julia_manifest_path",
        "julia_manifest_size_bytes", "julia_manifest_sha256",
        "julia_depot_path", "julia_depot_entry_count",
        "julia_depot_regular_bytes", "julia_depot_tree_sha256",
        "wsl_home", "julia_version", "fmi_jl_version",
        "runner_path", "runner_size_bytes", "runner_sha256",
        "plant_fmu_path", "plant_fmu_size_bytes",
        "plant_fmu_sha256", "governor_fmu_path", "governor_fmu_size_bytes",
        "governor_fmu_sha256", "reference_manifest_path",
        "reference_manifest_size_bytes", "reference_manifest_sha256",
        "process_timeout_seconds", "stream_limit_bytes",
    )

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        wsl_executable_path: Path,
        wsl_executable_size_bytes: int,
        wsl_executable_sha256: str,
        wsl_distribution: str,
        wsl_version: str,
        wsl_distribution_pretty_name: str,
        wsl_distribution_version_id: str,
        wsl_architecture: str,
        wsl_kernel: str,
        wsl_glibc_version: str,
        wsl_python_executable_path: Path,
        wsl_python_executable_size_bytes: int,
        wsl_python_executable_sha256: str,
        wsl_python_version: str,
        julia_archive_path: Path,
        julia_archive_size_bytes: int,
        julia_archive_sha256: str,
        julia_executable_path: Path,
        julia_executable_size_bytes: int,
        julia_executable_sha256: str,
        julia_runtime_entry_count: int,
        julia_runtime_regular_bytes: int,
        julia_runtime_tree_sha256: str,
        julia_project_path: Path,
        julia_project_size_bytes: int,
        julia_project_sha256: str,
        julia_manifest_path: Path,
        julia_manifest_size_bytes: int,
        julia_manifest_sha256: str,
        julia_depot_path: Path,
        julia_depot_entry_count: int,
        julia_depot_regular_bytes: int,
        julia_depot_tree_sha256: str,
        wsl_home: str,
        julia_version: str,
        fmi_jl_version: str,
        runner_path: Path,
        runner_size_bytes: int,
        runner_sha256: str,
        plant_fmu_path: Path,
        plant_fmu_size_bytes: int,
        plant_fmu_sha256: str,
        governor_fmu_path: Path,
        governor_fmu_size_bytes: int,
        governor_fmu_sha256: str,
        reference_manifest_path: Path,
        reference_manifest_size_bytes: int,
        reference_manifest_sha256: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Validate and retain one closed FMI.jl execution configuration.

        :param output_directory: New external evidence package directory.
        :param source_branch: Recorded source branch.
        :param source_revision: Recorded 40-character source revision.
        :param source_tree_sha256: Recorded source-tree SHA-256.
        :param wsl_executable_path: Explicit Windows WSL executable.
        :param wsl_executable_size_bytes: Expected WSL executable size.
        :param wsl_executable_sha256: Expected WSL executable digest.
        :param wsl_distribution: Explicit WSL distribution name.
        :param wsl_version: Required installed WSL version.
        :param wsl_distribution_pretty_name: Required Linux distribution label.
        :param wsl_distribution_version_id: Required Linux distribution version.
        :param wsl_architecture: Required WSL machine architecture.
        :param wsl_kernel: Required WSL kernel release.
        :param wsl_glibc_version: Required GNU C library version.
        :param wsl_python_executable_path: Authenticated WSL Python executable.
        :param wsl_python_executable_size_bytes: Expected Python executable size.
        :param wsl_python_executable_sha256: Expected Python executable digest.
        :param wsl_python_version: Required Python interpreter version.
        :param julia_archive_path: Authenticated Julia release archive.
        :param julia_archive_size_bytes: Expected Julia archive size.
        :param julia_archive_sha256: Expected Julia archive digest.
        :param julia_executable_path: Julia executable exposed through WSL UNC.
        :param julia_executable_size_bytes: Expected Julia executable size.
        :param julia_executable_sha256: Expected Julia executable digest.
        :param julia_runtime_entry_count: Expected runtime entry count.
        :param julia_runtime_regular_bytes: Expected runtime regular-file bytes.
        :param julia_runtime_tree_sha256: Expected complete runtime tree digest.
        :param julia_project_path: Isolated Project.toml path.
        :param julia_project_size_bytes: Expected project size.
        :param julia_project_sha256: Expected project digest.
        :param julia_manifest_path: Isolated Manifest.toml path.
        :param julia_manifest_size_bytes: Expected manifest size.
        :param julia_manifest_sha256: Expected manifest digest.
        :param julia_depot_path: Existing isolated Julia depot exposed by UNC.
        :param julia_depot_entry_count: Expected source-depot entry count.
        :param julia_depot_regular_bytes: Expected source-depot regular bytes.
        :param julia_depot_tree_sha256: Expected complete source-depot digest.
        :param wsl_home: Explicit child-process HOME inside WSL.
        :param julia_version: Required Julia version.
        :param fmi_jl_version: Required FMI.jl version.
        :param runner_path: Repository-owned Julia runner.
        :param runner_size_bytes: Expected Julia runner size.
        :param runner_sha256: Expected Julia runner digest.
        :param plant_fmu_path: Authenticated plant FMU.
        :param plant_fmu_size_bytes: Expected plant FMU size.
        :param plant_fmu_sha256: Expected plant FMU digest.
        :param governor_fmu_path: Authenticated governor FMU.
        :param governor_fmu_size_bytes: Expected governor FMU size.
        :param governor_fmu_sha256: Expected governor FMU digest.
        :param reference_manifest_path: Sealed VeraGrid reference manifest.
        :param reference_manifest_size_bytes: Expected reference manifest size.
        :param reference_manifest_sha256: Expected reference manifest digest.
        :param process_timeout_seconds: Hard native-process deadline.
        :param stream_limit_bytes: Independent stdout and stderr limit.
        :return: None.
        """

        explicit_paths: tuple[Path, ...] = (
            output_directory, wsl_executable_path, julia_archive_path,
            wsl_python_executable_path, julia_executable_path,
            julia_project_path, julia_manifest_path,
            julia_depot_path, runner_path, plant_fmu_path, governor_fmu_path,
            reference_manifest_path,
        )
        sizes: tuple[int, ...] = (
            wsl_executable_size_bytes, julia_archive_size_bytes,
            wsl_python_executable_size_bytes, julia_executable_size_bytes,
            julia_project_size_bytes,
            julia_manifest_size_bytes, plant_fmu_size_bytes,
            governor_fmu_size_bytes, reference_manifest_size_bytes,
            runner_size_bytes, julia_runtime_entry_count,
            julia_runtime_regular_bytes, julia_depot_entry_count,
            julia_depot_regular_bytes,
        )
        digests: tuple[str, ...] = (
            wsl_executable_sha256, julia_archive_sha256,
            wsl_python_executable_sha256, julia_executable_sha256,
            julia_runtime_tree_sha256, julia_project_sha256,
            julia_manifest_sha256, plant_fmu_sha256, governor_fmu_sha256,
            reference_manifest_sha256, runner_sha256, julia_depot_tree_sha256,
        )
        values_are_valid: bool = bool(
            all(isinstance(path_value, Path) and path_value.is_absolute()
                for path_value in explicit_paths)
            and all(type(size_value) is int and size_value > 0 for size_value in sizes)
            and all(re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                    for digest in digests)
            and len(source_branch) > 0
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and re.fullmatch(r"[0-9a-f]{64}", source_tree_sha256) is not None
            and wsl_distribution == "Ubuntu"
            and wsl_version == "2.6.3.0"
            and wsl_distribution_pretty_name == "Ubuntu 24.04.4 LTS"
            and wsl_distribution_version_id == "24.04"
            and wsl_architecture == "x86_64"
            and wsl_kernel == "6.6.87.2-microsoft-standard-WSL2"
            and wsl_glibc_version == "2.39"
            and wsl_python_version == "3.12.3"
            and julia_runtime_entry_count == 6143
            and julia_runtime_regular_bytes == 1_058_601_669
            and julia_depot_entry_count == 4527
            and julia_depot_regular_bytes == 221_392_845
            and wsl_home == "/home/andres"
            and julia_version == "1.12.6"
            and fmi_jl_version == "0.15.2"
            and float(process_timeout_seconds) == 120.0
            and stream_limit_bytes == 1_048_576
        )
        if values_are_valid:
            pass
        else:
            raise ValueError("FMI.jl configuration is incomplete or invalid")
        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.wsl_executable_path: Path = wsl_executable_path
        self.wsl_executable_size_bytes: int = wsl_executable_size_bytes
        self.wsl_executable_sha256: str = wsl_executable_sha256
        self.wsl_distribution: str = wsl_distribution
        self.wsl_version: str = wsl_version
        self.wsl_distribution_pretty_name: str = wsl_distribution_pretty_name
        self.wsl_distribution_version_id: str = wsl_distribution_version_id
        self.wsl_architecture: str = wsl_architecture
        self.wsl_kernel: str = wsl_kernel
        self.wsl_glibc_version: str = wsl_glibc_version
        self.wsl_python_executable_path: Path = wsl_python_executable_path
        self.wsl_python_executable_size_bytes: int = (
            wsl_python_executable_size_bytes
        )
        self.wsl_python_executable_sha256: str = wsl_python_executable_sha256
        self.wsl_python_version: str = wsl_python_version
        self.julia_archive_path: Path = julia_archive_path
        self.julia_archive_size_bytes: int = julia_archive_size_bytes
        self.julia_archive_sha256: str = julia_archive_sha256
        self.julia_executable_path: Path = julia_executable_path
        self.julia_executable_size_bytes: int = julia_executable_size_bytes
        self.julia_executable_sha256: str = julia_executable_sha256
        self.julia_runtime_entry_count: int = julia_runtime_entry_count
        self.julia_runtime_regular_bytes: int = julia_runtime_regular_bytes
        self.julia_runtime_tree_sha256: str = julia_runtime_tree_sha256
        self.julia_project_path: Path = julia_project_path
        self.julia_project_size_bytes: int = julia_project_size_bytes
        self.julia_project_sha256: str = julia_project_sha256
        self.julia_manifest_path: Path = julia_manifest_path
        self.julia_manifest_size_bytes: int = julia_manifest_size_bytes
        self.julia_manifest_sha256: str = julia_manifest_sha256
        self.julia_depot_path: Path = julia_depot_path
        self.julia_depot_entry_count: int = julia_depot_entry_count
        self.julia_depot_regular_bytes: int = julia_depot_regular_bytes
        self.julia_depot_tree_sha256: str = julia_depot_tree_sha256
        self.wsl_home: str = wsl_home
        self.julia_version: str = julia_version
        self.fmi_jl_version: str = fmi_jl_version
        self.runner_path: Path = runner_path
        self.runner_size_bytes: int = runner_size_bytes
        self.runner_sha256: str = runner_sha256
        self.plant_fmu_path: Path = plant_fmu_path
        self.plant_fmu_size_bytes: int = plant_fmu_size_bytes
        self.plant_fmu_sha256: str = plant_fmu_sha256
        self.governor_fmu_path: Path = governor_fmu_path
        self.governor_fmu_size_bytes: int = governor_fmu_size_bytes
        self.governor_fmu_sha256: str = governor_fmu_sha256
        self.reference_manifest_path: Path = reference_manifest_path
        self.reference_manifest_size_bytes: int = reference_manifest_size_bytes
        self.reference_manifest_sha256: str = reference_manifest_sha256
        self.process_timeout_seconds: float = float(process_timeout_seconds)
        self.stream_limit_bytes: int = stream_limit_bytes


class FmiJlProcessResult:
    """Own one bounded Julia process result."""

    __slots__ = ("exit_code", "stdout_text", "stderr_text")

    def __init__(self, exit_code: int, stdout_text: str, stderr_text: str) -> None:
        """Retain decoded process streams.

        :param exit_code: Native exit code.
        :param stdout_text: Strict UTF-8 stdout.
        :param stderr_text: Strict UTF-8 stderr.
        :return: None.
        """

        self.exit_code: int = exit_code
        self.stdout_text: str = stdout_text
        self.stderr_text: str = stderr_text


class FmiJlTreeIdentity:
    """Own one complete WSL tree identity including links and directories."""

    __slots__ = ("entry_count", "regular_bytes", "tree_sha256")

    def __init__(
        self,
        entry_count: int,
        regular_bytes: int,
        tree_sha256: str,
    ) -> None:
        """Validate and retain one deterministic tree identity.

        :param entry_count: Number of directory, file and link records.
        :param regular_bytes: Aggregate bytes of regular files.
        :param tree_sha256: Digest of the ordered ``D``, ``F`` and ``L`` records.
        :return: None.
        """

        values_are_valid: bool = bool(
            type(entry_count) is int
            and entry_count > 0
            and type(regular_bytes) is int
            and regular_bytes > 0
            and re.fullmatch(r"[0-9a-f]{64}", tree_sha256) is not None
        )
        if values_are_valid:
            self.entry_count: int = entry_count
            self.regular_bytes: int = regular_bytes
            self.tree_sha256: str = tree_sha256
        else:
            raise ValueError("FMI.jl tree identity is invalid")


class FmiJlDepotWorkspace:
    """Own the three explicit WSL paths used for isolated Julia execution."""

    __slots__ = ("root_path", "read_only_depot_path", "writable_overlay_path")

    def __init__(
        self,
        root_path: str,
        read_only_depot_path: str,
        writable_overlay_path: str,
    ) -> None:
        """Retain one caller-owned private depot workspace.

        :param root_path: Unique temporary root directly below ``/tmp``.
        :param read_only_depot_path: Authenticated private depot copy.
        :param writable_overlay_path: Disposable first Julia depot.
        :return: None.
        """

        paths_are_valid: bool = bool(
            re.fullmatch(r"/tmp/\.veragrid-fmi-jl-[0-9a-f]{32}", root_path)
            is not None
            and read_only_depot_path == root_path + "/depot"
            and writable_overlay_path == root_path + "/overlay"
        )
        if paths_are_valid:
            self.root_path: str = root_path
            self.read_only_depot_path: str = read_only_depot_path
            self.writable_overlay_path: str = writable_overlay_path
        else:
            raise ValueError("FMI.jl depot workspace paths are invalid")


class FmiJlTrace:
    """Own one validated 2,001-row, seven-signal composition trace."""

    __slots__ = ("header", "values")

    def __init__(self, header: tuple[str, ...], values: np.ndarray) -> None:
        """Validate and detach one canonical trajectory.

        :param header: Exact ordered trace schema.
        :param values: Time plus seven ordered signals.
        :return: None.
        """

        expected_header: tuple[str, ...] = (
            "time",
            "{controller}.controller.MECH_CONTROL",
            "{controller}.controller.SPEED",
            "{plant}.plant.ANGLE",
            "{plant}.plant.MECH_CONTROL",
            "{plant}.plant.PELEC",
            "{plant}.plant.SPEED",
            "{plant}.plant.X_EFFECTIVE",
        )
        valid: bool = bool(
            header == expected_header
            and isinstance(values, np.ndarray)
            and values.shape == (2001, 8)
            and np.all(np.isfinite(values))
            and np.max(
                np.abs(values[:, 0] - np.arange(2001, dtype=float) * 0.002)
            ) <= 1.0e-12
        )
        if valid:
            self.header: tuple[str, ...] = tuple(header)
            self.values: np.ndarray = np.array(values, dtype=float, copy=True)
        else:
            raise ValueError("FMI.jl trace is not on the canonical lattice")


class FmiJlMetrics:
    """Own decisive FMI.jl versus VeraGrid numerical evidence."""

    __slots__ = ("maximum_absolute_errors", "rms_absolute_errors")

    def __init__(
        self,
        maximum_absolute_errors: np.ndarray,
        rms_absolute_errors: np.ndarray,
    ) -> None:
        """Validate and retain per-column errors.

        :param maximum_absolute_errors: Eight maximum absolute errors.
        :param rms_absolute_errors: Eight RMS absolute errors.
        :return: None.
        """

        valid: bool = bool(
            maximum_absolute_errors.shape == (8,)
            and rms_absolute_errors.shape == (8,)
            and np.all(np.isfinite(maximum_absolute_errors))
            and np.all(np.isfinite(rms_absolute_errors))
            and np.all(maximum_absolute_errors >= 0.0)
            and np.all(rms_absolute_errors >= 0.0)
        )
        if valid:
            self.maximum_absolute_errors: np.ndarray = np.array(
                maximum_absolute_errors, dtype=float, copy=True
            )
            self.rms_absolute_errors: np.ndarray = np.array(
                rms_absolute_errors, dtype=float, copy=True
            )
        else:
            raise ValueError("FMI.jl metrics are invalid")


def _authenticate_fmi_jl_inputs(config: FmiJlComparisonConfig) -> None:
    """Authenticate all immutable files before launching Julia.

    :param config: Closed comparison configuration.
    :return: None.
    """

    # Every executable, package lock and model is pinned by size and digest.
    verify_regular_file_identity(
        config.wsl_executable_path,
        config.wsl_executable_size_bytes,
        config.wsl_executable_sha256,
    )
    verify_regular_file_identity(
        config.wsl_python_executable_path,
        config.wsl_python_executable_size_bytes,
        config.wsl_python_executable_sha256,
    )
    verify_regular_file_identity(
        config.julia_archive_path,
        config.julia_archive_size_bytes,
        config.julia_archive_sha256,
    )
    verify_regular_file_identity(
        config.julia_executable_path,
        config.julia_executable_size_bytes,
        config.julia_executable_sha256,
    )
    verify_regular_file_identity(
        config.julia_project_path,
        config.julia_project_size_bytes,
        config.julia_project_sha256,
    )
    verify_regular_file_identity(
        config.julia_manifest_path,
        config.julia_manifest_size_bytes,
        config.julia_manifest_sha256,
    )
    verify_regular_file_identity(
        config.runner_path,
        config.runner_size_bytes,
        config.runner_sha256,
    )
    verify_regular_file_identity(
        config.plant_fmu_path,
        config.plant_fmu_size_bytes,
        config.plant_fmu_sha256,
    )
    verify_regular_file_identity(
        config.governor_fmu_path,
        config.governor_fmu_size_bytes,
        config.governor_fmu_sha256,
    )
    verify_regular_file_identity(
        config.reference_manifest_path,
        config.reference_manifest_size_bytes,
        config.reference_manifest_sha256,
    )
    runtime_identity: FmiJlTreeIdentity = _inspect_fmi_jl_tree(
        config,
        _wsl_unc_path(config.julia_executable_path.parent.parent, config.wsl_distribution),
    )
    depot_identity: FmiJlTreeIdentity = _inspect_fmi_jl_tree(
        config,
        _wsl_unc_path(config.julia_depot_path, config.wsl_distribution),
    )
    trees_are_valid: bool = bool(
        runtime_identity.entry_count == config.julia_runtime_entry_count
        and runtime_identity.regular_bytes == config.julia_runtime_regular_bytes
        and runtime_identity.tree_sha256 == config.julia_runtime_tree_sha256
        and depot_identity.entry_count == config.julia_depot_entry_count
        and depot_identity.regular_bytes == config.julia_depot_regular_bytes
        and depot_identity.tree_sha256 == config.julia_depot_tree_sha256
    )
    if trees_are_valid:
        pass
    else:
        raise ValueError("Julia runtime or source-depot identity differs")

    # WSL emits its Windows-side version as UTF-16, so this one probe is
    # decoded separately from the strict UTF-8 Linux process contract.
    try:
        wsl_version_process: subprocess.CompletedProcess[bytes] = subprocess.run(
            [str(config.wsl_executable_path), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
            timeout=config.process_timeout_seconds,
        )
    except subprocess.TimeoutExpired as timeout_error:
        raise RuntimeError("WSL version probe exceeded its deadline") from timeout_error
    version_streams_are_valid: bool = bool(
        wsl_version_process.returncode == 0
        and len(wsl_version_process.stdout) <= config.stream_limit_bytes
        and len(wsl_version_process.stderr) <= config.stream_limit_bytes
        and wsl_version_process.stderr == b""
    )
    if version_streams_are_valid:
        wsl_version_text: str = wsl_version_process.stdout.decode(
            "utf-16", errors="strict"
        )
        wsl_version_match: re.Match[str] | None = re.search(
            r"(?:WSL version|Versi.n de WSL):\s*([0-9.]+)",
            wsl_version_text,
        )
    else:
        raise RuntimeError("WSL version probe failed or exceeded its stream bound")
    if (
        wsl_version_match is not None
        and wsl_version_match.group(1) == config.wsl_version
    ):
        pass
    else:
        raise ValueError("Installed WSL version differs from the sealed value")

    platform_script: str = (
        "import json,platform,sys\n"
        "values={}\n"
        "with open('/etc/os-release',encoding='utf-8') as source:\n"
        "    for line in source:\n"
        "        if '=' in line:\n"
        "            key,value=line.rstrip('\\n').split('=',1)\n"
        "            values[key]=value.strip('\\\"')\n"
        "payload={'pretty_name':values.get('PRETTY_NAME',''),"
        "'version_id':values.get('VERSION_ID',''),"
        "'architecture':platform.machine(),'kernel':platform.release(),"
        "'glibc_version':platform.libc_ver()[1],"
        "'python_version':'.'.join(str(value) for value in sys.version_info[:3])}\n"
        "print(json.dumps(payload,sort_keys=True,separators=(',',':')))\n"
    )
    platform_arguments: list[str] = [
        str(config.wsl_executable_path),
        "-d",
        config.wsl_distribution,
        "--",
        "/usr/bin/env",
        "-i",
        _wsl_unc_path(config.wsl_python_executable_path, config.wsl_distribution),
        "-I",
        "-S",
        "-c",
        platform_script,
    ]
    platform_result: FmiJlProcessResult = _run_fmi_jl_process(
        platform_arguments,
        config.process_timeout_seconds,
        config.stream_limit_bytes,
    )
    platform_value: object = json.loads(platform_result.stdout_text)
    if isinstance(platform_value, dict):
        platform_payload: dict[str, object] = platform_value
    else:
        raise ValueError("WSL platform probe did not return an object")
    platform_is_valid: bool = bool(
        platform_result.exit_code == 0
        and platform_result.stderr_text == ""
        and set(platform_payload.keys())
        == {
            "pretty_name", "version_id", "architecture", "kernel",
            "glibc_version", "python_version",
        }
        and platform_payload["pretty_name"] == config.wsl_distribution_pretty_name
        and platform_payload["version_id"] == config.wsl_distribution_version_id
        and platform_payload["architecture"] == config.wsl_architecture
        and platform_payload["kernel"] == config.wsl_kernel
        and platform_payload["glibc_version"] == config.wsl_glibc_version
        and platform_payload["python_version"] == config.wsl_python_version
    )
    if platform_is_valid:
        pass
    else:
        raise ValueError("WSL platform identity differs from the sealed values")


def _wsl_unc_path(path: Path, distribution: str) -> str:
    """Translate one authenticated WSL UNC path to its Linux absolute path.

    :param path: Existing absolute WSL UNC path.
    :param distribution: Required WSL distribution name.
    :return: Absolute Linux path visible inside that distribution.
    """

    normalized: str = str(path).replace("/", "\\")
    modern_prefix: str = "\\\\wsl.localhost\\" + distribution + "\\"
    legacy_prefix: str = "\\\\wsl$\\" + distribution + "\\"
    if normalized.lower().startswith(modern_prefix.lower()):
        relative_path: str = normalized[len(modern_prefix):]
    else:
        if normalized.lower().startswith(legacy_prefix.lower()):
            relative_path = normalized[len(legacy_prefix):]
        else:
            raise ValueError("Path is not owned by the selected WSL distribution")
    linux_path: str = "/" + relative_path.replace("\\", "/")
    if ".." not in linux_path.split("/"):
        return linux_path
    else:
        raise ValueError("WSL path contains a parent traversal")


def _windows_path_to_wsl(path: Path) -> str:
    """Translate one absolute Windows drive path for a WSL child process.

    :param path: Absolute Windows path below a mounted drive.
    :return: WSL mount path using portable separators.
    """

    drive: str = path.drive.rstrip(":").lower()
    relative_text: str = str(path)[len(path.drive):].lstrip("\\/")
    drive_is_valid: bool = bool(len(drive) == 1 and drive.isalpha())
    if drive_is_valid:
        return "/mnt/" + drive + "/" + relative_text.replace("\\", "/")
    else:
        raise ValueError("Only absolute Windows drive paths can be staged")


def _run_fmi_jl_process(
    arguments: list[str],
    timeout_seconds: float,
    stream_limit_bytes: int,
) -> FmiJlProcessResult:
    """Run one sealed Julia child process with bounded decoded streams.

    :param arguments: Explicit executable and argument vector.
    :param timeout_seconds: Hard process deadline.
    :param stream_limit_bytes: Maximum bytes accepted per output stream.
    :return: Strictly decoded process result.
    """

    try:
        completed: subprocess.CompletedProcess[bytes] = subprocess.run(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as timeout_error:
        raise RuntimeError("FMI.jl process exceeded its deadline") from timeout_error
    streams_are_bounded: bool = bool(
        len(completed.stdout) <= stream_limit_bytes
        and len(completed.stderr) <= stream_limit_bytes
    )
    if streams_are_bounded:
        stdout_text: str = completed.stdout.decode("utf-8", errors="strict")
        stderr_text: str = completed.stderr.decode("utf-8", errors="strict")
        return FmiJlProcessResult(completed.returncode, stdout_text, stderr_text)
    else:
        raise RuntimeError("FMI.jl process output exceeded the evidence bound")


def _inspect_fmi_jl_tree(
    config: FmiJlComparisonConfig,
    linux_root: str,
) -> FmiJlTreeIdentity:
    """Authenticate a complete WSL tree without following symbolic links.

    :param config: Closed comparison configuration owning the WSL interpreter.
    :param linux_root: Absolute Linux directory to inventory.
    :return: Ordered directory, regular-file and symbolic-link tree identity.
    """

    root_is_valid: bool = bool(
        linux_root.startswith("/") and ".." not in linux_root.split("/")
    )
    if root_is_valid:
        pass
    else:
        raise ValueError("FMI.jl tree root is not a safe Linux absolute path")

    # This is the exact algorithm used to seal both expected tree digests.
    inspector_script: str = (
        "import hashlib,json,os,stat,sys\n"
        "root=sys.argv[1]\n"
        "records=[]\n"
        "entry_count=0\n"
        "regular_bytes=0\n"
        "for current,directories,files in os.walk(root,topdown=True,followlinks=False):\n"
        "    directories.sort()\n"
        "    files.sort()\n"
        "    for name in directories+files:\n"
        "        path=os.path.join(current,name)\n"
        "        relative=os.path.relpath(path,root).replace(os.sep,'/')\n"
        "        mode=os.lstat(path).st_mode\n"
        "        if stat.S_ISLNK(mode):\n"
        "            records.append(f'L {relative} {os.readlink(path)}\\n')\n"
        "            entry_count+=1\n"
        "        elif stat.S_ISDIR(mode):\n"
        "            records.append(f'D {relative}\\n')\n"
        "            entry_count+=1\n"
        "        elif stat.S_ISREG(mode):\n"
        "            expected_size=os.lstat(path).st_size\n"
        "            content_hash=hashlib.sha256()\n"
        "            observed_size=0\n"
        "            with open(path,'rb') as source:\n"
        "                chunk=source.read(1048576)\n"
        "                while chunk:\n"
        "                    content_hash.update(chunk)\n"
        "                    observed_size+=len(chunk)\n"
        "                    chunk=source.read(1048576)\n"
        "            if observed_size!=expected_size or os.lstat(path).st_size!=expected_size:\n"
        "                raise RuntimeError('Tree file changed during inspection')\n"
        "            records.append(f'F {relative} {expected_size} {content_hash.hexdigest()}\\n')\n"
        "            entry_count+=1\n"
        "            regular_bytes+=expected_size\n"
        "        else:\n"
        "            raise RuntimeError('Unsupported tree entry: '+relative)\n"
        "payload={'entry_count':entry_count,'regular_bytes':regular_bytes,"
        "'tree_sha256':hashlib.sha256(''.join(records).encode('utf-8')).hexdigest()}\n"
        "print(json.dumps(payload,sort_keys=True,separators=(',',':')))\n"
    )
    inspector_arguments: list[str] = [
        str(config.wsl_executable_path),
        "-d",
        config.wsl_distribution,
        "--",
        "/usr/bin/env",
        "-i",
        _wsl_unc_path(config.wsl_python_executable_path, config.wsl_distribution),
        "-I",
        "-S",
        "-c",
        inspector_script,
        linux_root,
    ]
    inspector_result: FmiJlProcessResult = _run_fmi_jl_process(
        inspector_arguments,
        config.process_timeout_seconds,
        config.stream_limit_bytes,
    )
    inspector_value: object = json.loads(inspector_result.stdout_text)
    if isinstance(inspector_value, dict):
        inspector_payload: dict[str, object] = inspector_value
    else:
        raise ValueError("FMI.jl tree inspector did not return an object")
    payload_is_valid: bool = bool(
        inspector_result.exit_code == 0
        and inspector_result.stderr_text == ""
        and set(inspector_payload.keys())
        == {"entry_count", "regular_bytes", "tree_sha256"}
        and type(inspector_payload["entry_count"]) is int
        and type(inspector_payload["regular_bytes"]) is int
        and isinstance(inspector_payload["tree_sha256"], str)
    )
    if payload_is_valid:
        return FmiJlTreeIdentity(
            int(inspector_payload["entry_count"]),
            int(inspector_payload["regular_bytes"]),
            str(inspector_payload["tree_sha256"]),
        )
    else:
        raise ValueError("FMI.jl tree inspector result is invalid")


def _verify_fmi_jl_depot_permissions(
    config: FmiJlComparisonConfig,
    workspace: FmiJlDepotWorkspace,
) -> None:
    """Verify private depot identity, link containment and read-only state.

    :param config: Closed comparison configuration with the sealed depot identity.
    :param workspace: Owned WSL depot workspace to inspect.
    :return: None.
    """

    private_identity: FmiJlTreeIdentity = _inspect_fmi_jl_tree(
        config,
        workspace.read_only_depot_path,
    )
    identity_matches: bool = bool(
        private_identity.entry_count == config.julia_depot_entry_count
        and private_identity.regular_bytes == config.julia_depot_regular_bytes
        and private_identity.tree_sha256 == config.julia_depot_tree_sha256
    )
    if identity_matches:
        pass
    else:
        raise ValueError("Private FMI.jl depot copy differs from the sealed source")

    permission_script: str = (
        "import json,os,stat,sys\n"
        "root=os.path.realpath(sys.argv[1])\n"
        "symlink_count=0\n"
        "escaping_count=0\n"
        "writable_count=0\n"
        "root_mode=os.lstat(root).st_mode\n"
        "if root_mode & 0o222:\n"
        "    writable_count+=1\n"
        "for current,directories,files in os.walk(root,topdown=True,followlinks=False):\n"
        "    directories.sort()\n"
        "    files.sort()\n"
        "    for name in directories+files:\n"
        "        path=os.path.join(current,name)\n"
        "        mode=os.lstat(path).st_mode\n"
        "        if stat.S_ISLNK(mode):\n"
        "            symlink_count+=1\n"
        "            resolved=os.path.realpath(path)\n"
        "            if os.path.commonpath([root,resolved])!=root:\n"
        "                escaping_count+=1\n"
        "        elif stat.S_ISDIR(mode) or stat.S_ISREG(mode):\n"
        "            if mode & 0o222:\n"
        "                writable_count+=1\n"
        "        else:\n"
        "            raise RuntimeError('Unsupported private depot entry')\n"
        "payload={'symlink_count':symlink_count,'escaping_count':escaping_count,"
        "'writable_count':writable_count}\n"
        "print(json.dumps(payload,sort_keys=True,separators=(',',':')))\n"
    )
    permission_arguments: list[str] = [
        str(config.wsl_executable_path),
        "-d",
        config.wsl_distribution,
        "--",
        "/usr/bin/env",
        "-i",
        _wsl_unc_path(config.wsl_python_executable_path, config.wsl_distribution),
        "-I",
        "-S",
        "-c",
        permission_script,
        workspace.read_only_depot_path,
    ]
    permission_result: FmiJlProcessResult = _run_fmi_jl_process(
        permission_arguments,
        config.process_timeout_seconds,
        config.stream_limit_bytes,
    )
    permission_value: object = json.loads(permission_result.stdout_text)
    if isinstance(permission_value, dict):
        permission_payload: dict[str, object] = permission_value
    else:
        raise ValueError("FMI.jl permission probe did not return an object")
    permissions_are_valid: bool = bool(
        permission_result.exit_code == 0
        and permission_result.stderr_text == ""
        and set(permission_payload.keys())
        == {"symlink_count", "escaping_count", "writable_count"}
        and permission_payload["symlink_count"] == 7
        and permission_payload["escaping_count"] == 0
        and permission_payload["writable_count"] == 0
    )
    if permissions_are_valid:
        pass
    else:
        raise ValueError("Private FMI.jl depot is writable or escapes its root")


def _remove_fmi_jl_depot_workspace(
    config: FmiJlComparisonConfig,
    workspace: FmiJlDepotWorkspace,
) -> None:
    """Remove only the validated caller-owned WSL depot workspace.

    :param config: Closed comparison configuration owning the WSL interpreter.
    :param workspace: Exact private workspace to remove.
    :return: None.
    """

    cleanup_script: str = (
        "import os,shutil,stat,sys\n"
        "root=sys.argv[1]\n"
        "valid=root.startswith('/tmp/.veragrid-fmi-jl-') and '/' not in root[5:]\n"
        "if not valid:\n"
        "    raise RuntimeError('Unsafe cleanup root')\n"
        "if os.path.lexists(root):\n"
        "    if os.path.islink(root) or not os.path.isdir(root):\n"
        "        raise RuntimeError('Cleanup root is not an owned directory')\n"
        "    for current,directories,files in os.walk(root,topdown=False,followlinks=False):\n"
        "        for name in files+directories:\n"
        "            path=os.path.join(current,name)\n"
        "            mode=os.lstat(path).st_mode\n"
        "            if not stat.S_ISLNK(mode):\n"
        "                os.chmod(path,mode|0o700)\n"
        "    os.chmod(root,os.lstat(root).st_mode|0o700)\n"
        "    shutil.rmtree(root)\n"
        "print('REMOVED')\n"
    )
    cleanup_arguments: list[str] = [
        str(config.wsl_executable_path),
        "-d",
        config.wsl_distribution,
        "--",
        "/usr/bin/env",
        "-i",
        _wsl_unc_path(config.wsl_python_executable_path, config.wsl_distribution),
        "-I",
        "-S",
        "-c",
        cleanup_script,
        workspace.root_path,
    ]
    cleanup_result: FmiJlProcessResult = _run_fmi_jl_process(
        cleanup_arguments,
        config.process_timeout_seconds,
        config.stream_limit_bytes,
    )
    cleanup_succeeded: bool = bool(
        cleanup_result.exit_code == 0
        and cleanup_result.stdout_text == "REMOVED\n"
        and cleanup_result.stderr_text == ""
    )
    if cleanup_succeeded:
        pass
    else:
        raise RuntimeError("FMI.jl private depot cleanup failed")


def _prepare_fmi_jl_depot_workspace(
    config: FmiJlComparisonConfig,
) -> FmiJlDepotWorkspace:
    """Create and verify a private read-only copy plus writable overlay.

    :param config: Closed comparison configuration with the source depot.
    :return: Fully authenticated private WSL depot workspace.
    """

    root_path: str = "/tmp/.veragrid-fmi-jl-" + uuid.uuid4().hex
    workspace: FmiJlDepotWorkspace = FmiJlDepotWorkspace(
        root_path,
        root_path + "/depot",
        root_path + "/overlay",
    )
    source_depot_path: str = _wsl_unc_path(
        config.julia_depot_path,
        config.wsl_distribution,
    )
    preparation_script: str = (
        "import os,shutil,stat,sys\n"
        "source=sys.argv[1]\n"
        "root=sys.argv[2]\n"
        "private_depot=sys.argv[3]\n"
        "overlay=sys.argv[4]\n"
        "if os.path.lexists(root):\n"
        "    raise RuntimeError('Private workspace already exists')\n"
        "os.mkdir(root,0o700)\n"
        "shutil.copytree(source,private_depot,symlinks=True)\n"
        "os.mkdir(overlay,0o700)\n"
        "canonical_private=os.path.realpath(private_depot)\n"
        "for current,directories,files in os.walk(private_depot,topdown=False,followlinks=False):\n"
        "    directories.sort()\n"
        "    files.sort()\n"
        "    for name in files+directories:\n"
        "        path=os.path.join(current,name)\n"
        "        mode=os.lstat(path).st_mode\n"
        "        if stat.S_ISLNK(mode):\n"
        "            resolved=os.path.realpath(path)\n"
        "            if os.path.commonpath([canonical_private,resolved])!=canonical_private:\n"
        "                raise RuntimeError('Private depot link escapes its root')\n"
        "        elif stat.S_ISDIR(mode) or stat.S_ISREG(mode):\n"
        "            os.chmod(path,mode & ~0o222)\n"
        "        else:\n"
        "            raise RuntimeError('Unsupported private depot entry')\n"
        "os.chmod(private_depot,os.lstat(private_depot).st_mode & ~0o222)\n"
        "print('READY')\n"
    )
    preparation_arguments: list[str] = [
        str(config.wsl_executable_path),
        "-d",
        config.wsl_distribution,
        "--",
        "/usr/bin/env",
        "-i",
        _wsl_unc_path(config.wsl_python_executable_path, config.wsl_distribution),
        "-I",
        "-S",
        "-c",
        preparation_script,
        source_depot_path,
        workspace.root_path,
        workspace.read_only_depot_path,
        workspace.writable_overlay_path,
    ]
    try:
        preparation_result: FmiJlProcessResult = _run_fmi_jl_process(
            preparation_arguments,
            config.process_timeout_seconds,
            config.stream_limit_bytes,
        )
        preparation_succeeded: bool = bool(
            preparation_result.exit_code == 0
            and preparation_result.stdout_text == "READY\n"
            and preparation_result.stderr_text == ""
        )
        if preparation_succeeded:
            _verify_fmi_jl_depot_permissions(config, workspace)
            return workspace
        else:
            raise RuntimeError("FMI.jl private depot preparation failed")
    except (OSError, RuntimeError, UnicodeError, ValueError):
        _remove_fmi_jl_depot_workspace(config, workspace)
        raise


def _parse_fmi_jl_trace(path: Path) -> FmiJlTrace:
    """Parse one complete FMI.jl trace with an exact schema and cardinality.

    :param path: CSV file emitted by the authenticated Julia runner.
    :return: Validated canonical trace.
    """

    expected_header: tuple[str, ...] = (
        "time",
        "{controller}.controller.MECH_CONTROL",
        "{controller}.controller.SPEED",
        "{plant}.plant.ANGLE",
        "{plant}.plant.MECH_CONTROL",
        "{plant}.plant.PELEC",
        "{plant}.plant.SPEED",
        "{plant}.plant.X_EFFECTIVE",
    )
    values: np.ndarray = np.empty((2001, 8), dtype=float)
    source_file: TextIO = path.open("r", encoding="utf-8", newline="")
    try:
        rows: list[list[str]] = list(csv.reader(source_file))
    finally:
        source_file.close()
    cardinality_is_valid: bool = bool(
        len(rows) == 2002 and tuple(rows[0]) == expected_header
    )
    if cardinality_is_valid:
        for row_index in range(2001):
            row: list[str] = rows[row_index + 1]
            if len(row) == 8:
                values[row_index, :] = np.asarray(row, dtype=float)
            else:
                raise ValueError("FMI.jl trace row has the wrong width")
    else:
        raise ValueError("FMI.jl trace schema or cardinality is invalid")
    return FmiJlTrace(expected_header, values)


def _evaluate_fmi_jl(
    candidate: FmiJlTrace,
    reference: FmiJlTrace,
) -> FmiJlMetrics:
    """Evaluate numerical agreement and material event-family dynamics.

    :param candidate: FMI.jl coupled-FMU trajectory.
    :param reference: Sealed VeraGrid reference trajectory.
    :return: Per-column maximum and RMS errors.
    """

    absolute_errors: np.ndarray = np.abs(candidate.values - reference.values)
    maximum_errors: np.ndarray = np.max(absolute_errors, axis=0)
    rms_errors: np.ndarray = np.sqrt(np.mean(absolute_errors ** 2, axis=0))
    comparison_passes: bool = bool(np.all(maximum_errors <= 1.0e-12))
    if comparison_passes:
        pass
    else:
        raise ValueError("FMI.jl trajectory differs from the VeraGrid oracle")

    # The four boundary samples prove both fault insertion and fault clearing.
    event_rows: np.ndarray = candidate.values[[500, 501, 575, 576], 7]
    expected_event_rows: np.ndarray = np.array([0.6, 1.2, 1.2, 0.6])
    event_rows_match: bool = bool(
        np.all(np.abs(event_rows - expected_event_rows) <= 1.0e-12)
    )
    dynamic_ranges: np.ndarray = np.ptp(candidate.values[:, 1:7], axis=0)
    dynamics_are_material: bool = bool(
        dynamic_ranges[0] > 0.01
        and dynamic_ranges[2] > 0.1
        and dynamic_ranges[4] > 0.4
        and dynamic_ranges[5] > 0.005
    )
    if event_rows_match and dynamics_are_material:
        return FmiJlMetrics(maximum_errors, rms_errors)
    else:
        raise ValueError("FMI.jl trace does not exercise the event family")


def _render_fmi_jl_figure(
    candidate: FmiJlTrace,
    reference: FmiJlTrace,
    figure_stem: Path,
) -> None:
    """Render the decisive four-panel engineering comparison.

    :param candidate: FMI.jl coupled-FMU trajectory.
    :param reference: Sealed VeraGrid reference trajectory.
    :param figure_stem: Output path without a file extension.
    :return: None.
    """

    style: dict[str, object] = {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 9.0,
        "legend.fontsize": 7.0,
        "axes.linewidth": 0.7,
        "lines.linewidth": 1.15,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }
    with matplotlib.rc_context(style):
        figure: Figure = Figure(figsize=(7.2, 7.0), constrained_layout=True)
        FigureCanvasAgg(figure)
        axes: tuple[Axes, Axes, Axes, Axes] = (
            figure.add_subplot(2, 2, 1),
            figure.add_subplot(2, 2, 2),
            figure.add_subplot(2, 2, 3),
            figure.add_subplot(2, 2, 4),
        )
        signal_columns: tuple[int, int, int, int] = (3, 6, 5, 1)
        titles: tuple[str, str, str, str] = (
            "Rotor angle",
            "Rotor speed",
            "Electrical power",
            "Governor mechanical command",
        )
        y_labels: tuple[str, str, str, str] = (
            "Angle (rad)", "Speed (p.u.)", "Power (p.u.)", "Command (p.u.)"
        )
        for panel_index in range(4):
            axis: Axes = axes[panel_index]
            signal_column: int = signal_columns[panel_index]
            axis.plot(
                reference.values[:, 0],
                reference.values[:, signal_column],
                color="#1f4e79",
                label="VeraGrid",
            )
            axis.plot(
                candidate.values[:, 0],
                candidate.values[:, signal_column],
                color="#c44e52",
                linestyle="--",
                label="FMI.jl",
            )
            axis.axvline(1.001, color="#4c4c4c", linestyle=":", linewidth=0.8)
            axis.axvline(1.151, color="#4c4c4c", linestyle=":", linewidth=0.8)
            axis.set_title(titles[panel_index])
            axis.set_xlabel("Time (s)")
            axis.set_ylabel(y_labels[panel_index])
            axis.grid(True, color="#d9d9d9", linewidth=0.5)
            axis.legend(loc="best", frameon=False)
        figure.suptitle(
            "SMIB two-FMU composition: FMI.jl 0.15.2 versus VeraGrid",
            fontsize=10.0,
        )
        figure.savefig(figure_stem.with_suffix(".png"), dpi=300)
        figure.savefig(figure_stem.with_suffix(".svg"))
        figure.savefig(figure_stem.with_suffix(".pdf"))
        figure.clear()


def _fmi_jl_file_record(package_root: Path, path: Path) -> dict[str, object]:
    """Build one exact package-file identity record.

    :param package_root: Root used for portable relative paths.
    :param path: Regular file to authenticate.
    :return: JSON-ready path, size and digest record.
    """

    content: bytes = path.read_bytes()
    record: dict[str, object] = dict()
    record["path"] = path.relative_to(package_root).as_posix()
    record["size_bytes"] = len(content)
    record["sha256"] = hashlib.sha256(content).hexdigest()
    return record


def _write_fmi_jl_manifest(
    config: FmiJlComparisonConfig,
    package_root: Path,
    process_result: FmiJlProcessResult,
    candidate: FmiJlTrace,
    metrics: FmiJlMetrics,
    evidence_paths: tuple[Path, ...],
) -> None:
    """Write the closed FMI.jl comparison manifest.

    :param config: Authenticated comparison configuration.
    :param package_root: Temporary owned package root.
    :param process_result: Successful Julia process result.
    :param candidate: Validated FMI.jl trace.
    :param metrics: Validated numerical comparison metrics.
    :param evidence_paths: Eight non-manifest package files.
    :return: None.
    """

    file_records: list[dict[str, object]] = [dict()] * len(evidence_paths)
    for path_index in range(len(evidence_paths)):
        file_records[path_index] = _fmi_jl_file_record(
            package_root, evidence_paths[path_index]
        )
    manifest: dict[str, object] = dict()
    manifest["schema"] = "veragrid.fmi-jl-comparison/1"
    manifest["status"] = "PASS"
    manifest["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["source"] = {
        "branch": config.source_branch,
        "revision": config.source_revision,
        "tree_sha256": config.source_tree_sha256,
    }
    manifest["scope"] = {
        "claim": (
            "Independent FMI.jl 0.15.2 execution of two interacting FMI 2.0 "
            "Co-Simulation FMUs agrees with the sealed VeraGrid trajectory."
        ),
        "excluded_claims": [
            "FMI.jl native composition-master conformance",
            "FMI 1.0 or FMI 3.0 support",
            "Model Exchange support",
        ],
    }
    manifest["runtime"] = {
        "wsl": {
            "distribution": config.wsl_distribution,
            "version": config.wsl_version,
            "distribution_pretty_name": config.wsl_distribution_pretty_name,
            "distribution_version_id": config.wsl_distribution_version_id,
            "architecture": config.wsl_architecture,
            "kernel": config.wsl_kernel,
            "glibc_version": config.wsl_glibc_version,
            "executable_path": str(config.wsl_executable_path),
            "executable_size_bytes": config.wsl_executable_size_bytes,
            "executable_sha256": config.wsl_executable_sha256,
            "python_executable_path": _wsl_unc_path(
                config.wsl_python_executable_path,
                config.wsl_distribution,
            ),
            "python_executable_size_bytes": (
                config.wsl_python_executable_size_bytes
            ),
            "python_executable_sha256": config.wsl_python_executable_sha256,
            "python_version": config.wsl_python_version,
        },
        "julia": {
            "version": config.julia_version,
            "archive_path": _wsl_unc_path(
                config.julia_archive_path,
                config.wsl_distribution,
            ),
            "archive_size_bytes": config.julia_archive_size_bytes,
            "archive_sha256": config.julia_archive_sha256,
            "executable_path": _wsl_unc_path(
                config.julia_executable_path,
                config.wsl_distribution,
            ),
            "executable_size_bytes": config.julia_executable_size_bytes,
            "executable_sha256": config.julia_executable_sha256,
            "runtime_entry_count": config.julia_runtime_entry_count,
            "runtime_regular_bytes": config.julia_runtime_regular_bytes,
            "runtime_tree_sha256": config.julia_runtime_tree_sha256,
        },
        "fmi_jl": {
            "version": config.fmi_jl_version,
            "project_path": _wsl_unc_path(
                config.julia_project_path,
                config.wsl_distribution,
            ),
            "project_size_bytes": config.julia_project_size_bytes,
            "project_sha256": config.julia_project_sha256,
            "manifest_path": _wsl_unc_path(
                config.julia_manifest_path,
                config.wsl_distribution,
            ),
            "manifest_size_bytes": config.julia_manifest_size_bytes,
            "manifest_sha256": config.julia_manifest_sha256,
            "source_depot_path": _wsl_unc_path(
                config.julia_depot_path,
                config.wsl_distribution,
            ),
            "source_depot_entry_count": config.julia_depot_entry_count,
            "source_depot_regular_bytes": config.julia_depot_regular_bytes,
            "source_depot_tree_sha256": config.julia_depot_tree_sha256,
        },
        "process_environment": {
            "inherit_parent": False,
            "home": config.wsl_home,
            "julia_depot_path": (
                "<owned-writable-overlay>:<owned-read-only-copy>"
            ),
            "julia_pkg_precompile_auto": "0",
            "shared_depot_exposed": False,
            "private_depot_symlink_count": 7,
            "private_depot_writable_entry_count": 0,
        },
    }
    manifest["inputs"] = {
        "runner": {
            "size_bytes": config.runner_size_bytes,
            "sha256": config.runner_sha256,
        },
        "plant_fmu": {
            "size_bytes": config.plant_fmu_size_bytes,
            "sha256": config.plant_fmu_sha256,
        },
        "governor_fmu": {
            "size_bytes": config.governor_fmu_size_bytes,
            "sha256": config.governor_fmu_sha256,
        },
        "reference_manifest": {
            "size_bytes": config.reference_manifest_size_bytes,
            "sha256": config.reference_manifest_sha256,
        },
        "reference_trace": {
            "size_bytes": 279085,
            "sha256": (
                "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45"
            ),
        },
    }
    manifest["execution"] = {
        "exit_code": process_result.exit_code,
        "step_size_seconds": 0.002,
        "end_time_seconds": 4.0,
        "coupling": "Jacobi boundary exchange with one communication-step delay",
        "rows": int(candidate.values.shape[0]),
        "signals": int(candidate.values.shape[1] - 1),
        "scalar_values": int(candidate.values.shape[0] * (candidate.values.shape[1] - 1)),
        "process_timeout_seconds": config.process_timeout_seconds,
        "stream_limit_bytes": config.stream_limit_bytes,
    }
    manifest["event_family"] = {
        "fault_insertion_boundary_seconds": 1.001,
        "fault_clearing_boundary_seconds": 1.151,
        "effective_reactance_samples": [0.6, 1.2, 1.2, 0.6],
        "sample_rows": [500, 501, 575, 576],
    }
    manifest["comparison"] = {
        "absolute_tolerance": 1.0e-12,
        "maximum_absolute_errors": metrics.maximum_absolute_errors.tolist(),
        "rms_absolute_errors": metrics.rms_absolute_errors.tolist(),
    }
    manifest["figures"] = {
        "panels": ["angle", "speed", "electrical_power", "governor_command"],
        "formats": ["png", "svg", "pdf"],
        "png_pixels": [2160, 2100],
    }
    manifest["files"] = file_records
    manifest_path: Path = package_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _verify_fmi_jl_package(
    config: FmiJlComparisonConfig,
    package_root: Path,
) -> None:
    """Recompute decisive evidence from one closed FMI.jl package.

    :param config: Closed configuration anchoring source and runtime identities.
    :param package_root: Complete candidate evidence package.
    :return: None.
    """

    expected_files: tuple[str, ...] = (
        "figures/fmi-jl-smib-composition.pdf",
        "figures/fmi-jl-smib-composition.png",
        "figures/fmi-jl-smib-composition.svg",
        "inputs/fmi_jl_runner.jl",
        "manifest.json",
        "raw/fmi-jl-stderr.log",
        "raw/fmi-jl-stdout.log",
        "raw/fmi-jl-trace.csv",
        "raw/veragrid-reference.csv",
    )
    discovered_files: list[str] = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    ]
    discovered_files.sort()
    if tuple(discovered_files) == expected_files:
        pass
    else:
        raise ValueError("FMI.jl package is not the closed nine-file set")

    manifest_path: Path = package_root / "manifest.json"
    manifest_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(manifest_value, dict):
        manifest: dict[str, object] = manifest_value
    else:
        raise ValueError("FMI.jl manifest root is not an object")
    expected_source: dict[str, object] = {
        "branch": config.source_branch,
        "revision": config.source_revision,
        "tree_sha256": config.source_tree_sha256,
    }
    expected_scope: dict[str, object] = {
        "claim": (
            "Independent FMI.jl 0.15.2 execution of two interacting FMI 2.0 "
            "Co-Simulation FMUs agrees with the sealed VeraGrid trajectory."
        ),
        "excluded_claims": [
            "FMI.jl native composition-master conformance",
            "FMI 1.0 or FMI 3.0 support",
            "Model Exchange support",
        ],
    }
    expected_runtime: dict[str, object] = {
        "wsl": {
            "distribution": config.wsl_distribution,
            "version": config.wsl_version,
            "distribution_pretty_name": config.wsl_distribution_pretty_name,
            "distribution_version_id": config.wsl_distribution_version_id,
            "architecture": config.wsl_architecture,
            "kernel": config.wsl_kernel,
            "glibc_version": config.wsl_glibc_version,
            "executable_path": str(config.wsl_executable_path),
            "executable_size_bytes": config.wsl_executable_size_bytes,
            "executable_sha256": config.wsl_executable_sha256,
            "python_executable_path": _wsl_unc_path(
                config.wsl_python_executable_path,
                config.wsl_distribution,
            ),
            "python_executable_size_bytes": (
                config.wsl_python_executable_size_bytes
            ),
            "python_executable_sha256": config.wsl_python_executable_sha256,
            "python_version": config.wsl_python_version,
        },
        "julia": {
            "version": config.julia_version,
            "archive_path": _wsl_unc_path(
                config.julia_archive_path,
                config.wsl_distribution,
            ),
            "archive_size_bytes": config.julia_archive_size_bytes,
            "archive_sha256": config.julia_archive_sha256,
            "executable_path": _wsl_unc_path(
                config.julia_executable_path,
                config.wsl_distribution,
            ),
            "executable_size_bytes": config.julia_executable_size_bytes,
            "executable_sha256": config.julia_executable_sha256,
            "runtime_entry_count": config.julia_runtime_entry_count,
            "runtime_regular_bytes": config.julia_runtime_regular_bytes,
            "runtime_tree_sha256": config.julia_runtime_tree_sha256,
        },
        "fmi_jl": {
            "version": config.fmi_jl_version,
            "project_path": _wsl_unc_path(
                config.julia_project_path,
                config.wsl_distribution,
            ),
            "project_size_bytes": config.julia_project_size_bytes,
            "project_sha256": config.julia_project_sha256,
            "manifest_path": _wsl_unc_path(
                config.julia_manifest_path,
                config.wsl_distribution,
            ),
            "manifest_size_bytes": config.julia_manifest_size_bytes,
            "manifest_sha256": config.julia_manifest_sha256,
            "source_depot_path": _wsl_unc_path(
                config.julia_depot_path,
                config.wsl_distribution,
            ),
            "source_depot_entry_count": config.julia_depot_entry_count,
            "source_depot_regular_bytes": config.julia_depot_regular_bytes,
            "source_depot_tree_sha256": config.julia_depot_tree_sha256,
        },
        "process_environment": {
            "inherit_parent": False,
            "home": config.wsl_home,
            "julia_depot_path": (
                "<owned-writable-overlay>:<owned-read-only-copy>"
            ),
            "julia_pkg_precompile_auto": "0",
            "shared_depot_exposed": False,
            "private_depot_symlink_count": 7,
            "private_depot_writable_entry_count": 0,
        },
    }
    expected_inputs: dict[str, object] = {
        "runner": {
            "size_bytes": config.runner_size_bytes,
            "sha256": config.runner_sha256,
        },
        "plant_fmu": {
            "size_bytes": config.plant_fmu_size_bytes,
            "sha256": config.plant_fmu_sha256,
        },
        "governor_fmu": {
            "size_bytes": config.governor_fmu_size_bytes,
            "sha256": config.governor_fmu_sha256,
        },
        "reference_manifest": {
            "size_bytes": config.reference_manifest_size_bytes,
            "sha256": config.reference_manifest_sha256,
        },
        "reference_trace": {
            "size_bytes": 279085,
            "sha256": (
                "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45"
            ),
        },
    }
    expected_execution: dict[str, object] = {
        "exit_code": 0,
        "step_size_seconds": 0.002,
        "end_time_seconds": 4.0,
        "coupling": "Jacobi boundary exchange with one communication-step delay",
        "rows": 2001,
        "signals": 7,
        "scalar_values": 14007,
        "process_timeout_seconds": config.process_timeout_seconds,
        "stream_limit_bytes": config.stream_limit_bytes,
    }
    expected_event_family: dict[str, object] = {
        "fault_insertion_boundary_seconds": 1.001,
        "fault_clearing_boundary_seconds": 1.151,
        "effective_reactance_samples": [0.6, 1.2, 1.2, 0.6],
        "sample_rows": [500, 501, 575, 576],
    }
    expected_figures: dict[str, object] = {
        "panels": ["angle", "speed", "electrical_power", "governor_command"],
        "formats": ["png", "svg", "pdf"],
        "png_pixels": [2160, 2100],
    }
    # Canonical JSON comparison preserves both the complete key set and the
    # primitive JSON types; normal Python equality would accept ``0`` as
    # equivalent to ``False`` and an integer as equivalent to a float.
    expected_source_json: str = json.dumps(
        expected_source, sort_keys=True, separators=(",", ":")
    )
    expected_scope_json: str = json.dumps(
        expected_scope, sort_keys=True, separators=(",", ":")
    )
    expected_runtime_json: str = json.dumps(
        expected_runtime, sort_keys=True, separators=(",", ":")
    )
    expected_inputs_json: str = json.dumps(
        expected_inputs, sort_keys=True, separators=(",", ":")
    )
    expected_execution_json: str = json.dumps(
        expected_execution, sort_keys=True, separators=(",", ":")
    )
    expected_event_family_json: str = json.dumps(
        expected_event_family, sort_keys=True, separators=(",", ":")
    )
    expected_figures_json: str = json.dumps(
        expected_figures, sort_keys=True, separators=(",", ":")
    )
    generated_value: object = manifest.get("generated_at_utc", None)
    if isinstance(generated_value, str):
        try:
            generated_at: datetime = datetime.fromisoformat(generated_value)
        except ValueError as timestamp_error:
            raise ValueError("FMI.jl generation time is not ISO-8601") from timestamp_error
    else:
        raise ValueError("FMI.jl generation time is absent")
    top_level_is_valid: bool = bool(
        set(manifest.keys())
        == {
            "schema", "status", "generated_at_utc", "source", "scope",
            "runtime", "inputs", "execution", "event_family", "comparison",
            "figures", "files",
        }
        and manifest["schema"] == "veragrid.fmi-jl-comparison/1"
        and manifest["status"] == "PASS"
        and generated_at.tzinfo is not None
        and json.dumps(manifest["source"], sort_keys=True, separators=(",", ":"))
        == expected_source_json
        and json.dumps(manifest["scope"], sort_keys=True, separators=(",", ":"))
        == expected_scope_json
        and json.dumps(manifest["runtime"], sort_keys=True, separators=(",", ":"))
        == expected_runtime_json
        and json.dumps(manifest["inputs"], sort_keys=True, separators=(",", ":"))
        == expected_inputs_json
        and json.dumps(manifest["execution"], sort_keys=True, separators=(",", ":"))
        == expected_execution_json
        and json.dumps(
            manifest["event_family"], sort_keys=True, separators=(",", ":")
        )
        == expected_event_family_json
        and json.dumps(manifest["figures"], sort_keys=True, separators=(",", ":"))
        == expected_figures_json
        and isinstance(manifest["comparison"], dict)
        and set(manifest["comparison"].keys())
        == {"absolute_tolerance", "maximum_absolute_errors", "rms_absolute_errors"}
        and isinstance(manifest["files"], list)
    )
    if top_level_is_valid:
        pass
    else:
        raise ValueError("FMI.jl manifest contract is not exact")

    file_values: object = manifest["files"]
    if isinstance(file_values, list) and len(file_values) == 8:
        recorded_paths: set[str] = set()
        recorded_order: list[str] = [""] * len(file_values)
        for file_index in range(len(file_values)):
            file_value: object = file_values[file_index]
            if isinstance(file_value, dict):
                relative_value: object = file_value.get("path", None)
                size_value: object = file_value.get("size_bytes", None)
                digest_value: object = file_value.get("sha256", None)
                record_is_valid: bool = bool(
                    set(file_value.keys()) == {"path", "size_bytes", "sha256"}
                    and isinstance(relative_value, str)
                    and type(size_value) is int
                    and isinstance(digest_value, str)
                    and re.fullmatch(r"[0-9a-f]{64}", digest_value) is not None
                    and relative_value in expected_files
                    and relative_value != "manifest.json"
                    and relative_value not in recorded_paths
                )
                if record_is_valid:
                    recorded_paths.add(relative_value)
                    recorded_order[file_index] = relative_value
                    file_path: Path = package_root / relative_value
                    empty_record: bool = bool(
                        size_value == 0
                        and digest_value
                        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    )
                    if empty_record:
                        if file_path.read_bytes() == b"":
                            pass
                        else:
                            raise ValueError("Recorded empty evidence file is not empty")
                    else:
                        verify_regular_file_identity(
                            file_path, int(size_value), digest_value
                        )
                else:
                    raise ValueError("FMI.jl package file record is invalid")
            else:
                raise ValueError("FMI.jl package file record is not an object")
    else:
        raise ValueError("FMI.jl manifest does not record eight evidence files")
    expected_evidence_order: tuple[str, ...] = (
        "inputs/fmi_jl_runner.jl",
        "raw/fmi-jl-stdout.log",
        "raw/fmi-jl-stderr.log",
        "raw/fmi-jl-trace.csv",
        "raw/veragrid-reference.csv",
        "figures/fmi-jl-smib-composition.png",
        "figures/fmi-jl-smib-composition.svg",
        "figures/fmi-jl-smib-composition.pdf",
    )
    if len(recorded_paths) == 8 and tuple(recorded_order) == expected_evidence_order:
        pass
    else:
        raise ValueError("FMI.jl package file identities or order are incomplete")

    # These two copied inputs remain anchored to caller-sealed identities rather
    # than merely agreeing with self-consistent manifest records.
    verify_regular_file_identity(
        package_root / "inputs/fmi_jl_runner.jl",
        config.runner_size_bytes,
        config.runner_sha256,
    )
    verify_regular_file_identity(
        package_root / "raw/veragrid-reference.csv",
        279085,
        "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45",
    )

    stdout_text: str = (package_root / "raw/fmi-jl-stdout.log").read_text(
        encoding="utf-8"
    )
    stderr_text: str = (package_root / "raw/fmi-jl-stderr.log").read_text(
        encoding="utf-8"
    )
    stdout_is_exact: bool = bool(
        stdout_text
        == "Julia 1.12.6\nFMI.jl 0.15.2\nPASS FMI.jl rows=2001 signals=7\n"
        and stderr_text == ""
    )
    if stdout_is_exact:
        pass
    else:
        raise ValueError("FMI.jl process logs are not the sealed success result")

    candidate: FmiJlTrace = _parse_fmi_jl_trace(
        package_root / "raw/fmi-jl-trace.csv"
    )
    reference: FmiJlTrace = _parse_fmi_jl_trace(
        package_root / "raw/veragrid-reference.csv"
    )
    recomputed_metrics: FmiJlMetrics = _evaluate_fmi_jl(candidate, reference)
    comparison_value: object = manifest["comparison"]
    if isinstance(comparison_value, dict):
        recorded_maximum: np.ndarray = np.asarray(
            comparison_value.get("maximum_absolute_errors", list()), dtype=float
        )
        recorded_rms: np.ndarray = np.asarray(
            comparison_value.get("rms_absolute_errors", list()), dtype=float
        )
        expected_comparison: dict[str, object] = {
            "absolute_tolerance": 1.0e-12,
            "maximum_absolute_errors": (
                recomputed_metrics.maximum_absolute_errors.tolist()
            ),
            "rms_absolute_errors": recomputed_metrics.rms_absolute_errors.tolist(),
        }
        recorded_comparison_json: str = json.dumps(
            comparison_value, sort_keys=True, separators=(",", ":")
        )
        expected_comparison_json: str = json.dumps(
            expected_comparison, sort_keys=True, separators=(",", ":")
        )
        metrics_match: bool = bool(
            recorded_maximum.shape == (8,)
            and recorded_rms.shape == (8,)
            and np.array_equal(
                recorded_maximum, recomputed_metrics.maximum_absolute_errors
            )
            and np.array_equal(recorded_rms, recomputed_metrics.rms_absolute_errors)
            and recorded_comparison_json == expected_comparison_json
        )
    else:
        metrics_match = False
    if metrics_match:
        pass
    else:
        raise ValueError("FMI.jl manifest metrics do not recompute exactly")

    png_path: Path = package_root / "figures/fmi-jl-smib-composition.png"
    png_values: np.ndarray = mpimg.imread(png_path)
    svg_text: str = (
        package_root / "figures/fmi-jl-smib-composition.svg"
    ).read_text(encoding="utf-8")
    pdf_bytes: bytes = (
        package_root / "figures/fmi-jl-smib-composition.pdf"
    ).read_bytes()
    figure_contract_is_valid: bool = bool(
        png_values.shape[0] == 2100
        and png_values.shape[1] == 2160
        and "Rotor angle" in svg_text
        and "FMI.jl 0.15.2 versus VeraGrid" in svg_text
        and "<text" in svg_text
        and b"/MediaBox [ 0 0 518.4 504 ]" in pdf_bytes
        and (b"/FontFile2" in pdf_bytes or b"/Subtype /Type0" in pdf_bytes)
    )
    if figure_contract_is_valid:
        pass
    else:
        raise ValueError("FMI.jl figure geometry or vector text is invalid")


def generate_fmi_jl_comparison(config: FmiJlComparisonConfig) -> Path:
    """Execute, compare, render, verify and atomically publish FMI.jl evidence.

    :param config: Closed comparison configuration.
    :return: Published nine-file evidence-package path.
    """

    if not config.output_directory.exists() and config.output_directory.parent.is_dir():
        pass
    else:
        raise ValueError("FMI.jl output directory must be new with an existing parent")
    _authenticate_fmi_jl_inputs(config)

    reference_manifest_value: object = json.loads(
        config.reference_manifest_path.read_text(encoding="utf-8")
    )
    if isinstance(reference_manifest_value, dict):
        reference_manifest: dict[str, object] = reference_manifest_value
    else:
        raise ValueError("Reference manifest root is invalid")
    traces_value: object = reference_manifest.get("traces", None)
    reference_contract_is_valid: bool = bool(
        reference_manifest.get("schema", None)
        == "veragrid.fmi-maestro-comparison/1"
        and reference_manifest.get("status", None) == "PASS"
        and isinstance(traces_value, dict)
    )
    if reference_contract_is_valid and isinstance(traces_value, dict):
        trace_value: object = traces_value.get("veragrid_closed", None)
    else:
        raise ValueError("Reference manifest is not the sealed Maestro package")
    if isinstance(trace_value, dict):
        relative_value: object = trace_value.get("relative_path", None)
        size_value: object = trace_value.get("size_bytes", None)
        digest_value: object = trace_value.get("sha256", None)
    else:
        raise ValueError("Reference manifest lacks the VeraGrid closed trace")
    trace_record_is_valid: bool = bool(
        isinstance(relative_value, str)
        and relative_value == "raw/veragrid-closed-outputs.csv"
        and type(size_value) is int
        and size_value == 279085
        and isinstance(digest_value, str)
        and digest_value
        == "5dd944e79ca8646f377d31bd63e6f8c41069ee69c349063be082ee904e04ec45"
    )
    if trace_record_is_valid:
        reference_trace_path: Path = config.reference_manifest_path.parent / relative_value
        verify_regular_file_identity(reference_trace_path, size_value, digest_value)
    else:
        raise ValueError("Reference trace identity is not the approved oracle")

    temporary_text: str = tempfile.mkdtemp(
        prefix=".fmi-jl-comparison-", dir=config.output_directory.parent
    )
    temporary_root: Path = Path(temporary_text)
    package_root: Path = temporary_root / "package"
    work_root: Path = temporary_root / "work"
    depot_workspace: FmiJlDepotWorkspace | None = None
    published: bool = False
    try:
        inputs_root: Path = package_root / "inputs"
        raw_root: Path = package_root / "raw"
        figures_root: Path = package_root / "figures"
        inputs_root.mkdir(parents=True)
        raw_root.mkdir()
        figures_root.mkdir()
        work_root.mkdir()

        # Julia receives an owned write layer and a verified immutable package
        # layer, never the shared source depot used to prepare that copy.
        depot_workspace = _prepare_fmi_jl_depot_workspace(config)

        staged_runner: Path = inputs_root / "fmi_jl_runner.jl"
        staged_plant: Path = work_root / "SMIBNetworkPlant.fmu"
        staged_governor: Path = work_root / "SMIBGovernorController.fmu"
        shutil.copyfile(config.runner_path, staged_runner)
        shutil.copyfile(config.plant_fmu_path, staged_plant)
        shutil.copyfile(config.governor_fmu_path, staged_governor)
        verify_regular_file_identity(
            staged_runner, config.runner_size_bytes, config.runner_sha256
        )
        verify_regular_file_identity(
            staged_plant, config.plant_fmu_size_bytes, config.plant_fmu_sha256
        )
        verify_regular_file_identity(
            staged_governor,
            config.governor_fmu_size_bytes,
            config.governor_fmu_sha256,
        )

        candidate_trace_path: Path = raw_root / "fmi-jl-trace.csv"
        arguments: list[str] = [
            str(config.wsl_executable_path),
            "-d",
            config.wsl_distribution,
            "--",
            "/usr/bin/env",
            "-i",
            "HOME=" + config.wsl_home,
            "JULIA_DEPOT_PATH="
            + depot_workspace.writable_overlay_path
            + ":"
            + depot_workspace.read_only_depot_path,
            "JULIA_PKG_PRECOMPILE_AUTO=0",
            _wsl_unc_path(config.julia_executable_path, config.wsl_distribution),
            "--startup-file=no",
            "--history-file=no",
            "--project="
            + _wsl_unc_path(config.julia_project_path.parent, config.wsl_distribution),
            _windows_path_to_wsl(staged_runner),
            _windows_path_to_wsl(staged_plant),
            config.plant_fmu_sha256,
            _windows_path_to_wsl(staged_governor),
            config.governor_fmu_sha256,
            _windows_path_to_wsl(candidate_trace_path),
        ]
        process_result: FmiJlProcessResult = _run_fmi_jl_process(
            arguments,
            config.process_timeout_seconds,
            config.stream_limit_bytes,
        )
        expected_stdout: str = (
            "Julia 1.12.6\nFMI.jl 0.15.2\n"
            "PASS FMI.jl rows=2001 signals=7\n"
        )
        process_passes: bool = bool(
            process_result.exit_code == 0
            and process_result.stdout_text == expected_stdout
            and process_result.stderr_text == ""
        )
        if process_passes:
            pass
        else:
            raise RuntimeError("FMI.jl did not emit the sealed success contract")

        # Reauthenticate the private depot and every immutable shared/staged input
        # after native execution so runtime activity cannot alter the evidence base.
        _verify_fmi_jl_depot_permissions(config, depot_workspace)
        _authenticate_fmi_jl_inputs(config)
        verify_regular_file_identity(
            staged_runner, config.runner_size_bytes, config.runner_sha256
        )
        verify_regular_file_identity(
            staged_plant, config.plant_fmu_size_bytes, config.plant_fmu_sha256
        )
        verify_regular_file_identity(
            staged_governor,
            config.governor_fmu_size_bytes,
            config.governor_fmu_sha256,
        )
        stdout_path: Path = raw_root / "fmi-jl-stdout.log"
        stderr_path: Path = raw_root / "fmi-jl-stderr.log"
        reference_copy_path: Path = raw_root / "veragrid-reference.csv"
        stdout_path.write_text(process_result.stdout_text, encoding="utf-8")
        stderr_path.write_text(process_result.stderr_text, encoding="utf-8")
        shutil.copyfile(reference_trace_path, reference_copy_path)
        verify_regular_file_identity(reference_copy_path, size_value, digest_value)

        candidate: FmiJlTrace = _parse_fmi_jl_trace(candidate_trace_path)
        reference: FmiJlTrace = _parse_fmi_jl_trace(reference_copy_path)
        metrics: FmiJlMetrics = _evaluate_fmi_jl(candidate, reference)
        figure_stem: Path = figures_root / "fmi-jl-smib-composition"
        _render_fmi_jl_figure(candidate, reference, figure_stem)
        evidence_paths: tuple[Path, ...] = (
            staged_runner,
            stdout_path,
            stderr_path,
            candidate_trace_path,
            reference_copy_path,
            figure_stem.with_suffix(".png"),
            figure_stem.with_suffix(".svg"),
            figure_stem.with_suffix(".pdf"),
        )
        _write_fmi_jl_manifest(
            config,
            package_root,
            process_result,
            candidate,
            metrics,
            evidence_paths,
        )
        _verify_fmi_jl_package(config, package_root)
        package_root.replace(config.output_directory)
        _verify_fmi_jl_package(config, config.output_directory)
        published = True
    finally:
        try:
            if depot_workspace is not None:
                _remove_fmi_jl_depot_workspace(config, depot_workspace)
            else:
                pass
        finally:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
            else:
                pass
    if published:
        return config.output_directory
    else:
        raise RuntimeError("FMI.jl package was not published")
