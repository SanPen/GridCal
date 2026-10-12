# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import subprocess

from VeraGridEngine.enumerations import NativeCompilerFramework
from VeraGridEngine.IO.native_compiler.compiler_interface import (
    NativeCompilerSelection,
    NativeCompilerToolset,
    _native_host_contract,
    _trusted_tool_paths,
)


def resolve_local_llvm_toolset(selection: NativeCompilerSelection) -> NativeCompilerToolset:
    """Resolve a user-selected LLVM installation without environment lookup.

    :param selection: Explicit local LLVM roots for the current host.
    :return: Authenticated native compiler toolset.
    """

    if selection.framework == NativeCompilerFramework.LOCAL_LLVM:
        pass
    else:
        raise ValueError("The local LLVM adapter received another provider")
    if selection.binary_root is not None:
        binary_root: Path = selection.binary_root
    else:
        raise ValueError("LOCAL_LLVM requires an explicit absolute binary root")
    package_platform, package_arch, target_triple, library_suffix, linker_name = _native_host_contract()
    if package_platform == "win":
        tool_names: tuple[str, ...] = ("clang.exe", linker_name, "llvm-nm.exe", "llvm-objdump.exe")
    else:
        tool_names = ("clang", linker_name, "llvm-nm", "llvm-objdump")
    tools, tool_hashes = _trusted_tool_paths(binary_root, tool_names)
    if package_platform == "win":
        if selection.support_root is not None:
            support_root: Path | None = selection.support_root
            if support_root.is_absolute() and support_root.is_dir() and not support_root.is_symlink():
                support_root = support_root.resolve(strict=True)
            else:
                raise ValueError("LOCAL_LLVM requires an absolute Windows support root")
        else:
            raise ValueError("LOCAL_LLVM requires an explicit Windows support root")
        sdk_root: Path | None = None
    else:
        support_root = None
        if selection.support_root is None:
            pass
        else:
            raise ValueError("LOCAL_LLVM support_root is valid only on Windows")
        if package_platform == "darwin":
            if selection.sdk_root is not None:
                sdk_root = selection.sdk_root
                if sdk_root.is_absolute() and sdk_root.is_dir() and not sdk_root.is_symlink():
                    sdk_root = sdk_root.resolve(strict=True)
                else:
                    raise ValueError("LOCAL_LLVM requires an absolute native macOS SDK root")
            else:
                raise ValueError("LOCAL_LLVM requires an explicit native macOS SDK root")
        else:
            if selection.sdk_root is None:
                sdk_root = None
            else:
                raise ValueError("LOCAL_LLVM sdk_root is valid only on macOS")
    if package_platform == "darwin":
        target_result: subprocess.CompletedProcess[str] = subprocess.run(
            (str(tools[0]), "-dumpmachine"),
            check=False,
            capture_output=True,
            text=True,
        )
        observed_target: str = target_result.stdout.strip()
        valid_target: bool = bool(
            target_result.returncode == 0
            and observed_target.startswith(package_arch + "-apple-darwin")
        )
        if valid_target:
            target_triple = observed_target
        else:
            raise RuntimeError("The selected local Clang reported an invalid native macOS target")
    else:
        pass
    compiler_prefix_arguments: list[str] = [
        "--target=" + target_triple,
        "--ld-path=" + str(tools[1]),
    ]
    if package_platform == "win" and support_root is not None:
        compiler_prefix_arguments.extend(("--sysroot=" + str(support_root), "-rtlib=compiler-rt"))
    else:
        if package_platform == "darwin" and sdk_root is not None:
            compiler_prefix_arguments.extend(("-isysroot", str(sdk_root)))
        else:
            pass
    return NativeCompilerToolset(
        framework=selection.framework,
        provider_version="sha256:" + tool_hashes[0],
        binary_root=binary_root.resolve(strict=True),
        support_root=support_root,
        sdk_root=sdk_root,
        compiler_path=tools[0],
        linker_path=tools[1],
        nm_path=tools[2],
        objdump_path=tools[3],
        package_platform=package_platform,
        package_arch=package_arch,
        target_triple=target_triple,
        library_suffix=library_suffix,
        compiler_prefix_arguments=tuple(compiler_prefix_arguments),
        tool_hashes=tool_hashes,
    )
