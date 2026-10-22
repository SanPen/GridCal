# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Syntax objects shared by the standalone PSS/E auxiliary-file readers.

This module only frames records and preserves source context. Typed grammar
and version capabilities belong to versioned/base and versioned/v33-v36.
Arguments retain their spelling and quoting so model/device identifiers are not
confused with numbers. DataFormats chapter 12 defines the base command language.

Version references: POM 33.10 sections 8.1.1-8.1.4; CheatSheets 35.2
SUB/MON/CON; ReleaseNotes 35.2 pages 9-11; DataFormats 36.5 chapter 12.
Version 34 shares the legacy grammar; its local DataFormats manual covers RAW
and SEQ, not auxiliary commands. Only documented feature boundaries are checked.
Major version 35 includes the 35.2 additions; minor releases are not selected.

PsseCircuit owns complete versioned documents in registered *_files collections.
PsseProperty.file_type distinguishes these from RAWX network sections, which
remain the only properties returned by get_rawx_properties/get_rawx_dict.
Circuit loading passes each file's final bus_mode to the next command reader.
Reference resolution and applying file defaults remain separate from ownership.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Utils.charatcter_detection import detect_character_encoding


class BusInputMode(Enum):
    """Interpretation of bus identifiers at the point a record is read."""

    NUMBERS = "BUSNUMBERS"
    NAMES = "BUSNAMES"


class AuxiliaryFormat(Enum):
    """Supported command-file grammars."""

    SUB = "sub"
    MON = "mon"
    CON = "con"


class PsseVersion(Enum):
    """Supported major versions of the auxiliary-file syntax."""

    V33 = 33
    V34 = 34
    V35 = 35
    V36 = 36


def resolve_psse_version(version: int | PsseVersion, logger: Logger, source: str) -> PsseVersion | None:
    """Validate an explicit version without silently substituting another one.

    :param version: Major version number or enum.
    :param logger: Destination for unsupported-version errors.
    :param source: Diagnostic source label.
    :return: Supported version, or None when parsing must not proceed.
    """
    if isinstance(version, PsseVersion):
        return version
    else:
        versions: dict[int, PsseVersion] = dict((item.value, item) for item in PsseVersion)
        resolved: PsseVersion | None = versions.get(version, None)
        if resolved is None:
            logger.add_error('Unsupported PSS/E version; expected 33, 34, 35 or 36',
                             device=source, value=version)
        else:
            pass
        return resolved


class PsseCommand(Enum):
    """Command families; aliases are normalized without changing arguments."""

    SUBSYSTEM = "SUBSYSTEM"
    JOIN = "JOIN"
    PARTICIPATE = "PARTICIPATE"
    BUS = "BUS"
    BUSES = "BUSES"
    AREA = "AREA"
    AREAS = "AREAS"
    ZONE = "ZONE"
    ZONES = "ZONES"
    OWNER = "OWNER"
    OWNERS = "OWNERS"
    KV = "KV"
    KVRANGE = "KVRANGE"
    SKIP = "SKIP"
    BRANCH = "BRANCH"
    BRANCHES = "BRANCHES"
    ALL = "ALL"
    TIES = "TIES"
    INTERFACE = "INTERFACE"
    VOLTAGE = "VOLTAGE"
    BREAKER = "BREAKER"
    BREAKERS = "BREAKERS"
    SWITCH = "SWITCH"
    SWITCHES = "SWITCHES"
    SWD = "SWD"
    SWDS = "SWDS"
    CONTINGENCY = "CONTINGENCY"
    CATEGORY = "CATEGORY"
    VALUE = "VALUE"
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    BLOCK = "BLOCK"
    UNBLOCK = "UNBLOCK"
    SET = "SET"
    CHANGE = "CHANGE"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    REMOVE = "REMOVE"
    ADD = "ADD"
    MOVE = "MOVE"
    ISOLATE = "ISOLATE"
    STUCK = "STUCK"
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    BUSDOUBLE = "BUSDOUBLE"
    PARALLEL = "PARALLEL"
    DISPATCH = "DISPATCH"
    BUSNAMES = "BUSNAMES"
    BUSNUMBERS = "BUSNUMBERS"
    TRACE = "TRACE"
    ECHO = "ECHO"
    INCLUDE = "INCLUDE"
    MEMBER = "MEMBER"
    UNKNOWN = "UNKNOWN"


class PsseToken:
    """A field with its original spelling and whether it was quoted."""

    __slots__ = ("text", "quoted")

    def __init__(self, text: str, quoted: bool = False) -> None:
        """Initialize a field.

        :param text: Unescaped field contents.
        :param quoted: Whether the input field used quotes.
        """
        self.text: str = text
        self.quoted: bool = quoted


class PsseRecord:
    """A command or block, retaining source context and ordered children."""

    __slots__ = ("command", "tokens", "children", "line_number", "bus_mode", "valid")

    def __init__(self, command: PsseCommand, tokens: tuple[PsseToken, ...],
                 line_number: int, bus_mode: BusInputMode) -> None:
        """Initialize a syntax record.

        :param command: Normalized command family.
        :param tokens: Full record tokens, including the original keywords.
        :param line_number: One-based source line.
        :param bus_mode: Effective identifier interpretation.
        """
        self.command: PsseCommand = command
        self.tokens: tuple[PsseToken, ...] = tokens
        self.children: tuple[PsseRecord, ...] = ()
        self.line_number: int = line_number
        self.bus_mode: BusInputMode = bus_mode
        self.valid: bool = True


class PsseAuxiliaryFile:
    """Parsed syntax and diagnostics; network-dependent expansion is deferred."""

    __slots__ = ("records", "logger", "bus_mode", "source", "version")

    def __init__(self, source: str, bus_mode: BusInputMode,
                 version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize an independent parse result.

        :param source: Filename or diagnostic source label.
        :param bus_mode: Initial bus input mode.
        :param version: Explicit major version; auxiliary files have no version header.
        """
        self.records: tuple[PsseRecord, ...] = ()
        self.logger: Logger = Logger()
        self.bus_mode: BusInputMode = bus_mode
        self.source: str = source
        self.version: PsseVersion | None = resolve_psse_version(version, self.logger, source)


def read_auxiliary_text(file_name: str | Path) -> str:
    """Read a PSS/E text file using the existing encoding detector.

    :param file_name: Source path.
    :return: Decoded text.
    """
    encoding: str = detect_character_encoding(source=str(file_name))
    return Path(file_name).read_text(encoding=encoding)


def tokenize_psse(text: str, comma_separated: bool = False) -> tuple[tuple[PsseToken, ...], bool, bool]:
    """Read fields up to an unquoted slash, preserving quoted identifiers.

    :param text: One physical input line.
    :param comma_separated: Accept commas as separators for DYR records.
    :return: Tokens, slash encountered, and whether quoting is balanced.
    """
    tokens: list[PsseToken] = list()
    index: int = 0
    terminated: bool = False
    balanced: bool = True
    comma_seen: bool = False
    field_since_comma: bool = False
    # Slashes in quoted names are data; outside quotes they end the input record.
    while index < len(text) and not terminated:
        character: str = text[index]
        if character.isspace():
            index += 1
        elif comma_separated and character == ',':
            if comma_seen and not field_since_comma:
                tokens.append(PsseToken(''))
            else:
                pass
            comma_seen = True
            field_since_comma = False
            index += 1
        elif character == '/':
            if comma_separated and comma_seen and not field_since_comma:
                tokens.append(PsseToken(''))
            else:
                pass
            terminated = True
        elif character in ("'", '"'):
            quote: str = character
            contents: list[str] = list()
            closed: bool = False
            index += 1
            while index < len(text) and not closed:
                if text[index] == quote:
                    if index + 1 < len(text) and text[index + 1] == quote:
                        contents.append(quote)
                        index += 2
                    else:
                        closed = True
                        index += 1
                else:
                    contents.append(text[index])
                    index += 1
            tokens.append(PsseToken(''.join(contents), quoted=True))
            field_since_comma = True
            # Adjacent unquoted text cannot silently become another field.
            separated: bool = (index == len(text) or text[index].isspace()
                               or text[index] == '/' or (comma_separated and text[index] == ','))
            balanced = balanced and closed and separated
        else:
            start: int = index
            while (index < len(text) and not text[index].isspace()
                   and text[index] != '/' and not (comma_separated and text[index] == ',')):
                index += 1
            tokens.append(PsseToken(text[start:index]))
            field_since_comma = True
    return tuple(tokens), terminated, balanced


def identify_command(tokens: tuple[PsseToken, ...]) -> PsseCommand:
    """Normalize command aliases while preserving the original token sequence.

    :param tokens: Nonempty input fields.
    :return: Command family, or UNKNOWN for an extension.
    """
    keyword: str = tokens[0].text.upper() if not tokens[0].quoted else ''
    if keyword == 'MONITOR' and len(tokens) > 1 and not tokens[1].quoted:
        keyword = tokens[1].text.upper()
    else:
        pass
    aliases: dict[str, PsseCommand] = dict(
        SYSTEM=PsseCommand.SUBSYSTEM, LINE=PsseCommand.BRANCH,
        LINES=PsseCommand.BRANCHES, TIE=PsseCommand.TIES,
        TRIP=PsseCommand.OPEN, DISCONNECT=PsseCommand.OPEN,
        ALTER=PsseCommand.CHANGE, MODIFY=PsseCommand.CHANGE,
        RAISE=PsseCommand.INCREASE, REDUCE=PsseCommand.DECREASE)
    command: PsseCommand | None = aliases.get(keyword, None)
    if command is None:
        command = PsseCommand.__members__.get(keyword, PsseCommand.UNKNOWN)
    else:
        pass
    return command


def parse_command_file(text: str, tpe: AuxiliaryFormat, source: str,
                       bus_mode: BusInputMode,
                       version: int | PsseVersion = PsseVersion.V36) -> PsseAuxiliaryFile:
    """Build a syntax tree without resolving selectors against a network case.

    :param text: Complete file contents.
    :param tpe: Command-file grammar.
    :param source: Diagnostic source label.
    :param bus_mode: Initial bus identifier mode, possibly inherited from a file.
    :param version: Major syntax version (33-36); defaults to the existing 36 grammar.
    :return: Ordered records and diagnostics, including incomplete input.
    """
    result: PsseAuxiliaryFile = PsseAuxiliaryFile(source, bus_mode, version)
    if result.version is None:
        return result
    else:
        pass
    roots: list[PsseRecord] = list()
    stack: list[PsseRecord] = list()
    groups: list[list[PsseRecord]] = [roots]
    ended: bool = False
    lines: list[str] = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        tokens: tuple[PsseToken, ...]
        slash: bool
        balanced: bool
        # COM contents are arbitrary prose, including unmatched quotation marks.
        stripped: str = line.lstrip('\ufeff \t')
        if stripped.upper().split(maxsplit=1)[:1] == ['COM']:
            tokens, slash, balanced = (), False, True
        else:
            tokens, slash, balanced = tokenize_psse(stripped)
        if not balanced:
            result.logger.add_error('Unterminated quoted field', device=source, value=line_number)
        else:
            pass
        if len(tokens) == 0:
            pass
        elif ended:
            result.logger.add_warning('Record after end of input', device=source, value=line_number)
        elif not tokens[0].quoted and tokens[0].text.upper() == 'END':
            if len(tokens) != 1:
                result.logger.add_error('END does not accept arguments', device=source, value=line_number)
            else:
                pass
            if len(stack) > 0:
                block: PsseRecord = stack.pop()
                block.children = tuple(groups.pop())
                block.valid = block.valid and len(tokens) == 1
            else:
                ended = True
        else:
            command: PsseCommand = identify_command(tokens)
            if command == PsseCommand.BUSNAMES:
                result.bus_mode = BusInputMode.NAMES
            elif command == PsseCommand.BUSNUMBERS:
                result.bus_mode = BusInputMode.NUMBERS
            else:
                pass
            # Compact branch members are positional records inside MON/CON blocks.
            if (command == PsseCommand.UNKNOWN and len(stack) > 0
                    and stack[-1].command in (PsseCommand.BRANCHES, PsseCommand.INTERFACE, PsseCommand.SKIP)):
                command = PsseCommand.MEMBER
            else:
                pass
            record: PsseRecord = PsseRecord(command, tokens, line_number, result.bus_mode)
            record.valid = balanced
            groups[-1].append(record)
            if command == PsseCommand.UNKNOWN:
                result.logger.add_warning('Unsupported PSS/E command retained', device=source, value=line_number)
            elif command == PsseCommand.INCLUDE:
                # Includes belong to the MUST dialect; never open extra files implicitly.
                result.logger.add_warning('INCLUDE retained without expansion', device=source, value=line_number)
            else:
                pass
            is_block: bool = False
            if tpe == AuxiliaryFormat.SUB:
                is_block = command in (PsseCommand.SUBSYSTEM, PsseCommand.JOIN, PsseCommand.PARTICIPATE)
            elif tpe == AuxiliaryFormat.MON:
                is_block = (command in (PsseCommand.INTERFACE, PsseCommand.SKIP)
                            or (command == PsseCommand.BRANCHES
                                and len(tokens) == (2 if tokens[0].text.upper() == 'MONITOR' else 1)))
            else:
                is_block = (command in (PsseCommand.CONTINGENCY, PsseCommand.CATEGORY, PsseCommand.SKIP)
                            or (command in (PsseCommand.SET, PsseCommand.CHANGE, PsseCommand.INCREASE,
                                            PsseCommand.DECREASE, PsseCommand.ADD, PsseCommand.REMOVE)
                                and tokens[-1].text.upper() == 'DISPATCH'))
            if is_block:
                stack.append(record)
                groups.append(list())
            else:
                pass
    # Keep partial blocks inspectable, but never report an incomplete tree as valid.
    while len(stack) > 0:
        block = stack.pop()
        block.valid = False
        block.children = tuple(groups.pop())
        result.logger.add_error('Unterminated PSS/E block', device=source, value=block.line_number)
    result.records = tuple(roots)
    return result
