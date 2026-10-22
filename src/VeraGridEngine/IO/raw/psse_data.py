# SPDX-License-Identifier: MPL-2.0
"""Checked free-format records for SEQ, ROP and GCP (not RAW section parsing).

Omitted comma fields are preserved. Optional numeric fields remain None because
many PSS/E defaults depend on the working case or on change-case mode. File
readers must not replace those omissions with invented electrical data.
"""
from __future__ import annotations

import math
from enum import Enum, IntEnum

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.psse_auxiliary import PsseToken, PsseVersion, resolve_psse_version
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus


class ChangeMode(IntEnum):
    """Whether a data file replaces or modifies existing case data."""

    REPLACE = 0
    UPDATE = 1


class DataMarker(Enum):
    """Control records are distinct from actual data, including zero-valued points."""

    DATA = 'data'
    ZERO = 'zero'
    QUIT = 'quit'


class DataRow:
    """One physical record with exact source text and quote-aware fields."""

    __slots__ = ('tokens', 'line_number', 'text', 'status', 'marker')

    def __init__(self, tokens: tuple[PsseToken, ...], line_number: int,
                 text: str, valid: bool = True) -> None:
        """Retain source context and identify control records.

        :param tokens: Fields, including explicit comma omissions.
        :param line_number: One-based source line.
        :param text: Original physical line.
        :param valid: Whether lexical processing succeeded.
        """
        self.tokens: tuple[PsseToken, ...] = tokens
        self.line_number: int = line_number
        self.text: str = text
        self.status: RecordStatus = RecordStatus.VALID if valid else RecordStatus.INVALID
        self.marker: DataMarker = DataMarker.DATA
        if len(tokens) > 0 and not tokens[0].quoted:
            if tokens[0].text.strip() == '0':
                self.marker = DataMarker.ZERO
            elif tokens[0].text.upper() == 'Q':
                self.marker = DataMarker.QUIT
            else:
                pass
        else:
            pass


def split_data_row(line: str, line_number: int) -> DataRow:
    """Split mixed comma/blank input while preserving every omitted field.

    :param line: Physical line; unquoted slash introduces a comment.
    :param line_number: One-based source line.
    :return: Checked source record; a blank line has no fields.
    """
    fields: list[PsseToken] = list()
    index: int = 0
    pending: bool = True
    comma_seen: bool = False
    valid: bool = True
    finished: bool = False
    while index < len(line) and not finished:
        character: str = line[index]
        if character.isspace() or character == '\ufeff':
            index += 1
        elif character == '/':
            finished = True
        elif character == ',':
            if pending:
                fields.append(PsseToken(''))
            else:
                pass
            pending = True
            comma_seen = True
            index += 1
        elif character in ("'", '"'):
            quote: str = character
            value: list[str] = list()
            closed: bool = False
            index += 1
            while index < len(line) and not closed:
                if line[index] == quote:
                    if index + 1 < len(line) and line[index + 1] == quote:
                        value.append(quote)
                        index += 2
                    else:
                        closed = True
                        index += 1
                else:
                    value.append(line[index])
                    index += 1
            fields.append(PsseToken(''.join(value), quoted=True))
            valid = valid and closed and (index == len(line) or line[index].isspace() or line[index] in ',/')
            pending = False
        else:
            start: int = index
            while index < len(line) and not line[index].isspace() and line[index] not in ',/':
                index += 1
            fields.append(PsseToken(line[start:index]))
            pending = False
    if comma_seen and pending:
        fields.append(PsseToken(''))
    else:
        pass
    return DataRow(tuple(fields), line_number, line, valid)


class DataReader:
    """A bounded cursor for numeric data records and their documented defaults."""

    __slots__ = ('row', 'position', 'logger', 'source', 'valid')

    def __init__(self, row: DataRow, logger: Logger, source: str) -> None:
        """Initialize a record cursor.

        :param row: Physical or assembled logical record.
        :param logger: Diagnostic destination.
        :param source: Filename or source label.
        """
        self.row: DataRow = row
        self.position: int = 0
        self.logger: Logger = logger
        self.source: str = source
        self.valid: bool = row.status == RecordStatus.VALID

    def fail(self, message: str) -> None:
        """Invalidate the cursor and retain a source-located diagnostic.

        :param message: Specific grammar/value problem.
        """
        self.valid = False
        self.row.status = RecordStatus.INVALID
        self.logger.add_error(message, device=self.source, value=self.row.line_number)

    def take(self, required: bool = False) -> PsseToken | None:
        """Consume an optional or required field without shifting omissions.

        :param required: Diagnose missing or blank fields.
        :return: Field, or None for an omission.
        """
        token: PsseToken | None = None
        if self.position < len(self.row.tokens):
            token = self.row.tokens[self.position]
            self.position += 1
            if token.text == '' and not token.quoted:
                token = None
            else:
                pass
        else:
            pass
        if required and token is None:
            self.fail('Missing required field')
        else:
            pass
        return token

    def integer(self, required: bool = False) -> int | None:
        """Read an unquoted integer.

        :param required: Whether an omission is invalid.
        :return: Value, or None for omitted/invalid input.
        """
        token: PsseToken | None = self.take(required)
        if token is not None:
            if token.quoted:
                self.fail('Expected an unquoted integer')
            else:
                try:
                    return int(token.text)
                except ValueError:
                    self.fail('Expected an integer')
        else:
            pass
        return None

    def real(self, required: bool = False) -> float | None:
        """Read a finite real number, including Fortran D exponents.

        :param required: Whether an omission is invalid.
        :return: Value, or None for omitted/invalid input.
        """
        token: PsseToken | None = self.take(required)
        if token is not None:
            if token.quoted:
                self.fail('Expected an unquoted real number')
            else:
                try:
                    value: float = float(token.text.replace('D', 'E').replace('d', 'e'))
                    if math.isfinite(value):
                        return value
                    else:
                        self.fail('Numeric fields must be finite')
                except (ValueError, OverflowError):
                    self.fail('Expected a real number')
        else:
            pass
        return None

    def text(self, required: bool = False, default: str | None = None,
             maximum: int | None = None) -> str | None:
        """Read a textual field without converting numeric equipment IDs.

        :param required: Whether an omission is invalid.
        :param default: Documented context-independent default.
        :param maximum: Documented maximum field width.
        :return: Text, default, or None for an omission.
        """
        token: PsseToken | None = self.take(required)
        value: str | None = token.text if token is not None else default
        if value is not None and not value.strip():
            if default is not None:
                value = default
            elif required:
                self.fail('Required text field cannot be blank')
            else:
                pass
        else:
            pass
        if value is not None and maximum is not None and len(value) > maximum:
            self.fail('Text field exceeds its documented width')
        else:
            pass
        return value

    def positive_integer(self, required: bool = True, allow_zero: bool = False) -> int | None:
        """Read a bus/table reference while preserving an optional zero sentinel.

        :param required: Whether an omission is invalid.
        :param allow_zero: Whether zero is a valid unassigned reference.
        :return: Checked reference or None.
        """
        value: int | None = self.integer(required)
        if value is not None and (value < 0 or value == 0 and not allow_zero):
            self.fail('Expected a positive reference' if not allow_zero else 'Expected a nonnegative reference')
        else:
            pass
        return value

    def finish(self) -> bool:
        """Reject unconsumed input and finalize the source record's status.

        :return: Whether the complete record is valid.
        """
        if self.position < len(self.row.tokens):
            self.fail('Unexpected trailing fields')
        else:
            pass
        return self.valid


class RawDataFile:
    """Source ownership and common header checks for numeric PSS/E files."""

    __slots__ = ('source', 'version', 'logger', 'rows', 'change', 'ended', 'unsupported')

    def __init__(self, source: str, version: int | PsseVersion) -> None:
        """Initialize a standalone result without any circuit mutation.

        :param source: Filename or source label.
        :param version: Explicit major version.
        """
        self.source: str = source
        self.logger: Logger = Logger()
        self.version: PsseVersion | None = resolve_psse_version(version, self.logger, source)
        self.rows: tuple[DataRow, ...] = ()
        self.change: ChangeMode | None = None
        self.ended: bool = False
        self.unsupported: tuple[DataRow, ...] = ()

    def load_rows(self, text: str) -> bool:
        """Frame input and diagnose lexical errors before grammar interpretation.

        :param text: Complete input file.
        :return: Whether a supported version and nonempty input are available.
        """
        if self.version is None:
            return False
        else:
            pass
        self.logger = Logger()
        self.change = None
        self.ended = False
        self.unsupported = ()
        rows: list[DataRow] = list()
        for line_number, line in enumerate(text.split('\n'), start=1):
            stripped: str = line.lstrip('\ufeff \t\r')
            if stripped.startswith(('!', '@')) or stripped.upper().split(maxsplit=1)[:1] == ['COM']:
                pass
            else:
                row: DataRow = split_data_row(line, line_number)
                if len(row.tokens) > 0:
                    if row.status == RecordStatus.INVALID:
                        self.logger.add_error('Malformed quoted field', device=self.source, value=line_number)
                    else:
                        pass
                    rows.append(row)
                else:
                    pass
        self.rows = tuple(rows)
        if len(rows) == 0:
            self.logger.add_error('Empty PSS/E data file', device=self.source)
            return False
        else:
            return True

    def read_change_header(self, revision: bool) -> bool:
        """Read reset/update intent and reject an explicit revision mismatch.

        :param revision: Whether this format version includes a REV field.
        :return: Whether grammar parsing may proceed.
        """
        reader: DataReader = DataReader(self.rows[0], self.logger, self.source)
        code: int | None = reader.integer()
        if code is None and reader.valid:
            self.change = ChangeMode.REPLACE
        elif code in (0, 1):
            self.change = ChangeMode.REPLACE if code == 0 else ChangeMode.UPDATE
        else:
            reader.fail('Change code must be 0 or 1')
        if revision:
            rev: int | None = reader.integer()
            if rev is not None:
                parsed: PsseVersion | None = resolve_psse_version(rev, self.logger, self.source)
                if parsed != self.version:
                    reader.fail('File revision does not match the selected version')
                else:
                    pass
            else:
                pass
        else:
            pass
        return reader.finish()

    def finish_input(self, index: int) -> None:
        """Mark termination and diagnose every retained record after it.

        :param index: Index of the terminating row.
        """
        self.ended = True
        if self.rows[index].marker == DataMarker.QUIT and len(self.rows[index].tokens) > 1:
            self.rows[index].status = RecordStatus.INVALID
            self.logger.add_error('Q does not accept arguments', device=self.source, value=self.rows[index].line_number)
        else:
            pass
        self.unsupported = self.rows[index + 1:]
        for row in self.unsupported:
            self.logger.add_warning('Record after end of data retained', device=self.source, value=row.line_number)
