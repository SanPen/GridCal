# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
import platform
from pathlib import Path

from VeraGridEngine.enumerations import NativeCompilerFramework


class NativeCompilerSelection:
    """Explicit provider choice and provider-owned filesystem roots."""

    __slots__ = ("framework", "binary_root", "support_root", "sdk_root")

    def __init__(
        self,
        framework: NativeCompilerFramework,
        binary_root: Path | None = None,
        support_root: Path | None = None,
        sdk_root: Path | None = None,
    ) -> None:
        """Create one immutable-shape compiler selection.

        :param framework: Explicit native compiler provider.
        :param binary_root: Provider binary directory, required by local LLVM.
        :param support_root: Provider support/sysroot directory when required.
        :param sdk_root: Native SDK directory when required by the host.
        :return: None.
        """

        self.framework: NativeCompilerFramework = framework
        self.binary_root: Path | None = binary_root
        self.support_root: Path | None = support_root
        self.sdk_root: Path | None = sdk_root


class NativeCompilerToolset:
    """Authenticated native compiler tools and their complete host contract."""

    __slots__ = (
        "framework", "provider_version", "binary_root", "support_root", "sdk_root",
        "compiler_path", "linker_path", "nm_path", "objdump_path", "package_platform",
        "package_arch", "target_triple", "library_suffix", "compiler_prefix_arguments",
        "tool_hashes",
    )

    def __init__(
        self,
        framework: NativeCompilerFramework,
        provider_version: str,
        binary_root: Path,
        support_root: Path | None,
        sdk_root: Path | None,
        compiler_path: Path,
        linker_path: Path,
        nm_path: Path,
        objdump_path: Path,
        package_platform: str,
        package_arch: str,
        target_triple: str,
        library_suffix: str,
        compiler_prefix_arguments: tuple[str, ...],
        tool_hashes: tuple[str, ...],
    ) -> None:
        """Store one resolved provider contract.

        :param framework: Provider that resolved this toolset.
        :param provider_version: Provider-owned version or content identity.
        :param binary_root: Canonical directory containing all executable tools.
        :param support_root: Canonical support/sysroot directory when required.
        :param sdk_root: Canonical SDK directory when required.
        :param compiler_path: Canonical Clang executable.
        :param linker_path: Canonical LLD executable.
        :param nm_path: Canonical llvm-nm executable.
        :param objdump_path: Canonical llvm-objdump executable.
        :param package_platform: Reviewed platform identifier.
        :param package_arch: Reviewed architecture identifier.
        :param target_triple: Exact native target triple.
        :param library_suffix: Native shared-library suffix.
        :param compiler_prefix_arguments: Provider-owned compiler arguments.
        :param tool_hashes: Ordered SHA-256 values for the four executables.
        :return: None.
        """

        self.framework: NativeCompilerFramework = framework
        self.provider_version: str = provider_version
        self.binary_root: Path = binary_root
        self.support_root: Path | None = support_root
        self.sdk_root: Path | None = sdk_root
        self.compiler_path: Path = compiler_path
        self.linker_path: Path = linker_path
        self.nm_path: Path = nm_path
        self.objdump_path: Path = objdump_path
        self.package_platform: str = package_platform
        self.package_arch: str = package_arch
        self.target_triple: str = target_triple
        self.library_suffix: str = library_suffix
        self.compiler_prefix_arguments: tuple[str, ...] = compiler_prefix_arguments
        self.tool_hashes: tuple[str, ...] = tool_hashes

    def assert_unchanged(self) -> None:
        """Reauthenticate every executable against its selection-time digest.

        :return: None.
        """

        tool_paths: tuple[Path, ...] = (
            self.compiler_path,
            self.linker_path,
            self.nm_path,
            self.objdump_path,
        )
        tool_index: int
        tool_path: Path
        for tool_index, tool_path in enumerate(tool_paths):
            canonical_tool: Path = tool_path.resolve(strict=True)
            trusted_path: bool = bool(
                not tool_path.is_symlink()
                and tool_path.is_file()
                and canonical_tool.is_relative_to(self.binary_root)
            )
            if trusted_path:
                with canonical_tool.open("rb") as tool_stream:
                    actual_hash: str = hashlib.file_digest(tool_stream, "sha256").hexdigest()
                if actual_hash == self.tool_hashes[tool_index]:
                    pass
                else:
                    raise RuntimeError("A native compiler tool changed after authentication")
            else:
                raise RuntimeError("A native compiler tool path is no longer trusted")


def _native_host_contract() -> tuple[str, str, str, str, str]:
    """Resolve the reviewed native host row without discovering any tools.

    :return: Platform, architecture, target triple, library suffix and linker name.
    """

    system_name: str = platform.system().lower()
    machine_name: str = platform.machine().lower()
    if system_name == "windows":
        if machine_name == "amd64" or machine_name == "x86_64":
            return "win", "x86_64", "x86_64-w64-windows-gnu", ".dll", "ld.lld.exe"
        else:
            raise RuntimeError("Native compilation supports only AMD64 Windows hosts")
    else:
        if system_name == "linux":
            if machine_name == "x86_64" or machine_name == "amd64":
                return "linux", "x86_64", "x86_64-unknown-linux-gnu", ".so", "ld.lld"
            else:
                raise RuntimeError("Native compilation supports only x86_64 Linux hosts")
        else:
            if system_name == "darwin":
                if machine_name == "x86_64" or machine_name == "amd64":
                    return "darwin", "x86_64", "", ".dylib", "ld64.lld"
                else:
                    if machine_name == "arm64" or machine_name == "aarch64":
                        return "darwin", "arm64", "", ".dylib", "ld64.lld"
                    else:
                        raise RuntimeError("Native compilation supports only x86_64 or arm64 macOS hosts")
            else:
                raise RuntimeError("Native compilation does not support this operating system")


def _trusted_tool_paths(
    binary_root: Path,
    tool_names: tuple[str, ...],
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Resolve and hash a complete executable set inside one explicit root.

    :param binary_root: Absolute directory that must own every tool.
    :param tool_names: Ordered platform-specific executable names.
    :return: Canonical paths and matching SHA-256 values.
    """

    if binary_root.is_absolute() and binary_root.is_dir() and not binary_root.is_symlink():
        canonical_root: Path = binary_root.resolve(strict=True)
    else:
        raise ValueError("The native compiler binary root must be an absolute regular directory")
    resolved_tools: list[Path] = list()
    tool_hashes: list[str] = list()
    tool_name: str
    for tool_name in tool_names:
        candidate_path: Path = canonical_root / tool_name
        if candidate_path.is_file() and not candidate_path.is_symlink():
            canonical_tool: Path = candidate_path.resolve(strict=True)
            trusted_tool: bool = canonical_tool.is_relative_to(canonical_root)
        else:
            canonical_tool = candidate_path
            trusted_tool = False
        if trusted_tool:
            resolved_tools.append(canonical_tool)
            with canonical_tool.open("rb") as tool_stream:
                tool_hashes.append(hashlib.file_digest(tool_stream, "sha256").hexdigest())
        else:
            raise FileNotFoundError("A required native compiler tool is missing or untrusted: " + tool_name)
    return tuple(resolved_tools), tuple(tool_hashes)
