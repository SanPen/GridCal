# SPDX-License-Identifier: MPL-2.0
"""Standalone CON reader; grammar and typed objects live in versioned/."""
from pathlib import Path

from VeraGridEngine.IO.raw.psse_auxiliary import (
    AuxiliaryFormat, BusInputMode, PsseAuxiliaryFile, PsseVersion,
    parse_command_file, read_auxiliary_text,
)
from VeraGridEngine.IO.raw.versioned.base.con_ import RawCon
from VeraGridEngine.IO.raw.versioned.v33.con_ import RawConV33
from VeraGridEngine.IO.raw.versioned.v34.con_ import RawConV34
from VeraGridEngine.IO.raw.versioned.v35.con_ import RawConV35
from VeraGridEngine.IO.raw.versioned.v36.con_ import RawConV36


def parse_con(text: str, source: str = '<con>',
                bus_mode: BusInputMode = BusInputMode.NUMBERS,
                version: int | PsseVersion = PsseVersion.V36) -> RawCon:
    """Tokenize once and dispatch to the explicitly selected version grammar.

    :param text: Complete CON input.
    :param source: Diagnostic source label.
    :param bus_mode: Initial bus reference mode.
    :param version: PSS/E major version, 33 through 36.
    :return: Concrete version object, retaining syntax and typed definitions.
    """
    syntax: PsseAuxiliaryFile = parse_command_file(text, AuxiliaryFormat.CON, source, bus_mode, version)
    result: RawCon
    if syntax.version == PsseVersion.V33:
        result = RawConV33(source, bus_mode)
    elif syntax.version == PsseVersion.V34:
        result = RawConV34(source, bus_mode)
    elif syntax.version == PsseVersion.V35:
        result = RawConV35(source, bus_mode)
    elif syntax.version == PsseVersion.V36:
        result = RawConV36(source, bus_mode)
    else:
        result = RawCon(source, bus_mode, version)
    if syntax.version is not None:
        result.parse(syntax)
    else:
        result.logger = syntax.logger
    return result


def read_con(file_name: str | Path, bus_mode: BusInputMode = BusInputMode.NUMBERS,
               version: int | PsseVersion = PsseVersion.V36) -> RawCon:
    """Read an encoded auxiliary file without changing any network objects.

    :param file_name: Input path.
    :param bus_mode: Initial bus reference mode.
    :param version: PSS/E major version, 33 through 36.
    :return: Version-specific typed CON data and diagnostics.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_con(text, source=str(file_name), bus_mode=bus_mode, version=version)
