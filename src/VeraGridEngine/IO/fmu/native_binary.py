# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Validate native FMI binary selection before private staging."""

from __future__ import annotations

import platform
from pathlib import PurePosixPath
import sys

from VeraGridEngine.IO.fmu.Elements.inspection import FmuInspectionReceipt
from VeraGridEngine.enumerations import FmiVersion


def _resolve_legacy_host_binary() -> tuple[str, str]:
    """Return the FMI 1/2 binary directory and suffix for this process.

    FMI 1 and FMI 2 use legacy platform-directory names whose bitness follows the host
    process. The runtime intentionally fails closed on operating systems that
    FMPy cannot load through the current VeraGrid integration.

    :return: Pair containing the legacy platform directory and library suffix.
    :raises RuntimeError: If the current operating system is not supported.
    """

    # Legacy FMI platform names encode process bitness rather than a CPU tuple.
    if sys.maxsize <= 2**32:
        bitness: str = "32"
    else:
        bitness = "64"

    # Resolve only the operating systems supported by the current native host.
    if sys.platform.startswith("win"):
        platform_name: str = f"win{bitness}"
        library_suffix: str = ".dll"
    elif sys.platform.startswith("linux"):
        platform_name = f"linux{bitness}"
        library_suffix = ".so"
    elif sys.platform == "darwin":
        platform_name = f"darwin{bitness}"
        library_suffix = ".dylib"
    else:
        raise RuntimeError(
            f"FMI 1/2 runtime is not supported on host platform {sys.platform!r}"
        )

    return platform_name, library_suffix


def _resolve_fmi_three_binary_platform(
    machine_name: str,
    is_32_bit_process: bool,
    python_platform_name: str,
) -> tuple[str, str]:
    """Resolve one FMI 3 binary platform from explicit process identity.

    FMI 3 replaces legacy bitness folders with an architecture-system tuple.
    Keeping the pure mapping separate from environment detection makes every
    supported platform tuple verifiable on one development host.

    :param machine_name: Machine spelling reported for the Python process.
    :param is_32_bit_process: Whether the Python process uses a 32-bit ABI.
    :param python_platform_name: Platform spelling reported by Python.
    :return: Pair containing the FMI 3 platform tuple and library suffix.
    :raises RuntimeError: If the process architecture or system is unsupported.
    """

    # Normalize the machine spelling reported by the standard library, then
    # map only architectures supported by the current native host dependency.
    normalized_machine_name: str = machine_name.lower()
    if normalized_machine_name in ("aarch64", "arm64"):
        architecture_name: str = "aarch64"
    elif normalized_machine_name in (
        "amd64",
        "i386",
        "i686",
        "x86",
        "x86_64",
        "x86pc",
    ):
        if is_32_bit_process:
            architecture_name = "x86"
        else:
            architecture_name = "x86_64"
    else:
        raise RuntimeError(
            "FMI 3 native binary preflight is not defined for host architecture "
            f"{machine_name!r}"
        )

    # FMI 3 system names differ from the FMI 2 legacy directory prefixes.
    if python_platform_name.startswith("win"):
        system_name: str = "windows"
        library_suffix: str = ".dll"
    elif python_platform_name.startswith("linux"):
        system_name = "linux"
        library_suffix = ".so"
    elif python_platform_name == "darwin":
        system_name = "darwin"
        library_suffix = ".dylib"
    else:
        raise RuntimeError(
            "FMI 3 native binary preflight is not defined for host platform "
            f"{python_platform_name!r}"
        )

    platform_tuple: str = f"{architecture_name}-{system_name}"
    return platform_tuple, library_suffix


def resolve_fmi_three_host_binary() -> tuple[str, str]:
    """Return the FMI 3 platform tuple and suffix for this Python process.

    The architecture follows the Python process ABI so the selected library is
    loadable by the current process rather than merely matching the host OS.

    :return: Pair containing the FMI 3 platform tuple and library suffix.
    :raises RuntimeError: If the process architecture or system is unsupported.
    """

    # Read the active process identity once, then delegate the standard mapping
    # to the deterministic owner shared by local and cross-platform checks.
    machine_name: str = platform.machine()
    is_32_bit_process: bool = sys.maxsize <= 2**32
    return _resolve_fmi_three_binary_platform(
        machine_name=machine_name,
        is_32_bit_process=is_32_bit_process,
        python_platform_name=sys.platform,
    )


def _validate_exact_native_binary(
    receipt: FmuInspectionReceipt,
    model_identifier: str,
    binary_platform_directory: str,
    library_suffix: str,
) -> None:
    """Require one exact interface library from the inspected FMU entries.

    :param receipt: Bounded inspection receipt for the unchanged FMU source.
    :param model_identifier: Interface model identifier declared by metadata.
    :param binary_platform_directory: Version-specific current-host binary directory.
    :param library_suffix: Native library suffix for the current system.
    :return: None.
    :raises RuntimeError: If no exact current-host library can be executed.
    """

    expected_name: str = f"{model_identifier}{library_suffix}"
    expected_entry: str = f"binaries/{binary_platform_directory}/{expected_name}"
    expected_parts: tuple[str, str, str] = (
        "binaries",
        binary_platform_directory,
        expected_name,
    )

    # Three exact components reject nested identifiers and noncanonical case.
    # Other platform libraries and dependencies remain valid FMU content.
    matching_entry_found: bool = False
    binary_entry: str
    for binary_entry in receipt.binary_entries:
        entry_parts: tuple[str, ...] = PurePosixPath(binary_entry).parts
        if entry_parts == expected_parts:
            matching_entry_found = True
        else:
            pass
    if matching_entry_found:
        pass
    else:
        if receipt.get_contains_source_code():
            raise RuntimeError(
                f"FMU has no {expected_entry} binary; source compilation is not connected"
            )
        else:
            raise RuntimeError(
                f"FMU does not contain the required current-host binary {expected_entry}"
            )


def validate_fmi_two_native_binary(
    receipt: FmuInspectionReceipt,
    model_identifier: str,
) -> None:
    """Require the exact current-host FMI 2 library recorded by inspection.

    Additional platform binaries and dependent libraries are accepted, but the
    interface library itself must use the canonical root location and exact
    case. Source-bearing FMUs are not compiled implicitly because compilation
    requires a separate policy and toolchain contract.

    :param receipt: Bounded inspection receipt for the unchanged FMU source.
    :param model_identifier: FMI 2 interface model identifier from metadata.
    :return: None.
    :raises RuntimeError: If no exact current-host binary can be executed.
    """

    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    _validate_exact_native_binary(
        receipt=receipt,
        model_identifier=model_identifier,
        binary_platform_directory=platform_name,
        library_suffix=library_suffix,
    )


def validate_fmi_three_native_binary(
    receipt: FmuInspectionReceipt,
    model_identifier: str,
) -> None:
    """Require the exact current-host FMI 3 library recorded by inspection.

    The platform tuple, interface identifier, path depth, and case must match
    the FMI 3 host contract exactly. Source-bearing FMUs fail closed because no
    compiler or source-build policy is connected to the importer.

    :param receipt: Bounded inspection receipt for the unchanged FMU source.
    :param model_identifier: FMI 3 interface model identifier from metadata.
    :return: None.
    :raises RuntimeError: If no exact current-host binary can be executed.
    """

    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    _validate_exact_native_binary(
        receipt=receipt,
        model_identifier=model_identifier,
        binary_platform_directory=platform_tuple,
        library_suffix=library_suffix,
    )


def validate_native_binary(
    receipt: FmuInspectionReceipt,
    fmi_version_family: FmiVersion,
    model_identifier: str,
) -> None:
    """Validate the current-host library using the declared FMI family.

    :param receipt: Bounded inspection receipt for the unchanged FMU source.
    :param fmi_version_family: Parsed FMI version family controlling layout.
    :param model_identifier: Interface model identifier from parsed metadata.
    :return: None.
    :raises RuntimeError: If the FMI family has no native preflight contract.
    """

    # FMI 1 and FMI 2 share the standard legacy directory convention, while
    # FMI 3 uses an architecture-system tuple.
    if (
        fmi_version_family == FmiVersion.FMI_1_0
        or fmi_version_family == FmiVersion.FMI_2_0
    ):
        platform_name: str
        library_suffix: str
        platform_name, library_suffix = _resolve_legacy_host_binary()
        _validate_exact_native_binary(
            receipt=receipt,
            model_identifier=model_identifier,
            binary_platform_directory=platform_name,
            library_suffix=library_suffix,
        )
    else:
        if fmi_version_family == FmiVersion.FMI_3_0:
            validate_fmi_three_native_binary(receipt, model_identifier)
        else:
            raise RuntimeError(
                f"FMI {fmi_version_family.value} native binary preflight is not supported"
            )
