# SPDX-License-Identifier: MPL-2.0
"""Standalone SUB reader; grammar and typed objects live in versioned/."""
from pathlib import Path

from VeraGridEngine.IO.raw.psse_auxiliary import (
    AuxiliaryFormat, BusInputMode, PsseAuxiliaryFile, PsseVersion,
    parse_command_file, read_auxiliary_text,
)
from VeraGridEngine.IO.raw.versioned.base.sub import RawSub
from VeraGridEngine.IO.raw.versioned.v33.sub import RawSubV33
from VeraGridEngine.IO.raw.versioned.v34.sub import RawSubV34
from VeraGridEngine.IO.raw.versioned.v35.sub import RawSubV35
from VeraGridEngine.IO.raw.versioned.v36.sub import RawSubV36


def parse_sub(text: str, source: str = '<sub>',
                bus_mode: BusInputMode = BusInputMode.NUMBERS,
                version: int | PsseVersion = PsseVersion.V36) -> RawSub:
    """Tokenize once and dispatch to the explicitly selected version grammar.

    :param text: Complete SUB input.
    :param source: Diagnostic source label.
    :param bus_mode: Initial bus reference mode.
    :param version: PSS/E major version, 33 through 36.
    :return: Concrete version object, retaining syntax and typed definitions.
    """
    syntax: PsseAuxiliaryFile = parse_command_file(text, AuxiliaryFormat.SUB, source, bus_mode, version)
    result: RawSub
    if syntax.version == PsseVersion.V33:
        result = RawSubV33(source, bus_mode)
    elif syntax.version == PsseVersion.V34:
        result = RawSubV34(source, bus_mode)
    elif syntax.version == PsseVersion.V35:
        result = RawSubV35(source, bus_mode)
    elif syntax.version == PsseVersion.V36:
        result = RawSubV36(source, bus_mode)
    else:
        result = RawSub(source, bus_mode, version)
    if syntax.version is not None:
        result.parse(syntax)
    else:
        result.logger = syntax.logger
    return result


def read_sub(file_name: str | Path, bus_mode: BusInputMode = BusInputMode.NUMBERS,
               version: int | PsseVersion = PsseVersion.V36) -> RawSub:
    """Read an encoded auxiliary file without changing any network objects.

    :param file_name: Input path.
    :param bus_mode: Initial bus reference mode.
    :param version: PSS/E major version, 33 through 36.
    :return: Version-specific typed SUB data and diagnostics.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_sub(text, source=str(file_name), bus_mode=bus_mode, version=version)
