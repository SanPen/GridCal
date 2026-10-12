# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import csv
from enum import Enum, IntEnum
from typing import Dict, List


class PowerFactoryVscType(IntEnum):
    """Identify the native PowerFactory PWM-converter topology.

    The numeric members are the declarative ``vsctype`` values exported by
    ``ElmVsc`` and ``ElmVscmono``.
    """

    TwoLevel = 0
    HalfBridgeMmc = 1
    FullBridgeMmc = 2


class PowerFactoryLineInstallationType(Enum):
    """Classify the physical installation declared by a DGS line type.

    PowerFactory has used both the legacy ``aohl_`` text field and the newer
    ``cohl_`` integer field for the same cable-versus-overhead distinction.
    ``Unknown`` and ``Conflict`` preserve source uncertainty instead of
    replacing it with a parser default.
    """

    Unknown = 'unknown'
    Cable = 'cable'
    Overhead = 'overhead'
    Conflict = 'conflict'


def _split_dgs_line(line: str) -> List[str]:
    """
    Split a DGS record honoring quoted semicolons.

    :param line: Raw DGS record line.
    :return: Parsed record fields.
    """
    return next(csv.reader([line.rstrip('\n')], delimiter=';', quotechar='"'))


def _parse_elm_dsl_param_value(raw: str | None) -> float | str | None:
    """
    Parse one ElmDsl parameter value from the DGS row.

    :param raw: Raw DGS text.
    :return: Parsed numeric value, raw text fallback, or ``None`` for empty placeholders.
    """
    if raw is None:
        return None
    else:
        pass

    text: str = raw.strip()
    if text in {'', '*'}:
        return None
    else:
        pass

    try:
        return float(text.replace(',', '.'))
    except ValueError:
        return text


class DgsProperty:
    """
    Dgs Property
    """

    __slots__ = (
        "name",
        "dgs_type",
        "description",
        "py_name",
        "optional",
        "py_type",
        "default_value",
    )

    def __init__(self,
                 name: str,
                 dgs_type: str,
                 description: str,
                 py_name: str,
                 optional: bool = False) -> None:
        """Describe one typed DGS column.

        :param name: Exact DGS header name.
        :param dgs_type: Native DGS scalar type declaration.
        :param description: Human-readable column description.
        :param py_name: Target Python attribute name.
        :param optional: Preserve missing placeholders as ``None``.
        :return: None.
        """
        self.name: str = name
        self.dgs_type: str = dgs_type
        self.description: str = description
        self.py_name: str = py_name
        self.optional: bool = bool(optional)
        self.py_type: type = str
        self.default_value: str | int | bool | float | None = None

        if dgs_type.startswith("b"):  # boolean
            self.py_type = bool
            self.default_value = False

        elif dgs_type.startswith("i"):  # integer
            self.py_type = int
            self.default_value = 0

        elif dgs_type.startswith("r"):  # real/float
            self.py_type = float
            self.default_value = 0.0

        elif dgs_type.startswith("a"):  # string
            self.py_type = str
            self.default_value = ""

        elif dgs_type.startswith("p"):  # object reference
            self.py_type = str
            self.default_value = None

        else:
            # Unknown/rare types: keep as string by default
            self.py_type = str
            self.default_value = None

    def parse(self, raw: str | None) -> str | int | bool | float | None:
        """

        :param raw: incoming value
        :return:
        """
        if raw is None:
            if self.optional:
                return None
            else:
                return self.default_value

        raw = raw.strip()

        # PowerFactory placeholders / missing values
        if raw == "" or raw == "*":
            if self.optional:
                return None
            else:
                return self.default_value

        # Boolean parsing
        if self.py_type is bool:
            v = raw.strip().lower()
            if v in {"1", "true", "t", "yes", "y"}:
                return True
            elif v in {"0", "false", "f", "no", "n"}:
                return False
            else:
                # Unexpected encoding → fallback
                return self.default_value

        # Numeric parsing (int/float) with decimal comma
        if self.py_type in (int, float):
            raw_norm = raw.replace(",", ".")
            try:
                if self.py_type is int:
                    # Some PF fields may show "1.0" for ints; tolerate that
                    return int(float(raw_norm))
                else:
                    return float(raw_norm)
            except ValueError:
                if self.optional:
                    return None
                else:
                    return self.default_value

        # String/reference
        return raw

    def format(self, value: str | int | bool | float | None) -> str:
        """

        :param value:
        :return:
        """
        if value is None:
            return ''
        if self.dgs_type == 'b':
            return '1' if bool(value) else '0'
        return str(value)


class DGSElement:
    """
    Base class
    """
    __slots__ = ()
    element_type: str
    properties_list: List[DgsProperty]
    properties: Dict[str, DgsProperty]

    def __init_subclass__(cls):
        cls.properties = {p.name: p for p in cls.properties_list}

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> "BlkSlot":
        """
        Parse a DGS data line using a header-derived column map.

        Parameters
        ----------
        line : str
            Raw data line from DGS
        header_map : dict[str, int]
            Mapping {property_name -> column_index}
            derived from the $$ header line
        """
        parts = _split_dgs_line(line)
        obj = cls()

        for prop in cls.properties_list:

            idx = header_map.get(prop.name, None)

            # Fix ID vs FID thing, internally it is always ID, and we handle the FID issue
            if idx is None and prop.name == "ID":
                idx = header_map.get("FID", None)

            if idx is not None:

                if -1 < idx < len(parts):
                    raw = parts[idx]
                    value = prop.parse(raw)
                    setattr(obj, prop.py_name, value)
                else:
                    # Column declared but missing in this line
                    pass
            else:
                # Property not present in this DGS version
                pass

        return obj

    def to_dgs_line(self) -> str:
        """
        Create DGS line
        :return:
        """
        return ';'.join(p.format(getattr(self, p.py_name)) for p in self.properties_list)

    def __repr__(self):
        """

        :return:
        """
        if hasattr(self, "loc_name"):
            return getattr(self, "loc_name")
        else:
            return getattr(self, "ID")


class ChaRef(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
    )
    element_type = 'ChaRef'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""


class ChaVec(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "scale",
        "usage",
        "approx",
        "vector_SIZEROW",
        "vector_0",
        "vector_1",
        "vector_2",
    )
    element_type = 'ChaVec'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('scale', 'p', 'DGS field scale (p)', py_name='scale'),
        DgsProperty('usage', 'i', 'DGS field usage (i)', py_name='usage'),
        DgsProperty('approx', 'i', 'DGS field approx (i)', py_name='approx'),
        DgsProperty('vector:SIZEROW', 'i', 'DGS field vector:SIZEROW (i)', py_name='vector_SIZEROW'),
        DgsProperty('vector:0', 'r', 'DGS field vector:0 (r)', py_name='vector_0'),
        DgsProperty('vector:1', 'r', 'DGS field vector:1 (r)', py_name='vector_1'),
        DgsProperty('vector:2', 'r', 'DGS field vector:2 (r)', py_name='vector_2'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.scale: str = ""
        self.usage: int = 0
        self.approx: int = 0
        self.vector_SIZEROW: int = 0
        self.vector_0: float = 0.0
        self.vector_1: float = 0.0
        self.vector_2: float = 0.0


class ElmComp(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "outserv",
        "pblk",
        "pelm",
        "contents",
    )
    element_type = 'ElmComp'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.pblk: List[str | None] = list()
        self.pelm: List[str | None] = list()
        self.contents: List[str] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = _split_dgs_line(line)
        obj = super().parse_line(";".join(parts), header_map)

        raw_pblk = _dgs_get(parts, header_map, 'pblk:SIZEROW')
        n_pblk = int(float(raw_pblk.replace(',', '.'))) if raw_pblk is not None and raw_pblk.strip() != '' else 0
        for i in range(n_pblk):
            raw_ptr = _dgs_get(parts, header_map, f'pblk:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.pblk.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        raw_pelm = _dgs_get(parts, header_map, 'pelm:SIZEROW')
        n_pelm = int(float(raw_pelm.replace(',', '.'))) if raw_pelm is not None and raw_pelm.strip() != '' else 0
        for i in range(n_pelm):
            raw_ptr = _dgs_get(parts, header_map, f'pelm:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.pelm.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        raw_contents = _dgs_get(parts, header_map, 'contents:SIZEROW')
        n_contents = int(
            float(raw_contents.replace(',', '.'))) if raw_contents is not None and raw_contents.strip() != '' else 0
        for i in range(n_contents):
            raw_text = _dgs_get(parts, header_map, f'contents:{i}')
            raw_text = raw_text.strip() if raw_text is not None else ''
            if raw_text != '' and raw_text != '*':
                obj.contents.append(raw_text)

        return obj


class ElmDsl(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "outserv",
        "params",
        "pelm",
        "signal",
        "parameter_names",
    )
    element_type = 'ElmDsl'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.params: List[float | str | None] = list()
        self.pelm: List[str | None] = list()
        self.signal: List[str] = list()
        self.parameter_names: List[str] = list()

    def get_parameter_map(self) -> Dict[str, float | str | None]:
        """
        Return the instance parameter mapping using the DGS order.

        :return: Dictionary keyed by PowerFactory parameter name.
        """
        return {
            name: value
            for name, value in zip(self.parameter_names, self.params)
        }

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = _split_dgs_line(line)
        obj = super().parse_line(";".join(parts), header_map)

        raw_params_size = _dgs_get(parts, header_map, 'params:SIZEROW')
        n_params = int(float(
            raw_params_size.replace(',', '.'))) if raw_params_size is not None and raw_params_size.strip() != '' else 0
        for i in range(n_params):
            # The ElmDsl row stores the concrete instance values that must later feed the generated event_dict.
            obj.params.append(_parse_elm_dsl_param_value(_dgs_get(parts, header_map, f'params:{i}')))

        raw_pelm = _dgs_get(parts, header_map, 'pelm:SIZEROW')
        n_pelm = int(float(raw_pelm.replace(',', '.'))) if raw_pelm is not None and raw_pelm.strip() != '' else 0
        for i in range(n_pelm):
            raw_ptr = _dgs_get(parts, header_map, f'pelm:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.pelm.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        raw_signal = _dgs_get(parts, header_map, 'signal:SIZEROW')
        n_signal = int(
            float(raw_signal.replace(',', '.'))) if raw_signal is not None and raw_signal.strip() != '' else 0
        for i in range(n_signal):
            raw_sig = _dgs_get(parts, header_map, f'signal:{i}')
            raw_sig = raw_sig.strip() if raw_sig is not None else ''
            if raw_sig != '' and raw_sig != '*':
                obj.signal.append(raw_sig)

        raw_params = _dgs_get(parts, header_map, 'parameterNames')
        if raw_params is not None and raw_params.strip() not in {'', '*'}:
            obj.parameter_names = [item.strip() for item in raw_params.split(',') if item.strip()]

        return obj


class BlkFrom(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "sSig_SIZEROW",
        "sSig_0",
        "loc_name",
        "signals",
    )
    element_type = 'BlkFrom'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('sSig:SIZEROW', 'i', 'DGS field sSig:SIZEROW (i)', py_name='sSig_SIZEROW'),
        DgsProperty('sSig:0', 'a', 'DGS field sSig:0 (a)', py_name='sSig_0'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.sSig_SIZEROW: int = 0
        self.sSig_0: str = ''
        self.loc_name: str = ''
        self.signals: List[str] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = _split_dgs_line(line)
        obj = super().parse_line(";".join(parts), header_map)
        if obj.sSig_0.strip() not in {'', '*'}:
            obj.signals = [item.strip() for item in obj.sSig_0.split(',') if item.strip()]
        return obj


class BlkGoto(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "sSig_SIZEROW",
        "sSig_0",
        "signals",
    )
    element_type = 'BlkGoto'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('sSig:SIZEROW', 'i', 'DGS field sSig:SIZEROW (i)', py_name='sSig_SIZEROW'),
        DgsProperty('sSig:0', 'a', 'DGS field sSig:0 (a)', py_name='sSig_0'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.sSig_SIZEROW: int = 0
        self.sSig_0: str = ''
        self.signals: List[str] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> BlkGoto:
        """
        Parse the routing signal vector owned by one graphical goto node.

        :param line: Raw DGS record.
        :param header_map: Column-name to position mapping.
        :return: Parsed graphical goto object.
        """
        parts: List[str] = _split_dgs_line(line)
        obj: BlkGoto = cls()

        # Load the identifier with the PowerFactory FID compatibility rule.
        identifier_value: str | None = _dgs_get(parts, header_map, 'ID')
        if identifier_value is None:
            identifier_value = _dgs_get(parts, header_map, 'FID')
        else:
            pass
        if identifier_value is None or identifier_value.strip() in {'', '*'}:
            obj.ID = ''
        else:
            obj.ID = identifier_value.strip()

        # Load the remaining scalar fields without losing the concrete type.
        operation_value: str | None = _dgs_get(parts, header_map, 'OP')
        if operation_value is None or operation_value.strip() in {'', '*'}:
            obj.OP = ''
        else:
            obj.OP = operation_value.strip()
        location_value: str | None = _dgs_get(parts, header_map, 'loc_name')
        if location_value is None or location_value.strip() in {'', '*'}:
            obj.loc_name = ''
        else:
            obj.loc_name = location_value.strip()
        signal_count_value: str | None = _dgs_get(parts, header_map, 'sSig:SIZEROW')
        parsed_signal_count: str | int | bool | float | None = (
            obj.properties['sSig:SIZEROW'].parse(
                '' if signal_count_value is None else signal_count_value
            )
        )
        if isinstance(parsed_signal_count, int):
            obj.sSig_SIZEROW = parsed_signal_count
        else:
            obj.sSig_SIZEROW = 0
        signal_vector_value: str | None = _dgs_get(parts, header_map, 'sSig:0')
        if signal_vector_value is None or signal_vector_value.strip() in {'', '*'}:
            obj.sSig_0 = ''
        else:
            obj.sSig_0 = signal_vector_value.strip()

        # Preserve the ordered routed names for structural graph resolution.
        if obj.sSig_0.strip() in {'', '*'}:
            pass
        else:
            signal_name: str
            for signal_name in obj.sSig_0.split(','):
                normalized_signal_name: str = signal_name.strip()
                if normalized_signal_name == '':
                    pass
                else:
                    obj.signals.append(normalized_signal_name)
        return obj


class BlkDiv(DGSElement):
    """Represent one native graphical division node from an ASCII DGS file."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
    )

    element_type: str = 'BlkDiv'
    properties_list: List[DgsProperty] = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
    ]

    def __init__(self) -> None:
        """Initialize an empty native graphical division record."""
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''


class BlkMul(DGSElement):
    """Represent one native graphical multiplication node from an ASCII DGS file."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
    )

    element_type: str = 'BlkMul'
    properties_list: List[DgsProperty] = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
    ]

    def __init__(self) -> None:
        """Initialize an empty native graphical multiplication record."""
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''


class BlkSwt(DGSElement):
    """Represent one native graphical switch node from an ASCII DGS file."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "iNeg",
    )

    element_type: str = 'BlkSwt'
    properties_list: List[DgsProperty] = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('iNeg', 'i', 'Inverted zero position', py_name='iNeg'),
    ]

    def __init__(self) -> None:
        """Initialize an empty native graphical switch record."""
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.iNeg: int = 0


class BlkRef(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "typ_id",
        "cdisName",
        "params",
        "states",
        "internals",
    )
    element_type = 'BlkRef'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        DgsProperty('cdisName', 'a', 'DGS field cdisName (a)', py_name='cdisName'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.typ_id: str = ''
        self.cdisName: str = ''
        self.params: List[str] = list()
        self.states: List[str] = list()
        self.internals: List[str] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = _split_dgs_line(line)
        obj = super().parse_line(";".join(parts), header_map)

        raw_params = _dgs_get(parts, header_map, 'sParams:0')
        if raw_params is not None and raw_params.strip() not in {'', '*'}:
            obj.params = [item.strip() for item in raw_params.split(',') if item.strip()]

        raw_states = _dgs_get(parts, header_map, 'sStates:0')
        if raw_states is not None and raw_states.strip() not in {'', '*'}:
            obj.states = [item.strip() for item in raw_states.split(',') if item.strip()]

        raw_internals = _dgs_get(parts, header_map, 'sIntern:0')
        if raw_internals is not None and raw_internals.strip() not in {'', '*'}:
            obj.internals = [item.strip() for item in raw_internals.split(',') if item.strip()]

        return obj


class BlkSig(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "inodfrom",
        "loc_name",
        "iconfrom",
        "inodto",
        "iconto",
        "pnodfrom",
        "pnodto",
    )
    element_type = 'BlkSig'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('inodfrom', 'i', 'DGS field inodfrom (i)', py_name='inodfrom'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('iconfrom', 'i', 'DGS field iconfrom (i)', py_name='iconfrom'),
        DgsProperty('inodto', 'i', 'DGS field inodto (i)', py_name='inodto'),
        DgsProperty('iconto', 'i', 'DGS field iconto (i)', py_name='iconto'),
        DgsProperty('pnodfrom', 'p', 'DGS field pnodfrom (p)', py_name='pnodfrom'),
        DgsProperty('pnodto', 'p', 'DGS field pnodto (p)', py_name='pnodto'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.inodfrom: int = 0
        self.loc_name: str = ''
        self.iconfrom: int = 0
        self.inodto: int = 0
        self.iconto: int = 0
        self.pnodfrom: str = ''
        self.pnodto: str = ''


class BlkSlot(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "element",
        "filtmod",
        "outputs",
        "inputs",
    )
    element_type = 'BlkSlot'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('element', 'p', 'DGS field element (p)', py_name='element'),
        DgsProperty('filtmod', 'a:80', 'DGS field filtmod (a:80)', py_name='filtmod'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.element: str = ''
        self.filtmod: str = ''
        self.outputs: List[str] = list()
        self.inputs: List[str] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = _split_dgs_line(line)
        # Preserve the original quoting while the base parser resolves every
        # header column. Rejoining already-decoded fields would turn embedded
        # semicolons into false delimiters and shift ``element``/``filtmod``.
        obj: BlkSlot = super().parse_line(line, header_map)
        raw_outputs = _dgs_get(parts, header_map, 'sOutput:0')
        if raw_outputs is not None and raw_outputs.strip() not in {'', '*'}:
            obj.outputs = [item.strip() for item in raw_outputs.split(',') if item.strip()]
        raw_inputs = _dgs_get(parts, header_map, 'sInput:0')
        if raw_inputs is not None and raw_inputs.strip() not in {'', '*'}:
            obj.inputs = [item.strip() for item in raw_inputs.split(',') if item.strip()]
        return obj


class BlkSum(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "iInput0",
        "iInput0_act",
        "iInput1",
        "iInput1_act",
        "iInput3",
        "iInput3_act",
        "iInput2",
        "iInput2_act",
    )
    element_type = 'BlkSum'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('iInput0', 'i', 'DGS field iInput0 (i)', py_name='iInput0'),
        DgsProperty('iInput0:act', 'i', 'DGS field iInput0:act (i)', py_name='iInput0_act'),
        DgsProperty('iInput1', 'i', 'DGS field iInput1 (i)', py_name='iInput1'),
        DgsProperty('iInput1:act', 'i', 'DGS field iInput1:act (i)', py_name='iInput1_act'),
        DgsProperty('iInput3', 'i', 'DGS field iInput3 (i)', py_name='iInput3'),
        DgsProperty('iInput3:act', 'i', 'DGS field iInput3:act (i)', py_name='iInput3_act'),
        DgsProperty('iInput2', 'i', 'DGS field iInput2 (i)', py_name='iInput2'),
        DgsProperty('iInput2:act', 'i', 'DGS field iInput2:act (i)', py_name='iInput2_act'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.iInput0: int = 0
        self.iInput0_act: int = 0
        self.iInput1: int = 0
        self.iInput1_act: int = 0
        self.iInput3: int = 0
        self.iInput3_act: int = 0
        self.iInput2: int = 0
        self.iInput2_act: int = 0


class ElmAsm(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "typ_id",
        "ngnum",
        "i_mot",
        "outserv",
        "pgini",
        "qgini",
        "chr_name",
        "idfig",
        "bustp",
        "cCategory",
        "pmode",
    )
    element_type = 'ElmAsm'
    properties_list = [
        DgsProperty('FID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('OP', 'a:1', 'Operation', py_name='OP'),
        DgsProperty('loc_name', 'a', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypAsmo', py_name='typ_id'),
        DgsProperty('ngnum', 'i', 'Number of Parallel Machines', py_name='ngnum'),
        DgsProperty('i_mot', 'i', 'Operating Mode: Generator:Motor', py_name='i_mot'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('pgini', 'r', 'Active Power Setpoint in MW', py_name='pgini'),
        DgsProperty('qgini', 'r', 'Reactive Power Setpoint in MVAr', py_name='qgini'),
        DgsProperty('chr_name', 'a', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('idfig', 'i', 'Machine type', py_name='idfig'),
        DgsProperty('bustp', 'a:4', 'Bus type: AS:PQ', py_name='bustp'),
        DgsProperty('cCategory', 'a', 'Plant Category', py_name='cCategory'),
        DgsProperty('pmode', 'i', 'Electrical power:Mechanical power:Mechanical torque', py_name='pmode'),
    ]

    def __init__(self) -> None:
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.fold_id: str = ''
        self.typ_id: str = ''
        self.ngnum: int = 0
        self.i_mot: int = 0
        self.outserv: int = 0
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.chr_name: str = ''
        self.idfig: int = 0
        self.bustp: str = ''
        self.cCategory: str = ''
        self.pmode: int = 0


class ElmCoup(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "chr_name",
        "aUsage",
        "nneutral",
        "nphase",
        "on_off",
        "for_name",
    )
    element_type = 'ElmCoup'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypSwitch', py_name='typ_id'),
        DgsProperty('chr_name', 'a', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('aUsage', 'a', 'Switch Usage Code', py_name='aUsage'),
        DgsProperty('nneutral', 'i', 'Number of Neutral Conductors', py_name='nneutral'),
        DgsProperty('nphase', 'i', 'Number of Phases', py_name='nphase'),
        DgsProperty('on_off', 'i', 'Switch Position: Open:Closed', py_name='on_off'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.aUsage: str = ""
        self.nneutral: int = 0
        self.nphase: int = 3
        self.on_off: int = 0
        self.for_name: str = ""


class ElmBranch(DGSElement):
    """
    Branch element container (PowerFactory/DGS).

    Notes
    -----
    ElmBranch is a hierarchical container used to organize the project/model and
    the single-line diagram. It does NOT define electrical connectivity.
    """
    __slots__ = (
        "ID",
        "loc_name",
        "for_name",
        "fold_id",
        "iDatCon0",
        "iDatCon1",
    )
    element_type = 'ElmBranch'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('for_name', 'a:100', 'DGS field for_name (a:100)', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('iDatCon0', 'i', 'DGS field iDatCon0 (i)', py_name='iDatCon0'),
        DgsProperty('iDatCon1', 'i', 'DGS field iDatCon1 (i)', py_name='iDatCon1'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.iDatCon0: int = 0
        self.iDatCon1: int = 0


class ElmFeeder(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "obj_id",
        "iorient",
        "i_scale",
        "Iset",
        "icolor",
        "outserv",
    )
    element_type = 'ElmFeeder'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('obj_id', 'p', 'DGS field obj_id (p)', py_name='obj_id'),
        DgsProperty('iorient', 'i', 'DGS field iorient (i)', py_name='iorient'),
        DgsProperty('i_scale', 'i', 'DGS field i_scale (i)', py_name='i_scale'),
        DgsProperty('Iset', 'r', 'DGS field Iset (r)', py_name='Iset'),
        DgsProperty('icolor', 'i', 'DGS field icolor (i)', py_name='icolor'),
        DgsProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.obj_id: str = ""
        self.iorient: int = 0
        self.i_scale: int = 0
        self.Iset: float = 0.0
        self.icolor: int = 0
        self.outserv: int = 0


class PowerFactoryGeneratorTechnology(IntEnum):
    """Native ElmGenstat technology selector, in PowerFactory's declared order."""

    ThreePhase = 0
    ThreePhaseEarth = 1
    SinglePhaseEarth = 2
    SinglePhaseNeutral = 3
    SinglePhasePhase = 4


class ElmGenstat(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "bus1",
        "outserv",
        "sgn",
        "cosn",
        "ngnum",
        "pgini",
        "qgini",
        "av_mode",
        "mode_inp",
        "ip_ctrl",
        "cCategory",
        "c_pmod",
        "ddroop",
        "usp_max",
        "usp_min",
        "usetp",
        "cQ_min",
        "cQ_max",
        "phtech",
        "nneutral",
        "r0",
        "x0",
        "r2",
        "x2",
    )
    element_type = 'ElmGenstat'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('bus1', 'p', 'Connected Terminal Cubicle', py_name='bus1'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('sgn', 'r', 'Rated Apparent Power in MVA', py_name='sgn'),
        DgsProperty('cosn', 'r', 'Rated Power Factor', py_name='cosn'),
        DgsProperty('ngnum', 'i', 'Number of Parallel Units', py_name='ngnum'),
        DgsProperty('pgini', 'r', 'Active Power Setpoint in MW', py_name='pgini'),
        DgsProperty('qgini', 'r', 'Reactive Power Setpoint in MVAr', py_name='qgini'),
        DgsProperty('av_mode', 'a', 'Active Power Control Mode', py_name='av_mode'),
        DgsProperty('mode_inp', 'a:6', 'Dispatch: Input mode', py_name='mode_inp'),
        DgsProperty('ip_ctrl', 'i', 'Reference Machine Flag', py_name='ip_ctrl'),
        DgsProperty('cCategory', 'a:40', 'plant types', py_name='cCategory'),
        DgsProperty('c_pmod', 'a:40', 'plant model', py_name='c_pmod'),
        DgsProperty('ddroop', 'r', 'Voltage droop value [%]', py_name='ddroop'),
        DgsProperty('usp_max', 'r', 'Maximum voltage setpoint [pu]', py_name='usp_max'),
        DgsProperty('usp_min', 'r', 'Minimum voltage setpoint [pu]', py_name='usp_min'),
        DgsProperty('usetp', 'r', 'Specified voltage setpoint [pu]', py_name='usetp'),
        DgsProperty('cQ_min', 'r', 'Minimum reactive power to inject/absorb [MVAr]', py_name='cQ_min'),
        DgsProperty('cQ_max', 'r', 'Maximum reactive power to inject/absorb [MVAr]', py_name='cQ_max'),
        DgsProperty('phtech', 'i', 'Generator phase technology', py_name='phtech', optional=True),
        DgsProperty('nneutral', 'i', 'Neutral conductor connection', py_name='nneutral', optional=True),
        DgsProperty('r0', 'r', 'Zero-sequence resistance on machine base [pu]', py_name='r0', optional=True),
        DgsProperty('x0', 'r', 'Zero-sequence reactance on machine base [pu]', py_name='x0', optional=True),
        DgsProperty('r2', 'r', 'Load-flow negative-sequence resistance on machine base [pu]', py_name='r2', optional=True),
        DgsProperty('x2', 'r', 'Load-flow negative-sequence reactance on machine base [pu]', py_name='x2', optional=True),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.bus1: str = ""
        self.outserv: int = 0
        self.sgn: float = 0.0
        self.cosn: float = 0.0
        self.ngnum: int = 0
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.av_mode: str = ""
        self.mode_inp: str = ""
        self.ip_ctrl: int = 0
        self.cCategory: str = ""
        self.c_pmod: str = ""
        self.ddroop: float = 0.0
        self.usp_max: float = 0.0
        self.usp_min: float = 0.0
        self.usetp: float = 0.0
        self.cQ_min: float = 0.0
        self.cQ_max: float = 0.0
        self.phtech: int | None = None
        self.nneutral: int | None = None
        self.r0: float | None = None
        self.x0: float | None = None
        self.r2: float | None = None
        self.x2: float | None = None


# Alex review required: minimal source schema used to build the final three-phase VSC.
class ElmVsc(DGSElement):
    """Represent one native three-terminal voltage-source converter.

    DGS cubicles identify terminal zero as AC, terminal one as positive DC and
    terminal two as negative DC. The row keeps the exact native steady-state
    and equipment parameters needed to build the final VeraGrid ``VSC``.
    """

    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "for_name",
        "fold_id",
        "outserv",
        "Unom",
        "usetp",
        "psetp",
        "qsetp",
        "Pnold",
        "P_max",
        "Snom",
        "Pcu",
        "uk",
        "Rarm",
        "Larm",
        "mmcCmod",
        "NmmcSM",
        "MmmcSM",
        "iZarmDCside",
        "swtLossFactor",
        "resLossFactor",
        "usetpdc",
        "Unomdc",
        "vsctype",
        "Cdc",
        "i_acdc",
        "m_p_busac",
        "m_q_busac",
    )

    element_type = "ElmVsc"
    properties_list = [
        DgsProperty("FID", "a:40", "Unique identifier", py_name="ID"),
        DgsProperty("OP", "a:1", "DGS operation marker", py_name="OP"),
        DgsProperty("loc_name", "a:80", "Name", py_name="loc_name"),
        DgsProperty("for_name", "a:100", "Foreign key", py_name="for_name"),
        DgsProperty("fold_id", "p", "Parent folder", py_name="fold_id"),
        DgsProperty("outserv", "i", "Out-of-service flag", py_name="outserv"),
        DgsProperty("Unom", "r", "Nominal DC voltage in kV", py_name="Unom"),
        DgsProperty("usetp", "r", "AC voltage setpoint in p.u.", py_name="usetp"),
        DgsProperty("psetp", "r", "Active-power setpoint in MW", py_name="psetp"),
        DgsProperty("qsetp", "r", "Reactive-power setpoint in MVAr", py_name="qsetp"),
        DgsProperty("Pnold", "r", "No-load loss in kW", py_name="Pnold"),
        DgsProperty("P_max", "r", "Maximum active power in MW", py_name="P_max"),
        DgsProperty("Snom", "r", "Rated converter power in MVA", py_name="Snom", optional=True),
        DgsProperty("Pcu", "r", "Series-reactor copper losses in kW", py_name="Pcu", optional=True),
        DgsProperty("uk", "r", "Series-reactor short-circuit voltage in percent", py_name="uk", optional=True),
        DgsProperty("Rarm", "r", "MMC arm-reactor resistance in ohm", py_name="Rarm", optional=True),
        DgsProperty("Larm", "r", "MMC arm-reactor inductance in mH", py_name="Larm", optional=True),
        DgsProperty("mmcCmod", "r", "MMC submodule capacitance in uF", py_name="mmcCmod", optional=True),
        DgsProperty("NmmcSM", "i", "Number of MMC submodules per arm", py_name="NmmcSM", optional=True),
        DgsProperty("MmmcSM", "i", "Legacy MMC submodule count", py_name="MmmcSM", optional=True),
        DgsProperty("iZarmDCside", "i", "Place MMC arm reactor on the DC side", py_name="iZarmDCside", optional=True),
        DgsProperty("swtLossFactor", "r", "Switching loss factor in kW/A", py_name="swtLossFactor", optional=True),
        DgsProperty("resLossFactor", "r", "Resistive loss factor in ohm", py_name="resLossFactor", optional=True),
        DgsProperty("usetpdc", "r", "DC voltage setpoint in p.u.", py_name="usetpdc", optional=True),
        DgsProperty("Unomdc", "r", "Nominal DC voltage in kV", py_name="Unomdc", optional=True),
        DgsProperty("vsctype", "i", "Native converter topology selector", py_name="vsctype", optional=True),
        DgsProperty("Cdc", "r", "Two-level DC-link capacitance in uF", py_name="Cdc", optional=True),
        DgsProperty("i_acdc", "i", "Native AC/DC control-mode selector", py_name="i_acdc"),
        DgsProperty(
            "m:P:busac", "r", "Optional solved AC active-power evidence in MW",
            py_name="m_p_busac", optional=True,
        ),
        DgsProperty(
            "m:Q:busac", "r", "Optional solved AC reactive-power evidence in MVAr",
            py_name="m_q_busac", optional=True,
        ),
    ]

    def __init__(self) -> None:
        """Initialize one empty typed three-terminal converter row.

        :return: None.
        """
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.outserv: int = 0
        self.Unom: float = 0.0
        self.usetp: float = 1.0
        self.psetp: float = 0.0
        self.qsetp: float = 0.0
        self.Pnold: float = 0.0
        self.P_max: float = 0.0
        self.Snom: float | None = None
        self.Pcu: float | None = None
        self.uk: float | None = None
        self.Rarm: float | None = None
        self.Larm: float | None = None
        self.mmcCmod: float | None = None
        self.NmmcSM: int | None = None
        self.MmmcSM: int | None = None
        self.iZarmDCside: int | None = None
        self.swtLossFactor: float | None = None
        self.resLossFactor: float | None = None
        self.usetpdc: float | None = None
        self.Unomdc: float | None = None
        self.vsctype: int | None = None
        self.Cdc: float | None = None
        self.i_acdc: int = 5
        self.m_p_busac: float | None = None
        self.m_q_busac: float | None = None


# Alex review required: minimal source schema used to build the final monopolar VSC.
class ElmVscmono(DGSElement):
    """Represent one native two-terminal monopolar voltage-source converter."""

    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "for_name",
        "fold_id",
        "outserv",
        "Unom",
        "usetp",
        "psetp",
        "qsetp",
        "Pnold",
        "P_max",
        "Snom",
        "Pcu",
        "uk",
        "Rarm",
        "Larm",
        "mmcCmod",
        "NmmcSM",
        "MmmcSM",
        "iZarmDCside",
        "swtLossFactor",
        "resLossFactor",
        "usetpdc",
        "Unomdc",
        "vsctype",
        "Cdc",
        "i_acdc",
        "m_p_busac",
        "m_q_busac",
        "m_p_busdc",
        "m_q_busdc",
    )

    element_type = "ElmVscmono"
    properties_list = [
        DgsProperty("FID", "a:40", "Unique identifier", py_name="ID"),
        DgsProperty("OP", "a:1", "DGS operation marker", py_name="OP"),
        DgsProperty("loc_name", "a:80", "Name", py_name="loc_name"),
        DgsProperty("for_name", "a:100", "Foreign key", py_name="for_name"),
        DgsProperty("fold_id", "p", "Parent folder", py_name="fold_id"),
        DgsProperty("outserv", "i", "Out-of-service flag", py_name="outserv"),
        DgsProperty("Unom", "r", "Nominal converter voltage in kV", py_name="Unom"),
        DgsProperty("usetp", "r", "Voltage setpoint in p.u.", py_name="usetp"),
        DgsProperty("psetp", "r", "Active-power setpoint in MW", py_name="psetp"),
        DgsProperty("qsetp", "r", "Reactive-power setpoint in MVAr", py_name="qsetp"),
        DgsProperty("Pnold", "r", "No-load loss in kW", py_name="Pnold"),
        DgsProperty("P_max", "r", "Maximum active power in MW", py_name="P_max"),
        DgsProperty("Snom", "r", "Rated converter power in MVA", py_name="Snom", optional=True),
        DgsProperty("Pcu", "r", "Series-reactor copper losses in kW", py_name="Pcu", optional=True),
        DgsProperty("uk", "r", "Series-reactor short-circuit voltage in percent", py_name="uk", optional=True),
        DgsProperty("Rarm", "r", "MMC arm-reactor resistance in ohm", py_name="Rarm", optional=True),
        DgsProperty("Larm", "r", "MMC arm-reactor inductance in mH", py_name="Larm", optional=True),
        DgsProperty("mmcCmod", "r", "MMC submodule capacitance in uF", py_name="mmcCmod", optional=True),
        DgsProperty("NmmcSM", "i", "Number of MMC submodules per arm", py_name="NmmcSM", optional=True),
        DgsProperty("MmmcSM", "i", "Legacy MMC submodule count", py_name="MmmcSM", optional=True),
        DgsProperty("iZarmDCside", "i", "Place MMC arm reactor on the DC side", py_name="iZarmDCside", optional=True),
        DgsProperty("swtLossFactor", "r", "Switching loss factor in kW/A", py_name="swtLossFactor", optional=True),
        DgsProperty("resLossFactor", "r", "Resistive loss factor in ohm", py_name="resLossFactor", optional=True),
        DgsProperty("usetpdc", "r", "DC voltage setpoint in p.u.", py_name="usetpdc", optional=True),
        DgsProperty("Unomdc", "r", "Nominal DC voltage in kV", py_name="Unomdc", optional=True),
        DgsProperty("vsctype", "i", "Native converter topology selector", py_name="vsctype", optional=True),
        DgsProperty("Cdc", "r", "Two-level DC-link capacitance in uF", py_name="Cdc", optional=True),
        DgsProperty("i_acdc", "i", "Native AC/DC control-mode selector", py_name="i_acdc"),
        DgsProperty(
            "m:P:busac", "r", "Optional solved AC active-power evidence in MW",
            py_name="m_p_busac", optional=True,
        ),
        DgsProperty(
            "m:Q:busac", "r", "Optional solved AC reactive-power evidence in MVAr",
            py_name="m_q_busac", optional=True,
        ),
        DgsProperty(
            "m:P:busdc", "r", "Optional solved DC active-power evidence in MW",
            py_name="m_p_busdc", optional=True,
        ),
        DgsProperty(
            "m:Q:busdc", "r", "Optional solved DC reactive-power evidence in MVAr",
            py_name="m_q_busdc", optional=True,
        ),
    ]

    def __init__(self) -> None:
        """Initialize one empty typed monopolar converter row.

        :return: None.
        """
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.outserv: int = 0
        self.Unom: float = 0.0
        self.usetp: float = 1.0
        self.psetp: float = 0.0
        self.qsetp: float = 0.0
        self.Pnold: float = 0.0
        self.P_max: float = 0.0
        self.Snom: float | None = None
        self.Pcu: float | None = None
        self.uk: float | None = None
        self.Rarm: float | None = None
        self.Larm: float | None = None
        self.mmcCmod: float | None = None
        self.NmmcSM: int | None = None
        self.MmmcSM: int | None = None
        self.iZarmDCside: int | None = None
        self.swtLossFactor: float | None = None
        self.resLossFactor: float | None = None
        self.usetpdc: float | None = None
        self.Unomdc: float | None = None
        self.vsctype: int | None = None
        self.Cdc: float | None = None
        self.i_acdc: int = 5
        self.m_p_busac: float | None = None
        self.m_q_busac: float | None = None
        self.m_p_busdc: float | None = None
        self.m_q_busdc: float | None = None


class ElmLne(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "dline",
        "chr_name",
        "fline",
        "outserv",
        "pStoch",
        "for_name",
        "GPScoords_SIZEROW",
        "GPScoords_SIZECOL",
        "nlnum",
        "inAir",
    )
    element_type = 'ElmLne'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypLne', py_name='typ_id'),
        DgsProperty('dline', 'r', 'Line Length in km', py_name='dline'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('fline', 'r', 'Derating factor', py_name='fline'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('pStoch', 'p', 'Reference to Stochastic Model', py_name='pStoch'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('GPScoords:SIZEROW', 'i', 'Number of Stored GPS Coordinate Rows', py_name='GPScoords_SIZEROW'),
        DgsProperty('GPScoords:SIZECOL', 'i', 'Number of Stored GPS Coordinate Columns', py_name='GPScoords_SIZECOL'),
        DgsProperty('nlnum', 'i', 'Number of Parallel Line Systems', py_name='nlnum'),
        DgsProperty('inAir', 'i', 'Installation Flag: In Air: Underground/Other', py_name='inAir'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.dline: float = 0.0
        self.chr_name: str = ""
        self.fline: float = 1.0
        self.outserv: int = 0
        self.pStoch: str = ""
        self.for_name: str = ""
        self.GPScoords_SIZEROW: int = 0
        self.GPScoords_SIZECOL: int = 0
        self.nlnum: int = 1
        self.inAir: int = 0


class ElmZpu(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "for_name",
        "fold_id",
        "Sn",
        "ratfac",
        "r_pu",
        "x_pu",
        "r0_pu", "x0_pu", "r2_pu", "x2_pu", "iz2eqz1", "iequalz",
        "outserv",
    )
    element_type = 'ElmZpu'
    properties_list = [
        DgsProperty('FID', 'a:40', 'DGS field FID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('for_name', 'a:100', 'Foreign Key', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),

        DgsProperty('Sn', 'r', 'Rated Power in MVA', py_name='Sn'),
        DgsProperty('ratfac', 'r', 'Rating Factor', py_name='ratfac'),
        DgsProperty('r_pu', 'r', 'Positive-Sequence Impedance i-j: Real Part in p.u.',
                    py_name='r_pu'),
        DgsProperty('x_pu', 'r', 'Positive-Sequence Impedance i-j: Imaginary Part in p.u.',
                    py_name='x_pu'),
        DgsProperty('r0_pu', 'r', 'Zero-sequence resistance in p.u.', py_name='r0_pu', optional=True),
        DgsProperty('x0_pu', 'r', 'Zero-sequence reactance in p.u.', py_name='x0_pu', optional=True),
        DgsProperty('r2_pu', 'r', 'Negative-sequence resistance in p.u.', py_name='r2_pu', optional=True),
        DgsProperty('x2_pu', 'r', 'Negative-sequence reactance in p.u.', py_name='x2_pu', optional=True),
        DgsProperty('iz2eqz1', 'i', 'Negative-sequence impedance equals positive sequence',
                    py_name='iz2eqz1', optional=True),
        DgsProperty('iequalz', 'i', 'Equal forward and reverse series impedances',
                    py_name='iequalz', optional=True),

        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
    ]

    def __init__(self):
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""

        self.Sn: float = 0.0
        self.ratfac: float = 0.0
        self.r_pu: float = 0.0
        self.x_pu: float = 0.0
        self.r0_pu: float | None = None
        self.x0_pu: float | None = None
        self.r2_pu: float | None = None
        self.x2_pu: float | None = None
        self.iz2eqz1: int | None = None
        self.iequalz: int | None = None

        self.outserv: int = 0


class ElmScap(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "for_name",
        "fold_id",
        "ucn",
        "Curn",
        "xcap",
        "outserv",
    )
    element_type = 'ElmScap'
    properties_list = [
        DgsProperty('FID', 'a:40', 'DGS field FID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('for_name', 'a:100', 'Foreign Key', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),

        DgsProperty('ucn', 'r', 'Rated Voltage in kV', py_name='ucn'),
        DgsProperty('Curn', 'r', 'Rated Current in kA', py_name='Curn'),
        DgsProperty('xcap', 'r', 'Reactance 1/B in Ohm', py_name='xcap'),

        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
    ]

    def __init__(self):
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""

        self.ucn: float = 0.0
        self.Curn: float = 0.0
        self.xcap: float = 0.0

        self.outserv: int = 0


class ElmSind(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "for_name",
        "fold_id",
        "typ_id",
        "ucn",
        "Sn",
        "uk",
        "Pcu",
        "Rin",
        "initial_resistance_column_declared",
        "outserv",
    )
    element_type = 'ElmSind'
    properties_list = [
        # test_export_v5.dgs uses FID(...) not ID(...)
        DgsProperty('FID', 'a:40', 'DGS field FID (a:40)', py_name='ID'),
        # Optional alias (harmless if missing)
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),

        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('for_name', 'a:100', 'Foreign Key', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),

        DgsProperty('ucn', 'r', 'Rated Voltage in kV', py_name='ucn'),
        DgsProperty('Sn', 'r', 'Rated Power in MVA', py_name='Sn'),
        DgsProperty('uk', 'r', 'Short-Circuit Voltage uk in %', py_name='uk'),
        DgsProperty('Pcu', 'r', 'Copper Losses in kW', py_name='Pcu'),
        DgsProperty(
            's:Rin',
            'r',
            'Initial series resistance in Ohm',
            py_name='Rin',
            optional=True,
        ),

        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
    ]

    def __init__(self):
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""

        self.ucn: float = 0.0
        self.Sn: float = 0.0
        self.uk: float = 0.0
        self.Pcu: float = 0.0
        self.Rin: float | None = None
        self.initial_resistance_column_declared: bool = False

        self.outserv: int = 0


class TypSind(DGSElement):
    """PowerFactory Series Reactor type (TypSind)."""
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "Re",
        "Xe",
    )
    element_type = 'TypSind'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),

        # Type impedance parameters (same naming as ElmSind in many exports)
        DgsProperty('Re', 'r', 'Type series resistance (Re)', py_name='Re'),
        DgsProperty('Xe', 'r', 'Type series reactance (Xe)', py_name='Xe'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.Re: float = 0.0
        self.Xe: float = 0.0


class ComLdf(DGSElement):
    """PowerFactory Load Flow Calculation type (ComLdf)."""
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "iopt_pq",
    )
    element_type = 'ComLdf'
    properties_list = [
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('iopt_pq', 'i', 'Consider Voltage Dependency of Loads', py_name='iopt_pq'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.iopt_pq: int = 0


class ElmLnesec(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "chr_name",
        "dline",
        "fline",
        "index",
    )
    element_type = 'ElmLnesec'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Parent Line Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypLne', py_name='typ_id'),
        DgsProperty('chr_name', 'a', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('dline', 'r', 'Section Length in km', py_name='dline'),
        DgsProperty('fline', 'r', 'Section Derating Factor', py_name='fline'),
        DgsProperty('index', 'r', 'Section Order Index', py_name='index'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.dline: float = 0.0
        self.fline: float = 0.0
        self.index: float = 0.0


class ElmVac(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "for_name",
        "fold_id",
        "outserv",
        "itype",
        "Pload",
        "Qload",
        "Pgen",
        "Qgen",
        "Pzload",
        "Qzload",
    )
    element_type = 'ElmVac'
    properties_list = [
        DgsProperty('FID', 'a:40', 'DGS field FID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('for_name', 'a:100', 'Foreign Key', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),

        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('itype', 'i',
                    '0=Voltage Source, 1=Ideal RC-Source, 2=Ward Equivalent, 3=Extended Ward Equivalent',
                    py_name='itype'),

        DgsProperty('Pload', 'r', 'Constant P Load - Active Power in MW', py_name='Pload'),
        DgsProperty('Qload', 'r', 'Constant Q Load - Reactive Power in Mvar', py_name='Qload'),
        DgsProperty('Pgen', 'r', 'Generated Active Power in MW', py_name='Pgen'),
        DgsProperty('Qgen', 'r', 'Generated Reactive Power in Mvar', py_name='Qgen'),
        DgsProperty('Pzload', 'r', 'Constant Z Load - Active Power in MW', py_name='Pzload'),
        DgsProperty('Qzload', 'r', 'Constant Z Load - Reactive Power in Mvar', py_name='Qzload'),
    ]

    def __init__(self):
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""

        self.outserv: int = 0
        self.itype: int = 0

        self.Pload: float = 0.0
        self.Qload: float = 0.0
        self.Pgen: float = 0.0
        self.Qgen: float = 0.0
        self.Pzload: float = 0.0
        self.Qzload: float = 0.0


class ElmLod(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "chr_name",
        "plini",
        "plinir",
        "plinis",
        "plinit",
        "qlini",
        "qlinir",
        "qlinis",
        "qlinit",
        "scale0",
        "outserv",
        "i_sym",
        "for_name",
        "mode_inp",
        "slini",
        "coslini",
        "pf_recap",
        "i_scale",
        "classif",
        "phtech",
    )
    element_type = 'ElmLod'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        DgsProperty('chr_name', 'a:20', 'DGS field chr_name (a:20)', py_name='chr_name'),
        DgsProperty('plini', 'r', 'DGS field plini (r)', py_name='plini'),
        DgsProperty('plinir', 'r', 'DGS field plinir (r)', py_name='plinir'),
        DgsProperty('plinis', 'r', 'DGS field plinis (r)', py_name='plinis'),
        DgsProperty('plinit', 'r', 'DGS field plinit (r)', py_name='plinit'),
        DgsProperty('qlini', 'r', 'DGS field qlini (r)', py_name='qlini'),
        DgsProperty('qlinir', 'r', 'DGS field qlinir (r)', py_name='qlinir'),
        DgsProperty('qlinis', 'r', 'DGS field qlinis (r)', py_name='qlinis'),
        DgsProperty('qlinit', 'r', 'DGS field qlinit (r)', py_name='qlinit'),
        DgsProperty('scale0', 'r', 'DGS field scale0 (r)', py_name='scale0'),
        DgsProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        DgsProperty('i_sym', 'i', 'DGS field i_sym (i)', py_name='i_sym'),
        DgsProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        DgsProperty('mode_inp', 'a:3', 'DGS field mode_inp (a:3)', py_name='mode_inp'),
        DgsProperty('slini', 'r', 'DGS field slini (r)', py_name='slini'),
        DgsProperty('coslini', 'r', 'DGS field coslini (r)', py_name='coslini'),
        DgsProperty('pf_recap', 'i', 'DGS field pf_recap (i)', py_name='pf_recap'),
        DgsProperty('i_scale', 'i', 'DGS field i_scale (i)', py_name='i_scale'),
        DgsProperty('classif', 'a:20', 'DGS field classif (a:20)', py_name='classif'),
        DgsProperty('phtech', 'a', 'Phase and connection technology', py_name='phtech'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.plini: float = 0.0
        self.plinir: float = 0.0
        self.plinis: float = 0.0
        self.plinit: float = 0.0
        self.qlini: float = 0.0
        self.qlinir: float = 0.0
        self.qlinis: float = 0.0
        self.qlinit: float = 0.0
        self.scale0: float = 0.0
        self.outserv: int = 0
        self.i_sym: int = 0
        self.for_name: str = ""
        self.mode_inp: str = ""
        self.slini: float = 0.0
        self.coslini: float = 0.0
        self.pf_recap: int = 0
        self.i_scale: int = 0
        self.classif: str = ""
        self.phtech: str = ""


class ElmLodlv(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "chr_name",
        "for_name",
        "ulini",
    )
    element_type = 'ElmLodlv'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        DgsProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        DgsProperty('for_name', 'a', 'DGS field for_name (a)', py_name='for_name'),
        DgsProperty('ulini', 'r', 'DGS field ulini (r)', py_name='ulini'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.for_name: str = ""
        self.ulini: float = 0.0


class ElmLodlvp(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "chr_name",
        "for_name",
        "lneposkm",
        "outserv",
        "ulini",
    )
    element_type = 'ElmLodlvp'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        DgsProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        DgsProperty('for_name', 'a', 'DGS field for_name (a)', py_name='for_name'),
        DgsProperty('lneposkm', 'r', 'DGS field lneposkm (r)', py_name='lneposkm'),
        DgsProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
        DgsProperty('ulini', 'r', 'DGS field ulini (r)', py_name='ulini'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.for_name: str = ""
        self.lneposkm: float = 0.0
        self.outserv: int = 0
        self.ulini: float = 0.0


class ElmNet(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "frnom",
        "for_name",
        "pDiagram",
    )
    element_type = 'ElmNet'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('frnom', 'r', 'Nominal Frequency in Hz', py_name='frnom'),
        DgsProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        DgsProperty('pDiagram', 'p', 'Diagram in IntGrfnet', py_name='pDiagram'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.frnom: float = 0.0
        self.for_name: str = ""
        self.pDiagram: str = ""


class ElmShnt(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "chr_name",
        "shtype",
        "ushnm",
        "qcapn",
        "ncapx",
        "ncapa",
        "outserv",
        "qrean",
        "ctech",
        "fres",
        "greaf0",
        "grea",
        "iswitch",
        "qtotn",
        "tandc",
        "usetp",
        "rpara",
        "i_cont",
        "usetp_mx",
        "usetp_mn",
        "cgnd",
    )
    element_type = 'ElmShnt'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('shtype', 'i', 'Shunt Type Code', py_name='shtype'),
        DgsProperty('ushnm', 'r', 'Rated Voltage in kV', py_name='ushnm'),
        DgsProperty('qcapn', 'r', 'Rated Capacitive Reactive Power per Step in MVAr', py_name='qcapn'),
        DgsProperty('ncapx', 'i', 'Maximum Number of Capacitor Steps', py_name='ncapx'),
        DgsProperty('ncapa', 'i', 'Actual Number of Switched Capacitor Steps', py_name='ncapa'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('qrean', 'r', 'Rated Inductive Reactive Power per Step in MVAr', py_name='qrean'),
        DgsProperty('ctech', 'i', 'Connection Technology Code', py_name='ctech'),
        DgsProperty('fres', 'r', 'Resonance Frequency in Hz', py_name='fres'),
        DgsProperty('greaf0', 'r', 'Zero-Sequence Conductance in S', py_name='greaf0'),
        DgsProperty('grea', 'r', 'Positive-Sequence Conductance in S', py_name='grea'),
        DgsProperty('iswitch', 'i', 'Automatic Step Switching Enabled', py_name='iswitch'),
        DgsProperty('qtotn', 'r', 'Total Rated Reactive Power in MVAr', py_name='qtotn'),
        DgsProperty('tandc', 'r', 'Loss Factor tan(delta)', py_name='tandc'),
        # Voltage setpoint for controlled operation (p.u.). Not always present in the DGS header.
        # If absent in the file, it will remain at its default value (1.0).
        DgsProperty('usetp', 'r', 'Voltage Setpoint in p.u.', py_name='usetp'),
        DgsProperty('rpara', 'r', 'Parallel Damping Resistance in Ohm', py_name='rpara'),
        DgsProperty('i_cont', 'i', 'Tap Changer (Discrete=0, Continuous=1)', py_name='i_cont'),
        DgsProperty('usetp_mx', 'r', 'Upper Voltage Limit in p.u.', py_name='usetp_mx'),
        DgsProperty('usetp_mn', 'r', 'Lower Voltage Limit in p.u.', py_name='usetp_mn'),
        DgsProperty('cgnd', 'i', 'Star Point (Grounded=0, Neutral=1)', py_name='cgnd'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.shtype: int = 0
        self.ushnm: float = 0.0
        self.qcapn: float = 0.0
        self.ncapx: int = 0
        self.ncapa: int = 0
        self.outserv: int = 0
        self.qrean: float = 0.0
        self.ctech: int = 0
        self.fres: float = 0.0
        self.greaf0: float = 0.0
        self.grea: float = 0.0
        self.iswitch: int = 0
        self.qtotn: float = 0.0
        self.tandc: float = 0.0
        self.usetp: float = 1.0
        self.rpara: float = 0.0
        self.i_cont: int = 0
        self.usetp_mx: float = 1.0
        self.usetp_mn: float = 1.0
        self.cgnd: int = 0


class ElmSvs(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "chr_name",
        "qmin",
        "qmax",
        "tcrmax",
        "nxcap",
        "nfixcap",
        "Qfixcap",
        "outserv",
        "usetp",
        "ddroop",
        "Srated",
        "i_ctrl",
        "i_droop",
        "nncap",
        "tcrqact",
        "qsetp",
    )
    element_type = 'ElmSvs'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),

        # Reactive limits (MVAr @ v=1 p.u.)
        DgsProperty('qmin', 'r', 'Minimum Reactive Power at 1.0 p.u. in MVAr', py_name='qmin'),
        DgsProperty('qmax', 'r', 'Maximum Reactive Power at 1.0 p.u. in MVAr', py_name='qmax'),

        # PF SVS/SVC model-specific fields (kept for completeness)
        DgsProperty('tcrmax', 'r', 'Maximum TCR Reactive Absorption in MVAr', py_name='tcrmax'),
        DgsProperty('nxcap', 'i', 'Maximum Number of Switched Capacitor Steps', py_name='nxcap'),
        DgsProperty('nfixcap', 'i', 'Number of Fixed Capacitor Steps', py_name='nfixcap'),
        DgsProperty('Qfixcap', 'r', 'Reactive Power of Fixed Capacitor Part in MVAr', py_name='Qfixcap'),

        # Out of service flag (0/1)
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),

        # Voltage setpoint for controlled operation (p.u.). Not always present in the DGS header.
        # If absent in the file, it will remain at its default value (1.0).
        DgsProperty('usetp', 'r', 'Voltage Setpoint in p.u.', py_name='usetp'),

        DgsProperty('i_ctrl', 'i', 'Control mode', py_name='i_ctrl'),
        DgsProperty('i_droop', 'i', 'Droop control enabled?', py_name='i_droop'),
        DgsProperty('ddroop', 'r', 'Droop [%]', py_name='ddroop'),
        DgsProperty('Srated', 'r', 'Rated reactive power [Mvar]', py_name='Srated'),
        DgsProperty('nncap', 'i', 'Actual number of capacitors', py_name='nncap'),
        DgsProperty('tcrqact', 'r', 'Actual value of TCR [Mvar]', py_name='tcrqact'),
        DgsProperty('qsetp', 'r', 'Reactive Power Setpoint [Mvar]', py_name='qsetp'),
    ]

    def __init__(self) -> None:
        # Identifiers
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""

        # Operating limits (MVAr @ v=1 p.u.)
        self.qmin: float = 0.0
        self.qmax: float = 0.0

        # Thyristor controlled reactor max (PF SVC/SVS model-specific, may be unused in VeraGrid)
        self.tcrmax: float = 0.0

        # Step / block data (PF model-specific, may be used to infer an equivalent stepped model)
        self.nxcap: int = 0
        self.nfixcap: int = 0
        self.Qfixcap: float = 0.0

        # Status
        self.outserv: int = 0

        # Voltage setpoint (p.u.) for controlled shunts
        self.usetp: float = 1.0

        self.ddroop: float = 0.0  # Droop [%]
        self.Srated: float = 0.0  # Rated reactive power [Mvar]
        self.i_ctrl: int = 0  # Control mode
        self.i_droop: int = 0  # Droop control
        self.nncap: int = 0  # Actual number of capacitors
        self.tcrqact: float = 0.0  # Actual value of TCR [Mvar]
        self.qsetp: float = 0.0  # Reactive Power Setpoint [Mvar]


class ElmSite(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "for_name",
        "fold_id",
        "sType",
        "GPSlat",
        "GPSlon",
        "pDiagram",
    )
    element_type = 'ElmSite'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('sType', 'a:80', 'DGS field sType (a:80)', py_name='sType'),
        DgsProperty('GPSlat', 'r', 'DGS field GPSlat (r)', py_name='GPSlat'),
        DgsProperty('GPSlon', 'r', 'DGS field GPSlon (r)', py_name='GPSlon'),
        DgsProperty('pDiagram', 'p', 'Preferred static diagram in IntGrfnet', py_name='pDiagram'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.sType: str = ""
        self.GPSlat: float = 0.0
        self.GPSlon: float = 0.0
        self.pDiagram: str = ""


class ElmSubstat(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "Unom",
        "pRA",
        "for_name",
        "sShort",
        "sType",
        "GPSlat",
        "GPSlon",
        "cpArea",
        "cpZone",
        "pDiagram",
    )
    element_type = 'ElmSubstat'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'Operation flag', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('Unom', 'r', 'DGS field Unom (r)', py_name='Unom'),
        DgsProperty('pRA', 'p', 'DGS field pRA (p)', py_name='pRA'),
        DgsProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        DgsProperty('sShort', 'a:24', 'DGS field sShort (a:6)', py_name='sShort'),
        DgsProperty('sType', 'a:160', 'DGS field sType (a:80)', py_name='sType'),
        DgsProperty('GPSlat', 'r', 'Latitude / Northing in deg', py_name='GPSlat'),
        DgsProperty('GPSlon', 'r', 'Longitude / Easting in deg', py_name='GPSlon'),
        DgsProperty('cpArea', 'p', 'Default Area in ElmArea', py_name='cpArea'),
        DgsProperty('cpZone', 'p', 'Default Zone in ElmZone', py_name='cpZone'),
        DgsProperty('pDiagram', 'p', 'Preferred static diagram in IntGrfnet', py_name='pDiagram'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.Unom: float = 0.0
        self.pRA: str = ""
        self.for_name: str = ""
        self.sShort: str = ""
        self.sType: str = ""
        self.GPSlat: float = 0.0
        self.GPSlon: float = 0.0
        self.cpArea: str = ""
        self.cpZone: str = ""
        self.pDiagram: str = ""


class ElmSym(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "ngnum",
        "i_mot",
        "chr_name",
        "outserv",
        "pgini",
        "qgini",
        "usetp",
        "iv_mode",
        "q_min",
        "q_max",
        "Pmin_uc",
        "Pmax_uc",
        "iqtype",
        "for_name",
        "cCategory",
        "cosgini",
        "pf_recap",
        "av_mode",
        "phtech",
        "ip_ctrl",
        "c_pmod",
    )
    element_type = 'ElmSym'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypSym', py_name='typ_id'),
        DgsProperty('ngnum', 'i', 'Number of Parallel Machines', py_name='ngnum'),
        DgsProperty('i_mot', 'i', 'Operating Mode: Generator:Motor', py_name='i_mot'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('pgini', 'r', 'Active Power Setpoint in MW', py_name='pgini'),
        DgsProperty('qgini', 'r', 'Reactive Power Setpoint in MVAr', py_name='qgini'),
        DgsProperty('usetp', 'r', 'Voltage Setpoint in p.u.', py_name='usetp'),
        DgsProperty('iv_mode', 'i', 'Voltage Control Mode Code', py_name='iv_mode'),
        DgsProperty('q_min', 'r', 'Minimum Reactive Power Limit in MVAr', py_name='q_min'),
        DgsProperty('q_max', 'r', 'Maximum Reactive Power Limit in MVAr', py_name='q_max'),
        DgsProperty('Pmin_uc', 'r', 'Minimum Active Power Limit in MW', py_name='Pmin_uc'),
        DgsProperty('Pmax_uc', 'r', 'Maximum Active Power Limit in MW', py_name='Pmax_uc'),
        DgsProperty('iqtype', 'i', 'Reactive Power Capability Mode Code', py_name='iqtype'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('cCategory', 'a', 'Generator Category', py_name='cCategory'),
        DgsProperty('cosgini', 'r', 'Initial Power Factor', py_name='cosgini'),
        DgsProperty('pf_recap', 'i', 'Power Factor Sign: Overexcited:Underexcited', py_name='pf_recap'),
        DgsProperty('av_mode', 'a', 'Active Power Control Mode', py_name='av_mode'),
        DgsProperty('phtech', 'i', 'Phase Technology Code', py_name='phtech'),
        DgsProperty('ip_ctrl', 'i', 'Reference machine', py_name='ip_ctrl'),
        DgsProperty('c_pmod', 'a:40', 'plant model', py_name='c_pmod'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.ngnum: int = 1
        self.i_mot: int = 0
        self.chr_name: str = ""
        self.outserv: int = 0
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.usetp: float = 0.0
        self.iv_mode: int = 0
        self.q_min: float = 0.0
        self.q_max: float = 0.0
        self.Pmin_uc: float = 0.0
        self.Pmax_uc: float = 0.0
        self.iqtype: int = 0
        self.for_name: str = ""
        self.cCategory: str = ""
        self.cosgini: float = 0.0
        self.pf_recap: int = 0
        self.av_mode: str = ""
        self.phtech: int = 0
        self.ip_ctrl: int = 0
        self.c_pmod: str = ""


class ElmTerm(DGSElement):
    """

    *  FID: Unique identifier for DGS file
    *  OP: Operation (C=create, U=update, D=delete, M=merge, I=ignore)
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypBar
    *  systype: System Type:AC:DC:AC/BI
    *  iUsage: Usage:Busbar:Junction Node:Internal Node
    *  uknom: Nominal Voltage: Line-Line in kV
    *  unknom: Nominal Voltage: Line-Ground in kV
    *  iminus: Nominal Voltage: DC-Polarity:positive (+):negative (-):neutral
    *  outserv: Out of Service
    *  GPSlat: Geographical Position: Latitude / Northing in deg
    *  GPSlon: Geographical Position: Longitude / Easting in deg
    *  vtarget: Voltage Control: Target Voltage in p.u.

    """
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "iUsage",
        "uknom",
        "chr_name",
        "outserv",
        "phtech",
        "for_name",
        "systype",
        "unknom",
        "iminus",
        "GPSlat",
        "GPSlon",
        "vtarget",
        "m_u",
        "m_phiu",
        "cpArea",
        "cpZone",
        "cpGrid",
        "cpSubstat",
        "cpSite",
        "bustp"
    )
    element_type = 'ElmTerm'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypBar', py_name='typ_id'),
        DgsProperty('iUsage', 'i', 'Usage: Busbar:Junction Node:Internal Node', py_name='iUsage'),
        DgsProperty('uknom', 'r', 'Nominal Voltage Line-Line in kV', py_name='uknom'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('cpArea', 'p', 'Area in ElmArea', py_name='cpArea'),
        DgsProperty('cpZone', 'p', 'Zone in ElmZone', py_name='cpZone'),
        DgsProperty('cpGrid', 'p', 'Owning network in ElmNet', py_name='cpGrid'),
        DgsProperty('cpSubstat', 'p', 'Owning substation in ElmSubstat', py_name='cpSubstat'),
        DgsProperty('cpSite', 'p', 'Owning site in ElmSite', py_name='cpSite'),
        DgsProperty('phtech', 'i', 'Phase Technology Code', py_name='phtech'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('systype', 'i', 'System Type: AC:DC:AC/BI', py_name='systype'),
        DgsProperty('unknom', 'r', 'Nominal Voltage Line-Ground in kV', py_name='unknom'),
        DgsProperty('iminus', 'i', 'DC Polarity: Positive:Negative:Neutral', py_name='iminus'),
        DgsProperty('GPSlat', 'r', 'Latitude / Northing in deg', py_name='GPSlat'),
        DgsProperty('GPSlon', 'r', 'Longitude / Easting in deg', py_name='GPSlon'),
        DgsProperty('vtarget', 'r', 'Voltage Control Target in p.u.', py_name='vtarget'),
        DgsProperty('m:u', 'r', 'Measured Voltage Magnitude in p.u.', py_name='m_u'),
        DgsProperty('m:phiu', 'r', 'Measured Voltage Angle in deg', py_name='m_phiu'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.iUsage: int = 0
        self.uknom: float = 0.0
        self.chr_name: str = ""
        self.outserv: int = 0
        self.phtech: int = 0
        self.for_name: str = ""
        self.systype: int = 0
        self.unknom: float = 0.0
        self.iminus: int = 0
        self.GPSlat: float = 0.0
        self.GPSlon: float = 0.0
        self.vtarget: float = 0.0
        self.m_u: float = 0.0
        self.m_phiu: float = 0.0
        self.cpArea: str = ""
        self.cpZone: str = ""
        self.cpGrid: str = ""
        self.cpSubstat: str = ""
        self.cpSite: str = ""
        self.bustp = ""


class ElmTr2(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "outserv",
        "nntap",
        "sernum",
        "constr",
        "chr_name",
        "cgnd_h",
        "cgnd_l",
        "i_auto",
        "ntrcn",
        "ratfac",
        "for_name",
        "ntnum",
        "usetp",
        "usp_low",
        "usp_up",
        "t2ldc",
        "mTaps_SIZEROW",
        "mTaps_SIZECOL",
        "i_eahv",
        "i_ealv",
    )
    element_type = 'ElmTr2'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypTr2', py_name='typ_id'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('nntap', 'i', 'Tap Changer 1: Tap Position', py_name='nntap'),
        DgsProperty('sernum', 'a:20', 'Serial Number (a:20)', py_name='sernum'),
        DgsProperty('constr', 'i', 'Year of Construction', py_name='constr'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('cgnd_h', 'i', 'Internal Grounding Impedance, HV Side: Star Point:Connected:Not connected',
                    py_name='cgnd_h'),
        DgsProperty('cgnd_l', 'i', 'Internal Grounding Impedance, LV Side: Star Point:Connected:Not connected',
                    py_name='cgnd_l'),
        DgsProperty('i_auto', 'i', 'Auto Transformer', py_name='i_auto'),
        DgsProperty('ntrcn', 'i', 'Controller, Tap Changer 1: Automatic Tap Changing', py_name='ntrcn'),
        DgsProperty('ratfac', 'r', 'Rating Factor', py_name='ratfac'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('ntnum', 'i', 'Number of Parallel Transformers', py_name='ntnum'),
        DgsProperty('usetp', 'r', 'Voltage Setpoint in p.u.', py_name='usetp'),
        DgsProperty('usp_low', 'r', 'Lower Voltage Band in p.u.', py_name='usp_low'),
        DgsProperty('usp_up', 'r', 'Upper Voltage Band in p.u.', py_name='usp_up'),
        DgsProperty('t2ldc', 'i', 'Line Drop Compensation Enabled', py_name='t2ldc'),
        DgsProperty('mTaps_SIZEROW', 'i', 'Number of Stored Tap Table Rows', py_name='mTaps_SIZEROW'),
        DgsProperty('mTaps_SIZECOL', 'i', 'Number of Stored Tap Table Columns', py_name='mTaps_SIZECOL'),
        DgsProperty('i_eahv', 'i', 'HV-side, phase 2 internally grounded.', py_name='i_eahv'),
        DgsProperty('i_ealv', 'i', 'LV-side, phase 2 internally grounded.', py_name='i_ealv'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.nntap: int = 0
        self.sernum: str = ""
        self.constr: int = 0
        self.chr_name: str = ""
        self.cgnd_h: int = 0
        self.cgnd_l: int = 0
        self.i_auto: int = 0
        self.ntrcn: int = 0
        self.ratfac: float = 1.0
        self.for_name: str = ""
        self.ntnum: int = 1
        self.usetp: float = 0.0
        self.usp_low: float = 0.0
        self.usp_up: float = 0.0
        self.t2ldc: int = 0
        self.mTaps_SIZEROW: int = 0
        self.mTaps_SIZECOL: int = 0
        self.i_eahv: int = 0
        self.i_ealv: int = 0


class ElmTr3(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "outserv",
        "nt3nm",
        "n3tap_h",
        "n3tap_m",
        "n3tap_l",
        "chr_name",
        "for_name",
        "i_auto_hl",
        "ictrlside",
        "ntrcn",
        "t3ldc",
        "usetp",
        "usp_low",
        "usp_up",
        "mTaps_SIZEROW",
        "mTaps_SIZECOL",
        "mTaps_0_0",
        "mTaps_0_1",
        "mTaps_0_2",
        "mTaps_0_3",
        "mTaps_0_4",
        "mTaps_0_5",
        "mTaps_0_6",
        "mTaps_0_7",
        "mTaps_1_0",
        "mTaps_1_1",
        "mTaps_1_2",
        "mTaps_1_3",
        "mTaps_1_4",
        "mTaps_1_5",
        "mTaps_1_6",
        "mTaps_1_7",
        "mTaps_2_0",
        "mTaps_2_1",
        "mTaps_2_2",
        "mTaps_2_3",
        "mTaps_2_4",
        "mTaps_2_5",
        "mTaps_2_6",
        "mTaps_2_7",
        "iMeasTap",
    )
    element_type = 'ElmTr3'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypTr3', py_name='typ_id'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('nt3nm', 'i', 'Number of Parallel Transformers', py_name='nt3nm'),
        DgsProperty('n3tap_h', 'i', 'Tap Position at HV Side', py_name='n3tap_h'),
        DgsProperty('n3tap_m', 'i', 'Tap Position at MV Side', py_name='n3tap_m'),
        DgsProperty('n3tap_l', 'i', 'Tap Position at LV Side', py_name='n3tap_l'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('i_auto_hl', 'i', 'Autotransformer Flag for HV-LV Coupling', py_name='i_auto_hl'),
        DgsProperty('ictrlside', 'i', 'Controlled Side for Automatic Tap Changing', py_name='ictrlside'),
        DgsProperty('ntrcn', 'i', 'Automatic Tap Changing Enabled', py_name='ntrcn'),
        DgsProperty('t3ldc', 'i', 'Line Drop Compensation Enabled', py_name='t3ldc'),
        DgsProperty('usetp', 'r', 'Voltage Setpoint in p.u.', py_name='usetp'),
        DgsProperty('usp_low', 'r', 'Lower Voltage Band in p.u.', py_name='usp_low'),
        DgsProperty('usp_up', 'r', 'Upper Voltage Band in p.u.', py_name='usp_up'),
        DgsProperty('mTaps:SIZEROW', 'i', 'Number of Stored Tap Table Rows', py_name='mTaps_SIZEROW'),
        DgsProperty('mTaps:SIZECOL', 'i', 'Number of Stored Tap Table Columns', py_name='mTaps_SIZECOL'),
        DgsProperty('mTaps:0:0', 'r', 'Tap Table Entry Row 0 Column 0', py_name='mTaps_0_0'),
        DgsProperty('mTaps:0:1', 'r', 'Tap Table Entry Row 0 Column 1', py_name='mTaps_0_1'),
        DgsProperty('mTaps:0:2', 'r', 'Tap Table Entry Row 0 Column 2', py_name='mTaps_0_2'),
        DgsProperty('mTaps:0:3', 'r', 'Tap Table Entry Row 0 Column 3', py_name='mTaps_0_3'),
        DgsProperty('mTaps:0:4', 'r', 'Tap Table Entry Row 0 Column 4', py_name='mTaps_0_4'),
        DgsProperty('mTaps:0:5', 'r', 'Tap Table Entry Row 0 Column 5', py_name='mTaps_0_5'),
        DgsProperty('mTaps:0:6', 'r', 'Tap Table Entry Row 0 Column 6', py_name='mTaps_0_6'),
        DgsProperty('mTaps:0:7', 'r', 'Tap Table Entry Row 0 Column 7', py_name='mTaps_0_7'),
        DgsProperty('mTaps:1:0', 'r', 'Tap Table Entry Row 1 Column 0', py_name='mTaps_1_0'),
        DgsProperty('mTaps:1:1', 'r', 'Tap Table Entry Row 1 Column 1', py_name='mTaps_1_1'),
        DgsProperty('mTaps:1:2', 'r', 'Tap Table Entry Row 1 Column 2', py_name='mTaps_1_2'),
        DgsProperty('mTaps:1:3', 'r', 'Tap Table Entry Row 1 Column 3', py_name='mTaps_1_3'),
        DgsProperty('mTaps:1:4', 'r', 'Tap Table Entry Row 1 Column 4', py_name='mTaps_1_4'),
        DgsProperty('mTaps:1:5', 'r', 'Tap Table Entry Row 1 Column 5', py_name='mTaps_1_5'),
        DgsProperty('mTaps:1:6', 'r', 'Tap Table Entry Row 1 Column 6', py_name='mTaps_1_6'),
        DgsProperty('mTaps:1:7', 'r', 'Tap Table Entry Row 1 Column 7', py_name='mTaps_1_7'),
        DgsProperty('mTaps:2:0', 'r', 'Tap Table Entry Row 2 Column 0', py_name='mTaps_2_0'),
        DgsProperty('mTaps:2:1', 'r', 'Tap Table Entry Row 2 Column 1', py_name='mTaps_2_1'),
        DgsProperty('mTaps:2:2', 'r', 'Tap Table Entry Row 2 Column 2', py_name='mTaps_2_2'),
        DgsProperty('mTaps:2:3', 'r', 'Tap Table Entry Row 2 Column 3', py_name='mTaps_2_3'),
        DgsProperty('mTaps:2:4', 'r', 'Tap Table Entry Row 2 Column 4', py_name='mTaps_2_4'),
        DgsProperty('mTaps:2:5', 'r', 'Tap Table Entry Row 2 Column 5', py_name='mTaps_2_5'),
        DgsProperty('mTaps:2:6', 'r', 'Tap Table Entry Row 2 Column 6', py_name='mTaps_2_6'),
        DgsProperty('mTaps:2:7', 'r', 'Tap Table Entry Row 2 Column 7', py_name='mTaps_2_7'),
        DgsProperty('iMeasTap', 'i', 'Tap Position Used for Measurement', py_name='iMeasTap'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.nt3nm: int = 0
        self.n3tap_h: int = 0
        self.n3tap_m: int = 0
        self.n3tap_l: int = 0
        self.chr_name: str = ""
        self.for_name: str = ""
        self.i_auto_hl: int = 0
        self.ictrlside: int = 0
        self.ntrcn: int = 0
        self.t3ldc: int = 0
        self.usetp: float = 0.0
        self.usp_low: float = 0.0
        self.usp_up: float = 0.0
        self.mTaps_SIZEROW: int = 0
        self.mTaps_SIZECOL: int = 0
        self.mTaps_0_0: float = 0.0
        self.mTaps_0_1: float = 0.0
        self.mTaps_0_2: float = 0.0
        self.mTaps_0_3: float = 0.0
        self.mTaps_0_4: float = 0.0
        self.mTaps_0_5: float = 0.0
        self.mTaps_0_6: float = 0.0
        self.mTaps_0_7: float = 0.0
        self.mTaps_1_0: float = 0.0
        self.mTaps_1_1: float = 0.0
        self.mTaps_1_2: float = 0.0
        self.mTaps_1_3: float = 0.0
        self.mTaps_1_4: float = 0.0
        self.mTaps_1_5: float = 0.0
        self.mTaps_1_6: float = 0.0
        self.mTaps_1_7: float = 0.0
        self.mTaps_2_0: float = 0.0
        self.mTaps_2_1: float = 0.0
        self.mTaps_2_2: float = 0.0
        self.mTaps_2_3: float = 0.0
        self.mTaps_2_4: float = 0.0
        self.mTaps_2_5: float = 0.0
        self.mTaps_2_6: float = 0.0
        self.mTaps_2_7: float = 0.0
        self.iMeasTap: int = 0


class ElmTr4(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "typ_id",
        "outserv",
        "nt4nm",
        "ictrlside",
        "ntrcn",
        "usetp",
        "usp_low",
        "usp_up",
        "chr_name",
        "for_name",
        "Inom_l3",
        "Inom_l2",
        "Inom_l1",
        "Inom_h0",
        "Snom_l3",
        "Snom_l2",
        "Snom_l1",
        "Snom_h0",
        "Snom_l3_a",
        "Snom_l2_a",
        "Snom_l1_a",
        "Snom_h0_a",
        "xSbasepu_lv3",
        "xSbasepu_lv2",
        "xSbasepu_lv1",
        "xSbasepu_hv0",
        "rSbasepu_lv3",
        "rSbasepu_lv2",
        "rSbasepu_lv1",
        "rSbasepu_hv0",
        "xSbasepu_l2l3",
        "xSbasepu_l1l3",
        "xSbasepu_l1l2",
        "xSbasepu_h0l3",
        "xSbasepu_h0l2",
        "xSbasepu_h0l1",
        "rSbasepu_l2l3",
        "rSbasepu_l1l3",
        "rSbasepu_l1l2",
        "rSbasepu_h0l3",
        "rSbasepu_h0l2",
        "rSbasepu_h0l1",
        "x0Sbasepu_lv3",
        "x0Sbasepu_lv2",
        "x0Sbasepu_lv1",
        "x0Sbasepu_hv0",
        "r0Sbasepu_lv3",
        "r0Sbasepu_lv2",
        "r0Sbasepu_lv1",
        "r0Sbasepu_hv0",
        "bSbasepu",
        "pT_lv3",
        "pT_lv2",
        "pT_lv1",
        "pT_hv0",
        "i_tapini_lv3",
        "i_tapini_lv2",
        "i_tapini_lv1",
        "i_tapini_hv0",
        "ntap_h0",
        "ntap_l1",
        "ntap_l2",
        "ntap_l3",
        "busl3",
        "busl2",
        "busl1",
        "bush0",
        "cpSubstat",
        "cpArea",
        "cpZone",
        "cpGrid",
        "GPSlon",
        "GPSlat",
        "maxload",
        "ratfac_l3",
        "ratfac_l2",
        "ratfac_l1",
        "ratfac_h0",
        "desc_0",
        "desc_1",
        "desc_2",
        "desc_3",
        "commissionDate",
        "sernum",
        "dat_src",
    )
    element_type = 'ElmTr4'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('OP', 'a:1', 'Operation flag', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'Type in TypTr4', py_name='typ_id'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('nt4nm', 'i', 'Number of parallel transformers', py_name='nt4nm'),

        DgsProperty('ictrlside', 'i', 'Controlled Side', py_name='ictrlside'),
        DgsProperty('ntrcn', 'i', 'Control Node Number', py_name='ntrcn'),
        DgsProperty('usetp', 'r', 'Voltage Setpoint in p.u.', py_name='usetp'),
        DgsProperty('usp_low', 'r', 'Lower Voltage Setpoint Limit in p.u.', py_name='usp_low'),
        DgsProperty('usp_up', 'r', 'Upper Voltage Setpoint Limit in p.u.', py_name='usp_up'),
        DgsProperty('chr_name', 'a:40', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('for_name', 'a:100', 'Foreign Key', py_name='for_name'),

        DgsProperty('Inom_l3', 'r', 'Nominal Current LV3 in kA', py_name='Inom_l3'),
        DgsProperty('Inom_l2', 'r', 'Nominal Current LV2 in kA', py_name='Inom_l2'),
        DgsProperty('Inom_l1', 'r', 'Nominal Current LV1 in kA', py_name='Inom_l1'),
        DgsProperty('Inom_h0', 'r', 'Nominal Current HV in kA', py_name='Inom_h0'),

        DgsProperty('Snom_l3', 'r', 'Nominal Power LV3 in MVA', py_name='Snom_l3'),
        DgsProperty('Snom_l2', 'r', 'Nominal Power LV2 in MVA', py_name='Snom_l2'),
        DgsProperty('Snom_l1', 'r', 'Nominal Power LV1 in MVA', py_name='Snom_l1'),
        DgsProperty('Snom_h0', 'r', 'Nominal Power HV in MVA', py_name='Snom_h0'),

        DgsProperty('Snom_l3_a', 'r', 'Actual Nominal Power LV3 in MVA', py_name='Snom_l3_a'),
        DgsProperty('Snom_l2_a', 'r', 'Actual Nominal Power LV2 in MVA', py_name='Snom_l2_a'),
        DgsProperty('Snom_l1_a', 'r', 'Actual Nominal Power LV1 in MVA', py_name='Snom_l1_a'),
        DgsProperty('Snom_h0_a', 'r', 'Actual Nominal Power HV in MVA', py_name='Snom_h0_a'),

        DgsProperty('xSbasepu_lv3', 'r', 'Positive Sequence Reactance LV3 in p.u.', py_name='xSbasepu_lv3'),
        DgsProperty('xSbasepu_lv2', 'r', 'Positive Sequence Reactance LV2 in p.u.', py_name='xSbasepu_lv2'),
        DgsProperty('xSbasepu_lv1', 'r', 'Positive Sequence Reactance LV1 in p.u.', py_name='xSbasepu_lv1'),
        DgsProperty('xSbasepu_hv0', 'r', 'Positive Sequence Reactance HV in p.u.', py_name='xSbasepu_hv0'),

        DgsProperty('rSbasepu_lv3', 'r', 'Positive Sequence Resistance LV3 in p.u.', py_name='rSbasepu_lv3'),
        DgsProperty('rSbasepu_lv2', 'r', 'Positive Sequence Resistance LV2 in p.u.', py_name='rSbasepu_lv2'),
        DgsProperty('rSbasepu_lv1', 'r', 'Positive Sequence Resistance LV1 in p.u.', py_name='rSbasepu_lv1'),
        DgsProperty('rSbasepu_hv0', 'r', 'Positive Sequence Resistance HV in p.u.', py_name='rSbasepu_hv0'),

        DgsProperty('xSbasepu_l2l3', 'r', 'Positive Sequence Reactance LV2-LV3 in p.u.', py_name='xSbasepu_l2l3'),
        DgsProperty('xSbasepu_l1l3', 'r', 'Positive Sequence Reactance LV1-LV3 in p.u.', py_name='xSbasepu_l1l3'),
        DgsProperty('xSbasepu_l1l2', 'r', 'Positive Sequence Reactance LV1-LV2 in p.u.', py_name='xSbasepu_l1l2'),
        DgsProperty('xSbasepu_h0l3', 'r', 'Positive Sequence Reactance HV-LV3 in p.u.', py_name='xSbasepu_h0l3'),
        DgsProperty('xSbasepu_h0l2', 'r', 'Positive Sequence Reactance HV-LV2 in p.u.', py_name='xSbasepu_h0l2'),
        DgsProperty('xSbasepu_h0l1', 'r', 'Positive Sequence Reactance HV-LV1 in p.u.', py_name='xSbasepu_h0l1'),

        DgsProperty('rSbasepu_l2l3', 'r', 'Positive Sequence Resistance LV2-LV3 in p.u.', py_name='rSbasepu_l2l3'),
        DgsProperty('rSbasepu_l1l3', 'r', 'Positive Sequence Resistance LV1-LV3 in p.u.', py_name='rSbasepu_l1l3'),
        DgsProperty('rSbasepu_l1l2', 'r', 'Positive Sequence Resistance LV1-LV2 in p.u.', py_name='rSbasepu_l1l2'),
        DgsProperty('rSbasepu_h0l3', 'r', 'Positive Sequence Resistance HV-LV3 in p.u.', py_name='rSbasepu_h0l3'),
        DgsProperty('rSbasepu_h0l2', 'r', 'Positive Sequence Resistance HV-LV2 in p.u.', py_name='rSbasepu_h0l2'),
        DgsProperty('rSbasepu_h0l1', 'r', 'Positive Sequence Resistance HV-LV1 in p.u.', py_name='rSbasepu_h0l1'),

        DgsProperty('x0Sbasepu_lv3', 'r', 'Zero Sequence Reactance LV3 in p.u.', py_name='x0Sbasepu_lv3'),
        DgsProperty('x0Sbasepu_lv2', 'r', 'Zero Sequence Reactance LV2 in p.u.', py_name='x0Sbasepu_lv2'),
        DgsProperty('x0Sbasepu_lv1', 'r', 'Zero Sequence Reactance LV1 in p.u.', py_name='x0Sbasepu_lv1'),
        DgsProperty('x0Sbasepu_hv0', 'r', 'Zero Sequence Reactance HV in p.u.', py_name='x0Sbasepu_hv0'),

        DgsProperty('r0Sbasepu_lv3', 'r', 'Zero Sequence Resistance LV3 in p.u.', py_name='r0Sbasepu_lv3'),
        DgsProperty('r0Sbasepu_lv2', 'r', 'Zero Sequence Resistance LV2 in p.u.', py_name='r0Sbasepu_lv2'),
        DgsProperty('r0Sbasepu_lv1', 'r', 'Zero Sequence Resistance LV1 in p.u.', py_name='r0Sbasepu_lv1'),
        DgsProperty('r0Sbasepu_hv0', 'r', 'Zero Sequence Resistance HV in p.u.', py_name='r0Sbasepu_hv0'),

        DgsProperty('bSbasepu', 'r', 'Magnetizing Susceptance in p.u.', py_name='bSbasepu'),

        DgsProperty('pT_lv3', 'a', 'Tap Position LV3', py_name='pT_lv3'),
        DgsProperty('pT_lv2', 'a', 'Tap Position LV2', py_name='pT_lv2'),
        DgsProperty('pT_lv1', 'a', 'Tap Position LV1', py_name='pT_lv1'),
        DgsProperty('pT_hv0', 'a', 'Tap Position HV', py_name='pT_hv0'),

        DgsProperty('ntap_h0', 'i', 'Tap position HV', py_name='ntap_h0'),
        DgsProperty('ntap_l1', 'i', 'Tap position LV1', py_name='ntap_l1'),
        DgsProperty('ntap_l2', 'i', 'Tap position LV2', py_name='ntap_l2'),
        DgsProperty('ntap_l3', 'i', 'Tap position LV3', py_name='ntap_l3'),

        DgsProperty('i_tapini_lv3', 'i', 'Initial Tap Position LV3', py_name='i_tapini_lv3'),
        DgsProperty('i_tapini_lv2', 'i', 'Initial Tap Position LV2', py_name='i_tapini_lv2'),
        DgsProperty('i_tapini_lv1', 'i', 'Initial Tap Position LV1', py_name='i_tapini_lv1'),
        DgsProperty('i_tapini_hv0', 'i', 'Initial Tap Position HV', py_name='i_tapini_hv0'),

        DgsProperty('busl3', 'p', 'LV3 Terminal in ElmTerm', py_name='busl3'),
        DgsProperty('busl2', 'p', 'LV2 Terminal in ElmTerm', py_name='busl2'),
        DgsProperty('busl1', 'p', 'LV1 Terminal in ElmTerm', py_name='busl1'),
        DgsProperty('bush0', 'p', 'HV Terminal in ElmTerm', py_name='bush0'),

        DgsProperty('cpSubstat', 'p', 'Substation in ElmSubstat', py_name='cpSubstat'),
        DgsProperty('cpArea', 'p', 'Area in ElmArea', py_name='cpArea'),
        DgsProperty('cpZone', 'p', 'Zone in ElmZone', py_name='cpZone'),
        DgsProperty('cpGrid', 'p', 'Grid Reference', py_name='cpGrid'),

        DgsProperty('GPSlon', 'r', 'Longitude / Easting in deg', py_name='GPSlon'),
        DgsProperty('GPSlat', 'r', 'Latitude / Northing in deg', py_name='GPSlat'),

        DgsProperty('maxload', 'r', 'Maximum Loading in percent', py_name='maxload'),
        DgsProperty('ratfac_l3', 'r', 'Rating Factor LV3', py_name='ratfac_l3'),
        DgsProperty('ratfac_l2', 'r', 'Rating Factor LV2', py_name='ratfac_l2'),
        DgsProperty('ratfac_l1', 'r', 'Rating Factor LV1', py_name='ratfac_l1'),
        DgsProperty('ratfac_h0', 'r', 'Rating Factor HV', py_name='ratfac_h0'),

        DgsProperty('desc:0', 'a', 'Description Line 0', py_name='desc_0'),
        DgsProperty('desc:1', 'a', 'Description Line 1', py_name='desc_1'),
        DgsProperty('desc:2', 'a', 'Description Line 2', py_name='desc_2'),
        DgsProperty('desc:3', 'a', 'Description Line 3', py_name='desc_3'),

        DgsProperty('commissionDate', 'a:21', 'Commissioning Date', py_name='commissionDate'),
        DgsProperty('sernum', 'a:40', 'Serial Number', py_name='sernum'),
        DgsProperty('dat_src', 'a:6', 'Data Source', py_name='dat_src'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.outserv: int = 0
        self.nt4nm: int = 1

        self.ictrlside: int = 0
        self.ntrcn: int = 0
        self.usetp: float = 0.0
        self.usp_low: float = 0.0
        self.usp_up: float = 0.0
        self.chr_name: str = ""
        self.for_name: str = ""

        self.Inom_l3: float = 0.0
        self.Inom_l2: float = 0.0
        self.Inom_l1: float = 0.0
        self.Inom_h0: float = 0.0

        self.Snom_l3: float = 0.0
        self.Snom_l2: float = 0.0
        self.Snom_l1: float = 0.0
        self.Snom_h0: float = 0.0

        self.Snom_l3_a: float = 0.0
        self.Snom_l2_a: float = 0.0
        self.Snom_l1_a: float = 0.0
        self.Snom_h0_a: float = 0.0

        self.xSbasepu_lv3: float = 0.0
        self.xSbasepu_lv2: float = 0.0
        self.xSbasepu_lv1: float = 0.0
        self.xSbasepu_hv0: float = 0.0

        self.rSbasepu_lv3: float = 0.0
        self.rSbasepu_lv2: float = 0.0
        self.rSbasepu_lv1: float = 0.0
        self.rSbasepu_hv0: float = 0.0

        self.xSbasepu_l2l3: float = 0.0
        self.xSbasepu_l1l3: float = 0.0
        self.xSbasepu_l1l2: float = 0.0
        self.xSbasepu_h0l3: float = 0.0
        self.xSbasepu_h0l2: float = 0.0
        self.xSbasepu_h0l1: float = 0.0

        self.rSbasepu_l2l3: float = 0.0
        self.rSbasepu_l1l3: float = 0.0
        self.rSbasepu_l1l2: float = 0.0
        self.rSbasepu_h0l3: float = 0.0
        self.rSbasepu_h0l2: float = 0.0
        self.rSbasepu_h0l1: float = 0.0

        self.x0Sbasepu_lv3: float = 0.0
        self.x0Sbasepu_lv2: float = 0.0
        self.x0Sbasepu_lv1: float = 0.0
        self.x0Sbasepu_hv0: float = 0.0

        self.r0Sbasepu_lv3: float = 0.0
        self.r0Sbasepu_lv2: float = 0.0
        self.r0Sbasepu_lv1: float = 0.0
        self.r0Sbasepu_hv0: float = 0.0

        self.bSbasepu: float = 0.0

        self.pT_lv3: str = ""
        self.pT_lv2: str = ""
        self.pT_lv1: str = ""
        self.pT_hv0: str = ""

        self.i_tapini_lv3: int = 0
        self.i_tapini_lv2: int = 0
        self.i_tapini_lv1: int = 0
        self.i_tapini_hv0: int = 0

        self.ntap_h0: int = 0
        self.ntap_l1: int = 0
        self.ntap_l2: int = 0
        self.ntap_l3: int = 0

        self.busl3: str = ""
        self.busl2: str = ""
        self.busl1: str = ""
        self.bush0: str = ""

        self.cpSubstat: str = ""
        self.cpArea: str = ""
        self.cpZone: str = ""
        self.cpGrid: str = ""

        self.GPSlon: float = 0.0
        self.GPSlat: float = 0.0

        self.maxload: float = 0.0
        self.ratfac_l3: float = 0.0
        self.ratfac_l2: float = 0.0
        self.ratfac_l1: float = 0.0
        self.ratfac_h0: float = 0.0

        self.desc_0: str = ""
        self.desc_1: str = ""
        self.desc_2: str = ""
        self.desc_3: str = ""

        self.commissionDate: str = ""
        self.sernum: str = ""
        self.dat_src: str = ""


class ElmXnet(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "outserv",
        "snss",
        "rntxn",
        "z2tz1",
        "snssmin",
        "rntxnmin",
        "z2tz1min",
        "chr_name",
        "bustp",
        "pgini",
        "qgini",
        "phiini",
        "usetp",
        "cgnd",
        "iintgnd",
        "ikssmin",
        "r0tx0",
        "r0tx0min",
        "cmax",
        "xd",
        "xq",
    )
    element_type = 'ElmXnet'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('outserv', 'i', 'Out of Service', py_name='outserv'),
        DgsProperty('snss', 'r', 'Maximum Short-Circuit Power in MVA', py_name='snss'),
        DgsProperty('rntxn', 'r', 'R/X Ratio for Maximum Short-Circuit Power', py_name='rntxn'),
        DgsProperty('z2tz1', 'r', 'Ratio Z2 / Z1', py_name='z2tz1'),
        DgsProperty('snssmin', 'r', 'Minimum Short-Circuit Power in MVA', py_name='snssmin'),
        DgsProperty('rntxnmin', 'r', 'R/X Ratio for Minimum Short-Circuit Power', py_name='rntxnmin'),
        DgsProperty('z2tz1min', 'r', 'Minimum Ratio Z2 / Z1', py_name='z2tz1min'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('bustp', 'a:2', 'Bus Type: SL:PV:PQ', py_name='bustp'),
        DgsProperty('pgini', 'r', 'Active Power Setpoint in MW', py_name='pgini'),
        DgsProperty('qgini', 'r', 'Reactive Power Setpoint in MVAr', py_name='qgini'),
        DgsProperty('phiini', 'r', 'Voltage Angle Setpoint in deg', py_name='phiini'),
        DgsProperty('usetp', 'r', 'Voltage Magnitude Setpoint in p.u.', py_name='usetp'),
        DgsProperty('cgnd', 'i', 'Neutral Grounded: Connected:Not connected', py_name='cgnd'),
        DgsProperty('iintgnd', 'i', 'Internal Grounding Impedance Enabled', py_name='iintgnd'),
        DgsProperty('ikssmin', 'r', 'Minimum Initial Symmetrical Short-Circuit Current in kA', py_name='ikssmin'),
        DgsProperty('r0tx0', 'r', 'Ratio R0 / X0', py_name='r0tx0'),
        DgsProperty('r0tx0min', 'r', 'Minimum Ratio R0 / X0', py_name='r0tx0min'),
        DgsProperty('cmax', 'r', 'Maximum voltage factor', py_name='cmax'),
        DgsProperty('xd', 'r', 'd synchronous reactance', py_name='xd'),
        DgsProperty('xq', 'r', 'q synchronous reactance', py_name='xq'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.outserv: int = 0
        self.snss: float = 0.0
        self.rntxn: float = 0.0
        self.z2tz1: float = 0.0
        self.snssmin: float = 0.0
        self.rntxnmin: float = 0.0
        self.z2tz1min: float = 0.0
        self.chr_name: str = ""
        self.bustp: str = ""
        self.pgini: float = 0.0
        self.qgini: float = 0.0
        self.phiini: float = 0.0
        self.usetp: float = 0.0
        self.cgnd: int = 0
        self.iintgnd: int = 0
        self.ikssmin: float = 0.0
        self.r0tx0: float = 0.0
        self.r0tx0min: float = 0.0
        self.cmax: float = 1.0
        self.xd: float = 0.2
        self.xq: float = 0.2


class ElmZone(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "for_name",
        "fold_id",
        "icolor",
        "curscale",
    )
    element_type = 'ElmZone'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('icolor', 'i', 'DGS field icolor (i)', py_name='icolor'),
        DgsProperty('curscale', 'r', 'DGS field curscale (r)', py_name='curscale'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.for_name: str = ""
        self.fold_id: str = ""
        self.icolor: int = 0
        self.curscale: float = 0.0


class ElmArea(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "icolor",
        "for_name",
    )
    element_type = 'ElmArea'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field FID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS field OP (a:1)', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'DGS field loc_name (a:80)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('icolor', 'i', 'DGS field icolor (i)', py_name='icolor'),
        DgsProperty('for_name', 'a:100', 'DGS field for_name (a:100)', py_name='for_name'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.icolor: int = 0
        self.for_name: str = ""


class General(DGSElement):
    __slots__ = (
        "ID",
        "Descr",
        "Val",
    )
    element_type = 'General'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('Descr', 'a:40', 'DGS field Descr (a:40)', py_name='Descr'),
        DgsProperty('Val', 'a:40', 'DGS field Val (a:40)', py_name='Val'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.Descr: str = ""
        self.Val: str = ""


class BlkDef(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "isMacro",
        "level",
        "outputs",
        "inputs",
        "states",
        "params",
        "upper_limit_params",
        "lower_limit_params",
        "internals",
        "equations_raw",
    )
    element_type = 'BlkDef'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the block definition', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the block definition', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the DSL frame or block definition', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the block definition', py_name='fold_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.isMacro: int = 0
        self.level: int = 0

        self.outputs: List[str] = list()
        self.inputs: List[str] = list()
        self.states: List[str] = list()
        self.params: List[str] = list()
        self.upper_limit_params: List[str] = list()
        self.lower_limit_params: List[str] = list()
        self.internals: List[str] = list()
        self.equations_raw: List[str] = list()

    @staticmethod
    def _split_symbol_field(raw: str | None) -> List[str]:
        if raw is None:
            return list()

        text = raw.strip().strip('"')
        if text == "" or text == "*":
            return list()

        values: List[str] = list()
        token: List[str] = list()

        for ch in text:
            if ch in {',', ';'}:
                item = ''.join(token).strip()
                if item:
                    values.append(item)
                token = list()
            else:
                token.append(ch)

        item = ''.join(token).strip()
        if item:
            values.append(item)

        return values

    @classmethod
    def _append_unique_symbols(cls, target: List[str], raw: str | None) -> None:
        """
        Append parsed symbols to a target list preserving order and uniqueness.

        :param target: Destination symbol list.
        :param raw: Raw DGS symbol field.
        :return: None.
        """
        parsed_values: List[str] = cls._split_symbol_field(raw)
        for value in parsed_values:
            if value not in target:
                target.append(value)
            else:
                pass

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = _split_dgs_line(line)
        obj = super().parse_line(";".join(parts), header_map)

        is_macro = _dgs_get(parts, header_map, 'isMacro')
        level = _dgs_get(parts, header_map, 'level')
        obj.isMacro = int(float(is_macro.replace(',', '.'))) if is_macro is not None and is_macro.strip() != '' else 0
        obj.level = int(float(level.replace(',', '.'))) if level is not None and level.strip() != '' else 0

        obj.outputs = cls._split_symbol_field(_dgs_get(parts, header_map, 'cOutput'))
        obj.inputs = cls._split_symbol_field(_dgs_get(parts, header_map, 'cInput'))
        obj.states = cls._split_symbol_field(_dgs_get(parts, header_map, 'cStates'))
        obj.params = cls._split_symbol_field(_dgs_get(parts, header_map, 'cParams'))
        obj.internals = cls._split_symbol_field(_dgs_get(parts, header_map, 'cIntern'))

        # PowerFactory exports limiter parameters separately from cParams through upper/lower limit fields.
        cls._append_unique_symbols(obj.upper_limit_params, _dgs_get(parts, header_map, 'sUpLimPar:0'))
        cls._append_unique_symbols(obj.lower_limit_params, _dgs_get(parts, header_map, 'sLowLimPar:0'))
        for param_name in obj.upper_limit_params:
            if param_name not in obj.params:
                obj.params.append(param_name)
            else:
                pass
        for param_name in obj.lower_limit_params:
            if param_name not in obj.params:
                obj.params.append(param_name)
            else:
                pass

        raw_n_eq = _dgs_get(parts, header_map, 'sAddEquat:SIZEROW')
        n_eq = int(float(raw_n_eq.replace(',', '.'))) if raw_n_eq is not None and raw_n_eq.strip() != '' else 0
        for i in range(n_eq):
            raw_eq = _dgs_get(parts, header_map, f'sAddEquat:{i}')
            raw_eq = raw_eq.strip() if raw_eq is not None else ''
            if raw_eq != '' and raw_eq != '*':
                obj.equations_raw.append(raw_eq)

        return obj


class IntFolder(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "iopt_typ",
    )
    element_type = 'IntFolder'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('iopt_typ', 'i', 'DGS field iopt_typ (i)', py_name='iopt_typ'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.iopt_typ: int = 0


class IntRef(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "obj_id",
    )
    element_type = 'IntRef'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the internal reference object', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the internal reference object', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the internal reference object', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the internal reference object', py_name='fold_id'),
        DgsProperty('obj_id', 'p', 'Referenced PowerFactory object', py_name='obj_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.obj_id: str = ""


class IntTemplate(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
    )
    element_type = 'IntTemplate'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the internal template', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the internal template', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the internal template object', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the internal template object', py_name='fold_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""


class Matrix(DGSElement):
    __slots__ = (
        "ID",
        "MatRow",
        "MatColumn",
        "Val",
    )
    element_type = 'Matrix'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Identifier of the matrix object', py_name='ID'),
        DgsProperty('MatRow', 'i', 'Row index of the matrix entry', py_name='MatRow'),
        DgsProperty('MatColumn', 'i', 'Column index of the matrix entry', py_name='MatColumn'),
        DgsProperty('Val', 'r', 'Numeric value stored at the given matrix row and column', py_name='Val'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.MatRow: int = 0
        self.MatColumn: int = 0
        self.Val: float = 0.0


class IntGrf(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "iCol",
        "iVis",
        "iLevel",
        "rCenterX",
        "rCenterY",
        "sSymNam",
        "pDataObj",
        "iRot",
        "rSizeX",
        "rSizeY",
        "iIndLS",
        "iCollapsed",
        "sAttr_SIZEROW",
        "sAttr_0",
        "sAttr_1",
        "sAttr_2",
        "sAttr",
    )
    element_type = 'IntGrf'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker', py_name='OP'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('iCol', 'i', 'DGS field iCol (i)', py_name='iCol'),
        DgsProperty('iVis', 'i', 'DGS field iVis (i)', py_name='iVis'),
        DgsProperty('iLevel', 'i', 'DGS field iLevel (i)', py_name='iLevel'),
        DgsProperty('rCenterX', 'r', 'DGS field rCenterX (r)', py_name='rCenterX'),
        DgsProperty('rCenterY', 'r', 'DGS field rCenterY (r)', py_name='rCenterY'),
        DgsProperty('sSymNam', 'a:40', 'DGS field sSymNam (a:40)', py_name='sSymNam'),
        DgsProperty('pDataObj', 'p', 'DGS field pDataObj (p)', py_name='pDataObj'),
        DgsProperty('iRot', 'i', 'DGS field iRot (i)', py_name='iRot'),
        DgsProperty('rSizeX', 'r', 'DGS field rSizeX (r)', py_name='rSizeX'),
        DgsProperty('rSizeY', 'r', 'DGS field rSizeY (r)', py_name='rSizeY'),
        DgsProperty('iIndLS', 'i', 'Individual line-style flag', py_name='iIndLS'),
        DgsProperty('iCollapsed', 'i', 'Collapsed compound-graphic flag', py_name='iCollapsed'),
        DgsProperty('sAttr:SIZEROW', 'i', 'DGS field sAttr:SIZEROW (i)', py_name='sAttr_SIZEROW'),
        DgsProperty('sAttr:0', 'a', 'DGS field sAttr:0 (a)', py_name='sAttr_0'),
        DgsProperty('sAttr:1', 'a', 'DGS field sAttr:1 (a)', py_name='sAttr_1'),
        DgsProperty('sAttr:2', 'a', 'DGS field sAttr:2 (a)', py_name='sAttr_2'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.iCol: int = 0
        self.iVis: int = 0
        self.iLevel: int = 0
        self.rCenterX: float = 0.0
        self.rCenterY: float = 0.0
        self.sSymNam: str = ""
        self.pDataObj: str = ""
        self.iRot: int = 0
        self.rSizeX: float = 0.0
        self.rSizeY: float = 0.0
        self.iIndLS: int = 0
        self.iCollapsed: int = 0
        self.sAttr_SIZEROW: int = 0
        self.sAttr_0: str = ""
        self.sAttr_1: str = ""
        self.sAttr_2: str = ""
        self.sAttr: List[str] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> "IntGrf":
        """Parse the scalar graphic fields and its variable-length attribute vector."""
        obj: IntGrf = super().parse_line(line=line, header_map=header_map)
        parts: List[str] = _split_dgs_line(line)
        attributes: List[str] = list()

        for index in range(int(obj.sAttr_SIZEROW)):
            raw_value: str | None = _dgs_get(parts=parts, header_map=header_map, key=f"sAttr:{index}")
            attributes.append("" if raw_value is None or raw_value == "*" else raw_value)

        obj.sAttr = attributes
        return obj


class IntGrfcon(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "rX_SIZEROW",
        "rX_0",
        "rX_1",
        "rX_2",
        "rX_3",
        "rY_SIZEROW",
        "rY_0",
        "rY_1",
        "rY_2",
        "rY_3",
        "rX_4",
        "rX_5",
        "rX_6",
        "rX_7",
        "rX_8",
        "rX_9",
        "rY_4",
        "rY_5",
        "rY_6",
        "rY_7",
        "rY_8",
        "rY_9",
        "iDatConNr",
        "iLinSt",
        "rLinWd",
        "points_SIZEROW",
        "points_SIZECOL",
        "rX",
        "rY",
        "points",
    )
    element_type = 'IntGrfcon'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker', py_name='OP'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('rX:SIZEROW', 'i', 'DGS field rX:SIZEROW (i)', py_name='rX_SIZEROW'),
        DgsProperty('rX:0', 'r', 'DGS field rX:0 (r)', py_name='rX_0'),
        DgsProperty('rX:1', 'r', 'DGS field rX:1 (r)', py_name='rX_1'),
        DgsProperty('rX:2', 'r', 'DGS field rX:2 (r)', py_name='rX_2'),
        DgsProperty('rX:3', 'r', 'DGS field rX:3 (r)', py_name='rX_3'),
        DgsProperty('rY:SIZEROW', 'i', 'DGS field rY:SIZEROW (i)', py_name='rY_SIZEROW'),
        DgsProperty('rY:0', 'r', 'DGS field rY:0 (r)', py_name='rY_0'),
        DgsProperty('rY:1', 'r', 'DGS field rY:1 (r)', py_name='rY_1'),
        DgsProperty('rY:2', 'r', 'DGS field rY:2 (r)', py_name='rY_2'),
        DgsProperty('rY:3', 'r', 'DGS field rY:3 (r)', py_name='rY_3'),
        DgsProperty('rX:4', 'r', 'DGS field rX:4 (r)', py_name='rX_4'),
        DgsProperty('rX:5', 'r', 'DGS field rX:5 (r)', py_name='rX_5'),
        DgsProperty('rX:6', 'r', 'DGS field rX:6 (r)', py_name='rX_6'),
        DgsProperty('rX:7', 'r', 'DGS field rX:7 (r)', py_name='rX_7'),
        DgsProperty('rX:8', 'r', 'DGS field rX:8 (r)', py_name='rX_8'),
        DgsProperty('rX:9', 'r', 'DGS field rX:9 (r)', py_name='rX_9'),
        DgsProperty('rY:4', 'r', 'DGS field rY:4 (r)', py_name='rY_4'),
        DgsProperty('rY:5', 'r', 'DGS field rY:5 (r)', py_name='rY_5'),
        DgsProperty('rY:6', 'r', 'DGS field rY:6 (r)', py_name='rY_6'),
        DgsProperty('rY:7', 'r', 'DGS field rY:7 (r)', py_name='rY_7'),
        DgsProperty('rY:8', 'r', 'DGS field rY:8 (r)', py_name='rY_8'),
        DgsProperty('rY:9', 'r', 'DGS field rY:9 (r)', py_name='rY_9'),
        DgsProperty('iDatConNr', 'i', 'Graphic connector or terminal ordinal', py_name='iDatConNr'),
        DgsProperty('iLinSt', 'i', 'Graphic connector line style', py_name='iLinSt'),
        DgsProperty('rLinWd', 'r', 'Graphic connector line width', py_name='rLinWd'),
        DgsProperty('points:SIZEROW', 'i', 'Number of point-matrix rows', py_name='points_SIZEROW'),
        DgsProperty('points:SIZECOL', 'i', 'Number of point-matrix columns', py_name='points_SIZECOL'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.rX_SIZEROW: int = 0
        self.rX_0: float = 0.0
        self.rX_1: float = 0.0
        self.rX_2: float = 0.0
        self.rX_3: float = 0.0
        self.rY_SIZEROW: int = 0
        self.rY_0: float = 0.0
        self.rY_1: float = 0.0
        self.rY_2: float = 0.0
        self.rY_3: float = 0.0
        self.rX_4: float = 0.0
        self.rX_5: float = 0.0
        self.rX_6: float = 0.0
        self.rX_7: float = 0.0
        self.rX_8: float = 0.0
        self.rX_9: float = 0.0
        self.rY_4: float = 0.0
        self.rY_5: float = 0.0
        self.rY_6: float = 0.0
        self.rY_7: float = 0.0
        self.rY_8: float = 0.0
        self.rY_9: float = 0.0
        self.iDatConNr: int = -1
        self.iLinSt: int = 0
        self.rLinWd: float = 0.0
        self.points_SIZEROW: int = 0
        self.points_SIZECOL: int = 0
        self.rX: List[float] = list()
        self.rY: List[float] = list()
        self.points: List[tuple[float, float]] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> "IntGrfcon":
        """Parse connector geometry without imposing a fixed vector length."""
        obj: IntGrfcon = super().parse_line(line=line, header_map=header_map)
        parts: List[str] = _split_dgs_line(line)

        def parse_float_vector(prefix: str, size: int) -> List[float]:
            values: List[float] = list()
            for index in range(size):
                raw_value: str | None = _dgs_get(parts=parts, header_map=header_map, key=f"{prefix}:{index}")
                if raw_value is None or raw_value.strip() in {"", "*"}:
                    break
                try:
                    values.append(float(raw_value.replace(",", ".")))
                except ValueError:
                    break
            return values

        obj.rX = parse_float_vector(prefix="rX", size=int(obj.rX_SIZEROW))
        obj.rY = parse_float_vector(prefix="rY", size=int(obj.rY_SIZEROW))

        matrix_points: List[tuple[float, float]] = list()
        for row_index in range(int(obj.points_SIZEROW)):
            raw_x: str | None = _dgs_get(parts=parts, header_map=header_map, key=f"points:{row_index}:0")
            raw_y: str | None = _dgs_get(parts=parts, header_map=header_map, key=f"points:{row_index}:1")
            if raw_x is None or raw_y is None or raw_x.strip() in {"", "*"} or raw_y.strip() in {"", "*"}:
                break
            try:
                matrix_points.append((float(raw_x.replace(",", ".")), float(raw_y.replace(",", "."))))
            except ValueError:
                break
        obj.points = matrix_points
        return obj


class IntGrfnet(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "snap_on",
        "grid_on",
        "ortho_on",
        "pDataFolder",
        "iType",
        "rScalFac",
        "rXFak",
        "rYFak",
        "rRTopXc",
        "rRTopYc",
        "rLBotXc",
        "rLBotYc",
    )
    element_type = 'IntGrfnet'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker', py_name='OP'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('snap_on', 'i', 'DGS field snap_on (i)', py_name='snap_on'),
        DgsProperty('grid_on', 'i', 'DGS field grid_on (i)', py_name='grid_on'),
        DgsProperty('ortho_on', 'i', 'DGS field ortho_on (i)', py_name='ortho_on'),
        DgsProperty('pDataFolder', 'p', 'DGS field pDataFolder (p)', py_name='pDataFolder'),
        DgsProperty('iType', 'i', 'PowerFactory diagram type', py_name='iType'),
        DgsProperty('rScalFac', 'r', 'Diagram scale factor', py_name='rScalFac'),
        DgsProperty('rXFak', 'r', 'Diagram X factor', py_name='rXFak'),
        DgsProperty('rYFak', 'r', 'Diagram Y factor', py_name='rYFak'),
        DgsProperty('rRTopXc', 'r', 'Content right/top X bound', py_name='rRTopXc'),
        DgsProperty('rRTopYc', 'r', 'Content right/top Y bound', py_name='rRTopYc'),
        DgsProperty('rLBotXc', 'r', 'Content left/bottom X bound', py_name='rLBotXc'),
        DgsProperty('rLBotYc', 'r', 'Content left/bottom Y bound', py_name='rLBotYc'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.snap_on: int = 0
        self.grid_on: int = 0
        self.ortho_on: int = 0
        self.pDataFolder: str = ""
        self.iType: int = -1
        self.rScalFac: float = 1.0
        self.rXFak: float = 1.0
        self.rYFak: float = 1.0
        self.rRTopXc: float = 0.0
        self.rRTopYc: float = 0.0
        self.rLBotXc: float = 0.0
        self.rLBotYc: float = 0.0


class IntGrfgroup(DGSElement):
    """Optional PowerFactory graphic grouping node."""
    element_type = 'IntGrfgroup'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Graphic group name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Parent graphic container', py_name='fold_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.raw_attributes: Dict[str, str] = dict()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> "IntGrfgroup":
        obj: IntGrfgroup = super().parse_line(line=line, header_map=header_map)
        parts: List[str] = _split_dgs_line(line)
        known_names: set[str] = set(obj.properties)
        known_names.add("FID")
        for column_name, column_index in header_map.items():
            if column_name not in known_names and 0 <= column_index < len(parts):
                obj.raw_attributes[column_name] = parts[column_index]
        return obj


class RelFuse(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "typ_id",
        "chr_name",
        "aUsage",
        "nphase",
        "on_off",
        "outserv",
    )
    element_type = 'RelFuse'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('typ_id', 'p', 'DGS field typ_id (p)', py_name='typ_id'),
        DgsProperty('chr_name', 'a', 'DGS field chr_name (a)', py_name='chr_name'),
        DgsProperty('aUsage', 'a', 'DGS field aUsage (a)', py_name='aUsage'),
        DgsProperty('nphase', 'i', 'DGS field nphase (i)', py_name='nphase'),
        DgsProperty('on_off', 'i', 'DGS field on_off (i)', py_name='on_off'),
        DgsProperty('outserv', 'i', 'DGS field outserv (i)', py_name='outserv'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.typ_id: str = ""
        self.chr_name: str = ""
        self.aUsage: str = ""
        self.nphase: int = 3
        self.on_off: int = 0
        self.outserv: int = 0


class StaCubic(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "chr_name",
        "obj_bus",
        "obj_id",
        "for_name",
        "it2p1",
        "it2p2",
        "it2p3",
        "cPhInfo",
    )
    element_type = 'StaCubic'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('obj_bus', 'i', 'Bus Terminal Index within the Connected Device', py_name='obj_bus'),
        DgsProperty('obj_id', 'p', 'Connected PowerFactory Object', py_name='obj_id'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('it2p1', 'i', 'Phase-to-Phase Connection Flag 1', py_name='it2p1'),
        DgsProperty('it2p2', 'i', 'Phase-to-Phase Connection Flag 2', py_name='it2p2'),
        DgsProperty('it2p3', 'i', 'Phase-to-Phase Connection Flag 3', py_name='it2p3'),
        DgsProperty('cPhInfo', 'a', 'Connected phases information', py_name='cPhInfo'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.obj_bus: int = 0
        self.obj_id: str = ""
        self.for_name: str = ""
        self.it2p1: int = 0
        self.it2p2: int = 0
        self.it2p3: int = 0
        self.cPhInfo: str = ""


class StaSwitch(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "on_off",
        "typ_id",
        "iUse",
        "for_name",
        "aUsage",
    )
    element_type = 'StaSwitch'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('on_off', 'i', 'Switch Position: Open:Closed', py_name='on_off'),
        DgsProperty('typ_id', 'p', 'Type in TypSwitch', py_name='typ_id'),
        DgsProperty('iUse', 'i', 'Switch Use Code', py_name='iUse'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('aUsage', 'a', 'Switch Usage String', py_name='aUsage'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.on_off: int = 0
        self.typ_id: str = ""
        self.iUse: int = 0
        self.for_name: str = ""
        self.aUsage: str = ""


class StaCt(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "chr_name",
        "ptapset",
        "stapset",
        "outserv",
        "typ_id",
    )
    element_type = 'StaCt'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the current transformer', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the current transformer', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the current transformer', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Cubicle or parent object containing the current transformer', py_name='fold_id'),
        DgsProperty('chr_name', 'a:40', 'Short display name of the current transformer', py_name='chr_name'),
        DgsProperty('ptapset', 'r', 'Selected primary tap ratio multiplier', py_name='ptapset'),
        DgsProperty('stapset', 'r', 'Selected secondary tap ratio multiplier', py_name='stapset'),
        DgsProperty('outserv', 'i', 'Out-of-service flag of the current transformer', py_name='outserv'),
        DgsProperty('typ_id', 'p', 'Referenced current transformer type', py_name='typ_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.ptapset: float = 0.0
        self.stapset: float = 0.0
        self.outserv: int = 0
        self.typ_id: str = ""


# Dynamic contract: retain only the voltage reference and signal required to
# resolve the PLL; neither value is inferred from the dynamic block.
class StaVmea(DGSElement):
    """Represent one native voltage-measurement object.

    The row remains a signal source owned by its DGS composite. It is not
    materialized as a second network device.
    """

    __slots__ = (
        "ID", "OP", "loc_name", "fold_id", "chr_name", "pbusbar",
        "pbusbar2", "outserv", "i_mode", "iOutput", "iUdcOutput",
        "iFreq", "freqOutput", "nominalFreq", "meatech", "nphase",
        "it2p", "it2p2", "samplingFreq", "samplesPerPeriod",
        "samplesPerWindow", "windowLength", "rateLim", "clockPeriod",
    )

    element_type = "StaVmea"
    properties_list = [
        DgsProperty("FID", "a:40", "Unique identifier", py_name="ID"),
        DgsProperty("OP", "a:1", "DGS operation marker", py_name="OP"),
        DgsProperty("loc_name", "a:80", "Name", py_name="loc_name"),
        DgsProperty("fold_id", "p", "Owning object", py_name="fold_id"),
        DgsProperty("chr_name", "a:40", "Short display name", py_name="chr_name"),
        DgsProperty("pbusbar", "p", "Primary measured terminal", py_name="pbusbar"),
        DgsProperty("pbusbar2", "p", "Secondary measured terminal", py_name="pbusbar2"),
        DgsProperty("outserv", "i", "Out-of-service flag", py_name="outserv"),
        DgsProperty("i_mode", "i", "Voltage measurement mode", py_name="i_mode"),
        DgsProperty("iOutput", "i", "Voltage output selector", py_name="iOutput"),
        DgsProperty("iUdcOutput", "i", "DC-voltage output selector", py_name="iUdcOutput"),
        DgsProperty("iFreq", "i", "Frequency measurement enable", py_name="iFreq"),
        DgsProperty("freqOutput", "i", "Frequency output selector", py_name="freqOutput"),
        DgsProperty("nominalFreq", "r", "Nominal frequency", py_name="nominalFreq"),
        DgsProperty("meatech", "i", "Measurement technology", py_name="meatech"),
        DgsProperty("nphase", "i", "Number of measured phases", py_name="nphase"),
        DgsProperty("it2p", "i", "First phase selector", py_name="it2p"),
        DgsProperty("it2p2", "i", "Second phase selector", py_name="it2p2"),
        DgsProperty("samplingFreq", "r", "Sampling frequency", py_name="samplingFreq"),
        DgsProperty("samplesPerPeriod", "i", "Samples per period", py_name="samplesPerPeriod"),
        DgsProperty("samplesPerWindow", "i", "Samples per window", py_name="samplesPerWindow"),
        DgsProperty("windowLength", "r", "Window length", py_name="windowLength"),
        DgsProperty("rateLim", "r", "Output rate limit", py_name="rateLim"),
        DgsProperty("clockPeriod", "r", "Measurement clock period", py_name="clockPeriod"),
    ]

    def __init__(self) -> None:
        """Initialize one empty typed voltage-measurement row.

        :return: None.
        """
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.pbusbar: str = ""
        self.pbusbar2: str = ""
        self.outserv: int = 0
        self.i_mode: int = 0
        self.iOutput: int = 0
        self.iUdcOutput: int = 0
        self.iFreq: int = 0
        self.freqOutput: int = 0
        self.nominalFreq: float = 0.0
        self.meatech: int = 0
        self.nphase: int = 0
        self.it2p: int = 0
        self.it2p2: int = 0
        self.samplingFreq: float = 0.0
        self.samplesPerPeriod: int = 0
        self.samplesPerWindow: int = 0
        self.windowLength: float = 0.0
        self.rateLim: float = 0.0
        self.clockPeriod: float = 0.0


# Dynamic contract: retain only the current reference and signal required to
# bind the measurement; neither value is inferred from the final equipment.
class StaImea(DGSElement):
    """Represent one native current-measurement object."""

    __slots__ = (
        "ID", "OP", "loc_name", "fold_id", "chr_name", "pcubic",
        "outserv", "i_mode", "iOutput", "Inom", "nominalFreq",
        "nphase", "it2p", "samplingFreq", "samplesPerPeriod",
        "samplesPerWindow", "windowLength", "rateLim", "clockPeriod",
    )

    element_type = "StaImea"
    properties_list = [
        DgsProperty("FID", "a:40", "Unique identifier", py_name="ID"),
        DgsProperty("OP", "a:1", "DGS operation marker", py_name="OP"),
        DgsProperty("loc_name", "a:80", "Name", py_name="loc_name"),
        DgsProperty("fold_id", "p", "Owning object", py_name="fold_id"),
        DgsProperty("chr_name", "a:40", "Short display name", py_name="chr_name"),
        DgsProperty("pcubic", "p", "Measured cubicle", py_name="pcubic"),
        DgsProperty("outserv", "i", "Out-of-service flag", py_name="outserv"),
        DgsProperty("i_mode", "i", "Current measurement mode", py_name="i_mode"),
        DgsProperty("iOutput", "i", "Current output selector", py_name="iOutput"),
        DgsProperty("Inom", "r", "Nominal measured current", py_name="Inom"),
        DgsProperty("nominalFreq", "r", "Nominal frequency", py_name="nominalFreq"),
        DgsProperty("nphase", "i", "Number of measured phases", py_name="nphase"),
        DgsProperty("it2p", "i", "Phase selector", py_name="it2p"),
        DgsProperty("samplingFreq", "r", "Sampling frequency", py_name="samplingFreq"),
        DgsProperty("samplesPerPeriod", "i", "Samples per period", py_name="samplesPerPeriod"),
        DgsProperty("samplesPerWindow", "i", "Samples per window", py_name="samplesPerWindow"),
        DgsProperty("windowLength", "r", "Window length", py_name="windowLength"),
        DgsProperty("rateLim", "r", "Output rate limit", py_name="rateLim"),
        DgsProperty("clockPeriod", "r", "Measurement clock period", py_name="clockPeriod"),
    ]

    def __init__(self) -> None:
        """Initialize one empty typed current-measurement row.

        :return: None.
        """
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.pcubic: str = ""
        self.outserv: int = 0
        self.i_mode: int = 0
        self.iOutput: int = 0
        self.Inom: float = 0.0
        self.nominalFreq: float = 0.0
        self.nphase: int = 0
        self.it2p: int = 0
        self.samplingFreq: float = 0.0
        self.samplesPerPeriod: int = 0
        self.samplesPerWindow: int = 0
        self.windowLength: float = 0.0
        self.rateLim: float = 0.0
        self.clockPeriod: float = 0.0


# Dynamic contract: retain only the P/Q references and signals required to
# bind the control; they are not inferred from setpoints or solved m:* values.
class StaPqmea(DGSElement):
    """Represent one native active/reactive-power measurement object."""

    __slots__ = (
        "ID", "OP", "loc_name", "fold_id", "chr_name", "pcubic",
        "outserv", "i_mode", "i_orient", "Snom", "nominalFreq",
        "nphase", "it2p", "samplingFreq", "samplesPerPeriod",
        "samplesPerWindow", "windowLength", "rateLim", "clockPeriod",
    )

    element_type = "StaPqmea"
    properties_list = [
        DgsProperty("FID", "a:40", "Unique identifier", py_name="ID"),
        DgsProperty("OP", "a:1", "DGS operation marker", py_name="OP"),
        DgsProperty("loc_name", "a:80", "Name", py_name="loc_name"),
        DgsProperty("fold_id", "p", "Owning object", py_name="fold_id"),
        DgsProperty("chr_name", "a:40", "Short display name", py_name="chr_name"),
        DgsProperty("pcubic", "p", "Measured cubicle", py_name="pcubic"),
        DgsProperty("outserv", "i", "Out-of-service flag", py_name="outserv"),
        DgsProperty("i_mode", "i", "Power measurement mode", py_name="i_mode"),
        DgsProperty("i_orient", "i", "Measured-power orientation", py_name="i_orient"),
        DgsProperty("Snom", "r", "Nominal apparent power", py_name="Snom"),
        DgsProperty("nominalFreq", "r", "Nominal frequency", py_name="nominalFreq"),
        DgsProperty("nphase", "i", "Number of measured phases", py_name="nphase"),
        DgsProperty("it2p", "i", "Phase selector", py_name="it2p"),
        DgsProperty("samplingFreq", "r", "Sampling frequency", py_name="samplingFreq"),
        DgsProperty("samplesPerPeriod", "i", "Samples per period", py_name="samplesPerPeriod"),
        DgsProperty("samplesPerWindow", "i", "Samples per window", py_name="samplesPerWindow"),
        DgsProperty("windowLength", "r", "Window length", py_name="windowLength"),
        DgsProperty("rateLim", "r", "Output rate limit", py_name="rateLim"),
        DgsProperty("clockPeriod", "r", "Measurement clock period", py_name="clockPeriod"),
    ]

    def __init__(self) -> None:
        """Initialize one empty typed power-measurement row.

        :return: None.
        """
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.pcubic: str = ""
        self.outserv: int = 0
        self.i_mode: int = 0
        self.i_orient: int = 0
        self.Snom: float = 0.0
        self.nominalFreq: float = 0.0
        self.nphase: int = 0
        self.it2p: int = 0
        self.samplingFreq: float = 0.0
        self.samplesPerPeriod: int = 0
        self.samplesPerWindow: int = 0
        self.windowLength: float = 0.0
        self.rateLim: float = 0.0
        self.clockPeriod: float = 0.0


# Dynamic contract: represent the minimal native PLL row; its FID and
# connections are not inferred from ElmComp or the final VSC.
class ElmPhi(DGSElement):
    """Represent one native PowerFactory phase-locked-loop measurement."""

    __slots__ = (
        "ID", "OP", "loc_name", "fold_id", "pbusbar", "outserv",
        "Kp", "Ki",
    )

    element_type = "ElmPhi"
    properties_list = [
        DgsProperty("FID", "a:40", "Unique PLL identifier", py_name="ID"),
        DgsProperty("OP", "a:1", "DGS operation marker", py_name="OP"),
        DgsProperty("loc_name", "a:80", "PLL name", py_name="loc_name"),
        DgsProperty("fold_id", "p", "Owning composite", py_name="fold_id"),
        DgsProperty("pbusbar", "p", "Measured terminal or cubicle", py_name="pbusbar"),
        DgsProperty("outserv", "i", "Out-of-service flag", py_name="outserv"),
        DgsProperty("Kp", "r", "PLL proportional gain", py_name="Kp"),
        DgsProperty("Ki", "r", "PLL integration gain", py_name="Ki"),
    ]

    def __init__(self) -> None:
        """Initialize one empty typed PLL row.

        :return: None.
        """
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.pbusbar: str = ""
        self.outserv: int = 0
        self.Kp: float = 0.0
        self.Ki: float = 0.0


class StaVt(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "chr_name",
        "ptapset",
        "stapset",
        "typ_id",
        "outserv",
    )
    element_type = 'StaVt'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the voltage transformer', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the voltage transformer', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the voltage transformer', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Cubicle or parent object containing the voltage transformer', py_name='fold_id'),
        DgsProperty('chr_name', 'a:40', 'Short display name of the voltage transformer', py_name='chr_name'),
        DgsProperty('ptapset', 'r', 'Selected primary tap ratio multiplier', py_name='ptapset'),
        DgsProperty('stapset', 'r', 'Selected secondary tap ratio multiplier', py_name='stapset'),
        DgsProperty('typ_id', 'p', 'Referenced voltage transformer type', py_name='typ_id'),
        DgsProperty('outserv', 'i', 'Out-of-service flag of the voltage transformer', py_name='outserv'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.chr_name: str = ""
        self.ptapset: float = 0.0
        self.stapset: float = 0.0
        self.typ_id: str = ""
        self.outserv: int = 0


class TypSwitch(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "Ron",
        "Xon",
        "InomA",
        "InomB",
        "for_name",
    )
    element_type = 'TypSwitch'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the breaker or switch type', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name of the breaker or switch type', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the breaker or switch type', py_name='fold_id'),
        DgsProperty('Ron', 'r', 'Closed-state resistance of the switch', py_name='Ron'),
        DgsProperty('Xon', 'r', 'Closed-state reactance of the switch', py_name='Xon'),
        DgsProperty('InomA', 'r', 'Nominal current at terminal A', py_name='InomA'),
        DgsProperty('InomB', 'r', 'Nominal current at terminal B', py_name='InomB'),
        DgsProperty('for_name', 'a:50', 'Foreign name or external identifier of the switch type', py_name='for_name'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.Ron: float = 0.0
        self.Xon: float = 0.0
        self.InomA: float = 0.0
        self.InomB: float = 0.0
        self.for_name: str = ""

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        """Parse TypSwitch and tolerate several header aliases used by DGS variants."""
        parts = line.rstrip('\n').split(';')
        obj = cls()

        alias_map: Dict[str, List[str]] = dict()
        alias_map['ID'] = ['ID', 'FID']
        alias_map['loc_name'] = ['loc_name']
        alias_map['fold_id'] = ['fold_id']
        alias_map['Ron'] = ['Ron', 'ron', 'r_on']
        alias_map['Xon'] = ['Xon', 'xon', 'x_on']
        alias_map['InomA'] = ['InomA', 'inom_a', 'Inom1', 'inom1', 'InomBus1', 'inom_bus1']
        alias_map['InomB'] = ['InomB', 'inom_b', 'Inom2', 'inom2', 'InomBus2', 'inom_bus2']
        alias_map['for_name'] = ['for_name']

        prop_by_name: Dict[str, DgsProperty] = dict()
        for prop in cls.properties_list:
            prop_by_name[prop.py_name] = prop

        for py_name, aliases in alias_map.items():
            prop = prop_by_name.get(py_name, None)
            if prop is None:
                pass
            else:
                idx: int | None = None
                for alias in aliases:
                    idx = header_map.get(alias, None)
                    if idx is not None:
                        break
                    else:
                        pass

                if idx is not None and -1 < idx < len(parts):
                    raw = parts[idx]
                    value = prop.parse(raw)
                    setattr(obj, py_name, value)
                else:
                    pass

        return obj


class TypAsmo(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "i_mode",
        "aiazn",
        "amazn",
        "amkzn",
        "anend",
        "cosn",
        "effic",
        "frequ",
        "i_cage",
        "nppol",
        "pgn",
        "ugn",
        "xmrtr",
        "xstr",
        "sgn",
        "nslty",
        "rstr",
        "xm",
        "rrtrA",
        "xrtrA",
    )
    element_type = 'TypAsmo'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('i_mode', 'i', 'Machine Model Type Code', py_name='i_mode'),
        DgsProperty('aiazn', 'r', 'Starting Current Ratio Ia / In', py_name='aiazn'),
        DgsProperty('amazn', 'r', 'Breakdown Torque Ratio Mk / Mn', py_name='amazn'),
        DgsProperty('amkzn', 'r', 'Locked-Rotor Torque Ratio Ma / Mn', py_name='amkzn'),
        DgsProperty('anend', 'r', 'Nominal Speed in rpm', py_name='anend'),
        DgsProperty('cosn', 'r', 'Rated Power Factor', py_name='cosn'),
        DgsProperty('effic', 'r', 'Efficiency in p.u.', py_name='effic'),
        DgsProperty('frequ', 'r', 'Rated Frequency in Hz', py_name='frequ'),
        DgsProperty('i_cage', 'i', 'Rotor Type: Squirrel Cage:Slip Ring', py_name='i_cage'),
        DgsProperty('nppol', 'i', 'Number of Pole Pairs', py_name='nppol'),
        DgsProperty('pgn', 'r', 'Rated Mechanical Power in MW', py_name='pgn'),
        DgsProperty('sgn', 'r', 'Rated Apparent Power in MVA', py_name='sgn'),
        DgsProperty('nslty', 'i', 'Neutral Grounding Type Code', py_name='nslty'),
        DgsProperty('rstr', 'r', 'Stator Resistance in p.u.', py_name='rstr'),
        DgsProperty('xm', 'r', 'Magnetizing Reactance in p.u.', py_name='xm'),
        DgsProperty('ugn', 'r', 'Rated Voltage in kV', py_name='ugn'),
        DgsProperty('xmrtr', 'r', 'Rotor Mutual Reactance in p.u.', py_name='xmrtr'),
        DgsProperty('xstr', 'r', 'Stator Reactance in p.u.', py_name='xstr'),
        DgsProperty('rrtrA', 'r', 'Rotor resistance in p.u.', py_name='rrtrA'),
        DgsProperty('xrtrA', 'r', 'Rotor reactance in p.u.', py_name='xrtrA'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.i_mode: int = 0
        self.aiazn: float = 0.0
        self.amazn: float = 0.0
        self.amkzn: float = 0.0
        self.anend: float = 0.0
        self.cosn: float = 0.0
        self.effic: float = 0.0
        self.frequ: float = 0.0
        self.i_cage: int = 0
        self.nppol: int = 0
        self.pgn: float = 0.0
        self.ugn: float = 0.0
        self.xmrtr: float = 0.0
        self.xstr: float = 0.0
        self.sgn: float = 0.0
        self.nslty: int = 0
        self.rstr: float = 0.0
        self.xm: float = 0.0
        self.rrtrA: float = 0.0
        self.xrtrA: float = 0.0


class TypFuse(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "frq",
        "irat",
        "urat",
    )
    element_type = 'TypFuse'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a', 'DGS field loc_name (a)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('frq', 'r', 'DGS field frq (r)', py_name='frq'),
        DgsProperty('irat', 'r', 'DGS field irat (r)', py_name='irat'),
        DgsProperty('urat', 'r', 'DGS field urat (r)', py_name='urat'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.frq: float = 0.0
        self.irat: float = 0.0
        self.urat: float = 0.0


class TypLne(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "uline",
        "sline",
        "aohl_",
        "aohl_declared",
        "rline",
        "xline",
        "cline",
        "rline0",
        "xline0",
        "cline0",
        "rtemp",
        "Ithr",
        "chr_name",
        "nlnph",
        "nneutral",
        "for_name",
        "InomAir",
        "cohl_",
        "cohl_declared",
        "tmax",
        "systp",
        "frnom",
        "mlei",
        "bline",
        "gline",
        "bline0",
        "gline0",
    )
    element_type = 'TypLne'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('uline', 'r', 'Rated Voltage in kV', py_name='uline', optional=True),
        DgsProperty('sline', 'r', 'Rated Apparent Power in MVA', py_name='sline', optional=True),
        DgsProperty(
            'aohl_',
            'a:3',
            'Installation Type: OHL:CAB',
            py_name='aohl_',
            optional=True,
        ),
        DgsProperty('rline', 'r', 'Positive-Sequence Resistance in Ohm/km', py_name='rline', optional=True),
        DgsProperty('xline', 'r', 'Positive-Sequence Reactance in Ohm/km', py_name='xline', optional=True),
        DgsProperty('cline', 'r', 'Positive-Sequence Capacitance in uF/km', py_name='cline', optional=True),
        DgsProperty('rline0', 'r', 'Zero-Sequence Resistance in Ohm/km', py_name='rline0'),
        DgsProperty('xline0', 'r', 'Zero-Sequence Reactance in Ohm/km', py_name='xline0'),
        DgsProperty('cline0', 'r', 'Zero-Sequence Capacitance in uF/km', py_name='cline0'),
        DgsProperty('rtemp', 'r', 'Reference Temperature in degC', py_name='rtemp'),
        DgsProperty('Ithr', 'r', 'Thermal Current Rating in kA', py_name='Ithr'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('nlnph', 'i', 'Phases:1:2:3', py_name='nlnph'),
        DgsProperty('nneutral', 'i', 'Number of Neutral Conductors', py_name='nneutral'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('InomAir', 'r', 'Continuous Current Rating in Air in kA', py_name='InomAir', optional=True),
        DgsProperty(
            'cohl_',
            'i',
            'Conductor Arrangement Code',
            py_name='cohl_',
            optional=True,
        ),
        DgsProperty('tmax', 'r', 'Maximum Conductor Temperature in degC', py_name='tmax'),
        DgsProperty('systp', 'i', 'System Type Code', py_name='systp'),
        DgsProperty('frnom', 'r', 'Nominal Frequency in Hz', py_name='frnom', optional=True),
        DgsProperty('mlei', 'a:2', 'Line Model Type Code', py_name='mlei'),
        DgsProperty('bline', 'r', 'Positive-Sequence Susceptance in uS/km', py_name='bline', optional=True),
        DgsProperty('gline', 'r', 'Positive-Sequence Conductance in uS/km', py_name='gline', optional=True),
        DgsProperty('bline0', 'r', 'Zero-Sequence Susceptance in uS/km', py_name='bline0'),
        DgsProperty('gline0', 'r', 'Zero-Sequence Conductance in uS/km', py_name='gline0'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.uline: float | None = None
        self.sline: float | None = None
        self.aohl_: str | None = "cab"  # allowed values are "cab" and "ohl"
        self.aohl_declared: bool = False
        self.rline: float | None = None
        self.xline: float | None = None
        self.cline: float | None = None
        self.rline0: float = 0.0
        self.xline0: float = 0.0
        self.cline0: float = 0.0
        self.rtemp: float = 20.0
        self.Ithr: float = 0.0
        self.chr_name: str = ""
        self.nlnph: int = 3
        self.nneutral: int = 0
        self.for_name: str = ""
        self.InomAir: float | None = None
        self.cohl_: int | None = 0
        self.cohl_declared: bool = False
        self.tmax: float = 80.0
        self.systp: int = 0
        self.frnom: float | None = None
        self.mlei: str = ""
        self.bline: float | None = None
        self.gline: float | None = None
        self.bline0: float = 0.0
        self.gline0: float = 0.0

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> TypLne:
        """Parse a line type and retain which installation fields existed.

        The normal property values keep their historical constructor defaults
        for export compatibility. Separate flags retain import evidence so a
        missing ``aohl_`` or ``cohl_`` column cannot look like an explicit
        cable declaration.

        :param line: Raw DGS line-type record.
        :param header_map: DGS property names mapped to column positions.
        :return: Parsed line type with installation evidence flags.
        """
        obj: TypLne = super().parse_line(line=line, header_map=header_map)
        parts: List[str] = _split_dgs_line(line=line)

        # A header only describes the schema. The row must carry a concrete
        # value before it can count as installation evidence for this type.
        aohl_index: int | None = header_map.get('aohl_', None)
        if aohl_index is not None and -1 < aohl_index < len(parts):
            aohl_text: str = parts[aohl_index].strip()
            obj.aohl_declared = aohl_text != '' and aohl_text != '*'
        else:
            obj.aohl_declared = False

        cohl_index: int | None = header_map.get('cohl_', None)
        if cohl_index is not None and -1 < cohl_index < len(parts):
            cohl_text: str = parts[cohl_index].strip()
            obj.cohl_declared = cohl_text != '' and cohl_text != '*'
        else:
            obj.cohl_declared = False
        return obj


class TypLod(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "kpu",
        "kqu",
        "systp",
        "phtech",
        "for_name",
        "aP",
        "bP",
        "kpu0",
        "kpu1",
        "aQ",
        "bQ",
        "kqu0",
        "kqu1",
    )
    element_type = 'TypLod'
    properties_list = [
        DgsProperty('ID', 'a:40', 'DGS field ID (a:40)', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'DGS field loc_name (a:40)', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'DGS field fold_id (p)', py_name='fold_id'),
        DgsProperty('kpu', 'r', 'DGS field kpu (r)', py_name='kpu'),
        DgsProperty('kqu', 'r', 'DGS field kqu (r)', py_name='kqu'),
        DgsProperty('systp', 'i', 'DGS field systp (i)', py_name='systp'),
        DgsProperty('phtech', 'i', 'DGS field phtech (i)', py_name='phtech'),
        DgsProperty('for_name', 'a:50', 'DGS field for_name (a:50)', py_name='for_name'),
        DgsProperty('aP', 'r', 'DGS field aP (r)', py_name='aP'),
        DgsProperty('bP', 'r', 'DGS field bP (r)', py_name='bP'),
        DgsProperty('kpu0', 'r', 'DGS field kpu0 (r)', py_name='kpu0'),
        DgsProperty('kpu1', 'r', 'DGS field kpu1 (r)', py_name='kpu1'),
        DgsProperty('aQ', 'r', 'DGS field aQ (r)', py_name='aQ'),
        DgsProperty('bQ', 'r', 'DGS field bQ (r)', py_name='bQ'),
        DgsProperty('kqu0', 'r', 'DGS field kqu0 (r)', py_name='kqu0'),
        DgsProperty('kqu1', 'r', 'DGS field kqu1 (r)', py_name='kqu1'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.kpu: float = 0.0
        self.kqu: float = 0.0
        self.systp: int = 0
        self.phtech: int = 0
        self.for_name: str = ""
        self.aP: float = 0.0
        self.bP: float = 0.0
        self.kpu0: float = 0.0
        self.kpu1: float = 0.0
        self.aQ: float = 0.0
        self.bQ: float = 0.0
        self.kqu0: float = 0.0
        self.kqu1: float = 0.0


class TypSym(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "sgn",
        "ugn",
        "cosn",
        "xd",
        "xq",
        "xdsss",
        "rstr",
        "xstr",
        "xdsat",
        "satur",
        "Q_min",
        "Q_max",
        "q_min",
        "q_max",
        "for_name",
        "nphase",
        "nslty",
        "x0sy",
        "r0sy",
        "x2sy",
        "r2sy",
        "iopt_data",
        "xds",
        "xqs",
        "xl",
        "xdss",
        "xqss",
        "xrlq",
        "tds",
        "tqs",
        "tdss",
        "tqss",
    )
    element_type = 'TypSym'

    # We comment out the dynamic stuff because it will trigger errors at import
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('sgn', 'r', 'Rated Apparent Power in MVA', py_name='sgn'),
        DgsProperty('ugn', 'r', 'Rated voltage in kV', py_name='ugn'),
        DgsProperty('cosn', 'r', 'Rated Power Factor', py_name='cosn'),
        DgsProperty('xd', 'r', 'Synchronous d-Axis Reactance in p.u.', py_name='xd'),
        DgsProperty('xq', 'r', 'Synchronous q-Axis Reactance in p.u.', py_name='xq'),
        DgsProperty('xdsss', 'r', 'Subtransient d-Axis Reactance in p.u.', py_name='xdsss'),
        DgsProperty('rstr', 'r', 'Stator Resistance in p.u.', py_name='rstr'),
        DgsProperty('xstr', 'r', 'Stator Reactance in p.u.', py_name='xstr'),
        DgsProperty('xdsat', 'r', 'Saturated d-Axis Reactance in p.u.', py_name='xdsat'),
        DgsProperty('satur', 'i', 'Magnetic Saturation Enabled', py_name='satur'),
        DgsProperty('Q_min', 'r', 'Minimum Reactive Power Capability in MVAr', py_name='Q_min'),
        DgsProperty('Q_max', 'r', 'Maximum Reactive Power Capability in MVAr', py_name='Q_max'),
        DgsProperty('q_min', 'r', 'Minimum Reactive Power Limit in MVAr', py_name='q_min'),
        DgsProperty('q_max', 'r', 'Maximum Reactive Power Limit in MVAr', py_name='q_max'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('nphase', 'i', 'Number of Phases', py_name='nphase'),
        DgsProperty('nslty', 'i', 'Neutral Grounding Type Code', py_name='nslty'),
        DgsProperty('x0sy', 'r', 'Zero-Sequence Reactance in p.u.', py_name='x0sy'),
        DgsProperty('r0sy', 'r', 'Zero-Sequence Resistance in p.u.', py_name='r0sy'),
        DgsProperty('x2sy', 'r', 'Negative-Sequence Reactance in p.u.', py_name='x2sy'),
        DgsProperty('r2sy', 'r', 'Negative-Sequence Resistance in p.u.', py_name='r2sy'),
        DgsProperty('iopt_data', 'i', 'Machine Data Option Code', py_name='iopt_data'),
        DgsProperty('xds', 'r', 'Transient d-Axis Reactance in p.u.', py_name='xds'),
        DgsProperty('xqs', 'r', 'Transient q-Axis Reactance in p.u.', py_name='xqs'),
        DgsProperty('xl', 'r', 'Leakage Reactance in p.u.', py_name='xl'),
        DgsProperty('xdss', 'r', 'Subtransient d-Axis Reactance in p.u.', py_name='xdss'),
        DgsProperty('xqss', 'r', 'Subtransient q-Axis Reactance in p.u.', py_name='xqss'),
        DgsProperty('xrlq', 'r', 'q-Axis Damper Leakage Reactance in p.u.', py_name='xrlq'),
        DgsProperty('tds', 'r', 'Transient Open-Circuit Time Constant Tdo\' in s', py_name='tds'),
        DgsProperty('tqs', 'r', 'Transient Open-Circuit Time Constant Tqo\' in s', py_name='tqs'),
        DgsProperty('tdss', 'r', 'Subtransient Open-Circuit Time Constant Tdo\'\' in s', py_name='tdss'),
        DgsProperty('tqss', 'r', 'Subtransient Open-Circuit Time Constant Tqo\'\' in s', py_name='tqss'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.sgn: float = 0.1
        self.ugn: float = 0.0
        self.cosn: float = 0.0
        self.xd: float = 0.0
        self.xq: float = 0.0
        self.xdsss: float = 0.0
        self.rstr: float = 0.0
        self.xstr: float = 0.0
        self.xdsat: float = 0.0
        self.satur: int = 0
        self.Q_min: float = 0.0
        self.Q_max: float = 0.0
        self.q_min: float = 0.0
        self.q_max: float = 0.0
        self.for_name: str = ""
        self.nphase: int = 3
        self.nslty: int = 0
        self.x0sy: float = 0.0
        self.r0sy: float = 0.0
        self.x2sy: float = 0.0
        self.r2sy: float = 0.0
        self.iopt_data: int = 0
        self.xds: float = 0.0
        self.xqs: float = 0.0
        self.xl: float = 0.0
        self.xdss: float = 0.0
        self.xqss: float = 0.0
        self.xrlq: float = 0.0
        self.tds: float = 0.0
        self.tqs: float = 0.0
        self.tdss: float = 0.0
        self.tqss: float = 0.0


class TypTr2(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "strn",
        "frnom",
        "utrn_h",
        "utrn_l",
        "uktr",
        "pcutr",
        "uk0tr",
        "ur0tr",
        "tr2cn_h",
        "tr2cn_l",
        "nt2ag",
        "curmg",
        "pfe",
        "zx0hl_n",
        "tap_side",
        "dutap",
        "phitr",
        "nntap0",
        "ntpmn",
        "ntpmx",
        "manuf",
        "chr_name",
        "for_name",
        "nt2ph",
        "itapch",
    )
    element_type = 'TypTr2'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a:40', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('strn', 'r', 'Rated Power in MVA', py_name='strn'),
        DgsProperty('frnom', 'r', 'Nominal Frequency in Hz', py_name='frnom'),
        DgsProperty('utrn_h', 'r', 'Rated Voltage: HV-Side in kV', py_name='utrn_h'),
        DgsProperty('utrn_l', 'r', 'Rated Voltage: LV-Side in kV', py_name='utrn_l'),
        DgsProperty('uktr', 'r', 'Positive Sequence Impedance: Short-Circuit Voltage uk in %', py_name='uktr'),
        DgsProperty('pcutr', 'r', 'Positive Sequence Impedance: Copper Losses in kW', py_name='pcutr'),
        DgsProperty('uk0tr', 'r', 'Zero Sequence Impedance: Short-Circuit Voltage uk0 in %', py_name='uk0tr'),
        DgsProperty('ur0tr', 'r', 'Zero Sequence Impedance: SHC-Voltage (Re(uk0)) uk0r in %', py_name='ur0tr'),
        DgsProperty('tr2cn_h', 'a:2', 'Vector Group: HV-Side:Y :YN:Z :ZN:D', py_name='tr2cn_h'),
        DgsProperty('tr2cn_l', 'a:2', 'Vector Group: LV-Side:Y :YN:Z :ZN:D', py_name='tr2cn_l'),
        DgsProperty('nt2ag', 'r', 'Vector Group: Phase Shift in *30deg', py_name='nt2ag'),
        DgsProperty('curmg', 'r', 'Magnetizing Impedance: No Load Current in %', py_name='curmg'),
        DgsProperty('pfe', 'r', 'Magnetizing Impedance: No Load Losses in kW', py_name='pfe'),
        DgsProperty('zx0hl_n', 'r', 'Zero Sequence Magnetizing Impedance: Mag. Impedance/uk0', py_name='zx0hl_n'),
        DgsProperty('tap_side', 'i', 'Tap Changer 1: at Side:HV:LV', py_name='tap_side'),
        DgsProperty('dutap', 'r', 'Additional Voltage per Tap in %', py_name='dutap'),
        DgsProperty('phitr', 'r', 'Phase of du in deg', py_name='phitr'),
        DgsProperty('nntap0', 'i', 'Neutral Position', py_name='nntap0'),
        DgsProperty('ntpmn', 'i', 'Minimum Position', py_name='ntpmn'),
        DgsProperty('ntpmx', 'i', 'Maximum Position', py_name='ntpmx'),
        DgsProperty('manuf', 'a:20', 'Manufacturer', py_name='manuf'),
        DgsProperty('chr_name', 'a:20', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('nt2ph', 'i', 'Number of Phases', py_name='nt2ph'),
        DgsProperty('itapch', 'i', 'Tap Changer Type Code', py_name='itapch'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.strn: float = 0.0
        self.frnom: float = 0.0
        self.utrn_h: float = 0.0
        self.utrn_l: float = 0.0
        self.uktr: float = 0.0
        self.pcutr: float = 0.0
        self.uk0tr: float = 0.0
        self.ur0tr: float = 0.0
        self.tr2cn_h: str = "D"  # Y,YN,Z,ZN,D.
        self.tr2cn_l: str = "Y"
        self.nt2ag: float = 0.0
        self.curmg: float = 0.0
        self.pfe: float = 0.0
        self.zx0hl_n: float = 0.0
        self.tap_side: int = 0
        self.dutap: float = 0.0
        self.phitr: float = 0.0
        self.nntap0: int = 0
        self.ntpmn: int = 0
        self.ntpmx: int = 0
        self.manuf: str = ""
        self.chr_name: str = ""
        self.for_name: str = ""
        self.nt2ph: int = 3  # 3-phase
        self.itapch: int = 0


class TypTr3(DGSElement):
    __slots__ = (
        "ID",
        "loc_name",
        "fold_id",
        "curm3",
        "du3tp_h",
        "du3tp_l",
        "du3tp_m",
        "n3tmn_h",
        "n3tmn_l",
        "n3tmn_m",
        "n3tmx_h",
        "n3tmx_l",
        "n3tmx_m",
        "n3tp0_h",
        "n3tp0_l",
        "n3tp0_m",
        "nt3ag_h",
        "nt3ag_l",
        "nt3ag_m",
        "pcut3_h",
        "pcut3_l",
        "pcut3_m",
        "pfe",
        "ph3tr_h",
        "ph3tr_l",
        "ph3tr_m",
        "strn3_h",
        "strn3_l",
        "strn3_m",
        "tr3cn_h",
        "tr3cn_l",
        "tr3cn_m",
        "uk0hl",
        "uk0hm",
        "uk0ml",
        "uktr3_h",
        "uktr3_l",
        "uktr3_m",
        "ur0hl",
        "ur0hm",
        "ur0ml",
        "utrn3_h",
        "utrn3_l",
        "utrn3_m",
        "for_name",
        "itapos",
        "i3loc",
    )
    element_type = 'TypTr3'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('loc_name', 'a', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('curm3', 'r', 'No-Load Current in %', py_name='curm3'),
        DgsProperty('du3tp_h', 'r', 'Additional Voltage per Tap at HV Side in %', py_name='du3tp_h'),
        DgsProperty('du3tp_l', 'r', 'Additional Voltage per Tap at LV Side in %', py_name='du3tp_l'),
        DgsProperty('du3tp_m', 'r', 'Additional Voltage per Tap at MV Side in %', py_name='du3tp_m'),
        DgsProperty('n3tmn_h', 'i', 'Minimum Tap Position at HV Side', py_name='n3tmn_h'),
        DgsProperty('n3tmn_l', 'i', 'Minimum Tap Position at LV Side', py_name='n3tmn_l'),
        DgsProperty('n3tmn_m', 'i', 'Minimum Tap Position at MV Side', py_name='n3tmn_m'),
        DgsProperty('n3tmx_h', 'i', 'Maximum Tap Position at HV Side', py_name='n3tmx_h'),
        DgsProperty('n3tmx_l', 'i', 'Maximum Tap Position at LV Side', py_name='n3tmx_l'),
        DgsProperty('n3tmx_m', 'i', 'Maximum Tap Position at MV Side', py_name='n3tmx_m'),
        DgsProperty('n3tp0_h', 'i', 'Neutral Tap Position at HV Side', py_name='n3tp0_h'),
        DgsProperty('n3tp0_l', 'i', 'Neutral Tap Position at LV Side', py_name='n3tp0_l'),
        DgsProperty('n3tp0_m', 'i', 'Neutral Tap Position at MV Side', py_name='n3tp0_m'),
        DgsProperty('nt3ag_h', 'r', 'Vector Group Phase Shift at HV Side in multiples of 30 deg', py_name='nt3ag_h'),
        DgsProperty('nt3ag_l', 'r', 'Vector Group Phase Shift at LV Side in multiples of 30 deg', py_name='nt3ag_l'),
        DgsProperty('nt3ag_m', 'r', 'Vector Group Phase Shift at MV Side in multiples of 30 deg', py_name='nt3ag_m'),
        DgsProperty('pcut3_h', 'r', 'Copper Losses of HV-MV Branch in kW', py_name='pcut3_h'),
        DgsProperty('pcut3_l', 'r', 'Copper Losses of LV-HV Branch in kW', py_name='pcut3_l'),
        DgsProperty('pcut3_m', 'r', 'Copper Losses of MV-LV Branch in kW', py_name='pcut3_m'),
        DgsProperty('pfe', 'r', 'No-Load Losses in kW', py_name='pfe'),
        DgsProperty('ph3tr_h', 'r', 'Phase of du at HV Side in deg', py_name='ph3tr_h'),
        DgsProperty('ph3tr_l', 'r', 'Phase of du at LV Side in deg', py_name='ph3tr_l'),
        DgsProperty('ph3tr_m', 'r', 'Phase of du at MV Side in deg', py_name='ph3tr_m'),
        DgsProperty('strn3_h', 'r', 'Rated Power of HV Winding in MVA', py_name='strn3_h'),
        DgsProperty('strn3_l', 'r', 'Rated Power of LV Winding in MVA', py_name='strn3_l'),
        DgsProperty('strn3_m', 'r', 'Rated Power of MV Winding in MVA', py_name='strn3_m'),
        DgsProperty('tr3cn_h', 'a', 'Vector Group at HV Side: Y:YN:Z:ZN:D', py_name='tr3cn_h'),
        DgsProperty('tr3cn_l', 'a', 'Vector Group at LV Side: Y:YN:Z:ZN:D', py_name='tr3cn_l'),
        DgsProperty('tr3cn_m', 'a', 'Vector Group at MV Side: Y:YN:Z:ZN:D', py_name='tr3cn_m'),
        DgsProperty('uk0hl', 'r', 'Zero-Sequence Short-Circuit Voltage between HV and LV in %', py_name='uk0hl'),
        DgsProperty('uk0hm', 'r', 'Zero-Sequence Short-Circuit Voltage between HV and MV in %', py_name='uk0hm'),
        DgsProperty('uk0ml', 'r', 'Zero-Sequence Short-Circuit Voltage between MV and LV in %', py_name='uk0ml'),
        DgsProperty('uktr3_h', 'r', 'Positive-Sequence Short-Circuit Voltage of HV-MV Branch in %', py_name='uktr3_h'),
        DgsProperty('uktr3_l', 'r', 'Positive-Sequence Short-Circuit Voltage of LV-HV Branch in %', py_name='uktr3_l'),
        DgsProperty('uktr3_m', 'r', 'Positive-Sequence Short-Circuit Voltage of MV-LV Branch in %', py_name='uktr3_m'),
        DgsProperty('ur0hl', 'r', 'Real Part of uk0 between HV and LV in %', py_name='ur0hl'),
        DgsProperty('ur0hm', 'r', 'Real Part of uk0 between HV and MV in %', py_name='ur0hm'),
        DgsProperty('ur0ml', 'r', 'Real Part of uk0 between MV and LV in %', py_name='ur0ml'),
        DgsProperty('utrn3_h', 'r', 'Rated Voltage at HV Side in kV', py_name='utrn3_h'),
        DgsProperty('utrn3_l', 'r', 'Rated Voltage at LV Side in kV', py_name='utrn3_l'),
        DgsProperty('utrn3_m', 'r', 'Rated Voltage at MV Side in kV', py_name='utrn3_m'),
        DgsProperty('for_name', 'a:50', 'Foreign Key', py_name='for_name'),
        DgsProperty('itapos', 'i', 'Tapped Winding Position Code', py_name='itapos'),
        DgsProperty('i3loc', 'i', 'Transformer Model Layout Code', py_name='i3loc'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""

        # reals (r)
        self.curm3: float = 0.0
        self.du3tp_h: float = 0.0
        self.du3tp_l: float = 0.0
        self.du3tp_m: float = 0.0

        # ints (i)
        self.n3tmn_h: int = 0
        self.n3tmn_l: int = 0
        self.n3tmn_m: int = 0
        self.n3tmx_h: int = 0
        self.n3tmx_l: int = 0
        self.n3tmx_m: int = 0
        self.n3tp0_h: int = 0
        self.n3tp0_l: int = 0
        self.n3tp0_m: int = 0

        # reals (r)
        self.nt3ag_h: float = 0.0
        self.nt3ag_l: float = 0.0
        self.nt3ag_m: float = 0.0
        self.pcut3_h: float = 0.0
        self.pcut3_l: float = 0.0
        self.pcut3_m: float = 0.0
        self.pfe: float = 0.0
        self.ph3tr_h: float = 0.0
        self.ph3tr_l: float = 0.0
        self.ph3tr_m: float = 0.0
        self.strn3_h: float = 0.0
        self.strn3_l: float = 0.0
        self.strn3_m: float = 0.0

        # strings (a)
        self.tr3cn_h: str = ""
        self.tr3cn_l: str = ""
        self.tr3cn_m: str = ""

        # reals (r)
        self.uk0hl: float = 0.0
        self.uk0hm: float = 0.0
        self.uk0ml: float = 0.0
        self.uktr3_h: float = 0.0
        self.uktr3_l: float = 0.0
        self.uktr3_m: float = 0.0
        self.ur0hl: float = 0.0
        self.ur0hm: float = 0.0
        self.ur0ml: float = 0.0
        self.utrn3_h: float = 0.0
        self.utrn3_l: float = 0.0
        self.utrn3_m: float = 0.0

        # strings (a:50)
        self.for_name: str = ""

        # ints (i)
        self.itapos: int = 0
        self.i3loc: int = 0


class TypTr4(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "inputData",
        "pfe",
        "chr_name",
        "for_name",
        "dat_src",
        "trcon_h0",
        "trcon_l1",
        "trcon_l2",
        "trcon_l3",
        "vecgrp",
        "ansiclass",
        "manuf",
        "appr_modby",
        "appr_modif",
        "sn_h0",
        "sn_l1",
        "sn_l2",
        "sn_l3",
        "un_h0",
        "un_l1",
        "un_l2",
        "un_l3",
        "uk_h0l1",
        "uk_h0l2",
        "uk_h0l3",
        "uk_l1l2",
        "uk_l1l3",
        "uk_l2l3",
        "pcu_h0l1",
        "pcu_h0l2",
        "pcu_h0l3",
        "pcu_l1l2",
        "pcu_l1l3",
        "pcu_l2l3",
        "uk_h0",
        "uk_l1",
        "uk_l2",
        "uk_l3",
        "pcu_h0",
        "pcu_l1",
        "pcu_l2",
        "pcu_l3",
        "curmag",
        "cur0mag",
        "ntapmin_h0",
        "ntapmin_l1",
        "ntapmin_l2",
        "ntapmin_l3",
        "ntapmax_h0",
        "ntapmax_l1",
        "ntapmax_l2",
        "ntapmax_l3",
        "ntapneu_h0",
        "ntapneu_l1",
        "ntapneu_l2",
        "ntapneu_l3",
        "dutap_h0",
        "dutap_l1",
        "dutap_l2",
        "dutap_l3",
        "phitr_h0",
        "phitr_l1",
        "phitr_l2",
        "phitr_l3",
        "oltc_h0",
        "oltc_l1",
        "oltc_l2",
        "oltc_l3",
        "uk0_h0l1",
        "uk0_h0l2",
        "uk0_h0l3",
        "uk0_l1l2",
        "uk0_l1l3",
        "uk0_l2l3",
        "ukr0_h0l1",
        "ukr0_h0l2",
        "ukr0_h0l3",
        "ukr0_l1l2",
        "ukr0_l1l3",
        "ukr0_l2l3",
        "ukr_h0l1",
        "ukr_h0l2",
        "ukr_h0l3",
        "ukr_l1l2",
        "ukr_l1l3",
        "ukr_l2l3",
        "xtor_h0l1",
        "xtor_h0l2",
        "xtor_h0l3",
        "xtor_l1l2",
        "xtor_l1l3",
        "xtor_l2l3",
        "r1pu_h0l1",
        "r1pu_h0l2",
        "r1pu_h0l3",
        "r1pu_l1l2",
        "r1pu_l1l3",
        "r1pu_l2l3",
        "x1pu_h0l1",
        "x1pu_h0l2",
        "x1pu_h0l3",
        "x1pu_l1l2",
        "x1pu_l1l3",
        "x1pu_l2l3",
        "r0pu_h0",
        "r0pu_l1",
        "r0pu_l2",
        "r0pu_l3",
        "x0pu_h0",
        "x0pu_l1",
        "x0pu_l2",
        "x0pu_l3",
        "bm1",
        "gm1",
        "desc_0",
        "doc_id",
    )
    element_type = 'TypTr4'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier for DGS file', py_name='ID'),
        DgsProperty('OP', 'a:1', 'Operation flag', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('inputData', 'i', 'Input data mode for Tr4W, 0 for complete, 1 for simplified',
                    py_name='inputData'),

        DgsProperty('pfe', 'r', 'Iron Losses in kW', py_name='pfe'),
        DgsProperty('chr_name', 'a:40', 'Characteristic Name', py_name='chr_name'),
        DgsProperty('for_name', 'a:100', 'Foreign Key', py_name='for_name'),
        DgsProperty('dat_src', 'a:6', 'Data Source', py_name='dat_src'),

        DgsProperty('trcon_h0', 'a:4', 'Vector Group HV Winding', py_name='trcon_h0'),
        DgsProperty('trcon_l1', 'a:4', 'Vector Group LV1 Winding', py_name='trcon_l1'),
        DgsProperty('trcon_l2', 'a:4', 'Vector Group LV2 Winding', py_name='trcon_l2'),
        DgsProperty('trcon_l3', 'a:4', 'Vector Group LV3 Winding', py_name='trcon_l3'),
        DgsProperty('vecgrp', 'a', 'Vector Group', py_name='vecgrp'),

        DgsProperty('ansiclass', 'a:10', 'ANSI Class', py_name='ansiclass'),
        DgsProperty('manuf', 'a:40', 'Manufacturer', py_name='manuf'),
        DgsProperty('appr_modby', 'a:80', 'Approved / Modified By', py_name='appr_modby'),
        DgsProperty('appr_modif', 'l', 'Approval Modification Timestamp', py_name='appr_modif'),

        DgsProperty('sn_h0', 'r', 'Rated Power HV in MVA', py_name='sn_h0'),
        DgsProperty('sn_l1', 'r', 'Rated Power LV1 in MVA', py_name='sn_l1'),
        DgsProperty('sn_l2', 'r', 'Rated Power LV2 in MVA', py_name='sn_l2'),
        DgsProperty('sn_l3', 'r', 'Rated Power LV3 in MVA', py_name='sn_l3'),

        DgsProperty('un_h0', 'r', 'Rated Voltage HV in kV', py_name='un_h0'),
        DgsProperty('un_l1', 'r', 'Rated Voltage LV1 in kV', py_name='un_l1'),
        DgsProperty('un_l2', 'r', 'Rated Voltage LV2 in kV', py_name='un_l2'),
        DgsProperty('un_l3', 'r', 'Rated Voltage LV3 in kV', py_name='un_l3'),

        DgsProperty('uk_h0l1', 'r', 'Short-Circuit Voltage HV-LV1 in percent', py_name='uk_h0l1'),
        DgsProperty('uk_h0l2', 'r', 'Short-Circuit Voltage HV-LV2 in percent', py_name='uk_h0l2'),
        DgsProperty('uk_h0l3', 'r', 'Short-Circuit Voltage HV-LV3 in percent', py_name='uk_h0l3'),
        DgsProperty('uk_l1l2', 'r', 'Short-Circuit Voltage LV1-LV2 in percent', py_name='uk_l1l2'),
        DgsProperty('uk_l1l3', 'r', 'Short-Circuit Voltage LV1-LV3 in percent', py_name='uk_l1l3'),
        DgsProperty('uk_l2l3', 'r', 'Short-Circuit Voltage LV2-LV3 in percent', py_name='uk_l2l3'),

        DgsProperty('pcu_h0l1', 'r', 'Copper Losses HV-LV1 in kW', py_name='pcu_h0l1'),
        DgsProperty('pcu_h0l2', 'r', 'Copper Losses HV-LV2 in kW', py_name='pcu_h0l2'),
        DgsProperty('pcu_h0l3', 'r', 'Copper Losses HV-LV3 in kW', py_name='pcu_h0l3'),
        DgsProperty('pcu_l1l2', 'r', 'Copper Losses LV1-LV2 in kW', py_name='pcu_l1l2'),
        DgsProperty('pcu_l1l3', 'r', 'Copper Losses LV1-LV3 in kW', py_name='pcu_l1l3'),
        DgsProperty('pcu_l2l3', 'r', 'Copper Losses LV2-LV3 in kW', py_name='pcu_l2l3'),

        DgsProperty('uk_h0', 'r', 'Short-Circuit Voltage HV in percent', py_name='uk_h0'),
        DgsProperty('uk_l1', 'r', 'Short-Circuit Voltage LV1 in percent', py_name='uk_l1'),
        DgsProperty('uk_l2', 'r', 'Short-Circuit Voltage LV2 in percent', py_name='uk_l2'),
        DgsProperty('uk_l3', 'r', 'Short-Circuit Voltage LV3 in percent', py_name='uk_l3'),

        DgsProperty('pcu_h0', 'r', 'Copper Losses HV in kW', py_name='pcu_h0'),
        DgsProperty('pcu_l1', 'r', 'Copper Losses LV1 in kW', py_name='pcu_l1'),
        DgsProperty('pcu_l2', 'r', 'Copper Losses LV2 in kW', py_name='pcu_l2'),
        DgsProperty('pcu_l3', 'r', 'Copper Losses LV3 in kW', py_name='pcu_l3'),

        DgsProperty('curmag', 'r', 'No-Load Current in percent', py_name='curmag'),
        DgsProperty('cur0mag', 'r', 'Zero Sequence No-Load Current in percent', py_name='cur0mag'),

        DgsProperty('ntapmin_h0', 'i', 'Minimum Tap Position HV', py_name='ntapmin_h0'),
        DgsProperty('ntapmin_l1', 'i', 'Minimum Tap Position LV1', py_name='ntapmin_l1'),
        DgsProperty('ntapmin_l2', 'i', 'Minimum Tap Position LV2', py_name='ntapmin_l2'),
        DgsProperty('ntapmin_l3', 'i', 'Minimum Tap Position LV3', py_name='ntapmin_l3'),

        DgsProperty('ntapmax_h0', 'i', 'Maximum Tap Position HV', py_name='ntapmax_h0'),
        DgsProperty('ntapmax_l1', 'i', 'Maximum Tap Position LV1', py_name='ntapmax_l1'),
        DgsProperty('ntapmax_l2', 'i', 'Maximum Tap Position LV2', py_name='ntapmax_l2'),
        DgsProperty('ntapmax_l3', 'i', 'Maximum Tap Position LV3', py_name='ntapmax_l3'),

        DgsProperty('ntapneu_h0', 'i', 'Neutral Tap Position HV', py_name='ntapneu_h0'),
        DgsProperty('ntapneu_l1', 'i', 'Neutral Tap Position LV1', py_name='ntapneu_l1'),
        DgsProperty('ntapneu_l2', 'i', 'Neutral Tap Position LV2', py_name='ntapneu_l2'),
        DgsProperty('ntapneu_l3', 'i', 'Neutral Tap Position LV3', py_name='ntapneu_l3'),

        DgsProperty('dutap_h0', 'r', 'Tap Step HV in percent', py_name='dutap_h0'),
        DgsProperty('dutap_l1', 'r', 'Tap Step LV1 in percent', py_name='dutap_l1'),
        DgsProperty('dutap_l2', 'r', 'Tap Step LV2 in percent', py_name='dutap_l2'),
        DgsProperty('dutap_l3', 'r', 'Tap Step LV3 in percent', py_name='dutap_l3'),

        DgsProperty('phitr_h0', 'r', 'Phase Shift HV in deg', py_name='phitr_h0'),
        DgsProperty('phitr_l1', 'r', 'Phase Shift LV1 in deg', py_name='phitr_l1'),
        DgsProperty('phitr_l2', 'r', 'Phase Shift LV2 in deg', py_name='phitr_l2'),
        DgsProperty('phitr_l3', 'r', 'Phase Shift LV3 in deg', py_name='phitr_l3'),

        DgsProperty('oltc_h0', 'i', 'OLTC Available HV', py_name='oltc_h0'),
        DgsProperty('oltc_l1', 'i', 'OLTC Available LV1', py_name='oltc_l1'),
        DgsProperty('oltc_l2', 'i', 'OLTC Available LV2', py_name='oltc_l2'),
        DgsProperty('oltc_l3', 'i', 'OLTC Available LV3', py_name='oltc_l3'),

        DgsProperty('uk0_h0l1', 'r', 'Zero Sequence Short-Circuit Voltage HV-LV1 in percent', py_name='uk0_h0l1'),
        DgsProperty('uk0_h0l2', 'r', 'Zero Sequence Short-Circuit Voltage HV-LV2 in percent', py_name='uk0_h0l2'),
        DgsProperty('uk0_h0l3', 'r', 'Zero Sequence Short-Circuit Voltage HV-LV3 in percent', py_name='uk0_h0l3'),
        DgsProperty('uk0_l1l2', 'r', 'Zero Sequence Short-Circuit Voltage LV1-LV2 in percent', py_name='uk0_l1l2'),
        DgsProperty('uk0_l1l3', 'r', 'Zero Sequence Short-Circuit Voltage LV1-LV3 in percent', py_name='uk0_l1l3'),
        DgsProperty('uk0_l2l3', 'r', 'Zero Sequence Short-Circuit Voltage LV2-LV3 in percent', py_name='uk0_l2l3'),

        DgsProperty('ukr0_h0l1', 'r', 'Zero Sequence Resistive Short-Circuit Voltage HV-LV1 in percent',
                    py_name='ukr0_h0l1'),
        DgsProperty('ukr0_h0l2', 'r', 'Zero Sequence Resistive Short-Circuit Voltage HV-LV2 in percent',
                    py_name='ukr0_h0l2'),
        DgsProperty('ukr0_h0l3', 'r', 'Zero Sequence Resistive Short-Circuit Voltage HV-LV3 in percent',
                    py_name='ukr0_h0l3'),
        DgsProperty('ukr0_l1l2', 'r', 'Zero Sequence Resistive Short-Circuit Voltage LV1-LV2 in percent',
                    py_name='ukr0_l1l2'),
        DgsProperty('ukr0_l1l3', 'r', 'Zero Sequence Resistive Short-Circuit Voltage LV1-LV3 in percent',
                    py_name='ukr0_l1l3'),
        DgsProperty('ukr0_l2l3', 'r', 'Zero Sequence Resistive Short-Circuit Voltage LV2-LV3 in percent',
                    py_name='ukr0_l2l3'),

        DgsProperty('ukr_h0l1', 'r', 'Resistive Short-Circuit Voltage HV-LV1 in percent', py_name='ukr_h0l1'),
        DgsProperty('ukr_h0l2', 'r', 'Resistive Short-Circuit Voltage HV-LV2 in percent', py_name='ukr_h0l2'),
        DgsProperty('ukr_h0l3', 'r', 'Resistive Short-Circuit Voltage HV-LV3 in percent', py_name='ukr_h0l3'),
        DgsProperty('ukr_l1l2', 'r', 'Resistive Short-Circuit Voltage LV1-LV2 in percent', py_name='ukr_l1l2'),
        DgsProperty('ukr_l1l3', 'r', 'Resistive Short-Circuit Voltage LV1-LV3 in percent', py_name='ukr_l1l3'),
        DgsProperty('ukr_l2l3', 'r', 'Resistive Short-Circuit Voltage LV2-LV3 in percent', py_name='ukr_l2l3'),

        DgsProperty('xtor_h0l1', 'r', 'X/R Ratio HV-LV1', py_name='xtor_h0l1'),
        DgsProperty('xtor_h0l2', 'r', 'X/R Ratio HV-LV2', py_name='xtor_h0l2'),
        DgsProperty('xtor_h0l3', 'r', 'X/R Ratio HV-LV3', py_name='xtor_h0l3'),
        DgsProperty('xtor_l1l2', 'r', 'X/R Ratio LV1-LV2', py_name='xtor_l1l2'),
        DgsProperty('xtor_l1l3', 'r', 'X/R Ratio LV1-LV3', py_name='xtor_l1l3'),
        DgsProperty('xtor_l2l3', 'r', 'X/R Ratio LV2-LV3', py_name='xtor_l2l3'),

        DgsProperty('r1pu_h0l1', 'r', 'Positive Sequence Resistance HV-LV1 in p.u.', py_name='r1pu_h0l1'),
        DgsProperty('r1pu_h0l2', 'r', 'Positive Sequence Resistance HV-LV2 in p.u.', py_name='r1pu_h0l2'),
        DgsProperty('r1pu_h0l3', 'r', 'Positive Sequence Resistance HV-LV3 in p.u.', py_name='r1pu_h0l3'),
        DgsProperty('r1pu_l1l2', 'r', 'Positive Sequence Resistance LV1-LV2 in p.u.', py_name='r1pu_l1l2'),
        DgsProperty('r1pu_l1l3', 'r', 'Positive Sequence Resistance LV1-LV3 in p.u.', py_name='r1pu_l1l3'),
        DgsProperty('r1pu_l2l3', 'r', 'Positive Sequence Resistance LV2-LV3 in p.u.', py_name='r1pu_l2l3'),

        DgsProperty('x1pu_h0l1', 'r', 'Positive Sequence Reactance HV-LV1 in p.u.', py_name='x1pu_h0l1'),
        DgsProperty('x1pu_h0l2', 'r', 'Positive Sequence Reactance HV-LV2 in p.u.', py_name='x1pu_h0l2'),
        DgsProperty('x1pu_h0l3', 'r', 'Positive Sequence Reactance HV-LV3 in p.u.', py_name='x1pu_h0l3'),
        DgsProperty('x1pu_l1l2', 'r', 'Positive Sequence Reactance LV1-LV2 in p.u.', py_name='x1pu_l1l2'),
        DgsProperty('x1pu_l1l3', 'r', 'Positive Sequence Reactance LV1-LV3 in p.u.', py_name='x1pu_l1l3'),
        DgsProperty('x1pu_l2l3', 'r', 'Positive Sequence Reactance LV2-LV3 in p.u.', py_name='x1pu_l2l3'),

        DgsProperty('r0pu_h0', 'r', 'Zero Sequence Resistance HV in p.u.', py_name='r0pu_h0'),
        DgsProperty('r0pu_l1', 'r', 'Zero Sequence Resistance LV1 in p.u.', py_name='r0pu_l1'),
        DgsProperty('r0pu_l2', 'r', 'Zero Sequence Resistance LV2 in p.u.', py_name='r0pu_l2'),
        DgsProperty('r0pu_l3', 'r', 'Zero Sequence Resistance LV3 in p.u.', py_name='r0pu_l3'),

        DgsProperty('x0pu_h0', 'r', 'Zero Sequence Reactance HV in p.u.', py_name='x0pu_h0'),
        DgsProperty('x0pu_l1', 'r', 'Zero Sequence Reactance LV1 in p.u.', py_name='x0pu_l1'),
        DgsProperty('x0pu_l2', 'r', 'Zero Sequence Reactance LV2 in p.u.', py_name='x0pu_l2'),
        DgsProperty('x0pu_l3', 'r', 'Zero Sequence Reactance LV3 in p.u.', py_name='x0pu_l3'),

        DgsProperty('bm1', 'r', 'Positive Sequence Magnetizing Susceptance in p.u.', py_name='bm1'),
        DgsProperty('gm1', 'r', 'Positive Sequence Magnetizing Conductance in p.u.', py_name='gm1'),

        DgsProperty('desc:0', 'a', 'Description Line 0', py_name='desc_0'),
        DgsProperty('doc_id', 'p', 'Document Reference', py_name='doc_id'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.inputData: int = 0

        self.pfe: float = 0.0
        self.chr_name: str = ""
        self.for_name: str = ""
        self.dat_src: str = ""

        self.trcon_h0: str = ""
        self.trcon_l1: str = ""
        self.trcon_l2: str = ""
        self.trcon_l3: str = ""
        self.vecgrp: str = ""

        self.ansiclass: str = ""
        self.manuf: str = ""
        self.appr_modby: str = ""
        self.appr_modif: int = 0

        self.sn_h0: float = 0.0
        self.sn_l1: float = 0.0
        self.sn_l2: float = 0.0
        self.sn_l3: float = 0.0

        self.un_h0: float = 0.0
        self.un_l1: float = 0.0
        self.un_l2: float = 0.0
        self.un_l3: float = 0.0

        self.uk_h0l1: float = 0.0
        self.uk_h0l2: float = 0.0
        self.uk_h0l3: float = 0.0
        self.uk_l1l2: float = 0.0
        self.uk_l1l3: float = 0.0
        self.uk_l2l3: float = 0.0

        self.pcu_h0l1: float = 0.0
        self.pcu_h0l2: float = 0.0
        self.pcu_h0l3: float = 0.0
        self.pcu_l1l2: float = 0.0
        self.pcu_l1l3: float = 0.0
        self.pcu_l2l3: float = 0.0

        self.uk_h0: float = 0.0
        self.uk_l1: float = 0.0
        self.uk_l2: float = 0.0
        self.uk_l3: float = 0.0

        self.pcu_h0: float = 0.0
        self.pcu_l1: float = 0.0
        self.pcu_l2: float = 0.0
        self.pcu_l3: float = 0.0

        self.curmag: float = 0.0
        self.cur0mag: float = 0.0

        self.ntapmin_h0: int = 0
        self.ntapmin_l1: int = 0
        self.ntapmin_l2: int = 0
        self.ntapmin_l3: int = 0

        self.ntapmax_h0: int = 0
        self.ntapmax_l1: int = 0
        self.ntapmax_l2: int = 0
        self.ntapmax_l3: int = 0

        self.ntapneu_h0: int = 0
        self.ntapneu_l1: int = 0
        self.ntapneu_l2: int = 0
        self.ntapneu_l3: int = 0

        self.dutap_h0: float = 0.0
        self.dutap_l1: float = 0.0
        self.dutap_l2: float = 0.0
        self.dutap_l3: float = 0.0

        self.phitr_h0: float = 0.0
        self.phitr_l1: float = 0.0
        self.phitr_l2: float = 0.0
        self.phitr_l3: float = 0.0

        self.oltc_h0: int = 0
        self.oltc_l1: int = 0
        self.oltc_l2: int = 0
        self.oltc_l3: int = 0

        self.uk0_h0l1: float = 0.0
        self.uk0_h0l2: float = 0.0
        self.uk0_h0l3: float = 0.0
        self.uk0_l1l2: float = 0.0
        self.uk0_l1l3: float = 0.0
        self.uk0_l2l3: float = 0.0

        self.ukr0_h0l1: float = 0.0
        self.ukr0_h0l2: float = 0.0
        self.ukr0_h0l3: float = 0.0
        self.ukr0_l1l2: float = 0.0
        self.ukr0_l1l3: float = 0.0
        self.ukr0_l2l3: float = 0.0

        self.ukr_h0l1: float = 0.0
        self.ukr_h0l2: float = 0.0
        self.ukr_h0l3: float = 0.0
        self.ukr_l1l2: float = 0.0
        self.ukr_l1l3: float = 0.0
        self.ukr_l2l3: float = 0.0

        self.xtor_h0l1: float = 0.0
        self.xtor_h0l2: float = 0.0
        self.xtor_h0l3: float = 0.0
        self.xtor_l1l2: float = 0.0
        self.xtor_l1l3: float = 0.0
        self.xtor_l2l3: float = 0.0

        self.r1pu_h0l1: float = 0.0
        self.r1pu_h0l2: float = 0.0
        self.r1pu_h0l3: float = 0.0
        self.r1pu_l1l2: float = 0.0
        self.r1pu_l1l3: float = 0.0
        self.r1pu_l2l3: float = 0.0

        self.x1pu_h0l1: float = 0.0
        self.x1pu_h0l2: float = 0.0
        self.x1pu_h0l3: float = 0.0
        self.x1pu_l1l2: float = 0.0
        self.x1pu_l1l3: float = 0.0
        self.x1pu_l2l3: float = 0.0

        self.r0pu_h0: float = 0.0
        self.r0pu_l1: float = 0.0
        self.r0pu_l2: float = 0.0
        self.r0pu_l3: float = 0.0

        self.x0pu_h0: float = 0.0
        self.x0pu_l1: float = 0.0
        self.x0pu_l2: float = 0.0
        self.x0pu_l3: float = 0.0

        self.bm1: float = 0.0
        self.gm1: float = 0.0

        self.desc_0: str = ""
        self.doc_id: str = ""


# ----------------------------------------------------------------------------------------------------------------------
# Overhead line modelling (PowerFactory: conductor / tower / line coupling)
# ----------------------------------------------------------------------------------------------------------------------


def _dgs_get(parts: List[str], header_map: Dict[str, int], key: str) -> str | None:
    """Get the raw column value for a given DGS key."""
    idx = header_map.get(key)
    if idx is None:
        return None
    if 0 <= idx < len(parts):
        return parts[idx]
    return None


class TypCon(DGSElement):
    """PowerFactory conductor type (TypCon) mapped to VeraGrid Wire."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "uline",
        "sline",
        "ncsub",
        "dsubc",
        "rpha",
        "diaco",
        "diatub",
        "mlei",
        "iModel",
    )

    element_type = 'TypCon'

    properties_list = [
        DgsProperty(name='ID', dgs_type='a:40', description='Unique identifier for DGS file', py_name='ID'),
        DgsProperty(name='OP', dgs_type='a:1', description='Operation', py_name='OP'),
        DgsProperty(name='loc_name', dgs_type='a:80', description='Name', py_name='loc_name'),
        DgsProperty(name='fold_id', dgs_type='p', description='In Folder', py_name='fold_id'),
        DgsProperty(name='uline', dgs_type='r', description='Rated Voltage in kV', py_name='uline'),
        DgsProperty(name='sline', dgs_type='r', description='Rated Current in kA', py_name='sline'),
        DgsProperty(name='ncsub', dgs_type='i', description='Number of Subconductors', py_name='ncsub'),
        DgsProperty(name='dsubc', dgs_type='r', description='Bundle Spacing in m', py_name='dsubc'),
        DgsProperty(name='rpha', dgs_type='r', description='DC-Resistance (20C) in Ohm/km', py_name='rpha'),
        DgsProperty(name='diaco', dgs_type='r', description='Outer Diameter in mm', py_name='diaco'),
        DgsProperty(name='diatub', dgs_type='r', description='Inner Diameter in mm', py_name='diatub'),
        DgsProperty(name='mlei', dgs_type='a:20', description='Conductor Material', py_name='mlei'),
        DgsProperty(name='iModel', dgs_type='i', description='Solid or Tubular conductor', py_name='iModel'),
    ]

    def __init__(self):
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.fold_id: str | None = None
        self.uline: float = 0.0
        self.sline: float = 0.0
        self.ncsub: int = 1
        self.dsubc: float = 0.0
        self.rpha: float = 0.0
        self.diaco: float = 0.0
        self.diatub: float = 0.0
        self.mlei: str = ''
        self.iModel: int = 1


class TypCab(DGSElement):
    """PowerFactory geometrical single-core cable type."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "uline",
        "rpha",
        "diaCon",
        "diaTube",
        "diaCab",
        "thSht",
        "has_arm",
        "cHasEl_2",
        "thIns_SIZEROW",
        "thIns_0",
        "thIns_1",
        "thIns_2",
        "thIns",
        "crho_SIZEROW",
        "crho_0",
        "crho_1",
        "crho_2",
        "crho",
        "Cf_SIZEROW",
        "Cf_0",
        "Cf_1",
        "Cf_2",
        "Cf",
        "cepsr_SIZEROW",
        "cepsr_0",
        "cepsr_1",
        "cepsr_2",
        "cepsr",
        "ctand_SIZEROW",
        "ctand_0",
        "ctand_1",
        "ctand_2",
        "ctand",
        "my_SIZEROW",
        "my_0",
        "my_1",
        "my_2",
        "my",
        "ks",
        "kp",
    )

    element_type = 'TypCab'
    properties_list = list((
        DgsProperty('FID', 'a:40', 'Unique DGS identifier', py_name='ID'),
        DgsProperty('OP', 'a:1', 'Operation', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('uline', 'r', 'Rated voltage in kV', py_name='uline'),
        DgsProperty('rpha', 'r', 'Core DC resistance at 20 C in Ohm/km', py_name='rpha'),
        DgsProperty('diaCon', 'r', 'Core outer diameter in mm', py_name='diaCon'),
        DgsProperty('diaTube', 'r', 'Core inner diameter in mm', py_name='diaTube'),
        DgsProperty('diaCab', 'r', 'Overall cable diameter in mm', py_name='diaCab'),
        DgsProperty('thSht', 'r', 'Metallic sheath thickness in mm', py_name='thSht'),
        DgsProperty('has_arm', 'i', 'Armour enabled', py_name='has_arm', optional=True),
        DgsProperty('cHasEl:2', 'i', 'Third conducting layer enabled', py_name='cHasEl_2', optional=True),
        DgsProperty('thIns:SIZEROW', 'i', 'Insulation vector size', py_name='thIns_SIZEROW'),
        DgsProperty('thIns:0', 'r', 'Insulation thickness 0', py_name='thIns_0'),
        DgsProperty('thIns:1', 'r', 'Insulation thickness 1', py_name='thIns_1'),
        DgsProperty('thIns:2', 'r', 'Insulation thickness 2', py_name='thIns_2'),
        DgsProperty('crho:SIZEROW', 'i', 'Resistivity vector size', py_name='crho_SIZEROW'),
        DgsProperty('crho:0', 'r', 'Conducting resistivity 0', py_name='crho_0'),
        DgsProperty('crho:1', 'r', 'Conducting resistivity 1', py_name='crho_1'),
        DgsProperty('crho:2', 'r', 'Conducting resistivity 2', py_name='crho_2'),
        DgsProperty('Cf:SIZEROW', 'i', 'Filling-factor vector size', py_name='Cf_SIZEROW'),
        DgsProperty('Cf:0', 'r', 'Filling factor 0', py_name='Cf_0'),
        DgsProperty('Cf:1', 'r', 'Filling factor 1', py_name='Cf_1'),
        DgsProperty('Cf:2', 'r', 'Filling factor 2', py_name='Cf_2'),
        DgsProperty('cepsr:SIZEROW', 'i', 'Permittivity vector size', py_name='cepsr_SIZEROW'),
        DgsProperty('cepsr:0', 'r', 'Relative permittivity 0', py_name='cepsr_0'),
        DgsProperty('cepsr:1', 'r', 'Relative permittivity 1', py_name='cepsr_1'),
        DgsProperty('cepsr:2', 'r', 'Relative permittivity 2', py_name='cepsr_2'),
        DgsProperty('ctand:SIZEROW', 'i', 'Loss-factor vector size', py_name='ctand_SIZEROW'),
        DgsProperty('ctand:0', 'r', 'Dielectric loss factor 0', py_name='ctand_0'),
        DgsProperty('ctand:1', 'r', 'Dielectric loss factor 1', py_name='ctand_1'),
        DgsProperty('ctand:2', 'r', 'Dielectric loss factor 2', py_name='ctand_2'),
        DgsProperty('my:SIZEROW', 'i', 'Permeability vector size', py_name='my_SIZEROW'),
        DgsProperty('my:0', 'r', 'Relative permeability 0', py_name='my_0'),
        DgsProperty('my:1', 'r', 'Relative permeability 1', py_name='my_1'),
        DgsProperty('my:2', 'r', 'Relative permeability 2', py_name='my_2'),
        DgsProperty('ks', 'r', 'Core skin-effect factor', py_name='ks'),
        DgsProperty('kp', 'r', 'Core proximity-effect factor', py_name='kp'),
    ))

    def __init__(self) -> None:
        """Create an empty typed cable row.

        :return: None.
        """
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.fold_id: str | None = None
        self.uline: float = 0.0
        self.rpha: float = 0.0
        self.diaCon: float = 0.0
        self.diaTube: float = 0.0
        self.diaCab: float = 0.0
        self.thSht: float = 0.0
        self.has_arm: int | None = None
        self.cHasEl_2: int | None = None
        self.thIns_SIZEROW: int = 0
        self.thIns_0: float = 0.0
        self.thIns_1: float = 0.0
        self.thIns_2: float = 0.0
        self.thIns: List[float] = list()
        self.crho_SIZEROW: int = 0
        self.crho_0: float = 0.0
        self.crho_1: float = 0.0
        self.crho_2: float = 0.0
        self.crho: List[float] = list()
        self.Cf_SIZEROW: int = 0
        self.Cf_0: float = 0.0
        self.Cf_1: float = 0.0
        self.Cf_2: float = 0.0
        self.Cf: List[float] = list()
        self.cepsr_SIZEROW: int = 0
        self.cepsr_0: float = 0.0
        self.cepsr_1: float = 0.0
        self.cepsr_2: float = 0.0
        self.cepsr: List[float] = list()
        self.ctand_SIZEROW: int = 0
        self.ctand_0: float = 0.0
        self.ctand_1: float = 0.0
        self.ctand_2: float = 0.0
        self.ctand: List[float] = list()
        self.my_SIZEROW: int = 0
        self.my_0: float = 0.0
        self.my_1: float = 0.0
        self.my_2: float = 0.0
        self.my: List[float] = list()
        self.ks: float = 1.0
        self.kp: float = 1.0

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> TypCab:
        """Parse scalar and three-layer cable fields.

        :param line: Raw DGS row.
        :param header_map: DGS column map.
        :return: Parsed cable type.
        """
        obj: TypCab = super().parse_line(line=line, header_map=header_map)
        obj.thIns = list((obj.thIns_0, obj.thIns_1, obj.thIns_2))
        obj.crho = list((obj.crho_0, obj.crho_1, obj.crho_2))
        obj.Cf = list((obj.Cf_0, obj.Cf_1, obj.Cf_2))
        obj.cepsr = list((obj.cepsr_0, obj.cepsr_1, obj.cepsr_2))
        obj.ctand = list((obj.ctand_0, obj.ctand_1, obj.ctand_2))
        obj.my = list((obj.my_0, obj.my_1, obj.my_2))
        return obj


class TypCabsys(DGSElement):
    """PowerFactory geometrical cable-system type."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "systp",
        "frnom",
        "iopt_bur",
        "nlcir",
        "cnphas",
        "pcab_c_SIZEROW",
        "pcab_c_0",
        "pcab_c",
        "nphas_SIZEROW",
        "nphas_0",
        "nphas",
        "xy_c_SIZEROW",
        "xy_c_SIZECOL",
        "xy_c_0_0",
        "xy_c_0_1",
        "xy_c_0_2",
        "xy_c_0_3",
        "xy_c_0_4",
        "xy_c_0_5",
        "xy_c",
        "cGearth",
        "rhoEarth",
        "dInom_SIZEROW",
        "dInom_0",
        "dInom",
    )

    element_type = 'TypCabsys'
    properties_list = list((
        DgsProperty('FID', 'a:40', 'Unique DGS identifier', py_name='ID'),
        DgsProperty('OP', 'a:1', 'Operation', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'In Folder', py_name='fold_id'),
        DgsProperty('systp', 'i', 'System type', py_name='systp'),
        DgsProperty('frnom', 'r', 'Nominal frequency in Hz', py_name='frnom'),
        DgsProperty('iopt_bur', 'a:6', 'Laying type', py_name='iopt_bur'),
        DgsProperty('nlcir', 'i', 'Number of circuits', py_name='nlcir'),
        DgsProperty('cnphas', 'i', 'System phase count', py_name='cnphas'),
        DgsProperty('pcab_c:SIZEROW', 'i', 'Cable pointer vector size', py_name='pcab_c_SIZEROW'),
        DgsProperty('pcab_c:0', 'p', 'Cable pointer 0', py_name='pcab_c_0'),
        DgsProperty('nphas:SIZEROW', 'i', 'Phase-count vector size', py_name='nphas_SIZEROW'),
        DgsProperty('nphas:0', 'r', 'Circuit phase count 0', py_name='nphas_0'),
        DgsProperty('xy_c:SIZEROW', 'i', 'Coordinate matrix rows', py_name='xy_c_SIZEROW'),
        DgsProperty('xy_c:SIZECOL', 'i', 'Coordinate matrix columns', py_name='xy_c_SIZECOL'),
        DgsProperty('xy_c:0:0', 'r', 'Circuit coordinate 0', py_name='xy_c_0_0'),
        DgsProperty('xy_c:0:1', 'r', 'Circuit coordinate 1', py_name='xy_c_0_1'),
        DgsProperty('xy_c:0:2', 'r', 'Circuit coordinate 2', py_name='xy_c_0_2'),
        DgsProperty('xy_c:0:3', 'r', 'Circuit coordinate 3', py_name='xy_c_0_3'),
        DgsProperty('xy_c:0:4', 'r', 'Circuit coordinate 4', py_name='xy_c_0_4'),
        DgsProperty('xy_c:0:5', 'r', 'Circuit coordinate 5', py_name='xy_c_0_5'),
        DgsProperty('cGearth', 'r', 'Earth conductivity in uS/cm', py_name='cGearth'),
        DgsProperty('rhoEarth', 'r', 'Earth resistivity in Ohm*m', py_name='rhoEarth'),
        DgsProperty('dInom:SIZEROW', 'i', 'Rated-current vector size', py_name='dInom_SIZEROW'),
        DgsProperty('dInom:0', 'r', 'Rated current 0 in kA', py_name='dInom_0'),
    ))

    def __init__(self) -> None:
        """Create an empty typed cable-system row.

        :return: None.
        """
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.fold_id: str | None = None
        self.systp: int = 0
        self.frnom: float = 50.0
        self.iopt_bur: str = ''
        self.nlcir: int = 1
        self.cnphas: int = 3
        self.pcab_c_SIZEROW: int = 0
        self.pcab_c_0: str | None = None
        self.pcab_c: List[str | None] = list()
        self.nphas_SIZEROW: int = 0
        self.nphas_0: float = 0.0
        self.nphas: List[float] = list()
        self.xy_c_SIZEROW: int = 0
        self.xy_c_SIZECOL: int = 0
        self.xy_c_0_0: float = 0.0
        self.xy_c_0_1: float = 0.0
        self.xy_c_0_2: float = 0.0
        self.xy_c_0_3: float = 0.0
        self.xy_c_0_4: float = 0.0
        self.xy_c_0_5: float = 0.0
        self.xy_c: List[List[float]] = list()
        self.cGearth: float = 0.0
        self.rhoEarth: float = 100.0
        self.dInom_SIZEROW: int = 0
        self.dInom_0: float = 0.0
        self.dInom: List[float] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]) -> TypCabsys:
        """Parse variable-size cable references, phase counts and coordinates.

        :param line: Raw DGS row.
        :param header_map: DGS column map.
        :return: Parsed cable-system type.
        """
        parts: List[str] = _split_dgs_line(line=line)
        obj: TypCabsys = super().parse_line(line=line, header_map=header_map)

        obj.pcab_c = list()
        cable_index: int
        for cable_index in range(obj.pcab_c_SIZEROW):
            raw_pointer: str | None = _dgs_get(parts=parts, header_map=header_map, key=f'pcab_c:{cable_index}')
            if raw_pointer is not None and raw_pointer.strip() not in ('', '*'):
                obj.pcab_c.append(raw_pointer.strip())
            else:
                obj.pcab_c.append(None)

        obj.nphas = list()
        circuit_index: int
        for circuit_index in range(obj.nphas_SIZEROW):
            raw_phase_count: str | None = _dgs_get(
                parts=parts,
                header_map=header_map,
                key=f'nphas:{circuit_index}',
            )
            phase_count: float = float(raw_phase_count.replace(',', '.')) if raw_phase_count else 0.0
            obj.nphas.append(phase_count)

        obj.xy_c = list()
        row_index: int
        column_index: int
        for row_index in range(obj.xy_c_SIZEROW):
            coordinate_row: List[float] = list()
            for column_index in range(obj.xy_c_SIZECOL):
                raw_coordinate: str | None = _dgs_get(
                    parts=parts,
                    header_map=header_map,
                    key=f'xy_c:{row_index}:{column_index}',
                )
                coordinate: float = float(raw_coordinate.replace(',', '.')) if raw_coordinate else 0.0
                coordinate_row.append(coordinate)
            obj.xy_c.append(coordinate_row)

        obj.dInom = list()
        for circuit_index in range(obj.dInom_SIZEROW):
            raw_current: str | None = _dgs_get(
                parts=parts,
                header_map=header_map,
                key=f'dInom:{circuit_index}',
            )
            rated_current: float = float(raw_current.replace(',', '.')) if raw_current else 0.0
            obj.dInom.append(rated_current)
        return obj


class TypCt(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "primtaps_SIZEROW",
        "primtaps_0",
        "sectaps_SIZEROW",
        "sectaps_0",
        "primtaps",
        "sectaps",
    )
    element_type = 'TypCt'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the current transformer type', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the current transformer type', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the current transformer type', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the current transformer type', py_name='fold_id'),
        DgsProperty('primtaps:SIZEROW', 'i', 'Number of available primary tap values', py_name='primtaps_SIZEROW'),
        DgsProperty('primtaps:0', 'r', 'First primary tap value', py_name='primtaps_0'),
        DgsProperty('sectaps:SIZEROW', 'i', 'Number of available secondary tap values', py_name='sectaps_SIZEROW'),
        DgsProperty('sectaps:0', 'r', 'First secondary tap value', py_name='sectaps_0'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.primtaps_SIZEROW: int = 0
        self.primtaps_0: float = 0.0
        self.sectaps_SIZEROW: int = 0
        self.sectaps_0: float = 0.0
        self.primtaps: List[float] = list()
        self.sectaps: List[float] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = line.rstrip('\n').split(';')
        obj = cls()

        obj.ID = str(cls.properties['ID'].parse(_dgs_get(parts, header_map, 'ID') or ""))
        obj.OP = str(cls.properties['OP'].parse(_dgs_get(parts, header_map, 'OP') or ""))
        obj.loc_name = str(cls.properties['loc_name'].parse(_dgs_get(parts, header_map, 'loc_name') or ""))
        fold_raw = _dgs_get(parts, header_map, 'fold_id')
        obj.fold_id = str(cls.properties['fold_id'].parse(fold_raw or "")) if fold_raw is not None else ""
        obj.primtaps_SIZEROW = int(
            cls.properties['primtaps:SIZEROW'].parse(_dgs_get(parts, header_map, 'primtaps:SIZEROW') or "0") or 0)
        obj.primtaps_0 = float(
            cls.properties['primtaps:0'].parse(_dgs_get(parts, header_map, 'primtaps:0') or "0") or 0.0)
        obj.sectaps_SIZEROW = int(
            cls.properties['sectaps:SIZEROW'].parse(_dgs_get(parts, header_map, 'sectaps:SIZEROW') or "0") or 0)
        obj.sectaps_0 = float(cls.properties['sectaps:0'].parse(_dgs_get(parts, header_map, 'sectaps:0') or "0") or 0.0)

        obj.primtaps.append(obj.primtaps_0)
        obj.sectaps.append(obj.sectaps_0)

        return obj


class TypGeo(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "nlear",
        "nlcir",
        "xy_e_SIZEROW",
        "xy_e_SIZECOL",
        "xy_c_SIZEROW",
        "xy_c_SIZECOL",
        "xy_c_0_0",
        "xy_c_0_1",
        "xy_c_0_2",
        "xy_c_0_3",
        "xy_c_0_4",
        "xy_c_0_5",
        "xy_c_0_6",
        "xy_c_row_0",
    )
    element_type = 'TypGeo'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the tower geometry type', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the tower geometry type', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the tower geometry type', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the tower geometry type', py_name='fold_id'),
        DgsProperty('nlear', 'i', 'Number of earth wires in the tower geometry', py_name='nlear'),
        DgsProperty('nlcir', 'i', 'Number of line circuits represented by the tower geometry', py_name='nlcir'),
        DgsProperty('xy_e:SIZEROW', 'i', 'Number of earth-wire coordinate rows', py_name='xy_e_SIZEROW'),
        DgsProperty('xy_e:SIZECOL', 'i', 'Number of earth-wire coordinate columns', py_name='xy_e_SIZECOL'),
        DgsProperty('xy_c:SIZEROW', 'i', 'Number of conductor coordinate rows', py_name='xy_c_SIZEROW'),
        DgsProperty('xy_c:SIZECOL', 'i', 'Number of conductor coordinate columns', py_name='xy_c_SIZECOL'),
        DgsProperty('xy_c:0:0', 'r', 'Conductor geometry matrix entry row 0 column 0', py_name='xy_c_0_0'),
        DgsProperty('xy_c:0:1', 'r', 'Conductor geometry matrix entry row 0 column 1', py_name='xy_c_0_1'),
        DgsProperty('xy_c:0:2', 'r', 'Conductor geometry matrix entry row 0 column 2', py_name='xy_c_0_2'),
        DgsProperty('xy_c:0:3', 'r', 'Conductor geometry matrix entry row 0 column 3', py_name='xy_c_0_3'),
        DgsProperty('xy_c:0:4', 'r', 'Conductor geometry matrix entry row 0 column 4', py_name='xy_c_0_4'),
        DgsProperty('xy_c:0:5', 'r', 'Conductor geometry matrix entry row 0 column 5', py_name='xy_c_0_5'),
        DgsProperty('xy_c:0:6', 'r', 'Conductor geometry matrix entry row 0 column 6', py_name='xy_c_0_6'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.nlear: int = 0
        self.nlcir: int = 0
        self.xy_e_SIZEROW: int = 0
        self.xy_e_SIZECOL: int = 0
        self.xy_c_SIZEROW: int = 0
        self.xy_c_SIZECOL: int = 0
        self.xy_c_0_0: float = 0.0
        self.xy_c_0_1: float = 0.0
        self.xy_c_0_2: float = 0.0
        self.xy_c_0_3: float = 0.0
        self.xy_c_0_4: float = 0.0
        self.xy_c_0_5: float = 0.0
        self.xy_c_0_6: float = 0.0
        self.xy_c_row_0: List[float] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = line.rstrip('\n').split(';')
        obj = cls()

        obj.ID = str(cls.properties['ID'].parse(_dgs_get(parts, header_map, 'ID') or ""))
        obj.OP = str(cls.properties['OP'].parse(_dgs_get(parts, header_map, 'OP') or ""))
        obj.loc_name = str(cls.properties['loc_name'].parse(_dgs_get(parts, header_map, 'loc_name') or ""))
        fold_raw = _dgs_get(parts, header_map, 'fold_id')
        obj.fold_id = str(cls.properties['fold_id'].parse(fold_raw or "")) if fold_raw is not None else ""
        obj.nlear = int(cls.properties['nlear'].parse(_dgs_get(parts, header_map, 'nlear') or "0") or 0)
        obj.nlcir = int(cls.properties['nlcir'].parse(_dgs_get(parts, header_map, 'nlcir') or "0") or 0)
        obj.xy_e_SIZEROW = int(
            cls.properties['xy_e:SIZEROW'].parse(_dgs_get(parts, header_map, 'xy_e:SIZEROW') or "0") or 0)
        obj.xy_e_SIZECOL = int(
            cls.properties['xy_e:SIZECOL'].parse(_dgs_get(parts, header_map, 'xy_e:SIZECOL') or "0") or 0)
        obj.xy_c_SIZEROW = int(
            cls.properties['xy_c:SIZEROW'].parse(_dgs_get(parts, header_map, 'xy_c:SIZEROW') or "0") or 0)
        obj.xy_c_SIZECOL = int(
            cls.properties['xy_c:SIZECOL'].parse(_dgs_get(parts, header_map, 'xy_c:SIZECOL') or "0") or 0)

        row_values: List[float] = list()
        for idx in range(7):
            key = f'xy_c:0:{idx}'
            value = float(cls.properties[key].parse(_dgs_get(parts, header_map, key) or "0") or 0.0)
            row_values.append(value)

        obj.xy_c_0_0 = row_values[0]
        obj.xy_c_0_1 = row_values[1]
        obj.xy_c_0_2 = row_values[2]
        obj.xy_c_0_3 = row_values[3]
        obj.xy_c_0_4 = row_values[4]
        obj.xy_c_0_5 = row_values[5]
        obj.xy_c_0_6 = row_values[6]
        obj.xy_c_row_0 = row_values

        return obj


class TypVt(DGSElement):
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "primtaps_SIZEROW",
        "primtaps",
    )
    element_type = 'TypVt'
    properties_list = [
        DgsProperty('ID', 'a:40', 'Unique identifier of the voltage transformer type', py_name='ID'),
        DgsProperty('OP', 'a:1', 'DGS operation marker for the voltage transformer type', py_name='OP'),
        DgsProperty('loc_name', 'a:80', 'Name of the voltage transformer type', py_name='loc_name'),
        DgsProperty('fold_id', 'p', 'Folder containing the voltage transformer type', py_name='fold_id'),
        DgsProperty('primtaps:SIZEROW', 'i', 'Number of available primary tap values', py_name='primtaps_SIZEROW'),
        DgsProperty('primtaps:0', 'r', 'Primary tap value 0', py_name='primtaps_0'),
        DgsProperty('primtaps:1', 'r', 'Primary tap value 1', py_name='primtaps_1'),
        DgsProperty('primtaps:2', 'r', 'Primary tap value 2', py_name='primtaps_2'),
        DgsProperty('primtaps:3', 'r', 'Primary tap value 3', py_name='primtaps_3'),
        DgsProperty('primtaps:4', 'r', 'Primary tap value 4', py_name='primtaps_4'),
        DgsProperty('primtaps:5', 'r', 'Primary tap value 5', py_name='primtaps_5'),
        DgsProperty('primtaps:6', 'r', 'Primary tap value 6', py_name='primtaps_6'),
        DgsProperty('primtaps:7', 'r', 'Primary tap value 7', py_name='primtaps_7'),
        DgsProperty('primtaps:8', 'r', 'Primary tap value 8', py_name='primtaps_8'),
        DgsProperty('primtaps:9', 'r', 'Primary tap value 9', py_name='primtaps_9'),
        DgsProperty('primtaps:10', 'r', 'Primary tap value 10', py_name='primtaps_10'),
        DgsProperty('primtaps:11', 'r', 'Primary tap value 11', py_name='primtaps_11'),
        DgsProperty('primtaps:12', 'r', 'Primary tap value 12', py_name='primtaps_12'),
        DgsProperty('primtaps:13', 'r', 'Primary tap value 13', py_name='primtaps_13'),
        DgsProperty('primtaps:14', 'r', 'Primary tap value 14', py_name='primtaps_14'),
        DgsProperty('primtaps:15', 'r', 'Primary tap value 15', py_name='primtaps_15'),
        DgsProperty('primtaps:16', 'r', 'Primary tap value 16', py_name='primtaps_16'),
        DgsProperty('primtaps:17', 'r', 'Primary tap value 17', py_name='primtaps_17'),
        DgsProperty('primtaps:18', 'r', 'Primary tap value 18', py_name='primtaps_18'),
        DgsProperty('primtaps:19', 'r', 'Primary tap value 19', py_name='primtaps_19'),
        DgsProperty('primtaps:20', 'r', 'Primary tap value 20', py_name='primtaps_20'),
        DgsProperty('primtaps:21', 'r', 'Primary tap value 21', py_name='primtaps_21'),
        DgsProperty('primtaps:22', 'r', 'Primary tap value 22', py_name='primtaps_22'),
        DgsProperty('primtaps:23', 'r', 'Primary tap value 23', py_name='primtaps_23'),
        DgsProperty('primtaps:24', 'r', 'Primary tap value 24', py_name='primtaps_24'),
        DgsProperty('primtaps:25', 'r', 'Primary tap value 25', py_name='primtaps_25'),
        DgsProperty('primtaps:26', 'r', 'Primary tap value 26', py_name='primtaps_26'),
        DgsProperty('primtaps:27', 'r', 'Primary tap value 27', py_name='primtaps_27'),
        DgsProperty('primtaps:28', 'r', 'Primary tap value 28', py_name='primtaps_28'),
        DgsProperty('primtaps:29', 'r', 'Primary tap value 29', py_name='primtaps_29'),
        DgsProperty('primtaps:30', 'r', 'Primary tap value 30', py_name='primtaps_30'),
        DgsProperty('primtaps:31', 'r', 'Primary tap value 31', py_name='primtaps_31'),
        DgsProperty('primtaps:32', 'r', 'Primary tap value 32', py_name='primtaps_32'),
        DgsProperty('primtaps:33', 'r', 'Primary tap value 33', py_name='primtaps_33'),
        DgsProperty('primtaps:34', 'r', 'Primary tap value 34', py_name='primtaps_34'),
        DgsProperty('primtaps:35', 'r', 'Primary tap value 35', py_name='primtaps_35'),
        DgsProperty('primtaps:36', 'r', 'Primary tap value 36', py_name='primtaps_36'),
        DgsProperty('primtaps:37', 'r', 'Primary tap value 37', py_name='primtaps_37'),
        DgsProperty('primtaps:38', 'r', 'Primary tap value 38', py_name='primtaps_38'),
    ]

    def __init__(self) -> None:
        self.ID: str = ""
        self.OP: str = ""
        self.loc_name: str = ""
        self.fold_id: str = ""
        self.primtaps_SIZEROW: int = 0
        self.primtaps: List[float] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        parts = line.rstrip('\n').split(';')
        obj = cls()

        obj.ID = str(cls.properties['ID'].parse(_dgs_get(parts, header_map, 'ID') or ""))
        obj.OP = str(cls.properties['OP'].parse(_dgs_get(parts, header_map, 'OP') or ""))
        obj.loc_name = str(cls.properties['loc_name'].parse(_dgs_get(parts, header_map, 'loc_name') or ""))
        fold_raw = _dgs_get(parts, header_map, 'fold_id')
        obj.fold_id = str(cls.properties['fold_id'].parse(fold_raw or "")) if fold_raw is not None else ""
        obj.primtaps_SIZEROW = int(
            cls.properties['primtaps:SIZEROW'].parse(_dgs_get(parts, header_map, 'primtaps:SIZEROW') or "0") or 0)

        for idx in range(39):
            key = f'primtaps:{idx}'
            raw = _dgs_get(parts, header_map, key)
            value = float(cls.properties[key].parse(raw or "0") or 0.0)
            obj.primtaps.append(value)

        return obj

    def to_dgs_line(self) -> str:
        values: List[str] = list()
        values.append(self.properties['ID'].format(self.ID))
        values.append(self.properties['OP'].format(self.OP))
        values.append(self.properties['loc_name'].format(self.loc_name))
        values.append(self.properties['fold_id'].format(self.fold_id))
        values.append(self.properties['primtaps:SIZEROW'].format(self.primtaps_SIZEROW))
        for idx in range(39):
            if idx < len(self.primtaps):
                values.append(self.properties[f'primtaps:{idx}'].format(self.primtaps[idx]))
            else:
                values.append(self.properties[f'primtaps:{idx}'].format(0.0))
        return ';'.join(values)


class TypTow(DGSElement):
    """PowerFactory tower type (TypTow) mapped to VeraGrid OverheadLineType."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "frnom",
        "nlear",
        "nlcir",
        "gearth",
        "i_mode",
        "pcond_e_SIZEROW",
        "pcond_e",
        "nphas_SIZEROW",
        "pcond_c",
        "pcond_c_SIZEROW",
        "nphas",
        "ktrto_SIZEROW",
        "ktrto",
        "xy_e_SIZEROW",
        "xy_e_SIZECOL",
        "xy_e",
        "xy_c_SIZEROW",
        "xy_c_SIZECOL",
        "xy_c",
        "R_c0_SIZEROW",
        "R_c0_SIZECOL",
        "R_c0",
        "X_c0_SIZEROW",
        "X_c0_SIZECOL",
        "X_c0",
        "R_c1_SIZEROW",
        "R_c1_SIZECOL",
        "R_c1",
        "X_c1_SIZEROW",
        "X_c1_SIZECOL",
        "X_c1",
        "B_c0_SIZEROW",
        "B_c0_SIZECOL",
        "B_c0",
        "B_c1_SIZEROW",
        "B_c1_SIZECOL",
        "B_c1",
        "G_c0_SIZEROW",
        "G_c0_SIZECOL",
        "G_c0",
        "G_c1_SIZEROW",
        "G_c1_SIZECOL",
        "G_c1",
    )

    element_type = 'TypTow'

    properties_list = [
        DgsProperty(name='FID', dgs_type='a:40', description='Unique identifier for DGS file', py_name='ID'),
        DgsProperty(name='OP', dgs_type='a:1', description='Operation', py_name='OP'),
        DgsProperty(name='loc_name', dgs_type='a:80', description='Name', py_name='loc_name'),
        DgsProperty(name='fold_id', dgs_type='p', description='In Folder', py_name='fold_id'),
        DgsProperty(name='frnom', dgs_type='r', description='Nominal Frequency in Hz', py_name='frnom'),
        DgsProperty(name='nlear', dgs_type='i', description='Number of Earth Wires', py_name='nlear'),
        DgsProperty(name='nlcir', dgs_type='i', description='Number of Line Circuits', py_name='nlcir'),
        DgsProperty(name='gearth', dgs_type='r', description='Earth conductivity in uS/cm', py_name='gearth'),
        DgsProperty(name='i_mode', dgs_type='i', description='Tower model mode code', py_name='i_mode'),
        DgsProperty(name='pcond_e:SIZEROW', dgs_type='i', description='Earth conductor vector size',
                    py_name='pcond_e_SIZEROW'),
        DgsProperty(name='pcond_e:0', dgs_type='p', description='Earth conductor pointer 0', py_name='pcond_e_0'),
        DgsProperty(name='pcond_e:1', dgs_type='p', description='Earth conductor pointer 1', py_name='pcond_e_1'),
        DgsProperty(name='nphas:SIZEROW', dgs_type='i', description='Phase-count vector size', py_name='nphas_SIZEROW'),
        DgsProperty(name='nphas:0', dgs_type='r', description='Phase count value 0', py_name='nphas_0'),
        DgsProperty(name='nphas:1', dgs_type='r', description='Phase count value 1', py_name='nphas_1'),
        DgsProperty(name='ktrto:SIZEROW', dgs_type='i', description='Transposition vector size',
                    py_name='ktrto_SIZEROW'),
        DgsProperty(name='ktrto:0', dgs_type='r', description='Transposition value 0', py_name='ktrto_0'),
        DgsProperty(name='ktrto:1', dgs_type='r', description='Transposition value 1', py_name='ktrto_1'),
        DgsProperty(name='pcond_c:SIZEROW', dgs_type='i', description='Circuit conductor vector size',
                    py_name='pcond_c_SIZEROW'),
        DgsProperty(name='pcond_c:0', dgs_type='p', description='Circuit conductor pointer 0', py_name='pcond_c_0'),
        DgsProperty(name='pcond_c:1', dgs_type='p', description='Circuit conductor pointer 1', py_name='pcond_c_1'),
        DgsProperty(name='xy_e:SIZEROW', dgs_type='i', description='Earth coordinate matrix rows',
                    py_name='xy_e_SIZEROW'),
        DgsProperty(name='xy_e:SIZECOL', dgs_type='i', description='Earth coordinate matrix columns',
                    py_name='xy_e_SIZECOL'),
        DgsProperty(name='xy_e:0:0', dgs_type='r', description='Earth coordinate [0,0]', py_name='xy_e_0_0'),
        DgsProperty(name='xy_e:0:1', dgs_type='r', description='Earth coordinate [0,1]', py_name='xy_e_0_1'),
        DgsProperty(name='xy_e:1:0', dgs_type='r', description='Earth coordinate [1,0]', py_name='xy_e_1_0'),
        DgsProperty(name='xy_e:1:1', dgs_type='r', description='Earth coordinate [1,1]', py_name='xy_e_1_1'),
        DgsProperty(name='xy_c:SIZEROW', dgs_type='i', description='Circuit coordinate matrix rows',
                    py_name='xy_c_SIZEROW'),
        DgsProperty(name='xy_c:SIZECOL', dgs_type='i', description='Circuit coordinate matrix columns',
                    py_name='xy_c_SIZECOL'),
        DgsProperty(name='xy_c:0:0', dgs_type='r', description='Circuit coordinate [0,0]', py_name='xy_c_0_0'),
        DgsProperty(name='xy_c:0:1', dgs_type='r', description='Circuit coordinate [0,1]', py_name='xy_c_0_1'),
        DgsProperty(name='xy_c:0:2', dgs_type='r', description='Circuit coordinate [0,2]', py_name='xy_c_0_2'),
        DgsProperty(name='xy_c:0:3', dgs_type='r', description='Circuit coordinate [0,3]', py_name='xy_c_0_3'),
        DgsProperty(name='xy_c:0:4', dgs_type='r', description='Circuit coordinate [0,4]', py_name='xy_c_0_4'),
        DgsProperty(name='xy_c:0:5', dgs_type='r', description='Circuit coordinate [0,5]', py_name='xy_c_0_5'),
        DgsProperty(name='xy_c:1:0', dgs_type='r', description='Circuit coordinate [1,0]', py_name='xy_c_1_0'),
        DgsProperty(name='xy_c:1:1', dgs_type='r', description='Circuit coordinate [1,1]', py_name='xy_c_1_1'),
        DgsProperty(name='xy_c:1:2', dgs_type='r', description='Circuit coordinate [1,2]', py_name='xy_c_1_2'),
        DgsProperty(name='xy_c:1:3', dgs_type='r', description='Circuit coordinate [1,3]', py_name='xy_c_1_3'),
        DgsProperty(name='xy_c:1:4', dgs_type='r', description='Circuit coordinate [1,4]', py_name='xy_c_1_4'),
        DgsProperty(name='xy_c:1:5', dgs_type='r', description='Circuit coordinate [1,5]', py_name='xy_c_1_5'),
        DgsProperty(name='R_c0:SIZEROW', dgs_type='i', description='R_c0 matrix rows', py_name='R_c0_SIZEROW'),
        DgsProperty(name='R_c0:SIZECOL', dgs_type='i', description='R_c0 matrix cols', py_name='R_c0_SIZECOL'),
        DgsProperty(name='R_c0:0:0', dgs_type='r', description='R_c0 [0,0]', py_name='R_c0_0_0'),
        DgsProperty(name='R_c0:0:1', dgs_type='r', description='R_c0 [0,1]', py_name='R_c0_0_1'),
        DgsProperty(name='R_c0:1:0', dgs_type='r', description='R_c0 [1,0]', py_name='R_c0_1_0'),
        DgsProperty(name='R_c0:1:1', dgs_type='r', description='R_c0 [1,1]', py_name='R_c0_1_1'),
        DgsProperty(name='X_c0:SIZEROW', dgs_type='i', description='X_c0 matrix rows', py_name='X_c0_SIZEROW'),
        DgsProperty(name='X_c0:SIZECOL', dgs_type='i', description='X_c0 matrix cols', py_name='X_c0_SIZECOL'),
        DgsProperty(name='X_c0:0:0', dgs_type='r', description='X_c0 [0,0]', py_name='X_c0_0_0'),
        DgsProperty(name='X_c0:0:1', dgs_type='r', description='X_c0 [0,1]', py_name='X_c0_0_1'),
        DgsProperty(name='X_c0:1:0', dgs_type='r', description='X_c0 [1,0]', py_name='X_c0_1_0'),
        DgsProperty(name='X_c0:1:1', dgs_type='r', description='X_c0 [1,1]', py_name='X_c0_1_1'),
        DgsProperty(name='R_c1:SIZEROW', dgs_type='i', description='R_c1 matrix rows', py_name='R_c1_SIZEROW'),
        DgsProperty(name='R_c1:SIZECOL', dgs_type='i', description='R_c1 matrix cols', py_name='R_c1_SIZECOL'),
        DgsProperty(name='R_c1:0:0', dgs_type='r', description='R_c1 [0,0]', py_name='R_c1_0_0'),
        DgsProperty(name='R_c1:0:1', dgs_type='r', description='R_c1 [0,1]', py_name='R_c1_0_1'),
        DgsProperty(name='R_c1:1:0', dgs_type='r', description='R_c1 [1,0]', py_name='R_c1_1_0'),
        DgsProperty(name='R_c1:1:1', dgs_type='r', description='R_c1 [1,1]', py_name='R_c1_1_1'),
        DgsProperty(name='X_c1:SIZEROW', dgs_type='i', description='X_c1 matrix rows', py_name='X_c1_SIZEROW'),
        DgsProperty(name='X_c1:SIZECOL', dgs_type='i', description='X_c1 matrix cols', py_name='X_c1_SIZECOL'),
        DgsProperty(name='X_c1:0:0', dgs_type='r', description='X_c1 [0,0]', py_name='X_c1_0_0'),
        DgsProperty(name='X_c1:0:1', dgs_type='r', description='X_c1 [0,1]', py_name='X_c1_0_1'),
        DgsProperty(name='X_c1:1:0', dgs_type='r', description='X_c1 [1,0]', py_name='X_c1_1_0'),
        DgsProperty(name='X_c1:1:1', dgs_type='r', description='X_c1 [1,1]', py_name='X_c1_1_1'),
        DgsProperty(name='B_c0:SIZEROW', dgs_type='i', description='B_c0 matrix rows', py_name='B_c0_SIZEROW'),
        DgsProperty(name='B_c0:SIZECOL', dgs_type='i', description='B_c0 matrix cols', py_name='B_c0_SIZECOL'),
        DgsProperty(name='B_c0:0:0', dgs_type='r', description='B_c0 [0,0]', py_name='B_c0_0_0'),
        DgsProperty(name='B_c0:0:1', dgs_type='r', description='B_c0 [0,1]', py_name='B_c0_0_1'),
        DgsProperty(name='B_c0:1:0', dgs_type='r', description='B_c0 [1,0]', py_name='B_c0_1_0'),
        DgsProperty(name='B_c0:1:1', dgs_type='r', description='B_c0 [1,1]', py_name='B_c0_1_1'),
        DgsProperty(name='B_c1:SIZEROW', dgs_type='i', description='B_c1 matrix rows', py_name='B_c1_SIZEROW'),
        DgsProperty(name='B_c1:SIZECOL', dgs_type='i', description='B_c1 matrix cols', py_name='B_c1_SIZECOL'),
        DgsProperty(name='B_c1:0:0', dgs_type='r', description='B_c1 [0,0]', py_name='B_c1_0_0'),
        DgsProperty(name='B_c1:0:1', dgs_type='r', description='B_c1 [0,1]', py_name='B_c1_0_1'),
        DgsProperty(name='B_c1:1:0', dgs_type='r', description='B_c1 [1,0]', py_name='B_c1_1_0'),
        DgsProperty(name='B_c1:1:1', dgs_type='r', description='B_c1 [1,1]', py_name='B_c1_1_1'),
        DgsProperty(name='G_c0:SIZEROW', dgs_type='i', description='G_c0 matrix rows', py_name='G_c0_SIZEROW'),
        DgsProperty(name='G_c0:SIZECOL', dgs_type='i', description='G_c0 matrix cols', py_name='G_c0_SIZECOL'),
        DgsProperty(name='G_c0:0:0', dgs_type='r', description='G_c0 [0,0]', py_name='G_c0_0_0'),
        DgsProperty(name='G_c0:0:1', dgs_type='r', description='G_c0 [0,1]', py_name='G_c0_0_1'),
        DgsProperty(name='G_c0:1:0', dgs_type='r', description='G_c0 [1,0]', py_name='G_c0_1_0'),
        DgsProperty(name='G_c0:1:1', dgs_type='r', description='G_c0 [1,1]', py_name='G_c0_1_1'),
        DgsProperty(name='G_c1:SIZEROW', dgs_type='i', description='G_c1 matrix rows', py_name='G_c1_SIZEROW'),
        DgsProperty(name='G_c1:SIZECOL', dgs_type='i', description='G_c1 matrix cols', py_name='G_c1_SIZECOL'),
        DgsProperty(name='G_c1:0:0', dgs_type='r', description='G_c1 [0,0]', py_name='G_c1_0_0'),
        DgsProperty(name='G_c1:0:1', dgs_type='r', description='G_c1 [0,1]', py_name='G_c1_0_1'),
        DgsProperty(name='G_c1:1:0', dgs_type='r', description='G_c1 [1,0]', py_name='G_c1_1_0'),
        DgsProperty(name='G_c1:1:1', dgs_type='r', description='G_c1 [1,1]', py_name='G_c1_1_1'),
    ]

    def __init__(self):
        # Base scalar fields
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.fold_id: str | None = None
        self.frnom: float = 50.0
        self.nlear: int = 0
        self.nlcir: int = 1
        self.gearth: float = 0.0
        self.i_mode: int = 0

        # Dynamic fields (variable-size vectors/matrices)
        self.pcond_e_SIZEROW: int = 0
        self.pcond_e: List[str | None] = list()
        self.nphas_SIZEROW: int = 0
        self.pcond_c: List[str | None] = list()
        self.pcond_c_SIZEROW: int = 0
        self.nphas: List[float] = list()
        self.ktrto_SIZEROW: int = 0
        self.ktrto: List[float] = list()
        self.xy_e_SIZEROW: int = 0
        self.xy_e_SIZECOL: int = 0
        self.xy_e: List[List[float]] = list()  # Each row: [x, y]
        self.xy_c_SIZEROW: int = 0
        self.xy_c_SIZECOL: int = 0
        self.xy_c: List[List[float]] = list()  # Each row: [xA, xB, xC, yA, yB, yC]
        self.R_c0_SIZEROW: int = 0
        self.R_c0_SIZECOL: int = 0
        self.R_c0: List[List[float]] = list()
        self.X_c0_SIZEROW: int = 0
        self.X_c0_SIZECOL: int = 0
        self.X_c0: List[List[float]] = list()
        self.R_c1_SIZEROW: int = 0
        self.R_c1_SIZECOL: int = 0
        self.R_c1: List[List[float]] = list()
        self.X_c1_SIZEROW: int = 0
        self.X_c1_SIZECOL: int = 0
        self.X_c1: List[List[float]] = list()
        self.B_c0_SIZEROW: int = 0
        self.B_c0_SIZECOL: int = 0
        self.B_c0: List[List[float]] = list()
        self.B_c1_SIZEROW: int = 0
        self.B_c1_SIZECOL: int = 0
        self.B_c1: List[List[float]] = list()
        self.G_c0_SIZEROW: int = 0
        self.G_c0_SIZECOL: int = 0
        self.G_c0: List[List[float]] = list()
        self.G_c1_SIZEROW: int = 0
        self.G_c1_SIZECOL: int = 0
        self.G_c1: List[List[float]] = list()

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        """Parse TypTow data line including variable-sized arrays/matrices."""
        parts = line.rstrip('\n').split(';')
        obj = cls()

        # Parse the scalar fields via the base schema
        for prop in cls.properties_list:
            idx = header_map.get(prop.name)
            if idx is None and prop.name == 'FID':
                idx = header_map.get('ID')

            # Indexed vector and matrix members are reconstructed below into
            # their aggregate slotted fields, so they are not standalone attrs.
            is_dynamic_member: bool = any(part.isdigit() for part in prop.name.split(':'))
            if idx is not None and 0 <= idx < len(parts):
                if is_dynamic_member:
                    pass
                else:
                    raw = parts[idx]
                    val = prop.parse(raw)
                    setattr(obj, prop.py_name, val)

        # Variable-size vectors
        # Conductor types for earth wires
        raw_n = _dgs_get(parts, header_map, 'pcond_e:SIZEROW')
        n = int(float(raw_n.replace(',', '.'))) if raw_n is not None and raw_n.strip() != '' else 0
        obj.pcond_e_SIZEROW = n
        obj.pcond_e = list()
        for i in range(n):
            raw_ptr = _dgs_get(parts, header_map, f'pcond_e:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.pcond_e.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        # Num. of phases per circuit (often 3)
        raw_nphas = _dgs_get(parts, header_map, 'nphas:SIZEROW')
        nphas_n = int(float(raw_nphas.replace(',', '.'))) if raw_nphas is not None and raw_nphas.strip() != '' else 0
        obj.nphas_SIZEROW = nphas_n
        obj.nphas = list()
        for i in range(nphas_n):
            raw_v = _dgs_get(parts, header_map, f'nphas:{i}')
            raw_v = raw_v.strip() if raw_v is not None else ''
            obj.nphas.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)

        # Transposition flags per circuit
        raw_ktrto = _dgs_get(parts, header_map, 'ktrto:SIZEROW')
        ktrto_n = int(float(raw_ktrto.replace(',', '.'))) if raw_ktrto is not None and raw_ktrto.strip() != '' else 0
        obj.ktrto_SIZEROW = ktrto_n
        obj.ktrto = list()
        for i in range(ktrto_n):
            raw_v = _dgs_get(parts, header_map, f'ktrto:{i}')
            raw_v = raw_v.strip() if raw_v is not None else ''
            obj.ktrto.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)

        # Conductor types for line circuits
        raw_pc = _dgs_get(parts, header_map, 'pcond_c:SIZEROW')
        pc_n = int(float(raw_pc.replace(',', '.'))) if raw_pc is not None and raw_pc.strip() != '' else 0
        obj.pcond_c_SIZEROW = pc_n
        obj.pcond_c = list()
        for i in range(pc_n):
            raw_ptr = _dgs_get(parts, header_map, f'pcond_c:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.pcond_c.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        # Earth wire coordinates: xy_e is a matrix with 2 columns (x, y) in meters
        raw_xy_e_rows = _dgs_get(parts, header_map, 'xy_e:SIZEROW')
        xy_e_rows = int(
            float(raw_xy_e_rows.replace(',', '.'))) if raw_xy_e_rows is not None and raw_xy_e_rows.strip() != '' else 0
        raw_xy_e_cols = _dgs_get(parts, header_map, 'xy_e:SIZECOL')
        xy_e_cols = int(
            float(raw_xy_e_cols.replace(',', '.'))) if raw_xy_e_cols is not None and raw_xy_e_cols.strip() != '' else 0
        obj.xy_e_SIZEROW = xy_e_rows
        obj.xy_e_SIZECOL = xy_e_cols

        obj.xy_e = list()
        for r in range(xy_e_rows):
            row: List[float] = list()
            for c in range(xy_e_cols):
                raw_v = _dgs_get(parts, header_map, f'xy_e:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.xy_e.append(row)

        # Circuit coordinates: xy_c is a matrix; in this dataset it uses 6 columns:
        # [xA, xB, xC, yA, yB, yC] in meters.
        raw_xy_c_rows = _dgs_get(parts, header_map, 'xy_c:SIZEROW')
        xy_c_rows = int(
            float(raw_xy_c_rows.replace(',', '.'))) if raw_xy_c_rows is not None and raw_xy_c_rows.strip() != '' else 0
        raw_xy_c_cols = _dgs_get(parts, header_map, 'xy_c:SIZECOL')
        xy_c_cols = int(
            float(raw_xy_c_cols.replace(',', '.'))) if raw_xy_c_cols is not None and raw_xy_c_cols.strip() != '' else 0
        obj.xy_c_SIZEROW = xy_c_rows
        obj.xy_c_SIZECOL = xy_c_cols

        obj.xy_c = list()
        for r in range(xy_c_rows):
            row: List[float] = list()
            for c in range(xy_c_cols):
                raw_v = _dgs_get(parts, header_map, f'xy_c:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.xy_c.append(row)

        raw_R_c0_rows = _dgs_get(parts, header_map, 'R_c0:SIZEROW')
        R_c0_rows = int(
            float(raw_R_c0_rows.replace(',', '.'))) if raw_R_c0_rows is not None and raw_R_c0_rows.strip() != '' else 0
        raw_R_c0_cols = _dgs_get(parts, header_map, 'R_c0:SIZECOL')
        R_c0_cols = int(
            float(raw_R_c0_cols.replace(',', '.'))) if raw_R_c0_cols is not None and raw_R_c0_cols.strip() != '' else 0
        obj.R_c0_SIZEROW = R_c0_rows
        obj.R_c0_SIZECOL = R_c0_cols
        obj.R_c0 = list()
        for r in range(R_c0_rows):
            row = list()
            for c in range(R_c0_cols):
                raw_v = _dgs_get(parts, header_map, f'R_c0:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.R_c0.append(row)

        raw_X_c0_rows = _dgs_get(parts, header_map, 'X_c0:SIZEROW')
        X_c0_rows = int(
            float(raw_X_c0_rows.replace(',', '.'))) if raw_X_c0_rows is not None and raw_X_c0_rows.strip() != '' else 0
        raw_X_c0_cols = _dgs_get(parts, header_map, 'X_c0:SIZECOL')
        X_c0_cols = int(
            float(raw_X_c0_cols.replace(',', '.'))) if raw_X_c0_cols is not None and raw_X_c0_cols.strip() != '' else 0
        obj.X_c0_SIZEROW = X_c0_rows
        obj.X_c0_SIZECOL = X_c0_cols
        obj.X_c0 = list()
        for r in range(X_c0_rows):
            row = list()
            for c in range(X_c0_cols):
                raw_v = _dgs_get(parts, header_map, f'X_c0:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.X_c0.append(row)

        raw_R_c1_rows = _dgs_get(parts, header_map, 'R_c1:SIZEROW')
        R_c1_rows = int(
            float(raw_R_c1_rows.replace(',', '.'))) if raw_R_c1_rows is not None and raw_R_c1_rows.strip() != '' else 0
        raw_R_c1_cols = _dgs_get(parts, header_map, 'R_c1:SIZECOL')
        R_c1_cols = int(
            float(raw_R_c1_cols.replace(',', '.'))) if raw_R_c1_cols is not None and raw_R_c1_cols.strip() != '' else 0
        obj.R_c1_SIZEROW = R_c1_rows
        obj.R_c1_SIZECOL = R_c1_cols
        obj.R_c1 = list()
        for r in range(R_c1_rows):
            row = list()
            for c in range(R_c1_cols):
                raw_v = _dgs_get(parts, header_map, f'R_c1:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.R_c1.append(row)

        raw_X_c1_rows = _dgs_get(parts, header_map, 'X_c1:SIZEROW')
        X_c1_rows = int(
            float(raw_X_c1_rows.replace(',', '.'))) if raw_X_c1_rows is not None and raw_X_c1_rows.strip() != '' else 0
        raw_X_c1_cols = _dgs_get(parts, header_map, 'X_c1:SIZECOL')
        X_c1_cols = int(
            float(raw_X_c1_cols.replace(',', '.'))) if raw_X_c1_cols is not None and raw_X_c1_cols.strip() != '' else 0
        obj.X_c1_SIZEROW = X_c1_rows
        obj.X_c1_SIZECOL = X_c1_cols
        obj.X_c1 = list()
        for r in range(X_c1_rows):
            row = list()
            for c in range(X_c1_cols):
                raw_v = _dgs_get(parts, header_map, f'X_c1:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.X_c1.append(row)

        raw_B_c0_rows = _dgs_get(parts, header_map, 'B_c0:SIZEROW')
        B_c0_rows = int(
            float(raw_B_c0_rows.replace(',', '.'))) if raw_B_c0_rows is not None and raw_B_c0_rows.strip() != '' else 0
        raw_B_c0_cols = _dgs_get(parts, header_map, 'B_c0:SIZECOL')
        B_c0_cols = int(
            float(raw_B_c0_cols.replace(',', '.'))) if raw_B_c0_cols is not None and raw_B_c0_cols.strip() != '' else 0
        obj.B_c0_SIZEROW = B_c0_rows
        obj.B_c0_SIZECOL = B_c0_cols
        obj.B_c0 = list()
        for r in range(B_c0_rows):
            row = list()
            for c in range(B_c0_cols):
                raw_v = _dgs_get(parts, header_map, f'B_c0:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.B_c0.append(row)

        raw_B_c1_rows = _dgs_get(parts, header_map, 'B_c1:SIZEROW')
        B_c1_rows = int(
            float(raw_B_c1_rows.replace(',', '.'))) if raw_B_c1_rows is not None and raw_B_c1_rows.strip() != '' else 0
        raw_B_c1_cols = _dgs_get(parts, header_map, 'B_c1:SIZECOL')
        B_c1_cols = int(
            float(raw_B_c1_cols.replace(',', '.'))) if raw_B_c1_cols is not None and raw_B_c1_cols.strip() != '' else 0
        obj.B_c1_SIZEROW = B_c1_rows
        obj.B_c1_SIZECOL = B_c1_cols
        obj.B_c1 = list()
        for r in range(B_c1_rows):
            row = list()
            for c in range(B_c1_cols):
                raw_v = _dgs_get(parts, header_map, f'B_c1:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.B_c1.append(row)

        raw_G_c0_rows = _dgs_get(parts, header_map, 'G_c0:SIZEROW')
        G_c0_rows = int(
            float(raw_G_c0_rows.replace(',', '.'))) if raw_G_c0_rows is not None and raw_G_c0_rows.strip() != '' else 0
        raw_G_c0_cols = _dgs_get(parts, header_map, 'G_c0:SIZECOL')
        G_c0_cols = int(
            float(raw_G_c0_cols.replace(',', '.'))) if raw_G_c0_cols is not None and raw_G_c0_cols.strip() != '' else 0
        obj.G_c0_SIZEROW = G_c0_rows
        obj.G_c0_SIZECOL = G_c0_cols
        obj.G_c0 = list()
        for r in range(G_c0_rows):
            row = list()
            for c in range(G_c0_cols):
                raw_v = _dgs_get(parts, header_map, f'G_c0:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.G_c0.append(row)

        raw_G_c1_rows = _dgs_get(parts, header_map, 'G_c1:SIZEROW')
        G_c1_rows = int(
            float(raw_G_c1_rows.replace(',', '.'))) if raw_G_c1_rows is not None and raw_G_c1_rows.strip() != '' else 0
        raw_G_c1_cols = _dgs_get(parts, header_map, 'G_c1:SIZECOL')
        G_c1_cols = int(
            float(raw_G_c1_cols.replace(',', '.'))) if raw_G_c1_cols is not None and raw_G_c1_cols.strip() != '' else 0
        obj.G_c1_SIZEROW = G_c1_rows
        obj.G_c1_SIZECOL = G_c1_cols
        obj.G_c1 = list()
        for r in range(G_c1_rows):
            row = list()
            for c in range(G_c1_cols):
                raw_v = _dgs_get(parts, header_map, f'G_c1:{r}:{c}')
                raw_v = raw_v.strip() if raw_v is not None else ''
                row.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)
            obj.G_c1.append(row)

        return obj


class ElmTow(DGSElement):
    """PowerFactory line coupling (ElmTow) that binds ElmLne circuits to a tower geometry."""
    __slots__ = (
        "ID",
        "OP",
        "loc_name",
        "fold_id",
        "outserv",
        "i_dist",
        "ngeo",
        "pGeo",
        "plines",
        "dpolar",
        "dphasing",
        "ctransp",
    )

    element_type = 'ElmTow'

    properties_list = [
        DgsProperty(name='ID', dgs_type='a:40', description='Unique identifier for DGS file', py_name='ID'),
        DgsProperty(name='OP', dgs_type='a:1', description='Operation', py_name='OP'),
        DgsProperty(name='loc_name', dgs_type='a:80', description='Name', py_name='loc_name'),
        DgsProperty(name='fold_id', dgs_type='p', description='In Folder', py_name='fold_id'),
        DgsProperty(name='outserv', dgs_type='i', description='Out of Service', py_name='outserv'),
        DgsProperty(name='i_dist', dgs_type='i', description='Line Model', py_name='i_dist'),
        DgsProperty(name='ngeo', dgs_type='i', description='Number of overhead line systems', py_name='ngeo'),
    ]

    def __init__(self):
        self.ID: str = ''
        self.OP: str = ''
        self.loc_name: str = ''
        self.fold_id: str | None = None
        self.outserv: int = 0
        self.i_dist: int = 0
        self.ngeo: int = 0

        # Dynamic vectors
        self.pGeo: List[str | None] = list()  # Pointers to TypTow/TypGeo
        self.plines: List[str | None] = list()  # Pointers to ElmLne / ElmLneRoute
        self.dpolar: List[float] = list()  # Polarity flags
        self.dphasing: List[int] = list()  # Physical phase arrangement per circuit
        self.ctransp: List[float] = list()  # Transposition per circuit

    @classmethod
    def parse_line(cls, line: str, header_map: dict[str, int]):
        """Parse ElmTow data line including variable-sized vectors."""
        parts = line.rstrip('\n').split(';')
        obj = cls()

        # Parse scalars
        for prop in cls.properties_list:
            idx = header_map.get(prop.name)
            if idx is None and prop.name == 'ID':
                idx = header_map.get('FID')

            if idx is not None and 0 <= idx < len(parts):
                raw = parts[idx]
                val = prop.parse(raw)
                setattr(obj, prop.py_name, val)

        # Geometry pointers
        raw_ng = _dgs_get(parts, header_map, 'pGeo:SIZEROW')
        ng = int(float(raw_ng.replace(',', '.'))) if raw_ng is not None and raw_ng.strip() != '' else 0
        obj.pGeo = list()
        for i in range(ng):
            raw_ptr = _dgs_get(parts, header_map, f'pGeo:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.pGeo.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        # Circuit pointers (ElmLne)
        raw_nl = _dgs_get(parts, header_map, 'plines:SIZEROW')
        nl = int(float(raw_nl.replace(',', '.'))) if raw_nl is not None and raw_nl.strip() != '' else 0
        obj.plines = list()
        for i in range(nl):
            raw_ptr = _dgs_get(parts, header_map, f'plines:{i}')
            raw_ptr = raw_ptr.strip() if raw_ptr is not None else ''
            obj.plines.append(raw_ptr if raw_ptr != '' and raw_ptr != '*' else None)

        # Polarity flags (optional)
        raw_np = _dgs_get(parts, header_map, 'dpolar:SIZEROW')
        np = int(float(raw_np.replace(',', '.'))) if raw_np is not None and raw_np.strip() != '' else 0
        obj.dpolar = list()
        for i in range(np):
            raw_v = _dgs_get(parts, header_map, f'dpolar:{i}')
            raw_v = raw_v.strip() if raw_v is not None else ''
            obj.dpolar.append(float(raw_v.replace(',', '.')) if raw_v != '' and raw_v != '*' else 0.0)

        raw_count: str | None = _dgs_get(parts, header_map, 'dphasing:SIZEROW')
        count: int = int(float(raw_count.replace(',', '.'))) if raw_count is not None and raw_count.strip() else 0
        for i in range(count):
            raw_value: str | None = _dgs_get(parts, header_map, f'dphasing:{i}')
            obj.dphasing.append(int(float(raw_value.replace(',', '.')))
                                if raw_value is not None and raw_value.strip() not in ('', '*') else 0)
        raw_count = _dgs_get(parts, header_map, 'ctransp:SIZEROW')
        count = int(float(raw_count.replace(',', '.'))) if raw_count is not None and raw_count.strip() else 0
        for i in range(count):
            raw_value = _dgs_get(parts, header_map, f'ctransp:{i}')
            obj.ctransp.append(float(raw_value.replace(',', '.'))
                               if raw_value is not None and raw_value.strip() not in ('', '*') else 0.0)

        return obj
