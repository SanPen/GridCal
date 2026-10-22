# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Compiler detection and shared-library compilation interfaces."""

from __future__ import annotations

import os
import platform
from pathlib import Path
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import CompilerName, NativeCompilerFramework, OperatingSystem


def ensure_output_directory(output_dir: str, logger: Logger | None = None) -> bool:
    """Create the compiler output directory when necessary.

    :param output_dir: Directory for compiler output.
    :param logger: Optional logger for filesystem failures.
    :return: ``True`` when the directory is ready.
    """
    # Reuse an existing directory so repeated builds do not destroy unrelated files.
    if os.path.exists(output_dir):
        if os.path.isdir(output_dir):
            return True
        else:
            if logger is not None:
                logger.add_error(f"Compiler output path is not a directory: {output_dir}")
            return False
    else:
        # Create the complete directory chain because callers may provide a nested build path.
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as error:
            if logger is not None:
                logger.add_error(f"Could not create compiler output directory: {output_dir}; {error}")
            return False
        return True


class CompilerInterface(ABC):
    """Define the common compiler-handler interface."""

    def __init__(
            self,
            compiler_name: str,
            logger: Logger | None = None,
            executable_path: str | None = None,
    ) -> None:
        """Initialize and validate a compiler handler.

        :param compiler_name: Name used in setup errors.
        :param logger: Optional logger shared with the compiler coordinator.
        :param executable_path: Optional compiler executable path.
        :return: None.
        """
        self.logger: Logger = logger if logger is not None else Logger()
        self.executable_path: str = executable_path if executable_path is not None else compiler_name
        self._compiler_driver: CompilerName | None
        try:
            self._compiler_driver = CompilerName(compiler_name)
        except ValueError:
            self._compiler_driver = None
        self.setup_valid: bool = self._is_setup_valid()
        if self.setup_valid:
            return
        else:
            message: str = f"Cannot initialize {compiler_name}: setup failed."
            self.logger.add_error(message)

    def _run_command(self, command: list[str], cwd: str) -> subprocess.CompletedProcess[Any]:
        """Run a compiler command and log all process failures.

        :param command: Executable and command-line arguments.
        :param cwd: Requested working directory; Windows GCC-compatible tools
            use their compiler directory to resolve installed runtime DLLs.
        :return: Completed subprocess result with captured text output.
        """
        execution_directory: str = cwd
        execution_command: list[str] = command
        if platform.system() == "Windows" and self._compiler_driver in (CompilerName.GCC, CompilerName.CLANG):
            compiler_executable: str | None = shutil.which(self.executable_path)
            if compiler_executable is not None:
                # MSYS2 child tools need the selected compiler's runtime DLLs in
                # their working directory; this changes no parent or environment state.
                execution_directory = str(Path(compiler_executable).resolve().parent)
                command_executable: str | None = shutil.which(command[0]) if command else None
                if command_executable is not None:
                    # Preserve executable paths relative to the caller before selecting child cwd.
                    execution_command = list(command)
                    execution_command[0] = str(Path(command_executable).resolve())
                else:
                    pass
            else:
                pass
        else:
            pass
        # Capture both streams so compiler diagnostics remain available in Logger after failure.
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                execution_command, cwd=execution_directory, check=False, capture_output=True, text=True, errors="replace"
            )
        except OSError as error:
            self.logger.add_error(f"Compiler executable failed: {' '.join(command)}; {error}")
            return subprocess.CompletedProcess(command, 1, "", str(error))
        # Return the process result instead of raising so Compiler can keep failure handling centralized.
        if result.returncode == 0:
            return result
        else:
            self.logger.add_error(
                f"Compiler command failed: {' '.join(command)}; "
                f"stdout={result.stdout.strip()}; stderr={result.stderr.strip()}"
            )
            return result

    def _command_succeeded(self, result: subprocess.CompletedProcess[Any]) -> bool:
        """Return whether a compiler command completed successfully.

        :param result: Completed subprocess result.
        :return: ``True`` when the process exit code is zero.
        """
        return result.returncode == 0

    @abstractmethod
    def compile(
            self,
            source_files: list[str],
            output_dir: str,
            lib_name: str = "",
            include_directories: list[str] | None = None,
    ) -> str:
        """Compile source files into a shared library.

        :param source_files: Source files to compile.
        :param output_dir: Directory for output files.
        :param lib_name: Shared-library filename.
        :param include_directories: Header search directories.
        :return: Path to the generated library.
        """
        pass

    def get_native_framework(self) -> NativeCompilerFramework | None:
        """Identify an explicitly selected native provider.

        :return: Native framework, or None for a generic executable handler.
        """
        return None

    @abstractmethod
    def _is_setup_valid(self) -> bool:
        """Check whether the compiler is configured.

        :return: ``True`` when the compiler can be invoked.
        """
        pass

    def test_compiler(self) -> bool:
        """Compile a minimal C program as a compiler smoke test.

        :return: ``True`` when the output library exists.
        """
        source_name: str = "test.c"
        with open(source_name, "w") as source_file:
            source_file.write("int main() { return 0; }")
        try:
            library_path: str = self.compile([source_name], "build")
            return os.path.exists(library_path)
        except (OSError, subprocess.CalledProcessError) as error:
            self.logger.add_error(f"Compiler smoke test failed: {error}")
            print(f"Compilation failed: {error}")
            return False


class GCCHandler(CompilerInterface):
    """Compile shared libraries with GCC."""

    def __init__(self, logger: Logger | None = None, executable_path: str | None = None) -> None:
        """Initialize the GCC handler.

        :return: None.
        """
        super().__init__(CompilerName.GCC.value, logger, executable_path)

    def _execute_command(self, command: list[str], cwd: str) -> subprocess.CompletedProcess[Any]:
        """Execute a GCC command.

        :param command: GCC command and arguments.
        :param cwd: Working directory.
        :return: Completed subprocess result.
        """
        return self._run_command(command, cwd)

    def compile(
            self,
            source_files: list[str],
            output_dir: str,
            lib_name: str = "liboutput.so",
            include_directories: list[str] | None = None,
    ) -> str:
        """Compile C files into a GCC shared library.

        :param source_files: C source files.
        :param output_dir: Output directory.
        :param lib_name: Library filename.
        :param include_directories: Header search directories.
        :return: Generated library path.
        """
        if not ensure_output_directory(output_dir, self.logger):
            return ""
        else:
            pass
        # Compile each source independently so one failed translation stops before linking.
        library_path: str = os.path.join(output_dir, lib_name)
        object_files: list[str] = list()
        include_flags: list[str] = list()
        if include_directories is not None:
            for include_directory in include_directories:
                include_flags.extend(["-I", os.path.abspath(include_directory)])
        else:
            pass
        for source_file in source_files:
            object_file: str = os.path.join(
                output_dir, f"{os.path.splitext(os.path.basename(source_file))[0]}.o"
            )
            # Resolve caller-relative paths before Windows child tools use the
            # compiler directory to locate their existing runtime DLLs.
            object_files.append(os.path.abspath(object_file))
            compile_result: subprocess.CompletedProcess[Any] = self._execute_command(
                [self.executable_path, "-c", "-fPIC"] + include_flags
                + [os.path.abspath(source_file), "-o", os.path.abspath(object_file)], os.getcwd()
            )
            if not self._command_succeeded(compile_result):
                return ""
            else:
                pass
        # Link only after every source has produced a successful object file.
        link_result: subprocess.CompletedProcess[Any] = self._execute_command(
            [self.executable_path, "-shared"] + object_files + ["-o", os.path.abspath(library_path)], os.getcwd()
        )
        if not self._command_succeeded(link_result):
            return ""
        else:
            pass
        # Confirm the compiler produced the artifact before reporting success.
        if os.path.exists(library_path):
            return library_path
        else:
            self.logger.add_error(f"Shared library was not created: {library_path}")
            return ""

    def _is_setup_valid(self) -> bool:
        """Check whether GCC is available.

        :return: ``True`` when GCC responds to its version command.
        """
        try:
            result: subprocess.CompletedProcess[Any] = self._run_command([self.executable_path, "--version"],
                                                                         os.getcwd())
            return self._command_succeeded(result)
        except OSError as error:
            self.logger.add_error(f"Could not check GCC: {error}")
            return False


class ClangHandler(GCCHandler):
    """Compile shared libraries with Clang using the GCC-compatible flow."""

    def __init__(self, logger: Logger | None = None, executable_path: str | None = None) -> None:
        """Initialize the Clang handler.

        :return: None.
        """
        CompilerInterface.__init__(self, CompilerName.CLANG.value, logger, executable_path)

    def _execute_command(self, command: list[str], cwd: str) -> subprocess.CompletedProcess[Any]:
        """Execute a Clang command.

        :param command: Clang command and arguments.
        :param cwd: Working directory.
        :return: Completed subprocess result.
        """
        clang_command: list[str] = list(command)
        if clang_command:
            clang_command[0] = self.executable_path
        else:
            clang_command = [self.executable_path]
        return self._run_command(clang_command, cwd)

    def _is_setup_valid(self) -> bool:
        """Check whether Clang is available.

        :return: ``True`` when Clang responds to its version command.
        """
        try:
            result: subprocess.CompletedProcess[Any] = self._run_command([self.executable_path, "--version"],
                                                                         os.getcwd())
            return self._command_succeeded(result)
        except OSError as error:
            self.logger.add_error(f"Could not check Clang: {error}")
            return False


def load_visual_studio_environment(logger: Logger | None = None) -> None:
    """Load the x64 MSVC environment from Visual Studio when available.

    :return: None.
    :param logger: Optional logger for environment-loading failures.
    """
    if platform.system() != "Windows":
        return
    else:
        vswhere_path: str | None = shutil.which("vswhere.exe")
        if vswhere_path is None:
            program_files: str = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
            candidate: str = os.path.join(program_files, "Microsoft Visual Studio", "Installer", "vswhere.exe")
            if os.path.isfile(candidate):
                vswhere_path = candidate
            else:
                vswhere_path = None
        if vswhere_path is None:
            return
        else:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                [vswhere_path, "-latest", "-products", "*", "-requires",
                 "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                capture_output=True, text=True, check=False,
            )
            lines: list[str] = result.stdout.strip().splitlines()
            if lines:
                installation_path: str = lines[0]
            else:
                installation_path = ""
            if installation_path:
                vcvars_path: str = os.path.join(installation_path, "VC", "Auxiliary", "Build", "vcvars64.bat")
            else:
                return
            if os.path.isfile(vcvars_path):
                environment_result: subprocess.CompletedProcess[str] = subprocess.run(
                    f'call "{vcvars_path}" >nul && set', capture_output=True, text=True, check=False, shell=True
                )
                if environment_result.returncode == 0:
                    for line in environment_result.stdout.splitlines():
                        if "=" in line:
                            key: str
                            value: str
                            key, value = line.split("=", 1)
                            os.environ[key] = value
                        else:
                            pass
                else:
                    if logger is not None:
                        logger.add_error(
                            f"Visual Studio environment setup failed: "
                            f"stdout={environment_result.stdout.strip()}; "
                            f"stderr={environment_result.stderr.strip()}"
                        )
                    else:
                        pass
                    return
            else:
                if logger is not None:
                    logger.add_error(f"Visual Studio environment script not found: {vcvars_path}")
                else:
                    pass
                return


class MSVCHandler(CompilerInterface):
    """Compile shared libraries with Microsoft Visual C++."""

    def __init__(self, logger: Logger | None = None, executable_path: str | None = None) -> None:
        """Initialize the MSVC handler.

        :return: None.
        """
        super().__init__(CompilerName.MSVC.value, logger, executable_path)

    def _execute_command(self, command: list[str], cwd: str) -> subprocess.CompletedProcess[Any]:
        """Execute an MSVC command.

        :param command: MSVC command and arguments.
        :param cwd: Working directory.
        :return: Completed subprocess result.
        """
        return self._run_command(command, cwd)

    def compile(
            self,
            source_files: list[str],
            output_dir: str,
            lib_name: str = "output.dll",
            include_directories: list[str] | None = None,
    ) -> str:
        """Compile C files into an MSVC shared library.

        :param source_files: C source files.
        :param output_dir: Output directory.
        :param lib_name: Library filename.
        :param include_directories: Header search directories.
        :return: Generated library path.
        """
        if not ensure_output_directory(output_dir, self.logger):
            return ""
        else:
            pass
        library_path: str = os.path.join(output_dir, lib_name)
        object_files: list[str] = list()
        include_flags: list[str] = list()
        if include_directories is not None:
            for include_directory in include_directories:
                include_flags.extend([f"/I{include_directory}"])
        else:
            pass
        for source_file in source_files:
            object_file: str = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(source_file))[0]}.obj")
            object_files.append(object_file)
            compile_result: subprocess.CompletedProcess[Any] = self._execute_command(
                [self.executable_path, "/nologo", "/c"] + include_flags + [f"/Fo{object_file}", source_file], os.getcwd()
            )
            if not self._command_succeeded(compile_result):
                return ""
            else:
                pass
        link_result: subprocess.CompletedProcess[Any] = self._execute_command(
            [self.executable_path, "/nologo", "/LD"] + object_files + [f"/Fe{library_path}"], os.getcwd()
        )
        if not self._command_succeeded(link_result):
            return ""
        else:
            pass
        if os.path.exists(library_path):
            return library_path
        else:
            self.logger.add_error(f"Shared library was not created: {library_path}")
            return ""

    def _is_setup_valid(self) -> bool:
        """Check whether MSVC is available in the current environment.

        :return: ``True`` when MSVC responds to its help command.
        """
        if os.environ.get("VCToolsInstallDir") and os.environ.get("LIB"):
            environment_ready: bool = True
        else:
            load_visual_studio_environment(self.logger)
            environment_ready = bool(os.environ.get("VCToolsInstallDir") and os.environ.get("LIB"))
        try:
            result: subprocess.CompletedProcess[Any] = self._run_command([self.executable_path, "/?"], os.getcwd())
            return environment_ready and self._command_succeeded(result)
        except OSError as error:
            self.logger.add_error(f"Could not check MSVC: {error}")
            return False


class Compiler:
    """Detect, select, and centrally dispatch compiler operations."""

    __slots__ = (
        "logger",
        "_requested_compiler",
        "_operating_system",
        "_compiler_paths",
        "_compiler_status",
        "_selected_compiler",
        "_handler",
        "_compiled_library_path",
    )

    def __init__(
            self,
            compiler_name: CompilerName | None = None,
            logger: Logger | None = None,
            compiler_paths: dict[CompilerName, str] | None = None,
            compiler_directory: str | None = None,
            compiler_handler: CompilerInterface | None = None,
    ) -> None:
        """Initialize the compiler coordinator.

        :param compiler_name: Optional compiler to force; ``None`` selects the
            first available compiler for the current operating system.
        :param logger: Optional logger to retain and share with the handler.
        :param compiler_paths: Optional explicit executable paths by compiler.
        :param compiler_directory: Optional directory searched for compiler executables.
        :param compiler_handler: Explicit provider; bypasses unrelated discovery and setup.
        :return: None.
        """
        # Store the logger first because detection and handler validation can fail during construction.
        self.logger: Logger = logger if logger is not None else Logger()
        self._requested_compiler: CompilerName | None = compiler_name
        # Detect the platform once so every later decision uses the same snapshot.
        self._operating_system: str = self.detect_os()
        # Resolve paths before probing; probes and handlers must use identical executables.
        self._compiler_paths: dict[CompilerName, str | None]
        self._compiler_status: dict[CompilerName, dict[str, Any]]
        self._handler: CompilerInterface | None
        if compiler_handler is None:
            self._compiler_paths = self._resolve_compiler_paths(compiler_paths, compiler_directory)
            # Preserve the existing generic discovery and fallback behavior.
            self._compiler_status = self.check_compiler_availability()
            self._handler = self._select_handler(compiler_name)
        else:
            # Package providers have no executable probes; empty reports mean unperformed discovery.
            self._compiler_paths = dict()
            self._compiler_status = dict()
            self._handler = compiler_handler if compiler_handler.setup_valid else None
        self._selected_compiler: CompilerName | None = self._identify_handler(self._handler)
        self._compiled_library_path: str | None = None
        # Detection is observable through Logger; no aggregate report object is required.
        if compiler_handler is None:
            self._log_detection_info()
        else:
            self.logger.add_info("Explicit compiler provider selected", value=str(compiler_handler.get_native_framework()))

    def _log_detection_info(self) -> None:
        """Write the complete detection state to the coordinator logger.

        :return: None.
        """
        # Emit scalar entries so Logger remains searchable and does not receive nested dictionaries.
        self.logger.add_info("Operating system detected", value=self._operating_system)
        for compiler_type in CompilerName:
            # Report the resolved executable independently from its availability result.
            compiler_path: str | None = self._compiler_paths[compiler_type]
            path_value: str = compiler_path if compiler_path is not None else "Unavailable"
            self.logger.add_info("Compiler path", device=compiler_type.value, value=path_value)

            compiler_status: dict[str, Any] | None = self._compiler_status.get(compiler_type)
            # Unsupported or absent compilers get an explicit status instead of disappearing silently.
            if compiler_status is None:
                self.logger.add_info(
                    "Compiler availability",
                    device=compiler_type.value,
                    value="Not detected",
                )
            else:
                availability: str = "Available" if compiler_status.get("available") is True else "Unavailable"
                output: str = str(compiler_status.get("stdout", ""))
                error_output: str = str(compiler_status.get("stderr", ""))
                comment: str = f"stdout: {output}; stderr: {error_output}"
                self.logger.add_info(
                    "Compiler availability",
                    device=compiler_type.value,
                    value=availability,
                    comment=comment,
                )

        requested_compiler: str | None = (
            self._requested_compiler.value if self._requested_compiler is not None else None
        )
        selected_compiler: str | None = (
            self._selected_compiler.value if self._selected_compiler is not None else None
        )
        requested_value: str = requested_compiler if requested_compiler is not None else "Automatic selection"
        selected_value: str = selected_compiler if selected_compiler is not None else "None available"
        self.logger.add_info("Requested compiler", value=requested_value)
        self.logger.add_info("Selected compiler", value=selected_value)

    def _resolve_compiler_paths(
            self,
            compiler_paths: dict[CompilerName, str] | None,
            compiler_directory: str | None,
    ) -> dict[CompilerName, str | None]:
        """Resolve explicit compiler paths, a search directory, or system PATH.

        :param compiler_paths: Explicit executable paths by compiler enum.
        :param compiler_directory: Optional directory searched before PATH.
        :return: Resolved executable paths for all compiler types.
        """
        paths: dict[CompilerName, str | None] = dict()
        if compiler_directory is not None and not os.path.isdir(compiler_directory):
            self.logger.add_warning(f"Compiler search directory does not exist: {compiler_directory}")
        else:
            pass
        executable_names: dict[CompilerName, str] = dict()
        executable_names[CompilerName.GCC] = "gcc"
        executable_names[CompilerName.CLANG] = "clang"
        executable_names[CompilerName.MSVC] = "cl.exe"
        for compiler_type, executable_name in executable_names.items():
            # An explicit path is authoritative; otherwise search the requested directory and then PATH.
            explicit_path: str | None = compiler_paths.get(compiler_type) if compiler_paths is not None else None
            if explicit_path is not None:
                if os.path.isfile(explicit_path):
                    paths[compiler_type] = os.path.abspath(explicit_path)
                else:
                    self.logger.add_warning(f"Configured compiler path does not exist: {explicit_path}")
                    paths[compiler_type] = None
            else:
                paths[compiler_type] = shutil.which(executable_name, path=compiler_directory)
        return paths

    def _select_handler(self, compiler_name: CompilerName | None) -> CompilerInterface | None:
        """Select an available handler for the configured operating system.

        :param compiler_name: Optional explicitly requested compiler.
        :return: Selected compiler handler, or ``None`` when unavailable.
        """
        if compiler_name is not None:
            # Honor the caller's requested enum only when its probe succeeded.
            if self._is_available(compiler_name):
                requested_handler: CompilerInterface | None = self._create_handler(compiler_name)
                if requested_handler is not None:
                    return requested_handler
                else:
                    return self._select_preferred_handler()
            else:
                # A missing or invalid request must not make the coordinator unusable.
                return self._select_preferred_handler()
        else:
            return self._select_preferred_handler()

    def _create_handler(self, compiler_name: CompilerName) -> CompilerInterface | None:
        """Create a handler when the requested compiler is supported.

        :param compiler_name: Compiler enum identifying the requested handler.
        :return: Initialized compiler handler, or ``None`` when unsupported.
        """
        try:
            # Handlers own compiler-specific commands, while this factory injects shared logger/path state.
            if compiler_name == CompilerName.GCC:
                return GCCHandler(self.logger, self._compiler_paths[CompilerName.GCC])
            else:
                if compiler_name == CompilerName.CLANG:
                    return ClangHandler(self.logger, self._compiler_paths[CompilerName.CLANG])
                else:
                    if compiler_name == CompilerName.MSVC:
                        return MSVCHandler(self.logger, self._compiler_paths[CompilerName.MSVC])
                    else:
                        return None
        except (EnvironmentError, OSError, subprocess.CalledProcessError) as error:
            self.logger.add_error(f"Could not initialize {compiler_name.value}: {error}")
            return None

    def _is_available(self, compiler_name: CompilerName) -> bool:
        """Return whether a detected compiler is available.

        :param compiler_name: Compiler to inspect.
        :return: ``True`` when the compiler probe succeeded.
        """
        compiler_status: dict[str, Any] | None = self._compiler_status.get(compiler_name)
        if compiler_status is None:
            return False
        else:
            return compiler_status.get("available") is True

    def _identify_handler(self, handler: CompilerInterface | None) -> CompilerName | None:
        """Identify a selected handler without runtime attribute inspection.

        :param handler: Selected handler.
        :return: Matching compiler enum, or ``None``.
        """
        if isinstance(handler, MSVCHandler):
            return CompilerName.MSVC
        else:
            if isinstance(handler, ClangHandler):
                return CompilerName.CLANG
            else:
                if isinstance(handler, GCCHandler):
                    return CompilerName.GCC
                else:
                    return None

    def _select_preferred_handler(self) -> CompilerInterface | None:
        """Select the primary compiler or its configured fallback.

        :return: Selected compiler handler, or ``None`` when unavailable.
        """
        status: dict[CompilerName, dict[str, Any]] = self._compiler_status
        compiler_order: tuple[CompilerName, ...] = self._get_compiler_order()
        # The first enum is the platform default; later enums are ordered fallbacks.
        if not compiler_order:
            return None
        else:
            primary: dict[str, Any] | None = status.get(compiler_order[0])
        primary_available: bool = primary is not None and primary.get("available") is True
        if primary_available:
            primary_handler: CompilerInterface | None = self._create_handler(compiler_order[0])
            if primary_handler is not None:
                return primary_handler
            else:
                return self._select_alternative_handler(status)
        else:
            return self._select_alternative_handler(status)

    def _select_alternative_handler(self, status: dict[CompilerName, dict[str, Any]]) -> CompilerInterface | None:
        """Select a configured fallback compiler after primary detection fails.

        :param status: Compiler availability report.
        :return: Fallback compiler handler, or ``None`` when unavailable.
        """
        compiler_order: tuple[CompilerName, ...] = self._get_compiler_order()
        for alternative_handler in compiler_order[1:]:
            # Try fallbacks in declared order and continue if handler initialization also fails.
            alternative_status: dict[str, Any] | None = status.get(alternative_handler)
            if alternative_status is not None and alternative_status.get("available") is True:
                selected_handler: CompilerInterface | None = self._create_handler(alternative_handler)
                if selected_handler is not None:
                    return selected_handler
                else:
                    pass
            else:
                pass
        return None

    @staticmethod
    def detect_os() -> str:
        """Return the coordinator's detected operating-system identifier.

        :return: Lowercase operating-system identifier.
        """
        return platform.system().lower()

    def check_compiler_availability(self) -> dict[CompilerName, dict[str, Any]]:
        """Check compiler availability for the coordinator's operating system.

        :return: Compiler availability report.
        """
        compiler_order: tuple[CompilerName, ...] = self._get_compiler_order()
        if not compiler_order:
            message: str = f"Unsupported operating system: {self._operating_system}"
            self.logger.add_error(message)
            return dict()
        else:
            # Store probe results by enum so selection never depends on operational strings.
            results: dict[CompilerName, dict[str, Any]] = dict()
            primary_type: CompilerName = compiler_order[0]
            results[primary_type] = self._probe_compiler(primary_type)
            for alternative_type in compiler_order[1:]:
                results[alternative_type] = self._probe_compiler(alternative_type)
            return results

    def _get_compiler_order(self) -> tuple[CompilerName, ...]:
        """Return primary and fallback compilers for the detected OS.

        :return: Ordered compiler types, primary first.
        """
        if self._operating_system == OperatingSystem.LINUX.value:
            return (CompilerName.GCC, CompilerName.CLANG)
        else:
            if self._operating_system == OperatingSystem.MACOS.value:
                return (CompilerName.CLANG, CompilerName.GCC)
            else:
                if self._operating_system == OperatingSystem.WINDOWS.value:
                    return (CompilerName.MSVC, CompilerName.CLANG, CompilerName.GCC)
                else:
                    return tuple()

    def _probe_compiler(self, compiler_type: CompilerName) -> dict[str, Any]:
        """Probe one resolved compiler executable and log its failures.

        :param compiler_type: Compiler being probed.
        :return: Probe result containing availability and compiler name.
        """
        executable_path: str | None = self._compiler_paths[compiler_type]
        # Keep the path and command output together for diagnostics and later handler selection.
        result: dict[str, Any] = {
            "available": False,
            "name": compiler_type.value,
            "path": executable_path,
        }
        if executable_path is None:
            self.logger.add_warning(f"Compiler executable is unavailable: {compiler_type.value}")
            return result
        else:
            arguments: list[str] = ["/?"] if compiler_type == CompilerName.MSVC else ["--version"]
            command: list[str] = [executable_path] + arguments
            # A successful version/help command proves that this exact executable is invocable.
            try:
                completed_process: subprocess.CompletedProcess[str] = subprocess.run(
                    command, capture_output=True, text=True, errors="replace", check=True
                )
                result["available"] = True
                result["stdout"] = completed_process.stdout.strip()
                return result
            except FileNotFoundError as error:
                self.logger.add_warning(f"Compiler probe not found: {command}; {error}")
                return result
            except subprocess.CalledProcessError as error:
                stdout: str = str(error.stdout).strip()
                stderr: str = str(error.stderr).strip()
                result["stdout"] = stdout
                result["stderr"] = stderr
                self.logger.add_error(
                    f"Compiler probe failed: {command}; stdout={stdout}; stderr={stderr}"
                )
                return result

    def get_handler(self) -> CompilerInterface | None:
        """Return the selected compiler handler.

        :return: GCC, Clang, MSVC, or ``None``.
        """
        return self._handler

    def get_requested_compiler(self) -> CompilerName | None:
        """Return the compiler requested during construction.

        :return: Requested compiler enum, or ``None`` for automatic selection.
        """
        return self._requested_compiler

    def get_selected_compiler(self) -> CompilerName | None:
        """Return the compiler actually selected after detection.

        :return: Selected compiler enum, or ``None`` when unavailable.
        """
        return self._selected_compiler

    def get_operating_system(self) -> str:
        """Return the detected operating-system identifier.

        :return: Lowercase operating-system identifier.
        """
        return self._operating_system

    def get_compiler_status(self) -> dict[CompilerName, dict[str, Any]]:
        """Return the stored compiler availability report.

        :return: Availability report captured during construction.
        """
        return self._compiler_status

    def get_compiler_paths(self) -> dict[CompilerName, str | None]:
        """Return the resolved executable path for each compiler type.

        :return: Compiler executable paths, including unavailable entries as ``None``.
        """
        return self._compiler_paths

    def _move_compiled_library(self, library_path: str, final_destination: str, output_dir: str) -> str | None:
        """Move a compiled library outside the build directory.

        :param library_path: Path returned by the selected handler.
        :param final_destination: Final library path or existing directory.
        :param output_dir: Build directory used to reject self-destinations.
        :return: Final library path, or ``None`` on failure.
        """
        build_path: str = os.path.abspath(output_dir)
        destination_path: str = os.path.abspath(final_destination)
        # Reject destinations inside the build tree because cleanup would delete the final artifact.
        try:
            common_path: str = os.path.commonpath([build_path, destination_path])
        except ValueError as error:
            self.logger.add_error(f"Could not compare build and final paths: {error}")
            return None
        if common_path == build_path:
            message: str = "final_destination must be outside output_dir"
            self.logger.add_error(message)
            return None
        else:
            # Existing directories receive the generated filename; other paths are treated as filenames.
            if os.path.isdir(final_destination):
                destination_path = os.path.join(final_destination, os.path.basename(library_path))
            else:
                destination_parent: str = os.path.dirname(destination_path)
                if destination_parent:
                    try:
                        os.makedirs(destination_parent, exist_ok=True)
                    except OSError as error:
                        self.logger.add_error(str(error))
                        return None
                else:
                    pass
            # Move rather than copy so clean_after_build can remove all temporary build products.
            try:
                shutil.move(library_path, destination_path)
            except OSError as error:
                self.logger.add_error(str(error))
                return None
            if os.path.isfile(destination_path):
                return destination_path
            else:
                self.logger.add_error(
                    f"Compiled library is missing from final destination: {destination_path}"
                )
                return None

    def _clean_build_directory(self, output_dir: str) -> bool:
        """Remove the build directory after its output has been preserved.

        :param output_dir: Build directory to remove.
        :return: ``True`` when the build directory is removed or absent.
        """
        if os.path.isdir(output_dir):
            # Cleanup occurs only after the final artifact has been moved outside this directory.
            try:
                shutil.rmtree(output_dir)
            except OSError as error:
                self.logger.add_error(str(error))
                return False
            if os.path.exists(output_dir):
                self.logger.add_error(f"Build directory still exists after cleanup: {output_dir}")
                return False
            else:
                return True
        else:
            return True

    def compile(
            self,
            source_files: list[str],
            output_dir: str,
            lib_name: str = "",
            final_destination: str = "",
            clean_after_build: bool = False,
            include_directories: list[str] | None = None,
    ) -> bool:
        """Compile through the selected handler.

        :param source_files: Source files to compile.
        :param output_dir: Directory for compiler output.
        :param lib_name: Optional shared-library filename.
        :param final_destination: Optional final library path or existing directory.
        :param clean_after_build: Remove ``output_dir`` after preserving the library.
        :param include_directories: Header search directories.
        :return: ``True`` when compilation and requested file operations succeed.
        """
        self._compiled_library_path = None
        # Reset the previous result so callers never mistake an old artifact for this build's result.
        if clean_after_build and not final_destination:
            message: str = "clean_after_build requires final_destination"
            self.logger.add_error(message)
            return False
        else:
            if self._handler is None:
                # No handler means compilation is unavailable, but it is still a normal managed outcome.
                self.logger.add_error("Compilation requested but no compiler handler is available")
                return False
            else:
                try:
                    # Build into the temporary directory first; finalization is handled below.
                    if lib_name:
                        library_path: str = self._handler.compile(
                            source_files, output_dir, lib_name, include_directories
                        )
                    else:
                        library_path = self._handler.compile(
                            source_files, output_dir, include_directories=include_directories
                        )

                    if final_destination:
                        # Preserve the library before optional cleanup removes the build directory.
                        moved_library_path: str | None = self._move_compiled_library(
                            library_path, final_destination, output_dir
                        )
                        if moved_library_path is None:
                            return False
                        else:
                            result_path: str = moved_library_path
                    else:
                        result_path = library_path

                    if clean_after_build:
                        # Cleanup is part of success: a failed cleanup returns False and is logged.
                        cleanup_succeeded: bool = self._clean_build_directory(output_dir)
                        if not cleanup_succeeded:
                            return False
                        else:
                            pass
                    else:
                        pass
                    if result_path is None or not result_path:
                        self.logger.add_error("Compilation did not produce a final library path")
                        return False
                    else:
                        pass
                    self._compiled_library_path = result_path
                    return True
                except Exception as error:
                    self.logger.add_error(f"Compilation failed: {error}")
                    return False

    def get_compiled_library_path(self) -> str | None:
        """Return the path produced by the last successful compilation.

        :return: Final library path, or ``None`` when the last compilation failed.
        """
        return self._compiled_library_path

    def test_compiler(self) -> bool:
        """Run the selected handler's compiler smoke test.

        :return: ``True`` when compilation succeeds; otherwise ``False``.
        """
        if self._handler is None:
            self.logger.add_error("Compiler smoke test requested but no handler is available")
            self.logger.add_info("Compiler smoke test", value="Failed")
            return False
        else:
            source_name: str = "test.c"
            build_directory: str = "build"
            compilation_succeeded: bool = False
            library_exists: bool = False
            try:
                # Create a minimal source file that exercises the complete compiler path.
                with open(source_name, "w") as source_file:
                    source_file.write("int main() { return 0; }")
                compilation_succeeded = self.compile([source_name], build_directory)
                compiled_library_path: str | None = self.get_compiled_library_path()
                # Check the artifact before deleting the temporary build output.
                library_exists = (
                    compilation_succeeded
                    and compiled_library_path is not None
                    and os.path.isfile(compiled_library_path)
                )
            except Exception as error:
                self.logger.add_error(f"Compiler smoke test failed: {error}")

            # The smoke test owns these temporary files and must leave no build residue.
            build_cleanup_succeeded: bool = self._clean_build_directory(build_directory)
            source_cleanup_succeeded: bool = True
            if os.path.exists(source_name):
                try:
                    os.remove(source_name)
                except OSError as error:
                    self.logger.add_error(f"Could not remove smoke-test source: {error}")
                    source_cleanup_succeeded = False
            else:
                pass

            smoke_test_succeeded: bool = (
                compilation_succeeded
                and library_exists
                and build_cleanup_succeeded
                and source_cleanup_succeeded
            )
            outcome: str = "Succeeded" if smoke_test_succeeded else "Failed"
            self.logger.add_info("Compiler smoke test", value=outcome)
            return smoke_test_succeeded


def get_compiler(compiler_name: str) -> CompilerInterface | None:
    """Instantiate a compiler handler for the current operating system.

    :param compiler_name: Compiler name such as ``gcc`` or ``clang``.
    :return: Initialized compiler handler, or ``None`` when unavailable.
    """
    try:
        requested_name: CompilerName = CompilerName(compiler_name.lower())
    except ValueError:
        return None
    coordinator: Compiler = Compiler(requested_name)
    handler: CompilerInterface | None = coordinator.get_handler()
    return handler


def get_preferred_compiler() -> GCCHandler | ClangHandler | MSVCHandler | None:
    """Return the preferred available compiler for the current OS.

    :return: Initialized compiler handler, or ``None`` when unavailable.
    """
    coordinator: Compiler = Compiler()
    handler: CompilerInterface | None = coordinator.get_handler()
    if isinstance(handler, (GCCHandler, ClangHandler, MSVCHandler)):
        return handler
    else:
        return None


if __name__ == "__main__":
    compiler: Compiler = Compiler()
    if compiler.get_handler() is None:
        print("No compiler found.")
    else:
        compiler.test_compiler()
        compiler.logger.print()
