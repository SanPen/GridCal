# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""FMU compilation through the shared VeraGrid compiler interface."""

from __future__ import annotations

from pathlib import Path
import platform

from VeraGridEngine.Utils.Compiler.interface import Compiler
from VeraGridEngine.IO.native_compiler.selected_interface import resolve_native_compiler


def fmu_compiler_available(compiler: Compiler | None = None) -> bool:
    """Return whether the shared compiler coordinator has a usable handler.

    :param compiler: Optional compiler coordinator to inspect.
    :return: ``True`` when a compiler handler is available.
    """

    selected_compiler: Compiler | None = compiler if compiler is not None else resolve_native_compiler()
    if selected_compiler is None:
        return False
    else:
        return selected_compiler.get_handler() is not None


def _native_library_suffix() -> str:
    """Return the shared-library suffix for the current host.

    :return: Native shared-library suffix.
    """

    system_name: str = platform.system()
    if system_name == "Windows":
        return ".dll"
    if system_name == "Darwin":
        return ".dylib"
    return ".so"


def compile_fmu_shared_library(
    source_files: tuple[Path, ...],
    include_directories: tuple[Path, ...],
    output_path: Path,
    compiler: Compiler | None = None,
) -> Path:
    """Compile one host-native FMI shared library.

    :param source_files: Generated C translation units.
    :param include_directories: Header search directories.
    :param output_path: Destination shared-library path.
    :param compiler: Optional caller-owned compiler coordinator.
    :return: Compiled shared-library path.
    """

    if len(source_files) == 0:
        raise ValueError("FMU compilation requires source files")
    if len(include_directories) == 0:
        raise ValueError("FMU compilation requires include directories")
    for source_file in source_files:
        if source_file.is_file():
            pass
        else:
            raise FileNotFoundError(str(source_file))
    for include_directory in include_directories:
        if include_directory.is_dir():
            pass
        else:
            raise FileNotFoundError(str(include_directory))
    if output_path.suffix.lower() != _native_library_suffix():
        raise ValueError("The requested FMU binary suffix does not match the host")
    selected_compiler: Compiler | None = compiler if compiler is not None else resolve_native_compiler()
    if selected_compiler is None:
        raise RuntimeError("No selected native compiler is available for FMU compilation")
    else:
        pass
    build_directory: Path = output_path.parent / "compiler_build"
    compile_succeeded: bool = selected_compiler.compile(
        [str(source_file) for source_file in source_files],
        str(build_directory),
        output_path.name,
        str(output_path),
        True,
        [str(directory) for directory in include_directories],
    )
    if compile_succeeded:
        pass
    else:
        raise RuntimeError("The shared compiler failed to build the FMU library")
    if output_path.is_file():
        pass
    else:
        raise FileNotFoundError(str(output_path))
    # The packaged FMU is validated through the FMI loader by the exporter.
    return output_path
