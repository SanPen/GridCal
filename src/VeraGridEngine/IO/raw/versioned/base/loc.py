# SPDX-License-Identifier: MPL-2.0
"""Diagram locations: GUI Guide 33 §3.6.8; DataFormats 36 chapter 17.

LOC needs its own scanner: an apostrophe in a DMS coordinate is a unit marker,
not an unterminated quoted equipment identifier. No projection is performed.
"""
from __future__ import annotations
import math
import re
from enum import Enum
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.psse_data import DataRow, RawDataFile
from VeraGridEngine.IO.raw.versioned.base.auxiliary import BusIdentifier, FeatureSupport, RecordStatus


class LocationKind(Enum):
    """LOC block identities."""
    BUS = 'BUSES'
    BRANCH = 'BRANCHES'
    NODE = 'NODES'


class CoordinateSystem(Enum):
    """Coordinate interpretation specified by the block header."""
    GEOPHYSICAL = 'GEOPHYSICAL'
    CARTESIAN = 'CARTESIAN'


class BranchLocationLayout(Enum):
    """Whether first and last points have documented endpoint roles."""
    OPTIONAL_ENDPOINTS = 'optional_endpoints'
    REQUIRED_ENDPOINTS = 'required_endpoints'


class LocationFormat:
    """Immutable-by-convention block format, retained on every parsed record."""
    __slots__ = ('system', 'latitude_first', 'scale')

    def __init__(self, system: CoordinateSystem = CoordinateSystem.GEOPHYSICAL,
                 latitude_first: bool = False, scale: float | None = None) -> None:
        """Store interpretation without converting diagram units.

        :param system: Cartesian or geographic coordinates.
        :param latitude_first: Whether latitude precedes longitude.
        :param scale: Explicit Cartesian scale, otherwise logical diagram inches.
        """
        self.system: CoordinateSystem = system
        self.latitude_first: bool = latitude_first
        self.scale: float | None = scale


class LocationPoint:
    """One coordinate pair in declared order; geography is in decimal degrees."""
    __slots__ = ('x', 'y')

    def __init__(self, x: float | None, y: float | None) -> None:
        """Store coordinates, preserving invalid omissions.

        :param x: First coordinate in block order.
        :param y: Second coordinate in block order.
        """
        self.x: float | None = x
        self.y: float | None = y


class LocationRecord:
    """Typed bus/node/path record with source and coordinate interpretation."""
    __slots__ = ('row', 'status', 'kind', 'format', 'bus', 'to_bus', 'circuit',
                 'substation', 'node', 'points', 'rotation', 'length', 'branch_layout')

    def __init__(self, row: DataRow, kind: LocationKind, coordinates: LocationFormat,
                 layout: BranchLocationLayout) -> None:
        """Initialize optional references before parsing the block-specific fields.

        :param row: Source row.
        :param kind: Current block.
        :param coordinates: Current block coordinate format.
        :param layout: Version-owned endpoint interpretation.
        """
        self.row: DataRow = row
        self.status: RecordStatus = row.status
        self.kind: LocationKind = kind
        self.format: LocationFormat = coordinates
        self.bus: BusIdentifier | None = None
        self.to_bus: BusIdentifier | None = None
        self.circuit: str | None = None
        self.substation: int | None = None
        self.node: int | None = None
        self.points: tuple[LocationPoint, ...] = ()
        self.rotation: float | None = None
        self.length: float | None = None
        self.branch_layout: BranchLocationLayout = layout


class LocationCursor:
    """Checked character cursor separating equipment identifiers from DMS units."""
    __slots__ = ('owner', 'row', 'position', 'valid')

    def __init__(self, owner: RawLoc, row: DataRow) -> None:
        """Initialize line-local parsing.

        :param owner: Result receiving diagnostics.
        :param row: Original LOC record.
        """
        self.owner: RawLoc = owner
        self.row: DataRow = row
        self.position: int = 0
        self.valid: bool = True

    def fail(self, message: str) -> None:
        """Report a source-located error.

        :param message: Grammar or domain error.
        """
        self.valid = False
        self.row.status = RecordStatus.INVALID
        self.owner.logger.add_error(message, device=self.owner.source, value=self.row.line_number)

    def remaining(self) -> str:
        """Return remaining content after whitespace.

        :return: Unconsumed source substring.
        """
        return self.row.text[self.position:].lstrip()

    def separator(self) -> None:
        """Advance past whitespace and at most one field separator."""
        while self.position < len(self.row.text) and self.row.text[self.position].isspace():
            self.position += 1
        if self.position < len(self.row.text) and self.row.text[self.position] == ',':
            self.position += 1
        else:
            pass

    def identifier(self, required: bool = True, default: str | None = None) -> tuple[str | None, bool]:
        """Read a quoted name or unquoted equipment identifier.

        :param required: Whether missing input is an error.
        :param default: Default for an explicitly omitted field.
        :return: Text and whether it was quoted.
        """
        tail: str = self.remaining()
        self.position = len(self.row.text) - len(tail)
        match: re.Match[str] | None = re.match(r"'((?:[^']|'')*)'|\"((?:[^\"]|\"\")*)\"|([^,\s/]+)", tail)
        value: str | None = default
        quoted: bool = False
        if match is not None:
            quoted = match.group(1) is not None or match.group(2) is not None
            if match.group(1) is not None:
                value = match.group(1).replace("''", "'")
            elif match.group(2) is not None:
                value = match.group(2).replace('""', '"')
            else:
                value = match.group(3)
            self.position += match.end()
        elif required:
            self.fail('Missing LOC identifier')
        else:
            pass
        self.separator()
        return value, quoted

    def integer(self) -> int | None:
        """Read a positive numeric bus/substation/node reference.

        :return: Checked reference or None.
        """
        text: str | None
        quoted: bool
        text, quoted = self.identifier()
        try:
            value: int = int(text) if text is not None else 0
            if quoted or value <= 0:
                self.fail('LOC reference must be a positive integer')
            else:
                return value
        except ValueError:
            self.fail('LOC reference must be an integer')
        return None

    def bus_reference(self) -> BusIdentifier | None:
        """Read a numeric bus or a quoted extended name.

        :return: Explicitly typed reference.
        """
        text: str | None
        quoted: bool
        text, quoted = self.identifier()
        if quoted and text:
            return BusIdentifier(None, text)
        else:
            try:
                number: int = int(text) if text is not None else 0
                if number > 0:
                    return BusIdentifier(number, None)
                else:
                    self.fail('Bus reference must be positive')
            except ValueError:
                self.fail('Extended bus names must be quoted')
        return None

    def real(self, required: bool = True, default: float | None = None) -> float | None:
        """Read one finite scalar, preserving comma omissions.

        :param required: Whether an omission is invalid.
        :param default: Context-independent omitted default.
        :return: Scalar value or None.
        """
        text: str | None
        quoted: bool
        text, quoted = self.identifier(required, None)
        if text is None:
            return default
        else:
            try:
                value: float = float(text.replace('D', 'E').replace('d', 'e'))
                if not quoted and math.isfinite(value):
                    return value
                else:
                    self.fail('LOC scalar must be finite and unquoted')
            except ValueError:
                self.fail('Invalid LOC scalar')
        return None

    def coordinate(self, geographic: bool, latitude: bool, offset: bool) -> float | None:
        """Read decimal or DMS geography, validating axes and angular domains.

        :param geographic: Whether angular notation is accepted.
        :param latitude: Whether the current axis is latitude.
        :param offset: Node offsets have no absolute geographic range restriction.
        :return: Decimal degrees or Cartesian scalar.
        """
        if not geographic:
            return self.real()
        else:
            pass
        tail: str = self.remaining()
        self.position = len(self.row.text) - len(tail)
        number: str = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?'
        axis: str = 'NS' if latitude else 'EW'
        # Hemisphere and explicit units disambiguate comma-separated DMS parts.
        pattern: str = (
            rf'({number})(?:[\s,°ºd]+({number}))?(?:[\s,\x27′m]+({number}))?[\s\x27\x22′″s]*([{axis}])'
            rf'|({number})[°ºd](?:\s*({number})[\x27′m])?(?:\s*({number})[\x22″s]?)?'
            rf'|({number})\s+({number})\s+({number})(?=\s*(?:,|$))'
            rf'|({number})(?:\s*,\s*,\s*,)?')
        match: re.Match[str] | None = re.match(pattern, tail, re.IGNORECASE)
        result: float | None = None
        if match is None:
            self.fail('Missing or malformed LOC coordinate')
            # Consume one malformed field so later fields remain inspectable.
            self.identifier(required=False)
        else:
            groups: tuple[str | None, ...] = match.groups()
            parts_text: tuple[str | None, ...]
            hemisphere: str | None = None
            if groups[0] is not None:
                parts_text = groups[0:3]
                hemisphere = groups[3].upper() if groups[3] is not None else None
            elif groups[4] is not None:
                parts_text = groups[4:7]
            elif groups[7] is not None:
                parts_text = groups[7:10]
            else:
                parts_text = (groups[10],)
            parts: list[float] = [float(part.replace('D', 'E').replace('d', 'e')) for part in parts_text if part is not None]
            if all(math.isfinite(part) for part in parts):
                sign: float = -1.0 if parts[0] < 0 else 1.0
                if hemisphere is not None:
                    if parts[0] < 0 and hemisphere in ('N', 'E'):
                        self.fail('Coordinate sign conflicts with hemisphere')
                    else:
                        pass
                    sign = -1.0 if hemisphere in ('S', 'W') else 1.0
                else:
                    pass
                if any(abs(part) >= 60 for part in parts[1:]):
                    self.fail('Coordinate minutes and seconds must be below 60')
                elif any(part < 0 for part in parts[1:]) and parts[0] >= 0:
                    self.fail('Coordinate component signs conflict')
                else:
                    pass
                result = sign * sum(abs(part) / 60 ** index for index, part in enumerate(parts))
                if not offset and abs(result) > (90 if latitude else 180):
                    self.fail('Coordinate outside latitude/longitude range')
                else:
                    pass
            else:
                self.fail('LOC coordinates must be finite')
            self.position += match.end()
            self.separator()
        return result


class RawLoc(RawDataFile):
    """Version-owned LOC interpretation, with all blocks retained in source order."""
    __slots__ = ('records', 'branch_layout', 'branch_layout_support')

    def __init__(self, source: str = '<loc>', version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize location data without changing a diagram or circuit.

        :param source: Diagnostic source label.
        :param version: Selected major version.
        """
        super().__init__(source, version)
        self.records: tuple[LocationRecord, ...] = ()
        self.branch_layout: BranchLocationLayout = BranchLocationLayout.OPTIONAL_ENDPOINTS
        self.branch_layout_support: FeatureSupport = FeatureSupport.UNVERIFIED

    def parse(self, text: str) -> None:
        """Parse block headers and checked bus, node and path coordinates.

        :param text: Complete LOC contents.
        """
        self.records = ()
        self.rows = ()
        self.unsupported = ()
        self.ended = False
        if self.version is None:
            return
        else:
            pass
        self.logger = Logger()
        kind: LocationKind = LocationKind.BUS
        coordinates: LocationFormat = LocationFormat()
        rows: list[DataRow] = list()
        unsupported: list[DataRow] = list()
        records: list[LocationRecord] = list()
        known_block: bool = True
        for line_number, line in enumerate(text.split('\n'), start=1):
            content: str = line.strip().lstrip('\ufeff')
            if not content or content.startswith(('!', '/', '@')) or content.upper().split(maxsplit=1)[:1] == ['COM']:
                pass
            else:
                row: DataRow = DataRow((), line_number, line)
                rows.append(row)
                header: str = content.split('/', maxsplit=1)[0].strip().strip('[] ').upper()
                if header in ('BUSES', 'BRANCHES', 'NODES'):
                    kind = LocationKind(header)
                    coordinates = LocationFormat()
                    known_block = True
                elif header.startswith(('CARTESIAN', 'GEOPHYSICAL')):
                    cursor: LocationCursor = LocationCursor(self, row)
                    word: str | None
                    quoted: bool
                    word, quoted = cursor.identifier()
                    system: CoordinateSystem = CoordinateSystem.CARTESIAN if word is not None and word.upper() == 'CARTESIAN' else CoordinateSystem.GEOPHYSICAL
                    latitude_first: bool = False
                    scale: float | None = None
                    if cursor.remaining() and not cursor.remaining().startswith('/'):
                        option: str | None
                        option_start: int = cursor.position
                        option, quoted = cursor.identifier()
                        if system == CoordinateSystem.GEOPHYSICAL and option is not None and option.upper() == 'LATLON':
                            latitude_first = True
                        elif system == CoordinateSystem.CARTESIAN:
                            if option is not None and option.upper() == 'SCALE':
                                scale = cursor.real()
                            else:
                                cursor.position = option_start
                                scale = cursor.real()
                            if scale is not None and scale <= 0:
                                cursor.fail('Cartesian scale must be positive')
                            else:
                                pass
                        else:
                            cursor.fail('Unknown coordinate format option')
                    else:
                        pass
                    if cursor.remaining() and not cursor.remaining().startswith('/'):
                        cursor.fail('Trailing location format fields')
                    else:
                        pass
                    coordinates = LocationFormat(system, latitude_first, scale)
                    known_block = known_block and cursor.valid
                elif content.startswith('[') or re.fullmatch(r'[A-Za-z_]+', content) is not None:
                    known_block = False
                    row.status = RecordStatus.UNSUPPORTED
                    unsupported.append(row)
                    self.logger.add_error('Unknown location block', device=self.source, value=line_number)
                elif not known_block:
                    row.status = RecordStatus.UNSUPPORTED
                    unsupported.append(row)
                else:
                    records.append(self.read_record(row, kind, coordinates))
        self.rows = tuple(rows)
        self.records = tuple(records)
        self.unsupported = tuple(unsupported)
        self.ended = True
        if not rows:
            self.logger.add_error('Empty LOC file', device=self.source)
        else:
            pass

    def read_record(self, row: DataRow, kind: LocationKind, coordinates: LocationFormat) -> LocationRecord:
        """Read one block-specific location record.

        :param row: Source row.
        :param kind: Block identity.
        :param coordinates: Block coordinate settings.
        :return: Checked location record.
        """
        cursor: LocationCursor = LocationCursor(self, row)
        result: LocationRecord = LocationRecord(row, kind, coordinates, self.branch_layout)
        if kind == LocationKind.NODE:
            result.substation = cursor.integer()
            result.node = cursor.integer()
        elif kind == LocationKind.BRANCH:
            result.bus = cursor.bus_reference()
            result.to_bus = cursor.bus_reference()
            quoted: bool
            result.circuit, quoted = cursor.identifier(required=False, default='1')
            if result.circuit is not None and len(result.circuit) > 2:
                cursor.fail('Circuit identifier exceeds two characters')
            else:
                pass
        else:
            bus: int | None = cursor.integer()
            result.bus = BusIdentifier(bus, None) if bus is not None else None
        points: list[LocationPoint] = list()
        geographic: bool = coordinates.system == CoordinateSystem.GEOPHYSICAL
        if kind == LocationKind.BRANCH:
            while cursor.remaining() and not cursor.remaining().startswith('/'):
                before: int = cursor.position
                x: float | None = cursor.coordinate(geographic, coordinates.latitude_first, False)
                y: float | None = cursor.coordinate(geographic, not coordinates.latitude_first, False)
                points.append(LocationPoint(x, y))
                if cursor.position <= before:
                    cursor.fail('Cannot advance in branch coordinate list')
                    break
                else:
                    pass
            minimum: int = 2 if self.branch_layout == BranchLocationLayout.REQUIRED_ENDPOINTS else 1
            if len(points) < minimum:
                cursor.fail('Too few coordinate pairs for the version branch layout')
            else:
                pass
        else:
            x = cursor.coordinate(geographic, coordinates.latitude_first, kind == LocationKind.NODE)
            y = cursor.coordinate(geographic, not coordinates.latitude_first, kind == LocationKind.NODE)
            points.append(LocationPoint(x, y))
            result.rotation = cursor.real(required=False, default=0.0)
            result.length = cursor.real(required=False, default=0.0)
            if result.length is not None and result.length < 0:
                cursor.fail('Busbar length cannot be negative')
            else:
                pass
        if cursor.remaining() and not cursor.remaining().startswith('/'):
            cursor.fail('Unexpected trailing location fields')
        else:
            pass
        result.points = tuple(points)
        if not cursor.valid:
            result.status = RecordStatus.INVALID
        else:
            pass
        return result
