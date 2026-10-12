# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""FMU compilation through the shared VeraGrid compiler interface."""

from __future__ import annotations
from VeraGridEngine.enumerations import FmuBinaryInterface

import ctypes
from pathlib import Path
import platform

from VeraGridEngine.Utils.Compiler.interface import Compiler




def fmu_compiler_available(compiler: Compiler | None = None) -> bool:
    """Return whether the shared compiler coordinator has a usable handler.

    :param compiler: Optional compiler coordinator to inspect.
    :return: ``True`` when a compiler handler is available.
    """

    selected_compiler: Compiler = compiler if compiler is not None else Compiler()
    return selected_compiler.get_handler() is not None


def _required_fmi_symbols(
    interface: FmuBinaryInterface,
    model_identifier: str | None = None,
) -> tuple[str, ...]:
    """Return the required exported symbols for one FMI interface.

    :param interface: FMI binary interface being packaged.
    :param model_identifier: Explicit FMI 1 symbol prefix.
    :return: Immutable required symbol inventory.
    """

    fmi_one_co_simulation: tuple[str, ...] = (
        "fmiGetTypesPlatform", "fmiGetVersion", "fmiSetDebugLogging",
        "fmiInstantiateSlave", "fmiInitializeSlave", "fmiTerminateSlave",
        "fmiResetSlave", "fmiFreeSlaveInstance", "fmiSetReal",
        "fmiSetInteger", "fmiSetBoolean", "fmiSetString", "fmiGetReal",
        "fmiGetInteger", "fmiGetBoolean", "fmiGetString",
        "fmiSetRealInputDerivatives", "fmiGetRealOutputDerivatives",
        "fmiCancelStep", "fmiDoStep", "fmiGetStatus", "fmiGetRealStatus",
        "fmiGetIntegerStatus", "fmiGetBooleanStatus", "fmiGetStringStatus",
    )
    fmi_one_model_exchange: tuple[str, ...] = (
        "fmiGetModelTypesPlatform", "fmiGetVersion", "fmiSetDebugLogging",
        "fmiInstantiateModel", "fmiFreeModelInstance", "fmiSetTime",
        "fmiSetContinuousStates", "fmiCompletedIntegratorStep", "fmiSetReal",
        "fmiSetInteger", "fmiSetBoolean", "fmiSetString", "fmiGetReal",
        "fmiGetInteger", "fmiGetBoolean", "fmiGetString", "fmiInitialize",
        "fmiGetDerivatives", "fmiGetEventIndicators", "fmiEventUpdate",
        "fmiGetContinuousStates", "fmiGetNominalContinuousStates",
        "fmiGetStateValueReferences", "fmiTerminate",
    )
    if interface in (FmuBinaryInterface.FMI_ONE_CO_SIMULATION, FmuBinaryInterface.FMI_ONE_MODEL_EXCHANGE):
        if model_identifier is None or len(model_identifier) == 0:
            raise ValueError("FMI 1 symbol validation requires an explicit model identifier")
        suffixes: tuple[str, ...] = (
            fmi_one_co_simulation
            if interface == FmuBinaryInterface.FMI_ONE_CO_SIMULATION
            else fmi_one_model_exchange
        )
        return tuple(model_identifier + "_" + suffix for suffix in suffixes)
    fmi_two_common: tuple[str, ...] = (
        "fmi2GetTypesPlatform", "fmi2GetVersion", "fmi2SetDebugLogging", "fmi2Instantiate",
        "fmi2FreeInstance", "fmi2SetupExperiment", "fmi2EnterInitializationMode",
        "fmi2ExitInitializationMode", "fmi2Terminate", "fmi2Reset", "fmi2GetReal",
        "fmi2GetInteger", "fmi2GetBoolean", "fmi2GetString", "fmi2SetReal", "fmi2SetInteger",
        "fmi2SetBoolean", "fmi2SetString", "fmi2GetFMUstate", "fmi2SetFMUstate",
        "fmi2FreeFMUstate", "fmi2SerializedFMUstateSize", "fmi2SerializeFMUstate",
        "fmi2DeSerializeFMUstate", "fmi2GetDirectionalDerivative",
    )
    if interface == FmuBinaryInterface.FMI_TWO_CO_SIMULATION:
        return fmi_two_common + (
            "fmi2SetRealInputDerivatives", "fmi2GetRealOutputDerivatives", "fmi2DoStep",
            "fmi2CancelStep", "fmi2GetStatus", "fmi2GetRealStatus", "fmi2GetIntegerStatus",
            "fmi2GetBooleanStatus", "fmi2GetStringStatus",
        )
    if interface == FmuBinaryInterface.FMI_TWO_MODEL_EXCHANGE:
        return fmi_two_common + (
            "fmi2EnterEventMode", "fmi2NewDiscreteStates", "fmi2EnterContinuousTimeMode",
            "fmi2CompletedIntegratorStep", "fmi2SetTime", "fmi2SetContinuousStates",
            "fmi2GetDerivatives", "fmi2GetEventIndicators", "fmi2GetContinuousStates",
            "fmi2GetNominalsOfContinuousStates",
        )
    if interface in (FmuBinaryInterface.FMI_THREE_CO_SIMULATION, FmuBinaryInterface.FMI_THREE_MODEL_EXCHANGE):
        return (
            "fmi3GetVersion", "fmi3SetDebugLogging", "fmi3InstantiateModelExchange",
            "fmi3InstantiateCoSimulation", "fmi3InstantiateScheduledExecution", "fmi3FreeInstance",
            "fmi3EnterInitializationMode", "fmi3ExitInitializationMode", "fmi3EnterEventMode",
            "fmi3Terminate", "fmi3Reset", "fmi3GetFloat32", "fmi3GetFloat64", "fmi3GetInt8",
            "fmi3GetUInt8", "fmi3GetInt16", "fmi3GetUInt16", "fmi3GetInt32", "fmi3GetUInt32",
            "fmi3GetInt64", "fmi3GetUInt64", "fmi3GetBoolean", "fmi3GetString", "fmi3GetBinary",
            "fmi3GetClock", "fmi3SetFloat32", "fmi3SetFloat64", "fmi3SetInt8", "fmi3SetUInt8",
            "fmi3SetInt16", "fmi3SetUInt16", "fmi3SetInt32", "fmi3SetUInt32", "fmi3SetInt64",
            "fmi3SetUInt64", "fmi3SetBoolean", "fmi3SetString", "fmi3SetBinary", "fmi3SetClock",
            "fmi3GetNumberOfVariableDependencies", "fmi3GetVariableDependencies", "fmi3GetFMUState",
            "fmi3SetFMUState", "fmi3FreeFMUState", "fmi3SerializedFMUStateSize",
            "fmi3SerializeFMUState", "fmi3DeserializeFMUState", "fmi3GetDirectionalDerivative",
            "fmi3GetAdjointDerivative", "fmi3EnterConfigurationMode", "fmi3ExitConfigurationMode",
            "fmi3GetIntervalDecimal", "fmi3GetIntervalFraction", "fmi3GetShiftDecimal",
            "fmi3GetShiftFraction", "fmi3SetIntervalDecimal", "fmi3SetIntervalFraction",
            "fmi3SetShiftDecimal", "fmi3SetShiftFraction", "fmi3EvaluateDiscreteStates",
            "fmi3UpdateDiscreteStates", "fmi3EnterContinuousTimeMode", "fmi3CompletedIntegratorStep",
            "fmi3SetTime", "fmi3SetContinuousStates", "fmi3GetContinuousStateDerivatives",
            "fmi3GetEventIndicators", "fmi3GetContinuousStates", "fmi3GetNominalsOfContinuousStates",
            "fmi3GetNumberOfEventIndicators", "fmi3GetNumberOfContinuousStates", "fmi3EnterStepMode",
            "fmi3GetOutputDerivatives", "fmi3DoStep", "fmi3ActivateModelPartition",
        )
    raise RuntimeError("The FMI binary interface is unsupported")


def _missing_exported_symbols(
    symbol_text: str,
    interface: FmuBinaryInterface,
    package_platform: str,
    model_identifier: str | None = None,
) -> tuple[str, ...]:
    """Return required symbols absent from a native symbol inventory.

    :param symbol_text: Whitespace-separated native symbol inventory.
    :param interface: FMI binary interface being packaged.
    :param package_platform: Native package platform.
    :param model_identifier: Explicit FMI 1 symbol prefix.
    :return: Missing required symbols.
    """

    exported_symbols: set[str] = set()
    for output_line in symbol_text.splitlines():
        fields: list[str] = output_line.split()
        if len(fields) > 0:
            symbol_name: str = fields[0]
            if package_platform == "darwin" and symbol_name.startswith("_"):
                symbol_name = symbol_name[1:]
            exported_symbols.add(symbol_name)
        else:
            pass
    return tuple(
        symbol
        for symbol in _required_fmi_symbols(interface, model_identifier)
        if symbol not in exported_symbols
    )


def _binary_header_matches(header_text: str, package_platform: str, package_arch: str) -> bool:
    """Return whether native inspection text matches the requested platform.

    :param header_text: Native binary inspection output.
    :param package_platform: Normalized platform name.
    :param package_arch: Normalized architecture name.
    :return: ``True`` when the format and architecture match.
    """

    normalized_text: str = header_text.lower()
    if package_platform == "linux":
        return "elf64-x86-64" in normalized_text and package_arch == "x86_64"
    if package_platform == "win":
        return "coff-x86-64" in normalized_text and package_arch in ("x86_64", "mingw-x86_64")
    if package_platform == "darwin":
        return package_arch in normalized_text and "mach-o" in normalized_text
    return False


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


def _validate_loaded_symbols(
    library_path: Path,
    interface: FmuBinaryInterface,
    model_identifier: str | None,
) -> None:
    """Validate required FMI symbols through the native loader.

    :param library_path: Compiled shared-library path.
    :param interface: FMI interface being validated.
    :param model_identifier: Explicit FMI 1 symbol prefix.
    :return: None.
    """

    native_library: ctypes.CDLL = ctypes.CDLL(str(library_path))
    missing_symbols: list[str] = list()
    for symbol in _required_fmi_symbols(interface, model_identifier):
        try:
            native_library[symbol]
        except (AttributeError, KeyError):
            missing_symbols.append(symbol)
    if len(missing_symbols) == 0:
        pass
    else:
        raise RuntimeError("The FMU binary is missing required symbols: " + ", ".join(missing_symbols))


def compile_fmu_shared_library(
    source_files: tuple[Path, ...],
    include_directories: tuple[Path, ...],
    output_path: Path,
    interface: FmuBinaryInterface,
    model_identifier: str | None = None,
    compiler: Compiler | None = None,
) -> Path:
    """Compile one host-native FMI shared library.

    :param source_files: Generated C translation units.
    :param include_directories: Header search directories.
    :param output_path: Destination shared-library path.
    :param interface: FMI interface being compiled.
    :param model_identifier: Explicit FMI 1 symbol prefix.
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
    selected_compiler: Compiler = compiler if compiler is not None else Compiler()
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
    _validate_loaded_symbols(output_path, interface, model_identifier)
    return output_path
