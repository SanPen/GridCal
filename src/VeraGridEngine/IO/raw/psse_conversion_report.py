# SPDX-License-Identifier: MPL-2.0
"""PSS/E-owned outcomes of applying auxiliary data to a native circuit."""
from __future__ import annotations
from enum import Enum
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType
from VeraGridEngine.IO.raw.raw_types import PsseAuxiliaryDocument


class PsseConversionStatus(Enum):
    """Distinguish applied data from retained, unresolved or unsupported semantics."""
    CONVERTED = 'converted'
    PARTIAL = 'partial'
    INVALID = 'invalid'
    UNRESOLVED = 'unresolved'
    UNSUPPORTED = 'unsupported'


class PsseConversionEntry:
    """One source record and its actual target device identities."""
    __slots__ = ('source', 'line', 'file_type', 'status', 'target_ids', 'message')

    def __init__(self, source: str, line: int, file_type: PsseFileType,
                 status: PsseConversionStatus, target_ids: tuple[str, ...], message: str) -> None:
        """Store a fixed-shape conversion outcome.

        :param source: Input file label.
        :param line: One-based source line.
        :param file_type: Input grammar.
        :param status: Conversion outcome.
        :param target_ids: Native device idtags, never ambiguous display names.
        :param message: Explanation of the applied mapping or limitation.
        """
        self.source: str = source
        self.line: int = line
        self.file_type: PsseFileType = file_type
        self.status: PsseConversionStatus = status
        self.target_ids: tuple[str, ...] = target_ids
        self.message: str = message


class PsseResolvedSubsystem:
    """Resolved bus membership without replacing original RAW area/zone membership."""
    __slots__ = ('name', 'bus_ids', 'weights')

    def __init__(self, name: str, bus_ids: tuple[str, ...], weights: tuple[float, ...]) -> None:
        """Retain a named native-bus selection and optional participation weights.

        :param name: PSS/E subsystem label.
        :param bus_ids: MultiCircuit bus idtags in RAW order.
        :param weights: Per-bus participation weights, or an empty tuple.
        """
        self.name: str = name
        self.bus_ids: tuple[str, ...] = bus_ids
        self.weights: tuple[float, ...] = weights


class PsseImportReport:
    """Keep original documents and conversion results on the source PsseCircuit."""
    __slots__ = ('documents', 'entries', 'subsystems')

    def __init__(self, documents: tuple[PsseAuxiliaryDocument, ...],
                 entries: tuple[PsseConversionEntry, ...],
                 subsystems: tuple[PsseResolvedSubsystem, ...]) -> None:
        """Freeze the report once conversion has finished.

        :param documents: Original typed input, including unsupported fields.
        :param entries: Ordered conversion outcomes.
        :param subsystems: Resolved subsystem membership.
        """
        self.documents: tuple[PsseAuxiliaryDocument, ...] = documents
        self.entries: tuple[PsseConversionEntry, ...] = entries
        self.subsystems: tuple[PsseResolvedSubsystem, ...] = subsystems
