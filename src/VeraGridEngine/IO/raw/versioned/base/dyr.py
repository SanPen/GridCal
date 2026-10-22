# SPDX-License-Identifier: MPL-2.0
"""Typed dynamic assignments and explicit model schemas.

Sources: POM 33 section 15.1.1; POM 35 section 16.1.1; ModelLibrary 35
GENCLS, GENROU and GENSAL data sheets. User-model payloads are NI ICONs then
NC CONs, not NS states or NV variables. Unknown models remain inspectable and
are explicitly unsupported until a reviewed schema is supplied.
"""
from __future__ import annotations

import math
from enum import IntEnum

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.psse_auxiliary import PsseToken, PsseVersion, resolve_psse_version
from VeraGridEngine.IO.raw.versioned.base.auxiliary import BusIdentifier, EquipmentKind, FeatureSupport, RecordStatus
from VeraGridEngine.IO.raw.versioned.base.dyr_standard_schemas import standard_dyr_parameters


class UserModelType(IntEnum):
    """IC calling-sequence codes from POM 33/35; unknown codes stay explicit."""

    CONET = 0
    GENERATOR = 1
    COMPENSATOR = 2
    STABILIZER = 3
    EXCITER = 4
    GOVERNOR = 5
    LEGACY_DC = 7
    CONEC_OTHER = 8
    MINIMUM_EXCITATION_LIMITER = 9
    MAXIMUM_EXCITATION_LIMITER = 10
    CROSS_COMPOUND_GOVERNOR = 11
    LOAD = 12
    LOAD_RELAY = 13
    LINE_RELAY = 14
    AUXILIARY_SIGNAL = 17
    TWO_TERMINAL_DC = 18
    MULTI_TERMINAL_DC = 19
    VSC_DC = 20
    FACTS = 21
    TURBINE_LOAD_CONTROLLER = 23
    SWITCHED_SHUNT = 24
    INDUCTION_MACHINE = 25
    RENEWABLE_GENERATOR = 101
    RENEWABLE_ELECTRICAL = 102
    RENEWABLE_TURBINE = 103
    RENEWABLE_PITCH = 104
    RENEWABLE_AERODYNAMIC = 105
    RENEWABLE_GUST = 106
    RENEWABLE_AUXILIARY = 107
    RENEWABLE_TORQUE = 108
    BRANCH = 301
    TWO_WINDING = 302
    THREE_WINDING = 303
    THREE_WINDING_PROTECTION = 403
    BUS_PROTECTION = 404
    MACHINE_PROTECTION = 405
    TWO_TERMINAL_DC_PROTECTION = 406
    MULTI_TERMINAL_DC_PROTECTION = 407
    VSC_DC_PROTECTION = 408
    FACTS_PROTECTION = 409
    SHUNT_PROTECTION = 410
    INDUCTION_MACHINE_PROTECTION = 413
    BRANCH_OTHER = 501
    TWO_WINDING_OTHER = 502
    THREE_WINDING_OTHER = 503
    BUS_OTHER = 504
    MACHINE_OTHER = 505
    TWO_TERMINAL_DC_OTHER = 506
    MULTI_TERMINAL_DC_OTHER = 507
    VSC_DC_OTHER = 508
    FACTS_OTHER = 509
    SHUNT_OTHER = 510
    LOAD_OTHER = 511
    MISCELLANEOUS_OTHER = 512
    INDUCTION_MACHINE_OTHER = 513


class DynamicParameter:
    """A named model constant, defined by a reviewed model data sheet."""

    __slots__ = ('name', 'value')

    def __init__(self, name: str, value: float) -> None:
        """Store a named constant.

        :param name: Model data-sheet parameter name.
        :param value: Parsed numeric value.
        """
        self.name: str = name
        self.value: float = value


class DynamicModelSchema:
    """Record layout for a built-in machine or controller, independent of simulation."""

    __slots__ = ('name', 'parameters', 'icon_names', 'character_icon_names', 'signed_icon_names')

    def __init__(self, name: str, parameters: tuple[str, ...],
                 icon_names: tuple[str, ...] = (), character_icon_names: tuple[str, ...] = (),
                 signed_icon_names: tuple[str, ...] = ()) -> None:
        """Declare a machine or controller's ordered header and constant schema.

        :param name: PSS/E model name.
        :param parameters: Data-sheet constant names, in file order.
        :param icon_names: Ordered header fields preceding the constants; integers unless explicitly character fields.
        :param character_icon_names: Header fields preserving equipment identifiers, including leading zeros.
        :param signed_icon_names: Explicit integer fields permitting negative selector codes.
        """
        self.name: str = name
        self.parameters: tuple[str, ...] = parameters
        self.icon_names: tuple[str, ...] = icon_names
        self.character_icon_names: tuple[str, ...] = character_icon_names
        self.signed_icon_names: tuple[str, ...] = signed_icon_names


class UserModelHeader:
    """Allocation counts and calling convention from a user-model record."""

    __slots__ = ('name', 'model_type', 'model_type_code', 'call_type', 'icon_count', 'constant_count',
                 'state_count', 'variable_count', 'reserved_icon_count', 'references')

    def __init__(self, name: str, counts: tuple[int, ...]) -> None:
        """Store a checked six-field allocation header.

        :param name: User subroutine name.
        :param counts: IC, IT, NI, NC, NS and NV.
        """
        self.name: str = name
        types: dict[int, UserModelType] = dict((item.value, item) for item in UserModelType)
        self.model_type: UserModelType | None = types.get(counts[0], None)
        self.model_type_code: int = counts[0]
        self.call_type: int = counts[1]
        self.icon_count: int = counts[2]
        self.constant_count: int = counts[3]
        self.state_count: int = counts[4]
        self.variable_count: int = counts[5]
        self.reserved_icon_count: int | None = None
        self.references: tuple[int | float | str, ...] = ()


class UserDynamicModelSchema:
    """A named user subroutine's payload and exact calling/allocation contract."""

    __slots__ = ('layout', 'model_type', 'call_type', 'state_count', 'variable_count')

    def __init__(self, layout: DynamicModelSchema, model_type: UserModelType,
                 call_type: int, state_count: int, variable_count: int) -> None:
        """Declare one explicitly reviewed release-specific user-model contract.

        :param layout: Source subroutine name and ordered ICON/CON payload layout.
        :param model_type: Required calling sequence, independent of native attachment.
        :param call_type: Exact source IT value.
        :param state_count: Exact declared NS allocation.
        :param variable_count: Exact declared NV allocation.
        """
        self.layout: DynamicModelSchema = layout
        self.model_type: UserModelType = model_type
        self.call_type: int = call_type
        self.state_count: int = state_count
        self.variable_count: int = variable_count

    def matches(self, header: UserModelHeader) -> bool:
        """Check the whole calling contract without treating allocation fields as payload.

        :param header: Parsed source allocation header.
        :return: Whether source name, calling sequence and every allocation match.
        """
        return (header.name.upper() == self.layout.name and header.model_type == self.model_type
                and header.call_type == self.call_type and header.icon_count == len(self.layout.icon_names)
                and header.constant_count == len(self.layout.parameters)
                and header.state_count == self.state_count and header.variable_count == self.variable_count)


class DyrRecord:
    """A typed dynamic assignment with source tokens and explicit schema status."""

    __slots__ = ('identifier', 'model', 'data', 'tokens', 'line_number', 'equipment_id',
                 'user_header', 'user_schema', 'icons', 'constants', 'parameters', 'status',
                 'target_kind', 'bus', 'remote_buses', 'relay_side', 'auxiliary_device_type', 'signal_index')

    def __init__(self, tokens: tuple[PsseToken, ...], line_number: int) -> None:
        """Initialize a record whose identifier/model header has been checked.

        :param tokens: Entire logical record.
        :param line_number: First physical source line.
        """
        self.identifier: int | float | str = parse_dyr_value(tokens[0])
        self.model: str = tokens[1].text.strip()
        self.data: tuple[int | float | str, ...] = tuple(parse_dyr_value(token) for token in tokens[2:])
        self.tokens: tuple[PsseToken, ...] = tokens
        self.line_number: int = line_number
        self.equipment_id: str | None = None
        self.user_header: UserModelHeader | None = None
        self.user_schema: UserDynamicModelSchema | None = None
        self.icons: tuple[int | str, ...] = ()
        self.constants: tuple[float, ...] = ()
        self.parameters: tuple[DynamicParameter, ...] = ()
        self.status: RecordStatus = RecordStatus.UNSUPPORTED
        self.target_kind: EquipmentKind | None = None
        self.bus: BusIdentifier | None = None
        self.remote_buses: tuple[BusIdentifier, ...] = ()
        self.relay_side: int | None = None
        self.auxiliary_device_type: int | None = None
        self.signal_index: int | None = None


def parse_dyr_value(token: PsseToken) -> int | float | str:
    """Convert unquoted numbers and preserve quoted identifiers exactly.

    :param token: Input field with quote information.
    :return: Parsed value or original text.
    """
    if token.quoted:
        return token.text
    else:
        try:
            return int(token.text)
        except ValueError:
            try:
                return float(token.text.replace('D', 'E').replace('d', 'e'))
            except ValueError:
                return token.text


def parse_dyr_constant(token: PsseToken) -> float | None:
    """Read a finite unquoted real value without overflowing on large integers.

    :param token: Input constant field.
    :return: Finite value, or None for an invalid constant.
    """
    if token.quoted:
        return None
    else:
        try:
            value: float = float(token.text.replace('D', 'E').replace('d', 'e'))
            return value if math.isfinite(value) else None
        except (ValueError, OverflowError):
            return None


class RawDyr:
    """Versioned dynamic data; tokenization is owned by the standalone reader."""

    __slots__ = ('records', 'logger', 'source', 'version', 'usr_sws2_support', 'torque_model_support', 'rejected')

    def __init__(self, source: str = '<dyr>', version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize an independent dynamic-data container.

        :param source: Diagnostic source label.
        :param version: Major version selected by the concrete class.
        """
        self.records: tuple[DyrRecord, ...] = ()
        self.logger: Logger = Logger()
        self.source: str = source
        self.version: PsseVersion | None = resolve_psse_version(version, self.logger, source)
        self.usr_sws2_support: FeatureSupport = FeatureSupport.UNVERIFIED
        self.torque_model_support: FeatureSupport = FeatureSupport.UNVERIFIED
        self.rejected: tuple[tuple[PsseToken, ...], ...] = ()

    def get_model_schema(self, model: str) -> DynamicModelSchema | None:
        """Get a reviewed layout; subclasses override when a version changes it.

        :param model: Input model name, case-insensitive.
        :return: Schema or None; never infer an unknown model's attachment type.
        """
        schemas: dict[str, DynamicModelSchema] = dict(
            ST7B=DynamicModelSchema('ST7B',('TR','TG','TF','VMAX','VMIN','KPA','VRMAX','VRMIN','KH','KL','TC','TB','KIA','TIA'),('OEL','UEL')),
            DC4B=DynamicModelSchema('DC4B',('TR','KP','KI','KD','TD','VRMAX','VRMIN','KA','TA','KE','TE','KF','TF','VEMIN','E1','SE1','E2','SE2'),('OEL','UEL')),
            ESST1A=DynamicModelSchema('ESST1A',('TR','VIMAX','VIMIN','TC','TB','TC1','TB1','KA','TA','VAMAX','VAMIN','VRMAX','VRMIN','KC','KF','TF','KLR','ILR'),('UEL','VOS')),
            PSS3B=DynamicModelSchema('PSS3B',('KS1','T1','TW1','KS2','T2','TW2','TW3','A1','A2','A3','A4','A5','A6','A7','A8','VSTMAX','VSTMIN'),('ICS1','REMBUS1','ICS2','REMBUS2')),
            PIDGOV=DynamicModelSchema('PIDGOV',('RPERM','TREG','KP','KI','KD','TA','TB','DTURB','G0','G1','P1','G2','P2','P3','GMAX','GMIN','ATW','TW','VELMAX','VELMIN'),('FEEDBACK',)),
            GGOV1=DynamicModelSchema('GGOV1',
                ('R', 'TPELEC', 'MAXERR', 'MINERR', 'KPGOV', 'KIGOV', 'KDGOV', 'TDGOV',
                 'VMAX', 'VMIN', 'TACT', 'KTURB', 'WFNL', 'TB', 'TC', 'TENG', 'TFLOAD',
                 'KPLOAD', 'KILOAD', 'LDREF', 'DM', 'ROPEN', 'RCLOSE', 'KIMW', 'ASET',
                 'KA', 'TA', 'TRATE', 'DB', 'TSA', 'TSB', 'RUP', 'RDOWN'),
                ('RSELECT', 'FLAG'), (), ('RSELECT',)),
            LCFB1=DynamicModelSchema('LCFB1', ('FB', 'TPELEC', 'DB', 'EMAX', 'KP', 'KI', 'LRMAX'),
                ('FREQUENCY_BIAS_FLAG', 'POWER_CONTROL_FLAG')),
            DEGOV1=DynamicModelSchema('DEGOV1',
                ('T1','T2','T3','K','T4','T5','T6','TD','TMAX','TMIN','DROOP','TE'), ('DROOP_CONTROL',)),
            IEEEG1=DynamicModelSchema('IEEEG1',
                ('K', 'T1', 'T2', 'T3', 'UO', 'UC', 'PMAX', 'PMIN', 'T4', 'K1', 'K2',
                 'T5', 'K3', 'K4', 'T6', 'K5', 'K6', 'T7', 'K7', 'K8'),
                ('JBUS', 'M'), ('M',)),
            PSS2A=DynamicModelSchema('PSS2A',
                ('TW1', 'TW2', 'T6', 'TW3', 'TW4', 'T7', 'KS2', 'KS3', 'T8', 'T9',
                 'KS1', 'T1', 'T2', 'T3', 'T4', 'VSTMAX', 'VSTMIN'),
                ('IC1', 'IB1', 'IC2', 'IB2', 'M', 'N')),
            PSS2B=DynamicModelSchema('PSS2B',
                ('TW1', 'TW2', 'T6', 'TW3', 'TW4', 'T7', 'KS2', 'KS3', 'T8', 'T9',
                 'KS1', 'T1', 'T2', 'T3', 'T4', 'T10', 'T11', 'VS1MAX', 'VS1MIN',
                 'VS2MAX', 'VS2MIN', 'VSTMAX', 'VSTMIN'),
                ('IC1', 'IB1', 'IC2', 'IB2', 'M', 'N')),
            IEE2ST=DynamicModelSchema('IEE2ST',
                ('K1', 'K2', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8',
                 'T9', 'T10', 'LSMAX', 'LSMIN', 'VCU', 'VCL'), ('IC1', 'IB1', 'IC2', 'IB2')),
            IEEEST=DynamicModelSchema('IEEEST',
                ('A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'T1', 'T2', 'T3', 'T4',
                 'T5', 'T6', 'KS', 'LSMAX', 'LSMIN', 'VCU', 'VCL'), ('IC', 'IB')),
            GENCLS=DynamicModelSchema('GENCLS', ('H', 'D')),
            GENROU=DynamicModelSchema('GENROU', ('Tdo1', 'Tdo2', 'Tqo1', 'Tqo2', 'H', 'D',
                                                'Xd', 'Xq', 'Xd1', 'Xq1', 'Xd2', 'Xl', 'S10', 'S12')),
            GENSAL=DynamicModelSchema('GENSAL', ('Tdo1', 'Tdo2', 'Tqo2', 'H', 'D', 'Xd',
                                                'Xq', 'Xd1', 'Xd2', 'Xl', 'S10', 'S12')))
        schema: DynamicModelSchema | None = schemas.get(model.upper(), None)
        if schema is None:
            names: tuple[str, ...] | None = standard_dyr_parameters(model)
            return DynamicModelSchema(model.upper(), names) if names is not None else None
        else:
            return schema

    def get_user_model_schema(self, name: str) -> UserDynamicModelSchema | None:
        """Select an explicitly reviewed user-model contract in the concrete release.

        :param name: Source subroutine identifier, never a native template alias.
        :return: Release-owned contract or None, preserving arbitrary user data.
        """
        return None

    def read_schema_icons(self, record: DyrRecord, schema: DynamicModelSchema,
                          tokens: tuple[PsseToken, ...]) -> None:
        """Validate declared payload/header ICON kinds without relaxing unrelated fields.

        :param record: Source record receiving values and diagnostics.
        :param schema: Explicit ordered integer/character/signed field declarations.
        :param tokens: Exactly the ICON tokens, excluding CON and allocation fields.
        """
        icons: list[int | str] = list()
        for header_name, token in zip(schema.icon_names, tokens):
            icon: int | float | str = parse_dyr_value(token)
            if header_name in schema.character_icon_names:
                if 1 <= len(token.text.strip()) <= 2 and (token.quoted or isinstance(icon, int)):
                    icons.append(token.text.strip())
                else:
                    self.fail(record, 'Model equipment header identifiers require one or two characters')
            elif isinstance(icon, int) and (icon >= 0 or header_name in schema.signed_icon_names) and not token.quoted:
                icons.append(icon)
            else:
                self.fail(record, 'Model integer ICONs must be unquoted integers; negative values require an explicit signed field')
        record.icons = tuple(icons)

    def parse_record(self, tokens: tuple[PsseToken, ...], line_number: int) -> DyrRecord | None:
        """Validate header and dispatch a record to its explicit model schema.

        :param tokens: Entire logical record.
        :param line_number: First physical source line.
        :return: Typed assignment, or None for an invalid basic header.
        """
        if len(tokens) < 2 or not tokens[1].quoted or not 1 <= len(tokens[1].text.strip()) <= 16:
            self.logger.add_error('DYR requires an identifier and a quoted model name of 1-16 characters',
                                  device=self.source, value=line_number)
            return None
        else:
            pass
        record: DyrRecord = DyrRecord(tokens, line_number)
        if (isinstance(record.identifier, float) or
                (isinstance(record.identifier, int) and record.identifier < 0) or
                (isinstance(record.identifier, str) and (not tokens[0].quoted or len(record.identifier) == 0))):
            self.fail(record, 'DYR identifier must be a nonnegative integer or quoted device/name')
            return record
        else:
            pass
        schema: DynamicModelSchema | None = self.get_model_schema(record.model)
        if schema is not None:
            record.target_kind = EquipmentKind.MACHINE
            record.bus = self.read_bus_reference(record, tokens[0])
            if len(record.data) != len(schema.parameters) + len(schema.icon_names) + 1:
                self.fail(record, 'Incorrect field count for ' + schema.name)
            else:
                record.equipment_id = tokens[2].text
                # Integer signal selectors are not real-valued controller constants.
                constant_start: int = 3 + len(schema.icon_names)
                self.read_schema_icons(record, schema, tokens[3:constant_start])
                constants: list[float] = list()
                parameters: list[DynamicParameter] = list()
                for name, token in zip(schema.parameters, tokens[constant_start:]):
                    value: float | None = parse_dyr_constant(token)
                    if value is not None:
                        constants.append(value)
                        parameters.append(DynamicParameter(name, value))
                    else:
                        self.fail(record, 'Model constants must be finite numbers')
                record.constants = tuple(constants)
                record.parameters = tuple(parameters)
                if record.status != RecordStatus.INVALID:
                    record.status = RecordStatus.VALID
                else:
                    pass
                if not 1 <= len(record.equipment_id) <= 2:
                    self.fail(record, 'Machine identifier must contain one or two characters')
                else:
                    pass
        elif record.model.upper().startswith('USR'):
            self.parse_user_model(record)
        else:
            self.logger.add_warning('DYR model has no reviewed schema; assignment retained',
                                    device=self.source, value=record.model)
        return record

    def fail(self, record: DyrRecord, message: str) -> None:
        """Invalidate an assignment while keeping its complete original payload.

        :param record: Assignment to invalidate.
        :param message: Specific validation failure.
        """
        record.status = RecordStatus.INVALID
        self.logger.add_error(message, device=self.source, value=record.line_number)

    def parse_user_model(self, record: DyrRecord) -> None:
        """Decode documented USR headers and check allocation/payload counts.

        :param record: User assignment with checked leading identifier/model.
        """
        name_offsets: dict[str, int] = dict(USRLOD=3, USRBRN=4, USR2WT=4, USRREL=5,
                                            USR3WT=5, USRBUS=2, USRAUX=4, USRDCL=2,
                                            USRFCT=2, USRSWS=2, USRSWS2=3, USRIMC=3,
                                            USRMDL=3, USRMSC=2)
        keyword: str = record.model.upper()
        name_index: int | None = name_offsets.get(keyword, None)
        if name_index is None:
            self.logger.add_warning('Unknown user-model header retained', device=self.source, value=record.model)
            return
        else:
            pass
        if len(record.tokens) < name_index + 7 or not record.tokens[name_index].quoted:
            self.fail(record, 'Incomplete user-model name/allocation header')
            return
        else:
            pass
        counts: list[int] = list()
        for token in record.tokens[name_index + 1:name_index + 7]:
            value: int | float | str = parse_dyr_value(token)
            if isinstance(value, int) and value >= 0:
                counts.append(value)
            else:
                self.fail(record, 'User-model allocation fields must be nonnegative integers')
        if len(counts) != 6:
            return
        else:
            pass
        header: UserModelHeader = UserModelHeader(record.tokens[name_index].text.strip(), tuple(counts))
        record.user_header = header
        if not 1 <= len(header.name) <= 16:
            self.fail(record, 'User-model name must contain 1-16 characters')
        else:
            pass
        header.references = tuple(parse_dyr_value(token) for token in record.tokens[2:name_index])
        self.parse_user_target(record)
        position: int = name_index + 7
        if keyword == 'USRREL' or (keyword == 'USRLOD' and header.model_type in (UserModelType.LOAD, UserModelType.LOAD_RELAY)):
            if position < len(record.tokens):
                reserved: int | float | str = parse_dyr_value(record.tokens[position])
                if isinstance(reserved, int) and reserved >= 0:
                    header.reserved_icon_count = reserved
                    position += 1
                else:
                    self.fail(record, 'Invalid reserved ICON count')
            else:
                self.fail(record, 'Missing reserved ICON count')
        elif header.model_type == UserModelType.CROSS_COMPOUND_GOVERNOR:
            # LP targets precede payload ICONs. Preserve equipment text such as
            # unquoted 01; numeric conversion would silently select another unit.
            if len(record.tokens) < position+2:
                self.fail(record, 'Cross-compound governor requires an LP bus and machine identifier')
                return
            else:
                secondary: BusIdentifier | None = self.read_bus_reference(record, record.tokens[position])
                identity_token: PsseToken = record.tokens[position+1]
                identity: int | float | str = parse_dyr_value(identity_token)
                header.references = (parse_dyr_value(record.tokens[position]), identity_token.text.strip())
                if not 1 <= len(identity_token.text.strip()) <= 2 or not (identity_token.quoted or isinstance(identity,int)):
                    self.fail(record, 'Cross-compound LP machine identifier must contain one or two characters')
                else:
                    pass
                if secondary is not None:
                    record.remote_buses = (secondary,)
                else:
                    pass
                position += 2
        else:
            pass

        if (header.icon_count > 500 or header.constant_count > 1000
                or len(record.tokens) - position != header.icon_count + header.constant_count):
            self.fail(record, 'User-model payload does not match NI/NC allocation counts')
            return
        else:
            pass
        icons: list[int | str] = list()
        constants: list[float] = list()
        for token in record.tokens[position:position + header.icon_count]:
            value = parse_dyr_value(token)
            if isinstance(value, int) or (isinstance(value, str) and token.quoted):
                icons.append(value)
            else:
                self.fail(record, 'ICON fields require integers or quoted character values')
        for token in record.tokens[position + header.icon_count:]:
            constant: float | None = parse_dyr_constant(token)
            if constant is not None:
                constants.append(constant)
            else:
                self.fail(record, 'CON fields require finite numbers')
        record.icons = tuple(icons)
        record.constants = tuple(constants)
        # A reviewed subroutine must satisfy the release's complete contract.
        # Arbitrary user records retain their generic parsed payload unchanged.
        user_schema: UserDynamicModelSchema | None = self.get_user_model_schema(header.name) if keyword == 'USRMDL' else None
        if user_schema is None:
            pass
        elif not user_schema.matches(header):
            self.fail(record, 'User-model header does not match the reviewed calling/allocation contract: '+header.name)
        else:
            record.user_schema = user_schema
            if record.equipment_id is None or not 1 <= len(record.equipment_id) <= 2:
                self.fail(record, 'Reviewed user-model machine identifier must contain one or two characters')
            else:
                pass
            self.read_schema_icons(record, user_schema.layout, record.tokens[position:position+header.icon_count])
            record.parameters = tuple(DynamicParameter(name, value)
                for name, value in zip(user_schema.layout.parameters, record.constants))
        if keyword == 'USRSWS2' and self.usr_sws2_support != FeatureSupport.YES:
            if self.usr_sws2_support == FeatureSupport.NO:
                self.fail(record, 'USRSWS2 is introduced in PSS/E 35; legacy files use USRSWS')
            else:
                self.logger.add_warning('USRSWS2 support is unverified', device=self.source, value=record.line_number)
        elif header.model_type is None:
            self.logger.add_warning('Unknown user-model IC calling sequence retained', device=self.source, value=record.line_number)
        elif header.model_type == UserModelType.RENEWABLE_TORQUE and self.torque_model_support != FeatureSupport.YES:
            if self.torque_model_support == FeatureSupport.NO:
                self.fail(record, 'IC=108 is not documented in PSS/E 33')
            else:
                self.logger.add_warning('IC=108 support is unverified for this version', device=self.source, value=record.line_number)
        elif record.status != RecordStatus.INVALID:
            record.status = RecordStatus.VALID
        else:
            pass

    def read_bus_reference(self, record: DyrRecord, token: PsseToken) -> BusIdentifier | None:
        """Read a known bus field, without interpreting generic DYR identifiers.

        :param record: Assignment receiving diagnostics.
        :param token: Field whose schema explicitly declares a bus reference.
        :return: Typed bus reference, or None with a validation error.
        """
        value: int | float | str = parse_dyr_value(token)
        if isinstance(value, int) and value > 0:
            return BusIdentifier(number=value)
        elif isinstance(value, str) and token.quoted and len(value) > 0:
            return BusIdentifier(name=value)
        else:
            self.fail(record, 'Expected a positive bus number or quoted extended bus name')
            return None

    def parse_user_target(self, record: DyrRecord) -> None:
        """Decode equipment references from each documented user-header layout.

        :param record: Assignment with an already checked allocation header.
        """
        header: UserModelHeader | None = record.user_header
        if header is None:
            return
        else:
            pass
        keyword: str = record.model.upper()
        targets: dict[str, EquipmentKind] = dict(
            USRMDL=EquipmentKind.MACHINE, USRIMC=EquipmentKind.INDUCTION_MACHINE,
            USRLOD=EquipmentKind.LOAD, USRSWS=EquipmentKind.SWSHUNT, USRSWS2=EquipmentKind.SWSHUNT,
            USRBUS=EquipmentKind.BUS, USRBRN=EquipmentKind.BRANCH,
            USR2WT=EquipmentKind.BRANCH, USR3WT=EquipmentKind.THREE_WINDING,
            USRREL=EquipmentKind.BRANCH, USRFCT=EquipmentKind.FACTS)
        record.target_kind = targets.get(keyword, None)
        if keyword == 'USRMSC':
            if not isinstance(record.identifier, int) or record.identifier <= 0:
                self.fail(record, 'Miscellaneous model instance must be a positive integer')
            else:
                pass
        elif header.model_type in (UserModelType.CONET, UserModelType.CONEC_OTHER, UserModelType.LEGACY_DC):
            record.target_kind = None
        elif keyword in ('USRMDL', 'USRIMC', 'USRSWS', 'USRSWS2', 'USRBUS', 'USRBRN', 'USR2WT', 'USR3WT', 'USRREL'):
            record.bus = self.read_bus_reference(record, record.tokens[0])
        else:
            pass
        if keyword in ('USRMDL', 'USRLOD', 'USRIMC', 'USRSWS2'):
            record.equipment_id = record.tokens[2].text
        elif keyword in ('USRBRN', 'USR2WT', 'USRREL'):
            record.equipment_id = record.tokens[3].text
        elif keyword == 'USR3WT':
            record.equipment_id = record.tokens[4].text
        else:
            pass
        if keyword in ('USRBRN', 'USR2WT', 'USR3WT', 'USRREL'):
            remote: list[BusIdentifier] = list()
            count: int = 2 if keyword == 'USR3WT' else 1
            for token in record.tokens[2:2 + count]:
                bus: BusIdentifier | None = self.read_bus_reference(record, token)
                if bus is not None:
                    remote.append(bus)
                else:
                    pass
            record.remote_buses = tuple(remote)
        else:
            pass
        if keyword == 'USRREL':
            side: int | float | str = parse_dyr_value(record.tokens[4])
            if isinstance(side, int):
                record.relay_side = side
            else:
                self.fail(record, 'User relay side must be an integer')
        elif keyword == 'USRAUX':
            device_type: int | float | str = parse_dyr_value(record.tokens[2])
            signal_index: int | float | str = parse_dyr_value(record.tokens[3])
            if isinstance(device_type, int) and isinstance(signal_index, int):
                record.auxiliary_device_type = device_type
                record.signal_index = signal_index
            else:
                self.fail(record, 'User auxiliary device type and signal index must be integers')
        else:
            pass
        if record.equipment_id is not None and not 1 <= len(record.equipment_id) <= 2:
            self.fail(record, 'Equipment identifier must contain one or two characters')
        else:
            pass
