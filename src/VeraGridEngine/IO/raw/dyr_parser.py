# SPDX-License-Identifier: MPL-2.0
"""Standalone DYR reader; model schemas and version rules live in versioned/."""
from pathlib import Path

from VeraGridEngine.IO.raw.psse_auxiliary import (
    PsseToken, PsseVersion, read_auxiliary_text, tokenize_psse,
)
from VeraGridEngine.IO.raw.versioned.base.dyr import RawDyr as DyrFile
from VeraGridEngine.IO.raw.versioned.base.dyr import DyrRecord, parse_dyr_value
from VeraGridEngine.IO.raw.versioned.v33.dyr import RawDyrV33
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34
from VeraGridEngine.IO.raw.versioned.v35.dyr import RawDyrV35
from VeraGridEngine.IO.raw.versioned.v36.dyr import RawDyrV36


def parse_dyr(text: str, source: str = '<dyr>',
              version: int | PsseVersion = PsseVersion.V36) -> DyrFile:
    """Frame logical records and delegate their interpretation to version objects.

    :param text: Complete DYR input.
    :param source: Diagnostic source label.
    :param version: PSS/E major version, 33 through 36.
    :return: Concrete version object with typed assignments and diagnostics.
    """
    result: DyrFile = DyrFile(source, version)
    if result.version == PsseVersion.V33:
        result = RawDyrV33(source)
    elif result.version == PsseVersion.V34:
        result = RawDyrV34(source)
    elif result.version == PsseVersion.V35:
        result = RawDyrV35(source)
    elif result.version == PsseVersion.V36:
        result = RawDyrV36(source)
    else:
        return result
    records: list[DyrRecord] = list()
    rejected: list[tuple[PsseToken, ...]] = list()
    pending: list[PsseToken] = list()
    start_line: int = 0
    invalid: bool = False
    trailing_comma: bool = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped: str = line.lstrip('\ufeff \t')
        if stripped.startswith(('!', '@', '//')) or stripped.upper().split(maxsplit=1)[:1] == ['COM']:
            pass
        else:
            tokens: tuple[PsseToken, ...]
            slash: bool
            balanced: bool
            tokens, slash, balanced = tokenize_psse(stripped, comma_separated=True)
            if len(pending) == 0 and len(tokens) > 0:
                start_line = line_number
            elif len(pending) > 0 and trailing_comma and stripped.startswith(','):
                # A missing comma field must not shift every subsequent parameter.
                pending.append(PsseToken(''))
            else:
                pass
            pending.extend(tokens)
            if len(stripped) > 0:
                trailing_comma = stripped.rstrip().endswith(',')
            else:
                pass
            if not balanced:
                result.logger.add_error('Unterminated or malformed quoted DYR field', device=source, value=line_number)
                invalid = True
            else:
                pass
            if slash and len(pending) > 0:
                if not invalid:
                    record: DyrRecord | None = result.parse_record(tuple(pending), start_line)
                    if record is not None:
                        records.append(record)
                    else:
                        rejected.append(tuple(pending))
                else:
                    rejected.append(tuple(pending))
                pending.clear()
                invalid = False
                trailing_comma = False
            else:
                pass
    if len(pending) > 0:
        rejected.append(tuple(pending))
        result.logger.add_error('DYR record missing terminating slash', device=source, value=start_line)
    else:
        pass
    result.records = tuple(records)
    result.rejected = tuple(rejected)
    return result


def read_dyr(file_name: str | Path, version: int | PsseVersion = PsseVersion.V36) -> DyrFile:
    """Read an encoded DYR file independently of RAW import.

    :param file_name: Input path.
    :param version: PSS/E major version, 33 through 36.
    :return: Version-specific dynamic assignments and diagnostics.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_dyr(text, source=str(file_name), version=version)
