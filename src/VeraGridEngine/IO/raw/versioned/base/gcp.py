# SPDX-License-Identifier: MPL-2.0
"""Machine capability curves: POM 33 §11.21.1; DataFormats 35/36.

The 33 GCAP file has no change header and may imply a point at zero power.
The 35 REGC file has an IC,REV header and requires at least two explicit points.
These are distinct grammars, not an auto-detected interchangeable header.
"""
from __future__ import annotations

from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.psse_data import DataMarker, DataReader, DataRow, RawDataFile
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport, RecordStatus


class CapabilityPoint:
    """One explicit P/Q capability point; None retains an omitted Q field."""

    __slots__ = ('p', 'q_max', 'q_min')

    def __init__(self, p: float | None, q_max: float | None, q_min: float | None) -> None:
        """Store a point without resolving change-case defaults.

        :param p: Active power in MW.
        :param q_max: Overexcited reactive limit in Mvar.
        :param q_min: Underexcited reactive limit in Mvar.
        """
        self.p: float | None = p
        self.q_max: float | None = q_max
        self.q_min: float | None = q_min


class CapabilityCurve:
    """A machine reference, ordered points and source-located validity."""

    __slots__ = ('row', 'status', 'bus', 'machine_id', 'points', 'implicit_origin')

    def __init__(self, row: DataRow) -> None:
        """Initialize a curve.

        :param row: Source record.
        """
        self.row: DataRow = row
        self.status: RecordStatus = row.status
        self.bus: int | None = None
        self.machine_id: str | None = None
        self.points: tuple[CapabilityPoint, ...] = ()
        self.implicit_origin: bool = False


class RawGcp(RawDataFile):
    """Shared curve validation; concrete versions specify header and origin rules."""

    __slots__ = ('curves', 'has_header', 'minimum_points', 'infer_origin', 'format_support')

    def __init__(self, source: str = '<gcp>', version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize version-owned capability data.

        :param source: Diagnostic source label.
        :param version: Selected major version.
        """
        super().__init__(source, version)
        self.curves: tuple[CapabilityCurve, ...] = ()
        self.has_header: bool = True
        self.minimum_points: int = 2
        self.infer_origin: bool = False
        self.format_support: FeatureSupport = FeatureSupport.UNVERIFIED

    def parse(self, text: str) -> None:
        """Parse a complete GCP file without altering generator limits.

        :param text: Complete file contents.
        """
        self.curves = ()
        if not self.load_rows(text):
            return
        else:
            pass
        index: int = 0
        if self.has_header:
            if not self.read_change_header(revision=True):
                self.unsupported = self.rows
                return
            else:
                index = 1
        else:
            pass
        curves: list[CapabilityCurve] = list()
        keys: set[tuple[int, str]] = set()
        while index < len(self.rows) and not self.ended:
            row: DataRow = self.rows[index]
            if row.marker in (DataMarker.ZERO, DataMarker.QUIT):
                if row.marker == DataMarker.QUIT:
                    self.logger.add_error('GCP requires a zero end record', device=self.source, value=row.line_number)
                    row.status = RecordStatus.INVALID
                else:
                    pass
                self.finish_input(index)
            else:
                curve: CapabilityCurve = self.parse_curve(row)
                if curve.bus is not None and curve.machine_id is not None:
                    key: tuple[int, str] = (curve.bus, curve.machine_id)
                    if key in keys:
                        curve.status = RecordStatus.INVALID
                        self.logger.add_error('Duplicate capability curve', device=self.source, value=row.line_number)
                    else:
                        keys.add(key)
                else:
                    pass
                curves.append(curve)
            index += 1
        self.curves = tuple(curves)
        if not self.ended:
            self.logger.add_error('GCP file missing zero end record', device=self.source)
        else:
            pass

    def parse_curve(self, row: DataRow) -> CapabilityCurve:
        """Read and validate one curve, including generating and motoring order.

        :param row: Capability record.
        :return: Typed curve, including invalid source data.
        """
        reader: DataReader = DataReader(row, self.logger, self.source)
        curve: CapabilityCurve = CapabilityCurve(row)
        curve.bus = reader.positive_integer()
        curve.machine_id = reader.text(default='1', maximum=2)
        points: list[CapabilityPoint] = list()
        while reader.position < len(row.tokens):
            p: float | None = reader.real(required=True)
            q_max: float | None = reader.real()
            q_min: float | None = reader.real()
            if q_max is not None and q_min is not None and q_min > q_max:
                reader.fail('Capability QMIN exceeds QMAX')
            else:
                pass
            points.append(CapabilityPoint(p, q_max, q_min))
        curve.points = tuple(points)
        if not self.minimum_points <= len(points) <= 20:
            reader.fail('Capability point count is outside the version limits')
        else:
            pass
        if len(points) > 0:
            first: float | None = points[0].p
            curve.implicit_origin = self.infer_origin and first is not None and first != 0
            direction: float = first if first is not None else 0.0
            if direction == 0 and len(points) > 1 and points[1].p is not None:
                direction = points[1].p
            else:
                pass
            for previous, current in zip(points, points[1:]):
                if previous.p is not None and current.p is not None:
                    if direction >= 0 and current.p <= previous.p or direction < 0 and current.p >= previous.p:
                        reader.fail('Capability powers are not in generator/motor order')
                    else:
                        pass
                else:
                    pass
        else:
            pass
        if not reader.finish():
            curve.status = RecordStatus.INVALID
        else:
            pass
        return curve
