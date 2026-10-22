# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import subprocess

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Utils.Compiler.interface import ClangHandler, ensure_output_directory
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
        tool_names: tuple[str, ...] = ("clang.exe", linker_name)
    else:
        tool_names = ("clang", linker_name)
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
        package_platform=package_platform,
        package_arch=package_arch,
        target_triple=target_triple,
        library_suffix=library_suffix,
        compiler_prefix_arguments=tuple(compiler_prefix_arguments),
        tool_hashes=tool_hashes,
    )


def _build_local_llvm_compile_command(
    toolset: NativeCompilerToolset,
    source_files: list[str],
    include_directories: list[str] | None,
    output_path: Path,
) -> list[str]:
    """Build the existing native compile/link command from authenticated roots.

    :param toolset: Selected compiler, linker, target and platform support roots.
    :param source_files: Ordered source translation units.
    :param include_directories: Ordered header roots, when supplied.
    :param output_path: Shared-library destination inside the facade build tree.
    :return: Explicit command with no environment discovery.
    """
    command: list[str] = list((str(toolset.compiler_path),))
    command.extend(toolset.compiler_prefix_arguments)
    if toolset.package_platform == "darwin":
        command.extend(("-dynamiclib", "-fPIC"))
    else:
        command.append("-shared")
        if toolset.package_platform == "linux":
            command.append("-fPIC")
        else:
            pass
    command.extend(("-std=c99", "-O2"))
    if include_directories is not None:
        directory: str
        for directory in include_directories:
            command.extend(("-I", str(Path(directory).resolve())))
    else:
        pass
    command.extend(("-o", str(output_path.resolve())))
    source: str
    for source in source_files:
        command.append(str(Path(source).resolve()))
    if toolset.package_platform == "win":
        pass
    else:
        command.append("-lm")
    return command


class LocalLlvmCompilerHandler(ClangHandler):
    """Use the existing authenticated LLVM toolset behind the shared facade."""

    __slots__ = ("_toolset",)

    def __init__(self, toolset: NativeCompilerToolset, logger: Logger | None = None) -> None:
        """Initialize only the selected Clang, without probing other compilers.

        :param toolset: Authenticated tools and native target arguments.
        :param logger: Optional shared compiler logger.
        :return: None.
        """
        self._toolset: NativeCompilerToolset = toolset
        super().__init__(logger, str(toolset.compiler_path))

    def compile(self, source_files: list[str], output_dir: str, lib_name: str = "", include_directories: list[str] | None = None) -> str:
        """Compile using the selected native target, linker and support roots.

        :param source_files: Ordered C source paths.
        :param output_dir: Facade-owned temporary build directory.
        :param lib_name: Library filename, or the native default.
        :param include_directories: Header roots.
        :return: Generated path, or an empty string on compiler failure.
        """
        self._toolset.assert_unchanged()
        if ensure_output_directory(output_dir, self.logger):
            pass
        else:
            return ""
        output: Path = Path(output_dir).resolve() / (lib_name or ("liboutput" + self._toolset.library_suffix))
        # Reuse Clang process diagnostics while retaining the complete native contract.
        result: subprocess.CompletedProcess[str] = self._execute_command(
            _build_local_llvm_compile_command(self._toolset, source_files, include_directories, output),
            str(Path(output_dir).resolve()),
        )
        if result.returncode == 0 and output.is_file():
            return str(output)
        else:
            return ""

    def get_native_framework(self) -> NativeCompilerFramework:
        """Identify the selected provider independently of executable metadata.

        :return: LOCAL_LLVM.
        """
        return NativeCompilerFramework.LOCAL_LLVM
