# SPDX-License-Identifier: MPL-2.0
"""Optional in-process compiler provider behind the shared compiler interface."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

# Preserve the existing HiGHS import order: a broken installed highspy must not
# be loaded after pygslv has exported a conflicting native HiGHS implementation.
try:
    import highspy
except Exception:
    # This optional third-party initialization boundary must not disable LLVM.
    pass
if isinstance(sys.modules.get("highspy", None), ModuleType) or importlib.util.find_spec("highspy") is None:
    try:
        import pygslv
    except Exception:
        # Installed-package initialization errors remain unavailable, without fallback.
        pass
else:
    pass

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import NativeCompilerFramework
from VeraGridEngine.Utils.Compiler.interface import CompilerInterface, ensure_output_directory
from VeraGridEngine.IO.native_compiler.compiler_interface import _native_host_contract


class PygslvCompilerHandler(CompilerInterface):
    """Adapt the historical optional pygslv API without inventing CLI tools."""

    __slots__ = ("_provider",)

    def __init__(self, logger: Logger | None = None) -> None:
        """Validate the installed package without fallback or installation.

        :param logger: Optional shared compiler logger.
        :return: None.
        """
        self.logger: Logger = logger if logger is not None else Logger()
        provider: object | None = sys.modules.get("pygslv", None)
        self._provider: ModuleType | None = provider if isinstance(provider, ModuleType) else None
        # In-process compilation has no executable path or version subprocess.
        self.setup_valid: bool = self._is_setup_valid()

    def _is_setup_valid(self) -> bool:
        """Check the required compilation API without invoking native work.

        :return: True only when the selected package exposes the historical API.
        """
        if self._provider is None:
            if importlib.util.find_spec("pygslv") is None:
                self.logger.add_error("Selected optional pygslv package is not installed")
            elif not isinstance(sys.modules.get("highspy", None), ModuleType) and importlib.util.find_spec("highspy") is not None:
                self.logger.add_error("Installed pygslv cannot load safely because installed highspy failed first")
            else:
                self.logger.add_error("Installed pygslv failed to load; the selected provider remains unavailable")
            return False
        else:
            try:
                self._provider.compile_cpp_files_to_shared_library
            except AttributeError:
                self.logger.add_error("Selected pygslv lacks the required compilation API")
                return False
            else:
                return True

    def compile(self, source_files: list[str], output_dir: str, lib_name: str = "", include_directories: list[str] | None = None) -> str:
        """Compile with the package's existing header-parent include contract.

        :param source_files: Ordered C translation units.
        :param output_dir: Facade-owned build directory.
        :param lib_name: Native library filename, or the native default.
        :param include_directories: Roots whose headers declare package include paths.
        :return: Generated path, or an empty string on provider failure.
        """
        if self._provider is not None and self.setup_valid and ensure_output_directory(output_dir, self.logger):
            pass
        else:
            return ""
        host: tuple[str, str, str, str, str] = _native_host_contract()
        output: Path = Path(output_dir).resolve() / (lib_name or ("liboutput" + host[3]))
        roots: list[str] = include_directories if include_directories is not None else list()
        header_groups: list[tuple[Path, ...]] = [tuple()] * len(roots)
        header_count: int = 0
        index: int
        for index in range(len(roots)):
            header_groups[index] = tuple(sorted(Path(roots[index]).rglob("*.h")))
            header_count += len(header_groups[index])
        # Headers are package inputs that contribute include parents, not translation units.
        paths: list[str] = [""] * (len(source_files) + header_count)
        offset: int = 0
        source: str
        for source in source_files:
            paths[offset] = str(Path(source).resolve())
            offset += 1
        group: tuple[Path, ...]
        header: Path
        for group in header_groups:
            for header in group:
                paths[offset] = str(header.resolve())
                offset += 1
        result: tuple[bool, str] = self._provider.compile_cpp_files_to_shared_library(tuple(paths), str(output))
        if result[0] and output.is_file():
            return str(output)
        else:
            self.logger.add_error("pygslv compilation failed: " + result[1][-4000:])
            return ""

    def get_native_framework(self) -> NativeCompilerFramework:
        """Identify the package provider without executable metadata.

        :return: PYGSLV.
        """
        return NativeCompilerFramework.PYGSLV
