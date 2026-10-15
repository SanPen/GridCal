# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Validate the pinned Reference FMUs with FMPy and VDMCheck."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time
from typing import BinaryIO, cast
import zipfile

from fmpy.validation import validate_fmu

from VeraGridEngine.enumerations import FmiVersion, FmuInterfaceMode
from examples.fmi.evidence_identity import (
    read_regular_tree_identity,
    verify_regular_file_identity,
)
from examples.fmi.reference_fmu import (
    ReferenceFmuCatalog,
    ReferenceFmuCase,
    ValidatedReferenceFmuAsset,
    load_reference_fmu_catalog,
)
from examples.fmi.reference_fmu_execution import (
    read_fmpy_distribution_identity,
)


class VdmCheckValidationVerdict(str, Enum):
    """Verdicts emitted independently by either static validator."""

    PASS = "pass"
    FAIL = "fail"


class VdmCheckRunStatus(str, Enum):
    """Top-level outcomes of a completed dual-validator package."""

    PASS = "pass"
    COMPLETED_WITH_FINDINGS = "completed_with_findings"


class VdmCheckValidationConfig:
    """Own the explicit paths, identities and limits for one validation run."""

    __slots__ = (
        "output_directory",
        "source_branch",
        "source_revision",
        "source_tree_sha256",
        "catalog_path",
        "corpus_root",
        "fmpy_expected_version",
        "fmpy_expected_distribution_sha256",
        "java_runtime_root",
        "java_runtime_expected_file_count",
        "java_runtime_expected_total_size_bytes",
        "java_runtime_expected_tree_sha256",
        "java_expected_version",
        "vdmcheck_two_root",
        "vdmcheck_two_expected_file_count",
        "vdmcheck_two_expected_total_size_bytes",
        "vdmcheck_two_expected_tree_sha256",
        "vdmcheck_two_expected_version",
        "vdmcheck_three_root",
        "vdmcheck_three_expected_file_count",
        "vdmcheck_three_expected_total_size_bytes",
        "vdmcheck_three_expected_tree_sha256",
        "vdmcheck_three_expected_version",
        "process_timeout_seconds",
        "stream_limit_bytes",
    )

    output_directory: Path
    source_branch: str
    source_revision: str
    source_tree_sha256: str
    catalog_path: Path
    corpus_root: Path
    fmpy_expected_version: str
    fmpy_expected_distribution_sha256: str
    java_runtime_root: Path
    java_runtime_expected_file_count: int
    java_runtime_expected_total_size_bytes: int
    java_runtime_expected_tree_sha256: str
    java_expected_version: str
    vdmcheck_two_root: Path
    vdmcheck_two_expected_file_count: int
    vdmcheck_two_expected_total_size_bytes: int
    vdmcheck_two_expected_tree_sha256: str
    vdmcheck_two_expected_version: str
    vdmcheck_three_root: Path
    vdmcheck_three_expected_file_count: int
    vdmcheck_three_expected_total_size_bytes: int
    vdmcheck_three_expected_tree_sha256: str
    vdmcheck_three_expected_version: str
    process_timeout_seconds: float
    stream_limit_bytes: int

    def __init__(
        self,
        output_directory: Path,
        source_branch: str,
        source_revision: str,
        source_tree_sha256: str,
        catalog_path: Path,
        corpus_root: Path,
        fmpy_expected_version: str,
        fmpy_expected_distribution_sha256: str,
        java_runtime_root: Path,
        java_runtime_expected_file_count: int,
        java_runtime_expected_total_size_bytes: int,
        java_runtime_expected_tree_sha256: str,
        java_expected_version: str,
        vdmcheck_two_root: Path,
        vdmcheck_two_expected_file_count: int,
        vdmcheck_two_expected_total_size_bytes: int,
        vdmcheck_two_expected_tree_sha256: str,
        vdmcheck_two_expected_version: str,
        vdmcheck_three_root: Path,
        vdmcheck_three_expected_file_count: int,
        vdmcheck_three_expected_total_size_bytes: int,
        vdmcheck_three_expected_tree_sha256: str,
        vdmcheck_three_expected_version: str,
        process_timeout_seconds: float,
        stream_limit_bytes: int,
    ) -> None:
        """Validate the complete caller-supplied execution boundary.

        :param output_directory: Nonexistent final evidence directory.
        :param source_branch: Exact source branch represented by the package.
        :param source_revision: Forty-character source commit identifier.
        :param source_tree_sha256: Digest of the candidate source-tree state.
        :param catalog_path: Explicit pinned Reference FMU catalog path.
        :param corpus_root: Explicit root containing the pinned FMU files.
        :param fmpy_expected_version: Required installed FMPy version.
        :param fmpy_expected_distribution_sha256: Required FMPy tree digest.
        :param java_runtime_root: Root of the closed caller-owned JRE tree.
        :param java_runtime_expected_file_count: Required JRE file cardinality.
        :param java_runtime_expected_total_size_bytes: Required aggregate JRE size.
        :param java_runtime_expected_tree_sha256: Required deterministic JRE digest.
        :param java_expected_version: Exact Java Runtime Environment version line.
        :param vdmcheck_two_root: Complete caller-owned FMI 2 VDMCheck tree.
        :param vdmcheck_two_expected_file_count: Required FMI 2 file cardinality.
        :param vdmcheck_two_expected_total_size_bytes: Required FMI 2 aggregate size.
        :param vdmcheck_two_expected_tree_sha256: Required FMI 2 tree digest.
        :param vdmcheck_two_expected_version: Required FMI 2 implementation version.
        :param vdmcheck_three_root: Complete caller-owned FMI 3 VDMCheck tree.
        :param vdmcheck_three_expected_file_count: Required FMI 3 file cardinality.
        :param vdmcheck_three_expected_total_size_bytes: Required FMI 3 aggregate size.
        :param vdmcheck_three_expected_tree_sha256: Required FMI 3 tree digest.
        :param vdmcheck_three_expected_version: Required FMI 3 implementation version.
        :param process_timeout_seconds: Hard deadline for each external process.
        :param stream_limit_bytes: Independent byte limit for stdout and stderr.
        :return: None.
        """

        # Configuration validation happens before any external process can run.
        path_types_are_valid: bool = bool(
            isinstance(output_directory, Path)
            and isinstance(catalog_path, Path)
            and isinstance(corpus_root, Path)
            and isinstance(java_runtime_root, Path)
            and isinstance(vdmcheck_two_root, Path)
            and isinstance(vdmcheck_three_root, Path)
        )
        text_values: tuple[object, ...] = (
            source_branch,
            source_revision,
            source_tree_sha256,
            fmpy_expected_version,
            fmpy_expected_distribution_sha256,
            java_runtime_expected_tree_sha256,
            java_expected_version,
            vdmcheck_two_expected_tree_sha256,
            vdmcheck_two_expected_version,
            vdmcheck_three_expected_tree_sha256,
            vdmcheck_three_expected_version,
        )
        text_types_are_valid: bool = all(
            isinstance(value, str) and bool(value.strip())
            for value in text_values
        )
        identities_are_valid: bool = bool(
            source_branch == "devel_dynamics_rebuild"
            and re.fullmatch(r"[0-9a-f]{40}", source_revision) is not None
            and re.fullmatch(r"[0-9a-f]{64}", source_tree_sha256) is not None
            and fmpy_expected_version == "0.3.31"
            and fmpy_expected_distribution_sha256
            == "39eb2d78370dd241001e5724734f79caf2afcaafc968ba8f93afc597a0337e85"
            and re.fullmatch(r"[0-9a-f]{64}", java_runtime_expected_tree_sha256)
            is not None
            and re.fullmatch(r"[0-9a-f]{64}", vdmcheck_two_expected_tree_sha256)
            is not None
            and re.fullmatch(r"[0-9a-f]{64}", vdmcheck_three_expected_tree_sha256)
            is not None
        )
        integer_values: tuple[object, ...] = (
            java_runtime_expected_file_count,
            java_runtime_expected_total_size_bytes,
            vdmcheck_two_expected_file_count,
            vdmcheck_two_expected_total_size_bytes,
            vdmcheck_three_expected_file_count,
            vdmcheck_three_expected_total_size_bytes,
            stream_limit_bytes,
        )
        integer_values_are_valid: bool = all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
            for value in integer_values
        )
        timeout_is_valid: bool = bool(
            isinstance(process_timeout_seconds, (int, float))
            and not isinstance(process_timeout_seconds, bool)
            and 0.0 < float(process_timeout_seconds) <= 300.0
        )
        pinned_tools_are_valid: bool = bool(
            java_runtime_expected_file_count == 315
            and java_runtime_expected_total_size_bytes == 151_523_285
            and java_runtime_expected_tree_sha256
            == "98792300be37d6f994a12fd96459604c94e8c6c3f443c002e1df8a35a16b9408"
            and vdmcheck_two_expected_file_count == 55
            and vdmcheck_two_expected_total_size_bytes == 3_155_146
            and vdmcheck_two_expected_tree_sha256
            == "36facab758b6c2f45de5cde45a93ddec02f5efc37eaaecb962eaad0ca925bd1f"
            and vdmcheck_two_expected_version == "1.1.3 build 241016"
            and vdmcheck_three_expected_file_count == 56
            and vdmcheck_three_expected_total_size_bytes == 3_760_225
            and vdmcheck_three_expected_tree_sha256
            == "26c80b20d52febb7041aaf4bbd38767b1b9a76311a63e0ae20a97cd64606d2cc"
            and vdmcheck_three_expected_version == "1.1.3 build 241016"
            and stream_limit_bytes == 1_048_576
        )
        if (
            path_types_are_valid
            and text_types_are_valid
            and identities_are_valid
            and integer_values_are_valid
            and timeout_is_valid
            and pinned_tools_are_valid
        ):
            pass
        else:
            raise ValueError("VDMCheck validation configuration is invalid")

        # Publication uses a new same-parent directory and never overwrites evidence.
        output_parent: Path = output_directory.parent
        paths_are_safe: bool = bool(
            not output_directory.exists()
            and output_parent.exists()
            and output_parent.is_dir()
            and not output_parent.is_symlink()
            and catalog_path.exists()
            and catalog_path.is_file()
            and not catalog_path.is_symlink()
            and corpus_root.exists()
            and corpus_root.is_dir()
            and not corpus_root.is_symlink()
            and java_runtime_root.exists()
            and java_runtime_root.is_dir()
            and not java_runtime_root.is_symlink()
            and vdmcheck_two_root.exists()
            and vdmcheck_two_root.is_dir()
            and not vdmcheck_two_root.is_symlink()
            and vdmcheck_three_root.exists()
            and vdmcheck_three_root.is_dir()
            and not vdmcheck_three_root.is_symlink()
        )
        if paths_are_safe:
            pass
        else:
            raise ValueError("VDMCheck validation paths are unsafe or unavailable")

        self.output_directory: Path = output_directory
        self.source_branch: str = source_branch
        self.source_revision: str = source_revision
        self.source_tree_sha256: str = source_tree_sha256
        self.catalog_path: Path = catalog_path
        self.corpus_root: Path = corpus_root
        self.fmpy_expected_version: str = fmpy_expected_version
        self.fmpy_expected_distribution_sha256: str = (
            fmpy_expected_distribution_sha256
        )
        self.java_runtime_root: Path = java_runtime_root
        self.java_runtime_expected_file_count: int = (
            java_runtime_expected_file_count
        )
        self.java_runtime_expected_total_size_bytes: int = (
            java_runtime_expected_total_size_bytes
        )
        self.java_runtime_expected_tree_sha256: str = (
            java_runtime_expected_tree_sha256
        )
        self.java_expected_version: str = java_expected_version
        self.vdmcheck_two_root: Path = vdmcheck_two_root
        self.vdmcheck_two_expected_file_count: int = (
            vdmcheck_two_expected_file_count
        )
        self.vdmcheck_two_expected_total_size_bytes: int = (
            vdmcheck_two_expected_total_size_bytes
        )
        self.vdmcheck_two_expected_tree_sha256: str = (
            vdmcheck_two_expected_tree_sha256
        )
        self.vdmcheck_two_expected_version: str = vdmcheck_two_expected_version
        self.vdmcheck_three_root: Path = vdmcheck_three_root
        self.vdmcheck_three_expected_file_count: int = (
            vdmcheck_three_expected_file_count
        )
        self.vdmcheck_three_expected_total_size_bytes: int = (
            vdmcheck_three_expected_total_size_bytes
        )
        self.vdmcheck_three_expected_tree_sha256: str = (
            vdmcheck_three_expected_tree_sha256
        )
        self.vdmcheck_three_expected_version: str = (
            vdmcheck_three_expected_version
        )
        self.process_timeout_seconds: float = float(process_timeout_seconds)
        self.stream_limit_bytes: int = stream_limit_bytes


class VdmCheckProcessResult:
    """Own the bounded raw text returned by one completed VDMCheck process."""

    __slots__ = ("exit_code", "stdout_text", "stderr_text")

    exit_code: int
    stdout_text: str
    stderr_text: str

    def __init__(
        self,
        exit_code: int,
        stdout_text: str,
        stderr_text: str,
    ) -> None:
        """Validate one completed process observation.

        :param exit_code: Native process exit code.
        :param stdout_text: Strictly decoded standard output.
        :param stderr_text: Strictly decoded standard error.
        :return: None.
        """

        values_are_valid: bool = bool(
            isinstance(exit_code, int)
            and not isinstance(exit_code, bool)
            and isinstance(stdout_text, str)
            and isinstance(stderr_text, str)
        )
        if values_are_valid:
            pass
        else:
            raise ValueError("VDMCheck process result types are invalid")
        self.exit_code: int = exit_code
        self.stdout_text: str = stdout_text
        self.stderr_text: str = stderr_text


class VdmCheckCellResult:
    """Own both validator verdicts and retained log identities for one FMU."""

    __slots__ = (
        "case_id",
        "model_name",
        "fmi_version",
        "declared_interfaces",
        "fmu_size_bytes",
        "fmu_sha256",
        "fmpy_verdict",
        "fmpy_findings",
        "vdmcheck_verdict",
        "vdmcheck_exit_code",
        "vdmcheck_findings",
        "stdout_relative_path",
        "stdout_sha256",
        "stderr_relative_path",
        "stderr_sha256",
    )

    case_id: str
    model_name: str
    fmi_version: FmiVersion
    declared_interfaces: tuple[FmuInterfaceMode, ...]
    fmu_size_bytes: int
    fmu_sha256: str
    fmpy_verdict: VdmCheckValidationVerdict
    fmpy_findings: tuple[str, ...]
    vdmcheck_verdict: VdmCheckValidationVerdict
    vdmcheck_exit_code: int
    vdmcheck_findings: tuple[str, ...]
    stdout_relative_path: str
    stdout_sha256: str
    stderr_relative_path: str
    stderr_sha256: str

    def __init__(
        self,
        case_id: str,
        model_name: str,
        fmi_version: FmiVersion,
        declared_interfaces: tuple[FmuInterfaceMode, ...],
        fmu_size_bytes: int,
        fmu_sha256: str,
        fmpy_verdict: VdmCheckValidationVerdict,
        fmpy_findings: tuple[str, ...],
        vdmcheck_verdict: VdmCheckValidationVerdict,
        vdmcheck_exit_code: int,
        vdmcheck_findings: tuple[str, ...],
        stdout_relative_path: str,
        stdout_sha256: str,
        stderr_relative_path: str,
        stderr_sha256: str,
    ) -> None:
        """Validate one immutable dual-validator cell.

        :param case_id: Stable Reference FMU case identifier.
        :param model_name: Model name declared by the canonical case.
        :param fmi_version: FMI specification family selected for VDMCheck.
        :param declared_interfaces: Canonical CS and ME interface declarations.
        :param fmu_size_bytes: Exact validated FMU byte count.
        :param fmu_sha256: Exact validated FMU digest.
        :param fmpy_verdict: Independent FMPy validation verdict.
        :param fmpy_findings: Native FMPy findings without rewriting.
        :param vdmcheck_verdict: Native VDMCheck validation verdict.
        :param vdmcheck_exit_code: Native VDMCheck exit code.
        :param vdmcheck_findings: Parsed VDMCheck diagnostic lines.
        :param stdout_relative_path: Portable retained stdout path.
        :param stdout_sha256: Digest of retained stdout bytes.
        :param stderr_relative_path: Portable retained stderr path.
        :param stderr_sha256: Digest of retained stderr bytes.
        :return: None.
        """

        expected_interfaces: tuple[FmuInterfaceMode, ...] = (
            FmuInterfaceMode.CO_SIMULATION,
            FmuInterfaceMode.MODEL_EXCHANGE,
        )
        identity_is_valid: bool = bool(
            isinstance(case_id, str)
            and bool(case_id)
            and isinstance(model_name, str)
            and bool(model_name)
            and isinstance(fmi_version, FmiVersion)
            and declared_interfaces == expected_interfaces
            and isinstance(fmu_size_bytes, int)
            and not isinstance(fmu_size_bytes, bool)
            and fmu_size_bytes > 0
            and re.fullmatch(r"[0-9a-f]{64}", fmu_sha256) is not None
        )
        verdicts_are_valid: bool = bool(
            isinstance(fmpy_verdict, VdmCheckValidationVerdict)
            and isinstance(vdmcheck_verdict, VdmCheckValidationVerdict)
            and isinstance(vdmcheck_exit_code, int)
            and not isinstance(vdmcheck_exit_code, bool)
            and isinstance(fmpy_findings, tuple)
            and all(isinstance(finding, str) for finding in fmpy_findings)
            and isinstance(vdmcheck_findings, tuple)
            and all(isinstance(finding, str) for finding in vdmcheck_findings)
        )
        verdicts_are_coherent: bool = bool(
            (
                fmpy_verdict == VdmCheckValidationVerdict.PASS
                and len(fmpy_findings) == 0
            )
            or (
                fmpy_verdict == VdmCheckValidationVerdict.FAIL
                and len(fmpy_findings) > 0
            )
        )
        vdmcheck_is_coherent: bool = bool(
            (
                vdmcheck_verdict == VdmCheckValidationVerdict.PASS
                and vdmcheck_exit_code == 0
                and len(vdmcheck_findings) == 0
            )
            or (
                vdmcheck_verdict == VdmCheckValidationVerdict.FAIL
                and vdmcheck_exit_code == 1
                and len(vdmcheck_findings) > 0
            )
        )
        paths_are_valid: bool = bool(
            isinstance(stdout_relative_path, str)
            and re.fullmatch(
                r"raw/cell-[0-9]{2}--[a-z0-9.-]+/stdout\.log",
                stdout_relative_path,
            )
            is not None
            and isinstance(stderr_relative_path, str)
            and re.fullmatch(
                r"raw/cell-[0-9]{2}--[a-z0-9.-]+/stderr\.log",
                stderr_relative_path,
            )
            is not None
            and re.fullmatch(r"[0-9a-f]{64}", stdout_sha256) is not None
            and re.fullmatch(r"[0-9a-f]{64}", stderr_sha256) is not None
        )
        if (
            identity_is_valid
            and verdicts_are_valid
            and verdicts_are_coherent
            and vdmcheck_is_coherent
            and paths_are_valid
        ):
            pass
        else:
            raise ValueError("VDMCheck cell result is invalid or inconsistent")

        self.case_id: str = case_id
        self.model_name: str = model_name
        self.fmi_version: FmiVersion = fmi_version
        self.declared_interfaces: tuple[FmuInterfaceMode, ...] = (
            declared_interfaces
        )
        self.fmu_size_bytes: int = fmu_size_bytes
        self.fmu_sha256: str = fmu_sha256
        self.fmpy_verdict: VdmCheckValidationVerdict = fmpy_verdict
        self.fmpy_findings: tuple[str, ...] = fmpy_findings
        self.vdmcheck_verdict: VdmCheckValidationVerdict = vdmcheck_verdict
        self.vdmcheck_exit_code: int = vdmcheck_exit_code
        self.vdmcheck_findings: tuple[str, ...] = vdmcheck_findings
        self.stdout_relative_path: str = stdout_relative_path
        self.stdout_sha256: str = stdout_sha256
        self.stderr_relative_path: str = stderr_relative_path
        self.stderr_sha256: str = stderr_sha256


def _read_vdmcheck_jar_version(jar_content: bytes) -> str:
    """Read the unique VDMCheck implementation version from JAR bytes.

    :param jar_content: Previously authenticated complete JAR content.
    :return: Exact ``Implementation-Version`` manifest value.
    """

    if isinstance(jar_content, bytes) and len(jar_content) > 0:
        pass
    else:
        raise ValueError("VDMCheck JAR content is invalid")
    archive_stream: io.BytesIO = io.BytesIO(jar_content)
    archive: zipfile.ZipFile = zipfile.ZipFile(archive_stream, mode="r")
    try:
        manifest_info: zipfile.ZipInfo = archive.getinfo("META-INF/MANIFEST.MF")
        manifest_is_safe: bool = bool(
            manifest_info.file_size > 0
            and manifest_info.file_size <= 65_536
            and manifest_info.compress_size <= 65_536
            and not bool(manifest_info.flag_bits & 0x1)
        )
        if manifest_is_safe:
            manifest_content: bytes = archive.read(manifest_info)
        else:
            raise ValueError("VDMCheck JAR manifest is unsafe or oversized")
    finally:
        archive.close()
        archive_stream.close()
    manifest_text: str = manifest_content.decode("utf-8", errors="strict")
    canonical_text: str = manifest_text.replace("\r\n", "\n")
    if "\r" in canonical_text:
        raise ValueError("VDMCheck JAR manifest has unsupported line endings")
    else:
        pass
    versions: list[str] = list()
    manifest_lines: list[str] = canonical_text.split("\n")
    for manifest_line in manifest_lines:
        if manifest_line.startswith("Implementation-Version: "):
            versions.append(manifest_line.removeprefix("Implementation-Version: "))
        else:
            pass
    if len(versions) == 1 and bool(versions[0]):
        return versions[0]
    else:
        raise ValueError("VDMCheck JAR implementation version is absent or duplicated")


def _read_java_version(
    java_executable: Path,
    timeout_seconds: float,
    stream_limit_bytes: int,
) -> str:
    """Read the exact runtime-version line from authenticated Java.

    :param java_executable: Canonical launcher derived from the authenticated JRE root.
    :param timeout_seconds: Hard deadline for the version process.
    :param stream_limit_bytes: Maximum accepted bytes for either process stream.
    :return: Exact Java Runtime Environment version line.
    """

    arguments_are_valid: bool = bool(
        isinstance(java_executable, Path)
        and java_executable.exists()
        and java_executable.is_file()
        and not java_executable.is_symlink()
        and isinstance(timeout_seconds, (int, float))
        and not isinstance(timeout_seconds, bool)
        and float(timeout_seconds) > 0.0
        and isinstance(stream_limit_bytes, int)
        and not isinstance(stream_limit_bytes, bool)
        and stream_limit_bytes > 0
    )
    if arguments_are_valid:
        pass
    else:
        raise ValueError("Java version process arguments are invalid")

    # The authenticated JRE is trusted to emit its short version output; the
    # deadline and post-process byte gates still fail closed on corruption.
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        (str(java_executable), "-version"),
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=float(timeout_seconds),
        check=False,
    )
    streams_are_bounded: bool = bool(
        len(completed_process.stdout) <= stream_limit_bytes
        and len(completed_process.stderr) <= stream_limit_bytes
    )
    if streams_are_bounded and completed_process.returncode == 0:
        pass
    else:
        raise ValueError("Java version process failed or exceeded its stream limit")
    stdout_text: str = completed_process.stdout.decode("utf-8", errors="strict")
    stderr_text: str = completed_process.stderr.decode("utf-8", errors="strict")
    if stdout_text == "" and stderr_text.endswith("\n"):
        pass
    else:
        raise ValueError("Java version streams have unexpected structure")
    canonical_stderr: str = stderr_text.replace("\r\n", "\n")
    if "\r" in canonical_stderr:
        raise ValueError("Java version output has unsupported line endings")
    else:
        pass
    runtime_lines: list[str] = list()
    version_lines: list[str] = canonical_stderr[:-1].split("\n")
    for version_line in version_lines:
        if version_line.startswith("OpenJDK Runtime Environment "):
            runtime_lines.append(version_line)
        else:
            pass
    if len(runtime_lines) == 1:
        return runtime_lines[0]
    else:
        raise ValueError("Java Runtime Environment version line is absent or duplicated")


def _run_vdmcheck_process(
    java_executable: Path,
    jar_path: Path,
    fmu_path: Path,
    timeout_seconds: float,
    stream_limit_bytes: int,
) -> VdmCheckProcessResult:
    """Run one shell-free VDMCheck process with hard time and byte bounds.

    :param java_executable: Canonical launcher inside the authenticated JRE.
    :param jar_path: Authenticated staged VDMCheck JAR.
    :param fmu_path: Authenticated staged FMU archive.
    :param timeout_seconds: Hard process deadline.
    :param stream_limit_bytes: Independent raw byte limit for each stream.
    :return: Completed native exit code and strictly decoded streams.
    """

    arguments_are_valid: bool = bool(
        isinstance(java_executable, Path)
        and java_executable.is_file()
        and not java_executable.is_symlink()
        and isinstance(jar_path, Path)
        and jar_path.is_file()
        and not jar_path.is_symlink()
        and isinstance(fmu_path, Path)
        and fmu_path.is_file()
        and not fmu_path.is_symlink()
        and isinstance(timeout_seconds, (int, float))
        and not isinstance(timeout_seconds, bool)
        and float(timeout_seconds) > 0.0
        and isinstance(stream_limit_bytes, int)
        and not isinstance(stream_limit_bytes, bool)
        and stream_limit_bytes > 0
    )
    if arguments_are_valid:
        pass
    else:
        raise ValueError("Bounded VDMCheck process arguments are invalid")

    # Anonymous file-backed streams allow the parent to monitor size without
    # retaining a partial artifact or buffering unbounded child output in RAM.
    stdout_file: BinaryIO = tempfile.TemporaryFile(mode="w+b")
    stderr_file: BinaryIO = tempfile.TemporaryFile(mode="w+b")
    process: subprocess.Popen[bytes] | None = None
    result: VdmCheckProcessResult | None = None
    started_at: float = time.monotonic()
    try:
        process = subprocess.Popen(
            (
                str(java_executable),
                "-jar",
                str(jar_path),
                "-v",
                os.devnull,
                str(fmu_path),
            ),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        process_finished: bool = False
        while not process_finished:
            elapsed_seconds: float = time.monotonic() - started_at
            stdout_size_bytes: int = os.fstat(stdout_file.fileno()).st_size
            stderr_size_bytes: int = os.fstat(stderr_file.fileno()).st_size
            streams_are_bounded: bool = bool(
                stdout_size_bytes <= stream_limit_bytes
                and stderr_size_bytes <= stream_limit_bytes
            )
            deadline_is_valid: bool = bool(elapsed_seconds <= timeout_seconds)
            if streams_are_bounded and deadline_is_valid:
                process_finished = bool(process.poll() is not None)
                if process_finished:
                    pass
                else:
                    time.sleep(0.01)
            else:
                process.kill()
                process.wait(timeout=2.0)
                if streams_are_bounded:
                    raise TimeoutError("VDMCheck exceeded its execution deadline")
                else:
                    raise ValueError("VDMCheck stream exceeded its size boundary")

        # Read only after an observed process exit and reapply the same bounds.
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout_content: bytes = stdout_file.read(stream_limit_bytes + 1)
        stderr_content: bytes = stderr_file.read(stream_limit_bytes + 1)
        final_streams_are_bounded: bool = bool(
            len(stdout_content) <= stream_limit_bytes
            and len(stderr_content) <= stream_limit_bytes
        )
        if final_streams_are_bounded:
            pass
        else:
            raise ValueError("VDMCheck final stream exceeded its size boundary")
        return_code: int = cast(int, process.returncode)
        result = VdmCheckProcessResult(
            exit_code=return_code,
            stdout_text=stdout_content.decode("utf-8", errors="strict"),
            stderr_text=stderr_content.decode("utf-8", errors="strict"),
        )
    finally:
        if process is None or process.poll() is not None:
            pass
        else:
            process.kill()
            process.wait(timeout=2.0)
        stdout_file.close()
        stderr_file.close()
    if result is None:
        raise RuntimeError("VDMCheck process ended without an observable result")
    else:
        return result


def _parse_vdmcheck_output(
    exit_code: int,
    stdout_text: str,
    stderr_text: str,
) -> tuple[VdmCheckValidationVerdict, tuple[str, ...]]:
    """Classify only the exact observed VDMCheck 1.1.3 output grammar.

    :param exit_code: Native VDMCheck process exit code.
    :param stdout_text: Strictly decoded standard output.
    :param stderr_text: Strictly decoded standard error.
    :return: Validator verdict and native diagnostic lines.
    """

    arguments_are_valid: bool = bool(
        isinstance(exit_code, int)
        and not isinstance(exit_code, bool)
        and isinstance(stdout_text, str)
        and isinstance(stderr_text, str)
    )
    if arguments_are_valid and stderr_text == "":
        pass
    else:
        raise ValueError("VDMCheck output types or stderr are invalid")

    # Only platform newline spelling is normalized; all other whitespace is
    # semantic and therefore remains subject to the exact output grammar.
    canonical_stdout: str = stdout_text.replace("\r\n", "\n")
    canonical_shape_is_valid: bool = bool(
        "\r" not in canonical_stdout
        and canonical_stdout.endswith("\n")
        and len(canonical_stdout) > 1
    )
    if canonical_shape_is_valid:
        output_lines: list[str] = canonical_stdout[:-1].split("\n")
    else:
        raise ValueError("VDMCheck stdout has invalid line termination")
    lines_are_exact: bool = all(
        bool(output_line)
        and output_line == output_line.rstrip(" \t")
        for output_line in output_lines
    )
    if lines_are_exact:
        pass
    else:
        raise ValueError("VDMCheck stdout contains blank or padded lines")

    expected_sink_line: str = f"VDM source written to {os.devnull}"
    if exit_code == 0:
        expected_success_lines: list[str] = list(
            ("No errors found.", expected_sink_line)
        )
        if output_lines == expected_success_lines:
            return VdmCheckValidationVerdict.PASS, tuple()
        else:
            raise ValueError("VDMCheck exit zero lacks its exact success marker")
    else:
        if exit_code == 1:
            pass
        else:
            raise ValueError("VDMCheck returned an unsupported exit code")

    failure_shape_is_valid: bool = bool(
        len(output_lines) >= 4
        and output_lines[-2] == "Errors found."
        and output_lines[-1] == expected_sink_line
        and (len(output_lines) - 2) % 2 == 0
    )
    if failure_shape_is_valid:
        pass
    else:
        raise ValueError("VDMCheck exit one lacks exact finding pairs")
    finding_count: int = (len(output_lines) - 2) // 2
    findings: list[str] = [""] * finding_count
    for finding_index in range(finding_count):
        diagnostic_line: str = output_lines[2 * finding_index]
        source_url_line: str = output_lines[2 * finding_index + 1]
        diagnostic_is_valid: bool = bool(
            re.fullmatch(
                r"[A-Za-z][A-Za-z0-9]*: .+ at modelDescription\.xml:[0-9]+",
                diagnostic_line,
            )
            is not None
        )
        source_url_is_valid: bool = bool(
            re.fullmatch(r"https://fmi-standard\.org/.+", source_url_line)
            is not None
        )
        if diagnostic_is_valid and source_url_is_valid:
            findings[finding_index] = diagnostic_line
        else:
            raise ValueError("VDMCheck finding pair has invalid grammar")
    return VdmCheckValidationVerdict.FAIL, tuple(findings)


def _validate_fmpy_cell(
    asset: ValidatedReferenceFmuAsset,
) -> tuple[VdmCheckValidationVerdict, tuple[str, ...]]:
    """Validate one authenticated FMU with FMPy's public static validator.

    :param asset: Immutable authenticated FMU bytes and their staged path.
    :return: Independent FMPy verdict and unmodified findings.
    """

    if isinstance(asset, ValidatedReferenceFmuAsset):
        pass
    else:
        raise ValueError("FMPy validation requires an authenticated FMU asset")
    validation_findings: list[str] = validate_fmu(str(asset.source_path))
    findings_are_valid: bool = bool(
        isinstance(validation_findings, list)
        and all(isinstance(finding, str) for finding in validation_findings)
    )
    if findings_are_valid:
        pass
    else:
        raise ValueError("FMPy returned an invalid finding collection")

    # Reauthenticate after validation so the verdict remains bound to the same bytes.
    observed_content: bytes = verify_regular_file_identity(
        path=asset.source_path,
        expected_size_bytes=len(asset.content),
        expected_sha256=hashlib.sha256(asset.content).hexdigest(),
    )
    if observed_content == asset.content:
        pass
    else:
        raise ValueError("FMU bytes changed during FMPy validation")
    immutable_findings: tuple[str, ...] = tuple(validation_findings)
    if len(immutable_findings) == 0:
        return VdmCheckValidationVerdict.PASS, immutable_findings
    else:
        return VdmCheckValidationVerdict.FAIL, immutable_findings


def _write_vdmcheck_manifest(
    config: VdmCheckValidationConfig,
    catalog: ReferenceFmuCatalog,
    cells: tuple[VdmCheckCellResult, ...],
    staging_directory: Path,
    generated_at_utc: str,
    fmpy_version: str,
    fmpy_distribution_sha256: str,
    java_executable: Path,
    java_version: str,
    java_runtime_file_count: int,
    java_runtime_total_size_bytes: int,
    java_runtime_tree_sha256: str,
    vdmcheck_two_source_initial_identity: tuple[int, int, str],
    vdmcheck_two_source_final_identity: tuple[int, int, str],
    vdmcheck_two_entry_jar_identity: tuple[str, int, str],
    vdmcheck_two_checkpoints: tuple[tuple[str, str, int, int, str], ...],
    vdmcheck_two_version: str,
    vdmcheck_three_source_initial_identity: tuple[int, int, str],
    vdmcheck_three_source_final_identity: tuple[int, int, str],
    vdmcheck_three_entry_jar_identity: tuple[str, int, str],
    vdmcheck_three_checkpoints: tuple[tuple[str, str, int, int, str], ...],
    vdmcheck_three_version: str,
) -> Path:
    """Write one closed manifest after all four cells have completed.

    :param config: Validated caller configuration.
    :param catalog: Canonical Reference FMU catalog.
    :param cells: Four completed file-level validation cells.
    :param staging_directory: Owned unpublished same-parent staging directory.
    :param generated_at_utc: UTC package generation timestamp.
    :param fmpy_version: Observed installed FMPy version.
    :param fmpy_distribution_sha256: Observed FMPy distribution digest.
    :param java_executable: Canonical Java launcher inside the authenticated tree.
    :param java_version: Observed Java Runtime Environment version line.
    :param java_runtime_file_count: Observed JRE regular-file count.
    :param java_runtime_total_size_bytes: Observed aggregate JRE byte count.
    :param java_runtime_tree_sha256: Observed deterministic JRE tree digest.
    :param vdmcheck_two_source_initial_identity: FMI 2 source tree before execution.
    :param vdmcheck_two_source_final_identity: FMI 2 source tree after execution.
    :param vdmcheck_two_entry_jar_identity: FMI 2 entry path, size and digest.
    :param vdmcheck_two_checkpoints: Ordered FMI 2 staged-tree checkpoints.
    :param vdmcheck_two_version: Observed FMI 2 implementation version.
    :param vdmcheck_three_source_initial_identity: FMI 3 source tree before execution.
    :param vdmcheck_three_source_final_identity: FMI 3 source tree after execution.
    :param vdmcheck_three_entry_jar_identity: FMI 3 entry path, size and digest.
    :param vdmcheck_three_checkpoints: Ordered FMI 3 staged-tree checkpoints.
    :param vdmcheck_three_version: Observed FMI 3 implementation version.
    :return: Path of the staged manifest.
    """

    if (
        isinstance(config, VdmCheckValidationConfig)
        and isinstance(catalog, ReferenceFmuCatalog)
        and isinstance(cells, tuple)
        and len(cells) == 4
        and all(isinstance(cell, VdmCheckCellResult) for cell in cells)
        and isinstance(staging_directory, Path)
        and staging_directory.is_dir()
        and not staging_directory.is_symlink()
    ):
        pass
    else:
        raise ValueError("VDMCheck manifest inputs are invalid")

    # Derive the package result from independent cell verdicts before serialization.
    fmpy_pass_cells: int = 0
    vdmcheck_pass_cells: int = 0
    vdmcheck_fail_cells: int = 0
    vdmcheck_finding_count: int = 0
    fmi_two_cells: int = 0
    fmi_three_cells: int = 0
    for cell in cells:
        if cell.fmpy_verdict == VdmCheckValidationVerdict.PASS:
            fmpy_pass_cells += 1
        else:
            pass
        if cell.vdmcheck_verdict == VdmCheckValidationVerdict.PASS:
            vdmcheck_pass_cells += 1
        else:
            vdmcheck_fail_cells += 1
        vdmcheck_finding_count += len(cell.vdmcheck_findings)
        if cell.fmi_version == FmiVersion.FMI_2_0:
            fmi_two_cells += 1
        else:
            if cell.fmi_version == FmiVersion.FMI_3_0:
                fmi_three_cells += 1
            else:
                raise ValueError("VDMCheck package contains unsupported FMI version")
    current_result_is_exact: bool = bool(
        fmpy_pass_cells == 4
        and vdmcheck_pass_cells == 0
        and vdmcheck_fail_cells == 4
        and vdmcheck_finding_count == 5
        and fmi_two_cells == 2
        and fmi_three_cells == 2
    )
    if current_result_is_exact:
        package_status: VdmCheckRunStatus = (
            VdmCheckRunStatus.COMPLETED_WITH_FINDINGS
        )
    else:
        raise ValueError("VDMCheck current package verdicts differ from evidence")

    # Preserve every staged-tree authentication boundary in deterministic order.
    two_checkpoint_payloads: list[dict[str, object]] = [dict()] * len(
        vdmcheck_two_checkpoints
    )
    for checkpoint_index in range(len(vdmcheck_two_checkpoints)):
        checkpoint: tuple[str, str, int, int, str] = (
            vdmcheck_two_checkpoints[checkpoint_index]
        )
        two_checkpoint_payloads[checkpoint_index] = dict(
            process=checkpoint[0],
            phase=checkpoint[1],
            file_count=checkpoint[2],
            total_size_bytes=checkpoint[3],
            tree_sha256=checkpoint[4],
        )
    three_checkpoint_payloads: list[dict[str, object]] = [dict()] * len(
        vdmcheck_three_checkpoints
    )
    for checkpoint_index in range(len(vdmcheck_three_checkpoints)):
        checkpoint = vdmcheck_three_checkpoints[checkpoint_index]
        three_checkpoint_payloads[checkpoint_index] = dict(
            process=checkpoint[0],
            phase=checkpoint[1],
            file_count=checkpoint[2],
            total_size_bytes=checkpoint[3],
            tree_sha256=checkpoint[4],
        )

    # JSON dictionaries are confined to the evidence serialization boundary.
    cell_payloads: list[dict[str, object]] = [dict()] * len(cells)
    for cell_index in range(len(cells)):
        cell = cells[cell_index]
        declared_interface_values: list[str] = [""] * len(
            cell.declared_interfaces
        )
        for interface_index in range(len(cell.declared_interfaces)):
            declared_interface_values[interface_index] = (
                cell.declared_interfaces[interface_index].value
            )
        cell_payloads[cell_index] = dict(
            case_id=cell.case_id,
            model_name=cell.model_name,
            fmi_version=cell.fmi_version.value,
            declared_interfaces=declared_interface_values,
            fmu_size_bytes=cell.fmu_size_bytes,
            fmu_sha256=cell.fmu_sha256,
            fmpy_verdict=cell.fmpy_verdict.value,
            fmpy_findings=list(cell.fmpy_findings),
            vdmcheck_verdict=cell.vdmcheck_verdict.value,
            vdmcheck_exit_code=cell.vdmcheck_exit_code,
            vdmcheck_findings=list(cell.vdmcheck_findings),
            stdout_relative_path=cell.stdout_relative_path,
            stdout_sha256=cell.stdout_sha256,
            stderr_relative_path=cell.stderr_relative_path,
            stderr_sha256=cell.stderr_sha256,
        )
    remaining_adapters: list[str] = list(
        (
            "Maestro",
            "libcosim",
            "FMI.jl",
            "PathSim",
            "FMUGym",
            "train_fmu_gym",
            "EnergyPlusToFMU",
        )
    )
    manifest: dict[str, object] = dict(
        schema_version="veragrid-fmi-vdmcheck-evidence-v1",
        package_status=package_status.value,
        generated_at_utc=generated_at_utc,
        source=dict(
            branch=config.source_branch,
            revision=config.source_revision,
            tree_sha256=config.source_tree_sha256,
        ),
        execution_host=dict(
            system=platform.system(),
            release=platform.release(),
            machine=platform.machine(),
            python_version=platform.python_version(),
        ),
        corpus=dict(
            project_name=catalog.project_name,
            release_tag=catalog.release_tag,
            commit_sha=catalog.commit_sha,
            catalog_path=config.catalog_path.as_posix(),
            catalog_sha256=hashlib.sha256(config.catalog_path.read_bytes()).hexdigest(),
        ),
        tools=dict(
            fmpy=dict(
                version=fmpy_version,
                distribution_sha256=fmpy_distribution_sha256,
                verdict_role="independent_schema_and_semantic_validator",
            ),
            java_runtime=dict(
                root=config.java_runtime_root.as_posix(),
                executable=java_executable.as_posix(),
                executable_relative_path="bin/java.exe",
                version=java_version,
                file_count=java_runtime_file_count,
                total_size_bytes=java_runtime_total_size_bytes,
                tree_sha256=java_runtime_tree_sha256,
            ),
            vdmcheck_two=dict(
                source_root=config.vdmcheck_two_root.as_posix(),
                source_initial_file_count=vdmcheck_two_source_initial_identity[0],
                source_initial_total_size_bytes=(
                    vdmcheck_two_source_initial_identity[1]
                ),
                source_initial_tree_sha256=vdmcheck_two_source_initial_identity[2],
                source_final_file_count=vdmcheck_two_source_final_identity[0],
                source_final_total_size_bytes=(
                    vdmcheck_two_source_final_identity[1]
                ),
                source_final_tree_sha256=vdmcheck_two_source_final_identity[2],
                entry_jar_relative_path=vdmcheck_two_entry_jar_identity[0],
                entry_jar_size_bytes=vdmcheck_two_entry_jar_identity[1],
                entry_jar_sha256=vdmcheck_two_entry_jar_identity[2],
                version=vdmcheck_two_version,
                staged_authentication_checkpoints=two_checkpoint_payloads,
            ),
            vdmcheck_three=dict(
                source_root=config.vdmcheck_three_root.as_posix(),
                source_initial_file_count=vdmcheck_three_source_initial_identity[0],
                source_initial_total_size_bytes=(
                    vdmcheck_three_source_initial_identity[1]
                ),
                source_initial_tree_sha256=(
                    vdmcheck_three_source_initial_identity[2]
                ),
                source_final_file_count=vdmcheck_three_source_final_identity[0],
                source_final_total_size_bytes=(
                    vdmcheck_three_source_final_identity[1]
                ),
                source_final_tree_sha256=vdmcheck_three_source_final_identity[2],
                entry_jar_relative_path=vdmcheck_three_entry_jar_identity[0],
                entry_jar_size_bytes=vdmcheck_three_entry_jar_identity[1],
                entry_jar_sha256=vdmcheck_three_entry_jar_identity[2],
                version=vdmcheck_three_version,
                staged_authentication_checkpoints=three_checkpoint_payloads,
            ),
        ),
        counts=dict(
            fmu_files=len(cells),
            fmi_two_files=fmi_two_cells,
            fmi_three_files=fmi_three_cells,
            declared_interfaces_per_file=2,
            fmpy_pass_cells=fmpy_pass_cells,
            vdmcheck_pass_cells=vdmcheck_pass_cells,
            vdmcheck_fail_cells=vdmcheck_fail_cells,
            vdmcheck_findings=vdmcheck_finding_count,
            retained_log_files=2 * len(cells),
        ),
        cells=cell_payloads,
        remaining_open_source_adapters=remaining_adapters,
        claim_boundary=dict(
            supported=(
                "Static dual-oracle validation of the exact four Reference FMUs v0.0.41 "
                "files with FMPy 0.3.31 and VDMCheck 1.1.3 on the recorded host."
            ),
            excluded=(
                "This package is not FMI certification, numerical trajectory evidence, "
                "VeraGrid runtime evidence, FMI 1 evidence or multiplatform evidence."
            ),
        ),
    )
    manifest_content: bytes = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(manifest_content) <= 262_144:
        pass
    else:
        raise ValueError("VDMCheck manifest exceeds 256 KiB")
    manifest_path: Path = staging_directory / "manifest.json"
    manifest_file: BinaryIO = manifest_path.open("xb")
    try:
        manifest_file.write(manifest_content)
    finally:
        manifest_file.close()
    return manifest_path


def _verify_vdmcheck_package(
    config: VdmCheckValidationConfig,
    package_directory: Path,
    manifest_path: Path,
) -> None:
    """Reopen and independently verify every published package invariant.

    :param config: Validated identities that governed the completed execution.
    :param package_directory: Complete unpublished evidence package root.
    :param manifest_path: Manifest written inside that package root.
    :return: None after every byte identity and semantic count passes.
    """

    expected_manifest_path: Path = package_directory / "manifest.json"
    paths_are_valid: bool = bool(
        isinstance(config, VdmCheckValidationConfig)
        and isinstance(package_directory, Path)
        and package_directory.is_dir()
        and not package_directory.is_symlink()
        and isinstance(manifest_path, Path)
        and manifest_path == expected_manifest_path
        and manifest_path.is_file()
        and not manifest_path.is_symlink()
        and manifest_path.stat().st_size <= 262_144
    )
    if paths_are_valid:
        pass
    else:
        raise ValueError("VDMCheck package paths are invalid")
    manifest_bytes: bytes = manifest_path.read_bytes()
    parsed_manifest: object = json.loads(
        manifest_bytes.decode("utf-8", errors="strict")
    )
    if isinstance(parsed_manifest, dict):
        manifest: dict[str, object] = cast(dict[str, object], parsed_manifest)
    else:
        raise ValueError("VDMCheck manifest root must be an object")
    expected_root_keys: set[str] = set(
        (
            "schema_version",
            "package_status",
            "generated_at_utc",
            "source",
            "execution_host",
            "corpus",
            "tools",
            "counts",
            "cells",
            "remaining_open_source_adapters",
            "claim_boundary",
        )
    )
    root_is_closed: bool = bool(
        set(manifest.keys()) == expected_root_keys
        and manifest.get("schema_version", None)
        == "veragrid-fmi-vdmcheck-evidence-v1"
        and manifest.get("package_status", None)
        == VdmCheckRunStatus.COMPLETED_WITH_FINDINGS.value
    )
    if root_is_closed:
        pass
    else:
        raise ValueError("VDMCheck manifest root is not closed or accepted")

    generated_at_value: object = manifest.get("generated_at_utc", None)
    if isinstance(generated_at_value, str) and generated_at_value.endswith("Z"):
        generated_at: datetime = datetime.fromisoformat(
            generated_at_value.replace("Z", "+00:00")
        )
    else:
        raise ValueError("VDMCheck manifest timestamp is invalid")
    if generated_at.tzinfo is not None:
        pass
    else:
        raise ValueError("VDMCheck manifest timestamp lacks timezone")

    # Recompute the complete source closures and verify every staged checkpoint.
    tools_value: object = manifest.get("tools", None)
    if isinstance(tools_value, dict):
        tools: dict[str, object] = cast(dict[str, object], tools_value)
    else:
        raise ValueError("VDMCheck manifest tools must be an object")
    expected_tool_keys: set[str] = set(
        ("fmpy", "java_runtime", "vdmcheck_two", "vdmcheck_three")
    )
    if set(tools.keys()) == expected_tool_keys:
        pass
    else:
        raise ValueError("VDMCheck manifest tool set is not closed")
    expected_validator_keys: set[str] = set(
        (
            "source_root",
            "source_initial_file_count",
            "source_initial_total_size_bytes",
            "source_initial_tree_sha256",
            "source_final_file_count",
            "source_final_total_size_bytes",
            "source_final_tree_sha256",
            "entry_jar_relative_path",
            "entry_jar_size_bytes",
            "entry_jar_sha256",
            "version",
            "staged_authentication_checkpoints",
        )
    )
    expected_checkpoint_keys: set[str] = set(
        ("process", "phase", "file_count", "total_size_bytes", "tree_sha256")
    )
    expected_processes: tuple[str, ...] = (
        "version_probe",
        "version_probe",
        "BouncingBall",
        "BouncingBall",
        "Stair",
        "Stair",
    )
    expected_phases: tuple[str, ...] = (
        "before",
        "after",
        "before",
        "after",
        "before",
        "after",
    )
    validator_names: tuple[str, ...] = ("vdmcheck_two", "vdmcheck_three")
    for validator_index in range(len(validator_names)):
        validator_name: str = validator_names[validator_index]
        validator_value: object = tools.get(validator_name, None)
        if isinstance(validator_value, dict):
            validator: dict[str, object] = cast(
                dict[str, object], validator_value
            )
        else:
            raise ValueError("VDMCheck validator tool record must be an object")
        if validator_index == 0:
            expected_root: Path = config.vdmcheck_two_root
            expected_tree_identity: tuple[int, int, str] = (
                config.vdmcheck_two_expected_file_count,
                config.vdmcheck_two_expected_total_size_bytes,
                config.vdmcheck_two_expected_tree_sha256,
            )
            expected_entry_identity: tuple[str, int, str] = (
                "vdmcheck2.jar",
                52_911,
                "164da6863026750cd65cdb6be5c65261453c3e9f750451ca65032bbdacae41b0",
            )
            expected_version: str = config.vdmcheck_two_expected_version
        else:
            expected_root = config.vdmcheck_three_root
            expected_tree_identity = (
                config.vdmcheck_three_expected_file_count,
                config.vdmcheck_three_expected_total_size_bytes,
                config.vdmcheck_three_expected_tree_sha256,
            )
            expected_entry_identity = (
                "vdmcheck3.jar",
                43_855,
                "53226b3bdfd3aac1bc48f79db7d5bca928b4d15afd3d136923c746c749da8eb5",
            )
            expected_version = config.vdmcheck_three_expected_version
        current_source_identity: tuple[int, int, str] = (
            read_regular_tree_identity(expected_root)
        )
        validator_identity_is_exact: bool = bool(
            set(validator.keys()) == expected_validator_keys
            and validator.get("source_root", None) == expected_root.as_posix()
            and validator.get("source_initial_file_count", None)
            == expected_tree_identity[0]
            and validator.get("source_initial_total_size_bytes", None)
            == expected_tree_identity[1]
            and validator.get("source_initial_tree_sha256", None)
            == expected_tree_identity[2]
            and validator.get("source_final_file_count", None)
            == expected_tree_identity[0]
            and validator.get("source_final_total_size_bytes", None)
            == expected_tree_identity[1]
            and validator.get("source_final_tree_sha256", None)
            == expected_tree_identity[2]
            and current_source_identity == expected_tree_identity
            and validator.get("entry_jar_relative_path", None)
            == expected_entry_identity[0]
            and validator.get("entry_jar_size_bytes", None)
            == expected_entry_identity[1]
            and validator.get("entry_jar_sha256", None)
            == expected_entry_identity[2]
            and validator.get("version", None) == expected_version
        )
        if validator_identity_is_exact:
            pass
        else:
            raise ValueError("VDMCheck validator identity record does not match")
        checkpoints_value: object = validator.get(
            "staged_authentication_checkpoints", None
        )
        if isinstance(checkpoints_value, list) and len(checkpoints_value) == 6:
            checkpoint_values: list[object] = checkpoints_value
        else:
            raise ValueError("VDMCheck staged checkpoints are incomplete")
        for checkpoint_index in range(len(checkpoint_values)):
            checkpoint_value: object = checkpoint_values[checkpoint_index]
            if isinstance(checkpoint_value, dict):
                checkpoint: dict[str, object] = cast(
                    dict[str, object], checkpoint_value
                )
            else:
                raise ValueError("VDMCheck staged checkpoint must be an object")
            checkpoint_is_exact: bool = bool(
                set(checkpoint.keys()) == expected_checkpoint_keys
                and checkpoint.get("process", None)
                == expected_processes[checkpoint_index]
                and checkpoint.get("phase", None)
                == expected_phases[checkpoint_index]
                and checkpoint.get("file_count", None)
                == expected_tree_identity[0]
                and checkpoint.get("total_size_bytes", None)
                == expected_tree_identity[1]
                and checkpoint.get("tree_sha256", None)
                == expected_tree_identity[2]
            )
            if checkpoint_is_exact:
                pass
            else:
                raise ValueError("VDMCheck staged checkpoint does not match")

    counts_value: object = manifest.get("counts", None)
    if isinstance(counts_value, dict):
        counts: dict[str, object] = cast(dict[str, object], counts_value)
    else:
        raise ValueError("VDMCheck manifest counts must be an object")
    expected_counts: dict[str, object] = dict(
        fmu_files=4,
        fmi_two_files=2,
        fmi_three_files=2,
        declared_interfaces_per_file=2,
        fmpy_pass_cells=4,
        vdmcheck_pass_cells=0,
        vdmcheck_fail_cells=4,
        vdmcheck_findings=5,
        retained_log_files=8,
    )
    if counts == expected_counts:
        pass
    else:
        raise ValueError("VDMCheck manifest counts differ from the closed result")

    remaining_value: object = manifest.get("remaining_open_source_adapters", None)
    expected_remaining: list[str] = list(
        (
            "Maestro",
            "libcosim",
            "FMI.jl",
            "PathSim",
            "FMUGym",
            "train_fmu_gym",
            "EnergyPlusToFMU",
        )
    )
    if remaining_value == expected_remaining:
        pass
    else:
        raise ValueError("VDMCheck remaining-adapter gate is invalid")

    cells_value: object = manifest.get("cells", None)
    if isinstance(cells_value, list) and len(cells_value) == 4:
        cell_payloads: list[object] = cells_value
    else:
        raise ValueError("VDMCheck manifest must contain four cells")
    expected_case_ids: tuple[str, ...] = (
        "reference-fmus-2.0-bouncing-ball",
        "reference-fmus-2.0-stair",
        "reference-fmus-3.0-bouncing-ball",
        "reference-fmus-3.0-stair",
    )
    expected_model_names: tuple[str, ...] = (
        "BouncingBall",
        "Stair",
        "BouncingBall",
        "Stair",
    )
    expected_fmi_versions: tuple[str, ...] = ("2.0", "2.0", "3.0", "3.0")
    expected_fmu_sizes: tuple[int, ...] = (198_193, 185_583, 246_743, 231_692)
    expected_fmu_sha256: tuple[str, ...] = (
        "3959d0dea751e788b7b9591da6beb11955352a1ac46138244ee5343efb7ce5e4",
        "917f5a7123cf5b2857ac6bc7a121fe96e0a37a9a734b84d0166fd0554298789c",
        "f14f1f46c97c21bc208c139fa30d19ebce5b1d0fa0789f09a1ff1b9a6b9ee8c5",
        "031dc8028fae3d8c48c7f3c11ab4f7db5ab1df81f9e0a8dc1f5610c69d1939d4",
    )
    expected_findings_per_cell: tuple[int, ...] = (1, 1, 2, 1)
    expected_cell_keys: set[str] = set(
        (
            "case_id",
            "model_name",
            "fmi_version",
            "declared_interfaces",
            "fmu_size_bytes",
            "fmu_sha256",
            "fmpy_verdict",
            "fmpy_findings",
            "vdmcheck_verdict",
            "vdmcheck_exit_code",
            "vdmcheck_findings",
            "stdout_relative_path",
            "stdout_sha256",
            "stderr_relative_path",
            "stderr_sha256",
        )
    )
    expected_files: set[str] = set(("manifest.json",))
    observed_fmu_hashes: set[str] = set()
    observed_finding_count: int = 0
    for cell_index in range(len(cell_payloads)):
        cell_value: object = cell_payloads[cell_index]
        if isinstance(cell_value, dict):
            cell: dict[str, object] = cast(dict[str, object], cell_value)
        else:
            raise ValueError("VDMCheck cell must be an object")
        cell_identity_is_valid: bool = bool(
            set(cell.keys()) == expected_cell_keys
            and cell.get("case_id", None) == expected_case_ids[cell_index]
            and cell.get("model_name", None) == expected_model_names[cell_index]
            and cell.get("fmi_version", None) == expected_fmi_versions[cell_index]
            and cell.get("declared_interfaces", None)
            == list(("CoSimulation", "ModelExchange"))
            and cell.get("fmu_size_bytes", None) == expected_fmu_sizes[cell_index]
            and cell.get("fmu_sha256", None) == expected_fmu_sha256[cell_index]
            and cell.get("fmpy_verdict", None)
            == VdmCheckValidationVerdict.PASS.value
            and cell.get("fmpy_findings", None) == []
            and cell.get("vdmcheck_verdict", None)
            == VdmCheckValidationVerdict.FAIL.value
            and cell.get("vdmcheck_exit_code", None) == 1
        )
        if cell_identity_is_valid:
            observed_fmu_hashes.add(expected_fmu_sha256[cell_index])
        else:
            raise ValueError("VDMCheck cell identity or verdict is invalid")
        findings_value: object = cell.get("vdmcheck_findings", None)
        if (
            isinstance(findings_value, list)
            and len(findings_value) == expected_findings_per_cell[cell_index]
            and all(isinstance(finding, str) for finding in findings_value)
        ):
            manifest_findings: tuple[str, ...] = tuple(findings_value)
        else:
            raise ValueError("VDMCheck cell findings are invalid")
        observed_finding_count += len(manifest_findings)

        # Reopen both logs, bind their hashes and reclassify the native output.
        stdout_relative_value: object = cell.get("stdout_relative_path", None)
        stderr_relative_value: object = cell.get("stderr_relative_path", None)
        stdout_sha_value: object = cell.get("stdout_sha256", None)
        stderr_sha_value: object = cell.get("stderr_sha256", None)
        if (
            isinstance(stdout_relative_value, str)
            and isinstance(stderr_relative_value, str)
            and isinstance(stdout_sha_value, str)
            and isinstance(stderr_sha_value, str)
        ):
            pass
        else:
            raise ValueError("VDMCheck cell log metadata types are invalid")
        stdout_path: Path = package_directory / Path(stdout_relative_value)
        stderr_path: Path = package_directory / Path(stderr_relative_value)
        log_paths_are_safe: bool = bool(
            stdout_path.resolve(strict=True).is_relative_to(
                package_directory.resolve(strict=True)
            )
            and stderr_path.resolve(strict=True).is_relative_to(
                package_directory.resolve(strict=True)
            )
            and stdout_path.is_file()
            and stderr_path.is_file()
            and not stdout_path.is_symlink()
            and not stderr_path.is_symlink()
        )
        if log_paths_are_safe:
            pass
        else:
            raise ValueError("VDMCheck retained log path is unsafe")
        stdout_content: bytes = stdout_path.read_bytes()
        stderr_content: bytes = stderr_path.read_bytes()
        log_bytes_are_valid: bool = bool(
            len(stdout_content) <= 1_048_576
            and len(stderr_content) <= 1_048_576
            and hashlib.sha256(stdout_content).hexdigest() == stdout_sha_value
            and hashlib.sha256(stderr_content).hexdigest() == stderr_sha_value
        )
        if log_bytes_are_valid:
            pass
        else:
            raise ValueError("VDMCheck retained log identity is invalid")
        observed_verdict, observed_findings = _parse_vdmcheck_output(
            exit_code=1,
            stdout_text=stdout_content.decode("utf-8", errors="strict"),
            stderr_text=stderr_content.decode("utf-8", errors="strict"),
        )
        if (
            observed_verdict == VdmCheckValidationVerdict.FAIL
            and observed_findings == manifest_findings
        ):
            pass
        else:
            raise ValueError("VDMCheck retained logs differ from their manifest cell")
        expected_files.add(stdout_relative_value)
        expected_files.add(stderr_relative_value)

    if len(observed_fmu_hashes) == 4 and observed_finding_count == 5:
        pass
    else:
        raise ValueError("VDMCheck package cardinality is invalid")

    # The closed package contains only its manifest and eight immutable logs.
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    package_entries: list[Path] = list(package_directory.rglob("*"))
    for package_entry in package_entries:
        if package_entry.is_symlink():
            raise ValueError("VDMCheck package contains a symbolic link")
        else:
            if package_entry.is_file():
                actual_files.add(
                    package_entry.relative_to(package_directory).as_posix()
                )
            else:
                if package_entry.is_dir():
                    actual_directories.add(
                        package_entry.relative_to(package_directory).as_posix()
                    )
                else:
                    raise ValueError("VDMCheck package contains an unsupported entry")

    # Derive every permitted directory from the closed manifest-owned file set.
    expected_directories: set[str] = set()
    for expected_file in expected_files:
        expected_parent: Path = Path(expected_file).parent
        while expected_parent != Path("."):
            expected_directories.add(expected_parent.as_posix())
            expected_parent = expected_parent.parent

    if (
        actual_files == expected_files
        and len(actual_files) == 9
        and actual_directories == expected_directories
    ):
        pass
    else:
        raise ValueError("VDMCheck package structure is not closed")


def generate_vdmcheck_validation(config: VdmCheckValidationConfig) -> Path:
    """Execute and publish the exact four-file dual-validator package.

    :param config: Validated explicit tool, corpus and publication configuration.
    :return: Final verified manifest path.
    """

    if isinstance(config, VdmCheckValidationConfig):
        pass
    else:
        raise ValueError("VDMCheck generation requires validated configuration")

    # Authenticate the complete JRE before deriving the only permitted launcher.
    java_runtime_identity: tuple[int, int, str] = read_regular_tree_identity(
        config.java_runtime_root
    )
    expected_java_runtime_identity: tuple[int, int, str] = (
        config.java_runtime_expected_file_count,
        config.java_runtime_expected_total_size_bytes,
        config.java_runtime_expected_tree_sha256,
    )
    if java_runtime_identity == expected_java_runtime_identity:
        canonical_java_root: Path = config.java_runtime_root.resolve(strict=True)
    else:
        raise ValueError("Java runtime tree identity does not match")
    java_executable: Path = canonical_java_root / "bin" / "java.exe"
    java_path_is_exact: bool = bool(
        java_executable.exists()
        and java_executable.is_file()
        and not java_executable.is_symlink()
        and java_executable.resolve(strict=True) == java_executable
        and java_executable.resolve(strict=True).is_relative_to(canonical_java_root)
    )
    if java_path_is_exact:
        pass
    else:
        raise ValueError("Java launcher is not the canonical runtime-owned executable")

    # Bind both complete validator distributions before any dependency can load.
    vdmcheck_two_source_initial_identity: tuple[int, int, str] = (
        read_regular_tree_identity(config.vdmcheck_two_root)
    )
    expected_vdmcheck_two_identity: tuple[int, int, str] = (
        config.vdmcheck_two_expected_file_count,
        config.vdmcheck_two_expected_total_size_bytes,
        config.vdmcheck_two_expected_tree_sha256,
    )
    vdmcheck_three_source_initial_identity: tuple[int, int, str] = (
        read_regular_tree_identity(config.vdmcheck_three_root)
    )
    expected_vdmcheck_three_identity: tuple[int, int, str] = (
        config.vdmcheck_three_expected_file_count,
        config.vdmcheck_three_expected_total_size_bytes,
        config.vdmcheck_three_expected_tree_sha256,
    )
    validator_trees_are_exact: bool = bool(
        vdmcheck_two_source_initial_identity == expected_vdmcheck_two_identity
        and vdmcheck_three_source_initial_identity
        == expected_vdmcheck_three_identity
    )
    if validator_trees_are_exact:
        canonical_vdmcheck_two_root: Path = config.vdmcheck_two_root.resolve(
            strict=True
        )
        canonical_vdmcheck_three_root: Path = config.vdmcheck_three_root.resolve(
            strict=True
        )
    else:
        raise ValueError("VDMCheck distribution tree identity does not match")
    java_version: str = _read_java_version(
        java_executable=java_executable,
        timeout_seconds=config.process_timeout_seconds,
        stream_limit_bytes=config.stream_limit_bytes,
    )
    if java_version == config.java_expected_version:
        pass
    else:
        raise ValueError("Java Runtime Environment version does not match")

    # Reuse the existing complete-distribution identity owner for FMPy.
    fmpy_version, fmpy_distribution_sha256 = read_fmpy_distribution_identity()
    fmpy_identity_is_exact: bool = bool(
        fmpy_version == config.fmpy_expected_version
        and fmpy_distribution_sha256
        == config.fmpy_expected_distribution_sha256
    )
    if fmpy_identity_is_exact:
        pass
    else:
        raise ValueError("Installed FMPy identity does not match")
    catalog: ReferenceFmuCatalog = load_reference_fmu_catalog(config.catalog_path)
    if len(catalog.cases) == 4:
        pass
    else:
        raise ValueError("VDMCheck catalog must contain exactly four cases")

    staging_directory: Path = Path(
        tempfile.mkdtemp(
            prefix=f".{config.output_directory.name}-staging-",
            dir=config.output_directory.parent,
        )
    )
    publication_succeeded: bool = False
    try:
        # Complete copied distributions preserve every authenticated runtime sibling.
        runtime_directory: Path = staging_directory / "runtime"
        raw_directory: Path = staging_directory / "raw"
        runtime_directory.mkdir()
        raw_directory.mkdir()
        staged_vdmcheck_two_root: Path = runtime_directory / "vdmcheck2"
        staged_vdmcheck_three_root: Path = runtime_directory / "vdmcheck3"
        shutil.copytree(canonical_vdmcheck_two_root, staged_vdmcheck_two_root)
        shutil.copytree(canonical_vdmcheck_three_root, staged_vdmcheck_three_root)
        staged_vdmcheck_two: Path = staged_vdmcheck_two_root / "vdmcheck2.jar"
        staged_vdmcheck_three: Path = (
            staged_vdmcheck_three_root / "vdmcheck3.jar"
        )
        staged_entry_paths_are_exact: bool = bool(
            staged_vdmcheck_two.exists()
            and staged_vdmcheck_two.is_file()
            and not staged_vdmcheck_two.is_symlink()
            and staged_vdmcheck_two.resolve(strict=True).is_relative_to(
                staged_vdmcheck_two_root.resolve(strict=True)
            )
            and staged_vdmcheck_two.relative_to(staged_vdmcheck_two_root).as_posix()
            == "vdmcheck2.jar"
            and staged_vdmcheck_three.exists()
            and staged_vdmcheck_three.is_file()
            and not staged_vdmcheck_three.is_symlink()
            and staged_vdmcheck_three.resolve(strict=True).is_relative_to(
                staged_vdmcheck_three_root.resolve(strict=True)
            )
            and staged_vdmcheck_three.relative_to(
                staged_vdmcheck_three_root
            ).as_posix()
            == "vdmcheck3.jar"
        )
        if staged_entry_paths_are_exact:
            pass
        else:
            raise ValueError("VDMCheck staged entry JAR path is invalid")

        # The version read is bounded by the same before/after tree identity gate.
        vdmcheck_two_checkpoint_values: list[
            tuple[str, str, int, int, str] | None
        ] = [None] * 6
        vdmcheck_three_checkpoint_values: list[
            tuple[str, str, int, int, str] | None
        ] = [None] * 6
        two_version_before: tuple[int, int, str] = read_regular_tree_identity(
            staged_vdmcheck_two_root
        )
        if two_version_before == expected_vdmcheck_two_identity:
            vdmcheck_two_checkpoint_values[0] = (
                "version_probe",
                "before",
                two_version_before[0],
                two_version_before[1],
                two_version_before[2],
            )
        else:
            raise ValueError("VDMCheck 2 staged tree changed before version probe")
        vdmcheck_two_content: bytes = verify_regular_file_identity(
            staged_vdmcheck_two,
            52_911,
            "164da6863026750cd65cdb6be5c65261453c3e9f750451ca65032bbdacae41b0",
        )
        vdmcheck_two_version: str = _read_vdmcheck_jar_version(
            vdmcheck_two_content
        )
        two_version_after: tuple[int, int, str] = read_regular_tree_identity(
            staged_vdmcheck_two_root
        )
        if two_version_after == expected_vdmcheck_two_identity:
            vdmcheck_two_checkpoint_values[1] = (
                "version_probe",
                "after",
                two_version_after[0],
                two_version_after[1],
                two_version_after[2],
            )
        else:
            raise ValueError("VDMCheck 2 staged tree changed after version probe")

        three_version_before: tuple[int, int, str] = (
            read_regular_tree_identity(staged_vdmcheck_three_root)
        )
        if three_version_before == expected_vdmcheck_three_identity:
            vdmcheck_three_checkpoint_values[0] = (
                "version_probe",
                "before",
                three_version_before[0],
                three_version_before[1],
                three_version_before[2],
            )
        else:
            raise ValueError("VDMCheck 3 staged tree changed before version probe")
        vdmcheck_three_content: bytes = verify_regular_file_identity(
            staged_vdmcheck_three,
            43_855,
            "53226b3bdfd3aac1bc48f79db7d5bca928b4d15afd3d136923c746c749da8eb5",
        )
        vdmcheck_three_version: str = _read_vdmcheck_jar_version(
            vdmcheck_three_content
        )
        three_version_after: tuple[int, int, str] = (
            read_regular_tree_identity(staged_vdmcheck_three_root)
        )
        if three_version_after == expected_vdmcheck_three_identity:
            vdmcheck_three_checkpoint_values[1] = (
                "version_probe",
                "after",
                three_version_after[0],
                three_version_after[1],
                three_version_after[2],
            )
        else:
            raise ValueError("VDMCheck 3 staged tree changed after version probe")
        versions_are_exact: bool = bool(
            vdmcheck_two_version == config.vdmcheck_two_expected_version
            and vdmcheck_three_version == config.vdmcheck_three_expected_version
        )
        if versions_are_exact:
            pass
        else:
            raise ValueError("VDMCheck implementation version does not match")

        pending_cells: list[VdmCheckCellResult | None] = [None] * 4
        for cell_index in range(len(catalog.cases)):
            reference_case: ReferenceFmuCase = catalog.cases[cell_index]
            archive_path_parts: list[str] = reference_case.archive_relative_path.split(
                "/"
            )
            source_fmu_path: Path = config.corpus_root
            for archive_path_part in archive_path_parts:
                source_fmu_path = source_fmu_path / archive_path_part
            source_asset: ValidatedReferenceFmuAsset = catalog.validate_asset(
                reference_case.case_id,
                source_fmu_path,
            )
            staged_fmu_path: Path = runtime_directory / f"cell-{cell_index:02d}.fmu"
            staged_fmu_file: BinaryIO = staged_fmu_path.open("xb")
            try:
                staged_fmu_file.write(source_asset.content)
            finally:
                staged_fmu_file.close()
            staged_fmu_content: bytes = verify_regular_file_identity(
                staged_fmu_path,
                reference_case.fmu_size_bytes,
                reference_case.fmu_sha256,
            )
            staged_asset: ValidatedReferenceFmuAsset = ValidatedReferenceFmuAsset(
                case=reference_case,
                source_path=staged_fmu_path,
                content=staged_fmu_content,
            )
            fmpy_verdict, fmpy_findings = _validate_fmpy_cell(staged_asset)
            selected_jar_path: Path
            selected_vdmcheck_root: Path
            selected_expected_identity: tuple[int, int, str]
            selected_checkpoint_values: list[
                tuple[str, str, int, int, str] | None
            ]
            if reference_case.fmi_version == FmiVersion.FMI_2_0:
                selected_jar_path = staged_vdmcheck_two
                selected_vdmcheck_root = staged_vdmcheck_two_root
                selected_expected_identity = expected_vdmcheck_two_identity
                selected_checkpoint_values = vdmcheck_two_checkpoint_values
            else:
                if reference_case.fmi_version == FmiVersion.FMI_3_0:
                    selected_jar_path = staged_vdmcheck_three
                    selected_vdmcheck_root = staged_vdmcheck_three_root
                    selected_expected_identity = expected_vdmcheck_three_identity
                    selected_checkpoint_values = vdmcheck_three_checkpoint_values
                else:
                    raise ValueError("VDMCheck cannot select an FMI 1 validator")
            before_checkpoint_index: int
            after_checkpoint_index: int
            if reference_case.model_name == "BouncingBall":
                before_checkpoint_index = 2
                after_checkpoint_index = 3
            else:
                if reference_case.model_name == "Stair":
                    before_checkpoint_index = 4
                    after_checkpoint_index = 5
                else:
                    raise ValueError("VDMCheck catalog model is unsupported")

            # No validator process starts unless its complete staged tree is exact.
            process_tree_before: tuple[int, int, str] = (
                read_regular_tree_identity(selected_vdmcheck_root)
            )
            if process_tree_before == selected_expected_identity:
                selected_checkpoint_values[before_checkpoint_index] = (
                    reference_case.model_name,
                    "before",
                    process_tree_before[0],
                    process_tree_before[1],
                    process_tree_before[2],
                )
            else:
                raise ValueError("VDMCheck staged tree changed before validation")
            process_result: VdmCheckProcessResult = _run_vdmcheck_process(
                java_executable=java_executable,
                jar_path=selected_jar_path,
                fmu_path=staged_fmu_path,
                timeout_seconds=config.process_timeout_seconds,
                stream_limit_bytes=config.stream_limit_bytes,
            )
            process_tree_after: tuple[int, int, str] = (
                read_regular_tree_identity(selected_vdmcheck_root)
            )
            if process_tree_after == selected_expected_identity:
                selected_checkpoint_values[after_checkpoint_index] = (
                    reference_case.model_name,
                    "after",
                    process_tree_after[0],
                    process_tree_after[1],
                    process_tree_after[2],
                )
            else:
                raise ValueError("VDMCheck staged tree changed after validation")
            vdmcheck_verdict, vdmcheck_findings = _parse_vdmcheck_output(
                exit_code=process_result.exit_code,
                stdout_text=process_result.stdout_text,
                stderr_text=process_result.stderr_text,
            )

            # Retain native streams exactly; no finding is rewritten or suppressed.
            cell_directory: Path = raw_directory / (
                f"cell-{cell_index:02d}--{reference_case.case_id}"
            )
            cell_directory.mkdir()
            stdout_path: Path = cell_directory / "stdout.log"
            stderr_path: Path = cell_directory / "stderr.log"
            stdout_content: bytes = process_result.stdout_text.encode("utf-8")
            stderr_content: bytes = process_result.stderr_text.encode("utf-8")
            stdout_file: BinaryIO = stdout_path.open("xb")
            try:
                stdout_file.write(stdout_content)
            finally:
                stdout_file.close()
            stderr_file: BinaryIO = stderr_path.open("xb")
            try:
                stderr_file.write(stderr_content)
            finally:
                stderr_file.close()
            pending_cells[cell_index] = VdmCheckCellResult(
                case_id=reference_case.case_id,
                model_name=reference_case.model_name,
                fmi_version=reference_case.fmi_version,
                declared_interfaces=reference_case.interfaces,
                fmu_size_bytes=reference_case.fmu_size_bytes,
                fmu_sha256=reference_case.fmu_sha256,
                fmpy_verdict=fmpy_verdict,
                fmpy_findings=fmpy_findings,
                vdmcheck_verdict=vdmcheck_verdict,
                vdmcheck_exit_code=process_result.exit_code,
                vdmcheck_findings=vdmcheck_findings,
                stdout_relative_path=stdout_path.relative_to(
                    staging_directory
                ).as_posix(),
                stdout_sha256=hashlib.sha256(stdout_content).hexdigest(),
                stderr_relative_path=stderr_path.relative_to(
                    staging_directory
                ).as_posix(),
                stderr_sha256=hashlib.sha256(stderr_content).hexdigest(),
            )

        cells: tuple[VdmCheckCellResult, ...] = tuple(
            cast(VdmCheckCellResult, pending_cell)
            for pending_cell in pending_cells
        )

        # Close every external identity before removing unpublished runtime copies.
        vdmcheck_two_source_final_identity: tuple[int, int, str] = (
            read_regular_tree_identity(config.vdmcheck_two_root)
        )
        vdmcheck_three_source_final_identity: tuple[int, int, str] = (
            read_regular_tree_identity(config.vdmcheck_three_root)
        )
        post_run_java_identity: tuple[int, int, str] = (
            read_regular_tree_identity(config.java_runtime_root)
        )
        final_external_identities_are_exact: bool = bool(
            vdmcheck_two_source_final_identity
            == vdmcheck_two_source_initial_identity
            and vdmcheck_three_source_final_identity
            == vdmcheck_three_source_initial_identity
            and post_run_java_identity == java_runtime_identity
            and all(
                checkpoint is not None
                for checkpoint in vdmcheck_two_checkpoint_values
            )
            and all(
                checkpoint is not None
                for checkpoint in vdmcheck_three_checkpoint_values
            )
        )
        if final_external_identities_are_exact:
            pass
        else:
            raise ValueError("VDMCheck external identity changed during validation")
        vdmcheck_two_checkpoints: tuple[
            tuple[str, str, int, int, str], ...
        ] = tuple(
            cast(tuple[str, str, int, int, str], checkpoint)
            for checkpoint in vdmcheck_two_checkpoint_values
        )
        vdmcheck_three_checkpoints: tuple[
            tuple[str, str, int, int, str], ...
        ] = tuple(
            cast(tuple[str, str, int, int, str], checkpoint)
            for checkpoint in vdmcheck_three_checkpoint_values
        )
        vdmcheck_two_entry_jar_identity: tuple[str, int, str] = (
            "vdmcheck2.jar",
            52_911,
            "164da6863026750cd65cdb6be5c65261453c3e9f750451ca65032bbdacae41b0",
        )
        vdmcheck_three_entry_jar_identity: tuple[str, int, str] = (
            "vdmcheck3.jar",
            43_855,
            "53226b3bdfd3aac1bc48f79db7d5bca928b4d15afd3d136923c746c749da8eb5",
        )
        shutil.rmtree(runtime_directory)

        generated_at_utc: str = datetime.now(timezone.utc).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
        manifest_path: Path = _write_vdmcheck_manifest(
            config=config,
            catalog=catalog,
            cells=cells,
            staging_directory=staging_directory,
            generated_at_utc=generated_at_utc,
            fmpy_version=fmpy_version,
            fmpy_distribution_sha256=fmpy_distribution_sha256,
            java_executable=java_executable,
            java_version=java_version,
            java_runtime_file_count=java_runtime_identity[0],
            java_runtime_total_size_bytes=java_runtime_identity[1],
            java_runtime_tree_sha256=java_runtime_identity[2],
            vdmcheck_two_source_initial_identity=(
                vdmcheck_two_source_initial_identity
            ),
            vdmcheck_two_source_final_identity=vdmcheck_two_source_final_identity,
            vdmcheck_two_entry_jar_identity=vdmcheck_two_entry_jar_identity,
            vdmcheck_two_checkpoints=vdmcheck_two_checkpoints,
            vdmcheck_two_version=vdmcheck_two_version,
            vdmcheck_three_source_initial_identity=(
                vdmcheck_three_source_initial_identity
            ),
            vdmcheck_three_source_final_identity=(
                vdmcheck_three_source_final_identity
            ),
            vdmcheck_three_entry_jar_identity=vdmcheck_three_entry_jar_identity,
            vdmcheck_three_checkpoints=vdmcheck_three_checkpoints,
            vdmcheck_three_version=vdmcheck_three_version,
        )
        _verify_vdmcheck_package(config, staging_directory, manifest_path)
        os.replace(staging_directory, config.output_directory)
        publication_succeeded = True
    finally:
        if publication_succeeded:
            pass
        else:
            if staging_directory.exists():
                shutil.rmtree(staging_directory)
            else:
                pass
    return config.output_directory / "manifest.json"
