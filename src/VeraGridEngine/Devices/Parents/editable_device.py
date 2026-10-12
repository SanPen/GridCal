# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import random
import uuid
import numpy as np
import pandas as pd

from typing import List, Dict, AnyStr, Any, Union, Type, Tuple
from VeraGridEngine.basic_structures import Logger, IntVec
from VeraGridEngine.Devices.Profiles import AnyProfile, PROFILE_INSTANCE_TYPES
from VeraGridEngine.enumerations import (DeviceType, PrpCat, TimeFrame, BuildStatus, WindingsConnection,
                                         TapModuleControl, TapPhaseControl, SubObjectType, ConverterControlType,
                                         HvdcControlType, ActionType, AvailableTransferMode, ContingencyMethod,
                                         CpfParametrization, CpfStopAt, InvestmentEvaluationMethod, SolverType,
                                         InvestmentsEvaluationObjectives, NodalCapacityMethod, TimeGrouping,
                                         ZonalGrouping, MIPSolvers, AcOpfMode, VoltageLevelTypes, BranchGroupTypes,
                                         BranchImpedanceMode, FaultType, TapChangerTypes, ContingencyOperationTypes,
                                         WindingType, MethodShortCircuit, PhasesShortCircuit, ShuntConnectionType,
                                         BusGraphicType, SwitchGraphicType, DynamicIntegrationMethod, OpfDispatchMode,
                                         EmtLineTypes, EmtProblemTypes, EmtInitializationMethod,
                                         SmallSignalEmtBuildTypes, FmuTemplateDomain, DynamicPlotMode,
                                         EraSvdSolverType, ShuntControlMode, RmsProblemTypes, FmuTemplateDomain,
                                         FmuTemplateMode, RmsInitializationMethod, EmtSolverTypes, PlotSimulationType,
                                         DynamicEventTransitionType, DynamicPlotEntryKind, DynamicPlotEntryRole,
                                         ParamPowerFlowReferenceType, GeneratorControlMode)
# types that can be assigned to a VeraGrid property
GCPROP_TYPES = Union[
    Type[int],
    Type[bool],
    Type[float],
    Type[str],
    DeviceType,
    SubObjectType,
    Type[HvdcControlType],
    Type[BuildStatus],
    Type[WindingsConnection],
    Type[TapModuleControl],
    Type[TapPhaseControl],
    Type[ActionType],
    Type[AvailableTransferMode],
    Type[ContingencyMethod],
    Type[CpfParametrization],
    Type[CpfStopAt],
    Type[InvestmentEvaluationMethod],
    Type[InvestmentsEvaluationObjectives],
    Type[NodalCapacityMethod],
    Type[ShuntControlMode],
    Type[GeneratorControlMode],
    Type[SolverType],
    Type[TimeGrouping],
    Type[ZonalGrouping],
    Type[MIPSolvers],
    Type[AcOpfMode],
    Type[BranchImpedanceMode],
    Type[FaultType],
    Type[TapChangerTypes],
    Type[VoltageLevelTypes],
    Type[ContingencyOperationTypes],
    Type[BranchGroupTypes],
    Type[ConverterControlType],
    Type[WindingType],
    Type[MethodShortCircuit],
    Type[PhasesShortCircuit],
    Type[DeviceType],
    Type[ShuntConnectionType],
    Type[BusGraphicType],
    Type[SwitchGraphicType],
    Type[DynamicIntegrationMethod],
    Type[RmsInitializationMethod],
    Type[OpfDispatchMode],
    Type[EmtLineTypes],
    Type[EmtSolverTypes],
    Type[EmtProblemTypes],
    Type[EmtInitializationMethod],
    Type[RmsProblemTypes],
    Type[SmallSignalEmtBuildTypes],
    Type[EraSvdSolverType],
    Type[FmuTemplateDomain],
    Type[FmuTemplateMode],
    Type[PlotSimulationType],
    Type[DynamicEventTransitionType],
    Type[DynamicPlotMode],
    Type[DynamicPlotEntryKind],
    Type[DynamicPlotEntryRole],
]


def uuid2idtag(val: str):
    """
    Remove the useless characters and format as a proper 32-char UID
    :param val: value that looks like a UUID
    :return: proper UUID
    """
    return val.replace('_', '').replace('-', '')


def parse_idtag(val: Union[str, None]) -> str:
    """
    idtag setter
    :param val: any string or None
    """
    if val is None:
        return uuid.uuid4().hex  # generate a proper UUIDv4 string
    elif isinstance(val, str):
        if len(val) == 32:
            return val  # this is probably a proper UUID
        elif len(val) == 0:
            return uuid.uuid4().hex  # generate a proper UUIDv4 string
        else:
            candidate_val = uuid2idtag(val)
            if len(candidate_val) == 32:
                return candidate_val  # if the string passed can be a UUID, set it
            else:
                return val  # otherwise this is just a plain string, that we hope is valid...
    else:
        return str(val)


def smart_compare(a, b, atol=1.e-10):
    """
    Compares two Python objects with tolerance for numerical values.

    If both inputs are numeric (int, float, complex, or NumPy numbers),
    the function uses `np.isclose()` to compare them. For all other types, it falls back to
    standard equality comparison (`==`).

    a :First object to compare.
    b :Second object to compare.
    :return: bool
    """
    if isinstance(a, float) and isinstance(b, float):
        return np.isclose(a, b, atol=atol)
    return a == b


class GCProp:
    """
    VeraGrid property, this class must remain immutable
    """
    __slots__ = (
        "_name",
        "_units",
        "_tpe",
        "_definition",
        "_profile_name",
        "_display",
        "_editable",
        "_old_names",
        "_is_color",
        "_is_date",
        "_category",
        "dyn_ref"
    )

    def __init__(self,
                 prop_name: Union[str, None] = None,
                 units: str = "",
                 tpe: Union[GCPROP_TYPES, None] = None,
                 definition: str = "",
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True,
                 old_names: List[str] | Tuple[str, ...] | None = None,
                 is_color: bool = False,
                 is_date: bool = False,
                 key: Union[str, None] = None,
                 cat: List[PrpCat] | None = None,
                 dyn_ref: ParamPowerFlowReferenceType | None = None,):
        """
        VeraGrid property
        :param prop_name:
        :param units: units of the property
        :param tpe: data type [Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]]
        :param definition: Definition of the property
        :param profile_name: name of the associated profile property
        :param display: Display the property in the GUI
        :param editable: Is this editable?
        :param is_color: Is this a color? i.e. the tpe is str, but it represents a color
        :param is_date: Is this a date? i.e. the tpe is int but represents a date
        :param key: Property key
        :param cat: Property categories
        :param dyn_ref: Property dynamic reference
        """

        if prop_name is None:
            if key is None:
                raise ValueError("Either 'prop_name' or 'key' must be provided.")
            else:
                self._name = key
        else:
            self._name = prop_name
        if tpe is None:
            raise ValueError("The 'tpe' argument must be provided.")
        else:
            pass
        self._units: str = units
        self._tpe: GCPROP_TYPES = tpe
        self._definition: str = definition
        self._profile_name: str = profile_name
        self._display: bool = display
        self._editable: bool = editable
        self._is_color: bool = is_color
        self._is_date: bool = is_date
        self.dyn_ref = dyn_ref

        self._old_names: Tuple[str, ...] = tuple() if old_names is None else tuple(old_names)

        self._category: List[PrpCat] = [PrpCat.All] if cat is None else cat

    @property
    def name(self) -> str:
        """
        Property name.
        :return: str
        """
        return self._name

    @property
    def units(self) -> str:
        """
        Property units.
        :return: str
        """
        return self._units

    @property
    def tpe(self) -> GCPROP_TYPES:
        """
        Property type.
        :return: GCPROP_TYPES
        """
        return self._tpe

    @property
    def definition(self) -> str:
        """
        Property definition.
        :return: str
        """
        return self._definition

    @property
    def profile_name(self) -> str:
        """
        Linked profile name.
        :return: str
        """
        return self._profile_name

    @property
    def display(self) -> bool:
        """
        Display flag.
        :return: bool
        """
        return self._display

    @property
    def editable(self) -> bool:
        """
        Editable flag.
        :return: bool
        """
        return self._editable

    @property
    def old_names(self) -> Tuple[str, ...]:
        """
        Compatibility aliases.
        :return: Tuple[str, ...]
        """
        return self._old_names

    @property
    def is_color(self) -> bool:
        """
        Color flag.
        :return: bool
        """
        return self._is_color

    @property
    def is_date(self) -> bool:
        """
        Date flag.
        :return: bool
        """
        return self._is_date

    @property
    def category(self) -> List[PrpCat] :
        """
        List of categories
        :return: List[PropertyCategory]
        """
        return self._category

    def has_profile(self) -> bool:
        """
        Check if this property has an associated profile
        :return:
        """
        return self.profile_name != ''

    def get_class_name(self) -> str:
        """
        Convert the class name to a string
        :return: str
        """
        tpe_name = str(self.tpe)
        if '.' in tpe_name:
            chunks = tpe_name.split('.')
            return (chunks[-1]
                    .replace("'", "")
                    .replace("<", "")
                    .replace(">", "").strip())
        else:
            return (tpe_name
                    .replace('class', '')
                    .replace("'", "")
                    .replace("<", "")
                    .replace(">", "").strip())

    def get_dict(self) -> Dict[str, str | bool]:
        """
        Get the values of this property as a dictionary
        :return: Dict[name, value]
        """
        return {'name': self.name,
                'class_type': self.get_class_name(),
                'unit': self.units,
                'mandatory': False,
                'max_chars': '',
                "descriptions": self.definition,
                "has_profile": self.has_profile(),
                'comment': ''}

    def __str__(self):
        return self.name

    def __repr__(self):
        return "prop:" + self.name


def get_action_symbol(action: ActionType):
    """

    :param action:
    :return:
    """
    if action == ActionType.NoAction:
        return "."
    elif action == ActionType.Add:
        return "+"
    elif action == ActionType.Delete:
        return "-"
    elif action == ActionType.Modify:
        return "~"
    else:
        return ""


def get_at(snapshot_val: GCPROP_TYPES | float | int,
           profile: AnyProfile,
           t: int | None) -> GCPROP_TYPES | float | int:
    """
    Get a GCPROP_TYPES value from a snapshot or a profile
    :param snapshot_val: snapshot value
    :param profile: Associated profile
    :param t: time index (None for snapshot)
    :return: Value
    """
    if t is None:
        return snapshot_val
    else:
        # A size-zero profile is not time-series data. Indexing it would silently replace
        # the snapshot the user set, so fall back to the snapshot until a real profile
        # of matching length exists.
        if not profile.is_initialized:
            return snapshot_val
        else:
            profile_size: int = profile.size()
            if profile_size == 0:
                return snapshot_val
            else:
                if t < 0 or t >= profile_size:
                    return snapshot_val
                else:
                    return profile[t]



class EditableDeviceMeta(type):
    """
    Metaclass that pre-builds inherited class schema declarations.
    """

    def __new__(mcs, name, bases, namespace):
        """
        Build a new class and aggregate property declarations from base to child.
        :param name: Class name
        :param bases: Base classes
        :param namespace: Class namespace
        :return: New class
        """
        cls = super().__new__(mcs, name, bases, namespace)

        aggregated_declarations: List[GCProp] = list()
        for base in bases:
            base_declarations: Tuple[GCProp, ...] = getattr(base, "CLASS_PROPERTY_DECLARATIONS", tuple())
            for declaration in base_declarations:
                aggregated_declarations.append(declaration)

        local_declarations: Tuple[GCProp, ...] = namespace.get("LOCAL_PROPERTY_DECLARATIONS", tuple())
        for declaration in local_declarations:
            aggregated_declarations.append(declaration)

        cls.CLASS_PROPERTY_DECLARATIONS = tuple(aggregated_declarations)

        class_property_list: List[GCProp] = list()
        class_registered_properties: Dict[str, GCProp] = dict()
        class_non_editable_properties: List[str] = list()
        class_properties_with_profile: Dict[str, str] = dict()

        for declaration in cls.CLASS_PROPERTY_DECLARATIONS:
            prop: GCProp = declaration
            class_registered_properties[prop.name] = prop
            class_property_list.append(prop)

            if prop.profile_name != '':
                class_properties_with_profile[prop.name] = prop.profile_name
            else:
                pass

            if prop.editable:
                pass
            else:
                class_non_editable_properties.append(prop.name)

        cls.CLASS_PROPERTY_LIST = tuple(class_property_list)
        cls.CLASS_REGISTERED_PROPERTIES = class_registered_properties
        cls.CLASS_NON_EDITABLE_PROPERTIES = tuple(class_non_editable_properties)
        cls.CLASS_PROPERTIES_WITH_PROFILE = class_properties_with_profile

        return cls


class PropertyChanges:
    __slots__ = ("__property_merge_selections",)

    def __init__(self):
        # This per-instance map stores merge toggles to avoid mutating shared schema objects.
        self.__property_merge_selections: Dict[str, bool] = dict()

    def set(self, property_name: str, selected: bool) -> None:
        """
        Set merge-selection state for one property in this instance.
        :param property_name: Property name
        :param selected: Should this property be merged
        :return: None
        """
        self.__property_merge_selections[property_name] = selected

    def get(self, property_name: str) -> bool:
        """
        Query merge-selection state for one property in this instance.
        :param property_name: Property name
        :return: True if selected for merge
        """

        # If the property is not in the dictionary of properties to merge, it should not be modified.
        # Otherwise, check what should be the behaviour.

        return self.__property_merge_selections.get(property_name, False)

    def to_dict(self):
        return dict(self.__property_merge_selections)

    def parse(self, data: Dict[str, bool]):
        if isinstance(data, dict):
            self.__property_merge_selections = data

    def __eq__(self, other):
        return self.__property_merge_selections == other.__property_merge_selections

    def copy(self):
        elm = PropertyChanges()
        elm.__property_merge_selections = self.__property_merge_selections.copy()
        return elm


class EditableDevice(metaclass=EditableDeviceMeta):
    """
    This is the main device class from which all inherit
    """
    __slots__ = (
        '_idtag',
        '_name',
        '_code',
        '_rdfid',
        'device_type',
        'comment',
        'action',
        'selected_to_merge',
        'diff_changes',
        '__auto_update_enabled',
    )
    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='idtag',
            units='',
            tpe=str,
            definition='Unique ID',
            editable=False,
            cat=[PrpCat.MT],
        ),
        GCProp(
            prop_name='name',
            units='',
            tpe=str,
            definition='Name of the device.',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='code',
            units='',
            tpe=str,
            definition='Secondary ID',
            cat=[PrpCat.MT],
        ),
        GCProp(
            prop_name='rdfid',
            units='',
            tpe=str,
            definition='RDF ID for further compatibility',
            cat=[PrpCat.MT],
        ),
        GCProp(
            prop_name='action',
            units='',
            tpe=ActionType,
            definition='Object action to perform.\nOnly used for model merging.',
            display=False,
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='selected_to_merge',
            units='',
            tpe=bool,
            definition='Whether this object should be applied during diff merge.',
            display=False,
            editable=False,
            cat=[PrpCat.MT],
        ),
        GCProp(
            prop_name='comment',
            units='',
            tpe=str,
            definition='User comment',
            cat=[PrpCat.MT],
        ),
        GCProp(
            prop_name='diff_changes',
            units='',
            tpe=SubObjectType.MergeInformation,
            display=False,
            editable=False,
            cat=[PrpCat.MT],
        )
    )
    CLASS_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = tuple()
    CLASS_PROPERTY_LIST: Tuple[GCProp, ...] = tuple()
    CLASS_REGISTERED_PROPERTIES: Dict[str, GCProp] = dict()
    CLASS_NON_EDITABLE_PROPERTIES: Tuple[str, ...] = tuple()
    CLASS_PROPERTIES_WITH_PROFILE: Dict[str, str] = dict()

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 device_type: DeviceType,
                 comment: str = "",
                 rdfid: str = ""):
        """
        Class to generalize any editable device
        :param name: Asset's name
        :param idtag: unique ID, if not provided it is generated
        :param code: alternative code to identify this object in other databases (i.e. psse number tec...)
        :param device_type: DeviceType instance
        :param rdfid: RDFID code optional
        """

        self._idtag = parse_idtag(val=idtag)

        if isinstance(name, str):
            self._name: str = name
        else:
            self._name: str = ""

        self._code: str = code

        self._rdfid = rdfid

        self.device_type: DeviceType = device_type

        self.comment: str = comment

        self.action: ActionType = ActionType.NoAction
        self.selected_to_merge = True

        self.diff_changes = PropertyChanges()

        # some devices have an auto update of a property when another property changes
        # (i.e. Line's R, X, B when the length changes) this controls that behaviour and disables it during loading
        self.__auto_update_enabled = True

    @property
    def property_list(self) -> Tuple[GCProp, ...]:
        """
        Class-level property list exposed as read-only instance view.
        :return: Tuple of GCProp
        """
        self_cls: type = type(self)
        return self_cls.CLASS_PROPERTY_LIST

    @property
    def registered_properties(self) -> Dict[str, GCProp]:
        """
        Class-level registered properties exposed as read-only instance view.
        :return: Dict[str, GCProp]
        """
        self_cls: type = type(self)
        return self_cls.CLASS_REGISTERED_PROPERTIES

    @property
    def non_editable_properties(self) -> Tuple[str, ...]:
        """
        Class-level non-editable property names exposed as read-only instance view.
        :return: Tuple[str, ...]
        """
        self_cls: type = type(self)
        return self_cls.CLASS_NON_EDITABLE_PROPERTIES

    @property
    def properties_with_profile(self) -> Dict[str, str]:
        """
        Class-level property/profile map exposed as read-only instance view.
        :return: Dict[str, str]
        """
        self_cls: type = type(self)
        return self_cls.CLASS_PROPERTIES_WITH_PROFILE

    def set_diff_change(self, property_name: str, selected: bool) -> None:
        """
        Set merge-selection state for one property in this instance.
        :param property_name: Property name
        :param selected: Should this property be merged
        :return: None
        """
        self.diff_changes.set(property_name, selected)

    def get_diff_change_selected(self, property_name: str) -> bool:
        """
        Query merge-selection state for one property in this instance.
        :param property_name: Property name
        :return: True if selected for merge
        """

        return self.diff_changes.get(property_name)

    def get_all_diff_changes_dict(self) -> Dict[str, bool]:
        """
        Get the dictionary of all diff changes
        :return:
        """
        return self.diff_changes.to_dict()

    def iter_properties_selected_to_merge(self):
        """
        Iterate over properties selected to be merged for this instance.
        :return: Generator[GCProp, None, None]
        """
        for prop in self.property_list:
            if self.get_diff_change_selected(property_name=prop.name):
                yield prop
            else:
                pass

    @property
    def auto_update_enabled(self):
        """

        :return:
        """
        return self.__auto_update_enabled

    def enable_auto_updates(self):
        """

        :return:
        """
        self.__auto_update_enabled = True

    def disable_auto_updates(self):
        """

        :return:
        """
        self.__auto_update_enabled = False

    def get_uuid(self) -> str:
        """
        If the idtag property looks like a UUID, it adds the dashes
        :return: UUID with dashes
        """
        if isinstance(self._idtag, str):
            if len(self.idtag) == 32:
                return str(uuid.UUID(self.idtag))
            else:
                raise Exception("The idtag is not a proper UUID")
        else:
            raise Exception("The idtag is not a proper UUID string")

    def __str__(self) -> str:
        """
        Name of the object
        :return: string
        """
        return str(self.name)

    def __repr__(self) -> str:
        return get_action_symbol(self.action) + "::" + self.idtag + '::' + self.name

    def __hash__(self) -> int:
        # alternatively, return hash(repr(self))
        # return int(self.idtag, 16)  # hex string to int
        return hash(repr(self))

    def __lt__(self, other) -> bool:
        return self.__hash__() < other.__hash__()

    def __eq__(self, other) -> bool:
        if hasattr(other, 'idtag'):
            return self.idtag == other.idtag
        else:
            return False

    @property
    def idtag(self) -> str:
        """
        idtag getter
        :return: string, hopefully an UUIDv4
        """
        return self._idtag

    @idtag.setter
    def idtag(self, val: Union[str, None]):
        """
        idtag setter
        :param val: any string or None
        """
        self._idtag = parse_idtag(val)

    @property
    def code(self) -> str:
        """
        code getter
        :return: string, hopefully an UUIDv4
        """
        return self._code

    @code.setter
    def code(self, val: Union[str, None]):
        """
        code setter
        :param val: any string or None
        """
        self._code = val

    @property
    def rdfid(self) -> str:
        return self._rdfid

    @rdfid.setter
    def rdfid(self, val: str):
        self._rdfid = val

    def flatten_idtag(self):
        """
        Remove useless underscore (_) and dash (-)
        :return:
        """
        self._idtag = self._idtag.replace('_', '').replace('-', '')

    @property
    def type_name(self) -> str:
        """
        Name of the device type
        :return: name of the type (str)
        """
        return self.device_type.value

    def get_rdfid(self) -> str:
        """
        Convert the idtag to RDFID
        :return: UUID converted to RDFID
        """
        if len(self._rdfid) == 0:
            lenghts = [8, 4, 4, 4, 12]
            chunks = list()
            s = 0
            for length_ in lenghts:
                a = self.idtag[s:s + length_]
                chunks.append(a)
                s += length_
            return "-".join(chunks)
        else:
            return self.rdfid

    def register(self,
                 key: str,
                 tpe: GCPROP_TYPES,
                 units: str = "",
                 definition: str = "",
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True,
                 old_names: List[str] = None,
                 is_color: bool = False,
                 is_date: bool = False):
        """
        Runtime registration is intentionally disabled.
        :param key: key (this is the displayed name)
        :param units: string with the declared units
        :param tpe: type of the attribute [Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]]
        :param definition: Definition of the property
        :param profile_name: name of the profile property (if any)
        :param display: display this property?
        :param editable: is this editable?
        :param old_names: List of old names
        :param is_color: is this a color property?
        :param is_date: Is this a date property?
        """
        raise RuntimeError(
            "Runtime property registration is disabled. "
            "Declare properties in LOCAL_PROPERTY_DECLARATIONS."
        )

    def get_property_name_replacements_dict(self) -> Dict[str, str]:
        """
        Get dictionary of old names related to their current name
        This is useful for retro compatibility
        :return: {old_name: new_name} dict
        """
        data = dict()
        for key, prop in self.registered_properties.items():

            for old_name in prop.old_names:
                data[old_name] = prop.name

        return data

    def generate_uuid(self):
        """
        Generate new UUID for the idtag property
        """
        self.idtag = uuid.uuid4().hex

    @property
    def name(self) -> str:
        """
        Name of the object
        """
        return self._name

    @name.setter
    def name(self, val: str):
        if isinstance(val, str):
            self._name = val
        else:
            print(f"Trying {self.device_type.value} to set name with {str(val)}")

    def get_save_data(self) -> List[Union[str, float, int, bool, object]]:
        """
        Return the data that matches the edit_headers
        :return: list with data
        """

        data = list()
        for name, properties in self.registered_properties.items():
            obj = getattr(self, name)

            if obj is not None:
                if properties.tpe in [str, float, int, bool]:
                    data.append(obj)

                else:
                    # if the object is not of a primary type, get the idtag instead
                    if hasattr(obj, 'idtag'):
                        data.append(obj.idtag)
                    else:
                        # some data types might not have the idtag, ten just use the str method
                        data.append(str(obj))
            else:
                data.append(None)

        return data

    def get_headers(self) -> List[AnyStr]:
        """
        Return a list of headers
        """
        return list(self.registered_properties.keys())

    def get_number_of_properties(self) -> int:
        """
        Return the number of registered properties
        :return: int
        """
        return len(self.property_list)

    def get_properties_containing_object(self, obj: "EditableDevice") -> Tuple[List[GCProp], List[int]]:
        """
        Return the list of properties that contain a certain object
        :param obj:
        :return: list of GCProp, list of indices
        """
        props = list()
        indices = list()
        for i, prop in enumerate(self.property_list):
            if getattr(self, prop.name) == obj:
                props.append(prop)
                indices.append(i)

        return props, indices

    def get_association_properties(self) -> Tuple[List[GCProp], List[int]]:
        """
        Return the list of properties that contain associate another type
        :return: list of GCProp, list of indices
        """
        props = list()
        indices = list()
        for i, prop in enumerate(self.property_list):
            if prop.tpe == SubObjectType.Associations:
                props.append(prop)
                indices.append(i)

        return props, indices

    def get_snapshot_value(self, prop: GCProp) -> Any:
        """
        Return the stored object value from the property index
        :param prop: GCProp
        :return: Whatever value is there
        """
        return getattr(self, prop.name)

    def set_snapshot_value(self, property_name, value: Any) -> None:
        """
        Set the value of a snapshot property
        :param property_name: name of the property
        :param value: Any
        """
        # set the snapshot value whatever it is
        setattr(self, property_name, value)

    def get_snapshot_value_by_name(self, name) -> Any:
        """
        Return the stored object value from the property index
        :param name: snapshot property name
        :return: Whatever value is there
        """
        return getattr(self, name)

    def get_property_value(self, prop: GCProp, t_idx: Union[None, int]) -> Any:
        """
        Return the stored object value from the property index
        :param prop: GCProp
        :param t_idx: Time index, None for Snapshot values
        :return: Whatever value is there
        """

        if t_idx is None:
            # pick the snapshot value whatever it is
            return self.get_snapshot_value(prop=prop)
        else:
            if prop.has_profile():
                # the property has a profile, return the value at t_idx (or the snapshot
                # when the profile was never filled)
                return get_at(self.get_snapshot_value(prop=prop),
                              self.get_profile_by_prop(prop=prop),
                              t_idx)
            else:
                # the property has no profile, just return it
                return self.get_snapshot_value(prop=prop)

    def get_property_by_idx(self, property_idx: int) -> GCProp:
        """
        Return the stored object value from the property index
        :param property_idx: Property index
        :return: GCProp
        """
        return self.property_list[property_idx]

    def get_property_by_name(self, prop_name: str) -> GCProp:
        """

        :param prop_name:
        :return:
        """
        return self.registered_properties[prop_name]

    def get_property_value_by_idx(self, property_idx: int, t_idx: Union[None, int]) -> Any:
        """
        Return the stored object value from the property index
        :param property_idx: Property index
        :param t_idx: Time index, None for Snapshot values
        :return: Whatever value is there
        """
        prop = self.property_list[property_idx]
        return self.get_property_value(prop=prop, t_idx=t_idx)

    def set_profile(self, prop: GCProp, arr: Union[AnyProfile, np.ndarray]) -> None:
        """
        Set the profile from eithr an array or an actual profile object
        :param prop: GCProp instance
        :param arr: Profile object or numpy array object
        """
        if isinstance(arr, np.ndarray):
            profile: AnyProfile = getattr(self, prop.profile_name)
            profile.set(arr)
        elif isinstance(arr, PROFILE_INSTANCE_TYPES):
            setattr(self, prop.profile_name, arr)
        else:
            raise Exception("profile type not supported")

    def set_profile_array(self, magnitude, arr: Union[AnyProfile, np.ndarray]) -> None:
        """
        Set the profile from either an array or an actual profile object
        :param magnitude: snapshot magnitude
        :param arr: Profile object or numpy array object
        """
        if isinstance(arr, np.ndarray):
            prof_name = self.properties_with_profile[magnitude]
            profile: AnyProfile = getattr(self, prof_name)
            profile.set(arr)
        else:
            raise Exception("profile type not supported")

    def set_property_value(self, prop: GCProp, value: Any, t_idx: Union[None, int]):
        """
        Return the stored object value from the property index
        :param prop: GCProp
        :param value: any value is there
        :param t_idx: Time index, None for Snapshot values
        :return: Whatever value is there
        """

        if t_idx is None:
            # set the snapshot value whatever it is
            setattr(self, prop.name, value)
        else:
            if prop.has_profile():
                # the property has a profile, get it and set the t_idx value
                getattr(self, prop.profile_name)[t_idx] = value
            else:
                # the property has no profile, just return it
                setattr(self, prop.name, value)

    def get_value(self, prop: GCProp, t_idx: Union[None, int]) -> Any:
        """
        Return value regardless of the property index
        :param prop: GCProp
        :param t_idx: time index
        :return: Some value
        """
        if t_idx is None:
            # return the normal property
            return getattr(self, prop.name)
        else:
            if prop.has_profile():
                # get the profile value, falling back to the snapshot if the profile is empty
                return get_at(getattr(self, prop.name),
                              getattr(self, prop.profile_name),
                              t_idx)
            else:
                # return the normal property
                return getattr(self, prop.name)

    def is_property_editable(self, prop: GCProp) -> bool:
        """Return instance-specific GUI editability without mutating shared metadata."""
        return prop.editable

    def set_value(self, prop: GCProp, t_idx: Union[None, int], value: Any) -> None:
        """
        Return value regardless of the property index
        :param prop: GCProp
        :param t_idx: time index
        :param value: Some value
        """
        if t_idx is None:
            # return the normal property
            setattr(self, prop.name, value)
        else:
            if prop.has_profile():
                # get the profile value
                prof: AnyProfile = getattr(self, prop.profile_name)
                prof[t_idx] = value  # assign the value
            else:
                # return the normal property
                setattr(self, prop.name, value)

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
        :param index: pandas time index
        """
        for magnitude, values in self.properties_with_profile.items():
            self.create_profile(magnitude=magnitude, index=index)

    def resize_profiles(self, index, time_frame: TimeFrame):
        """
        Resize the profiles in this object
        :param index: pandas time index
        :param time_frame: Time frame to use (Short term, Long term)
        """
        n1 = index.shape[0]
        for magnitude, values in self.properties_with_profile.items():
            if values[1] == time_frame:
                # get the current profile
                val = getattr(self, self.properties_with_profile[magnitude]).values[:, 0]
                n2 = val.shape[0]

                if n1 > n2:
                    # extend the values
                    extension = np.ones(n1 - n2, dtype=val.dtype) * getattr(self, magnitude)  # copy the current value
                    val2 = np.r_[val, extension]
                else:
                    # curtail the values
                    val2 = val[:n1]

                # set the profile variable associated with the magnitude
                setattr(self, self.properties_with_profile[magnitude], val2)

    def create_profile(self, magnitude, index: pd.DatetimeIndex):
        """
        Create power profile based on index
        :param magnitude: name of the property
        :param index: pandas time index
        """
        # get the value of the magnitude
        snapshot_value = getattr(self, magnitude)

        # get the already existing profile
        prof: AnyProfile = self.get_profile(magnitude=magnitude)

        if prof is None:
            print("The profile is none, this is a bug!")
        elif index is pd.NaT:
            pass
        else:
            prof.create_sparse(size=len(index), default_value=snapshot_value)

        # set the profile variable associated with the magnitude
        # setattr(self, self.properties_with_profile[magnitude], prof)

    def ensure_profiles_exist(self, index: pd.DatetimeIndex, set_profile_default_as_snapshot: bool = False):
        """
        It might be that when loading the VeraGrid Model has properties that the file has not.
        Those properties must be initialized as well
        :param index: Time series index (timestamps)
        :param set_profile_default_as_snapshot: set the bool default profile value as the snapshot
        """
        if index is None or index is pd.NaT:
            raise Exception("ensure_profiles_exist: No index provided")
        else:
            for magnitude, prof_attr in self.properties_with_profile.items():

                # get the profile
                profile = getattr(self, prof_attr)

                if profile.is_initialized:
                    if profile.size() == 0:
                        # Size zero means the profile was marked initialized on construction
                        # or file load but never filled. Recreate from the snapshot.
                        self.create_profile(magnitude=magnitude, index=index)
                    elif profile.size() != len(index):
                        # the length of the profile is different from the length of the master profile
                        profile.resize(n=len(index))
                    else:
                        # all ok
                        pass
                else:
                    # there is no profile, create a new one with the snapshot values
                    self.create_profile(magnitude=magnitude, index=index)

                if set_profile_default_as_snapshot:
                    prop = self.registered_properties[magnitude]
                    val = getattr(self, magnitude)
                    profile.default_value = val

    def delete_profiles(self):
        """
        Delete the object profiles (set all to None)
        """
        for magnitude in self.properties_with_profile.keys():
            self.get_profile(magnitude=magnitude).clear()

    def resample_profiles(self, indices: IntVec):
        """
        re-sample the object profiles (set all to None)
        """
        for magnitude in self.properties_with_profile.keys():
            prof = self.get_profile(magnitude=magnitude)
            prof.resample(indices=indices)

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index (integer)
        """
        for property_name, profile_name in self.properties_with_profile.items():
            profile: AnyProfile = getattr(self, profile_name)
            setattr(self, property_name, profile[t])

    def get_profile(self, magnitude: str) -> Union[AnyProfile, None]:
        """
        Get the profile of a property name
        :param magnitude: name of the property
        :return: Profile object
        """

        # try to get the profile name
        profile_name = self.properties_with_profile.get(magnitude, None)

        if profile_name is None:
            return None
        else:
            return getattr(self, profile_name)

    def get_profile_by_prop(self, prop: GCProp) -> Union[AnyProfile, None]:
        """
        Get the profile of a property name
        :param prop: GCProp
        :return: Profile object
        """
        return getattr(self, prop.profile_name)

    def copy(self, forced_new_idtag: bool = False):
        """
        Create a deep copy of this object
        """

        # Create a new instance of the object
        tpe = self.__class__
        new_obj: EditableDevice

        try:
            new_obj = tpe(name=self.name,
                          idtag=uuid.uuid4().hex if forced_new_idtag else self.idtag,
                          code=self.code,
                          device_type=self.device_type)
            new_obj.disable_auto_updates()

        except TypeError:
            new_obj: EditableDevice = tpe()
            new_obj.disable_auto_updates()

        # deep-copy each property
        for prop_name, gc_prop in self.registered_properties.items():
            value = getattr(self, prop_name)

            if isinstance(gc_prop.tpe, SubObjectType):
                # This is a complex object, make a deep copy
                setattr(new_obj, prop_name, value.copy())
            else:
                setattr(new_obj, prop_name, value)

            if gc_prop.has_profile():
                my_prof = getattr(self, gc_prop.profile_name)
                setattr(new_obj, gc_prop.profile_name, my_prof.copy())

        if forced_new_idtag:
            new_obj.idtag = uuid.uuid4().hex

        new_obj.enable_auto_updates()
        return new_obj

    @staticmethod
    def rgb2hex(r: int, g: int, b: int) -> str:
        """
        Convert R, G, B to hexadecimal tuple
        :param r: Red amount (0, 255)
        :param g: Green amount (0, 255)
        :param b: Blue amount (0, 255)
        :return: Hexadecimal string
        """
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    @staticmethod
    def hex2rgb(hexcode: int) -> Tuple[int, ...]:
        """
        Convert hexadecimal string to rgb tuple
        :param hexcode: hexadecimal string
        :return: (R, G, B)
        """
        return tuple(map(ord, hexcode[1:].decode('hex')))

    def rnd_color(self) -> str:
        """
        Generate random colour
        :return: hex string
        """
        r = random.randint(0, 128)
        g = random.randint(0, 128)
        b = random.randint(0, 128)
        return self.rgb2hex(r, g, b)

    def new_idtag(self):
        """
        Generate a new IdTag
        """
        self._idtag = uuid.uuid4().hex  # generate a proper UUIDv4 string

    def replace_objects(self, old_object: Any, new_obj: Any, logger: Logger) -> None:
        """
        Replace object in this objects' properties
        :param old_object: object to replace
        :param new_obj: object used to replace the old one
        :param logger: Logger to record what happened
        """
        for key, prop in self.registered_properties.items():

            obj = getattr(self, prop.name)

            if obj == old_object:
                setattr(self, prop.name, new_obj)
                logger.add_info(msg="Replaced object",
                                device=self.idtag + ":" + self.name,
                                device_property=prop.name,
                                value=str(new_obj))

    def rebind_device_references(self,
                                 objects_by_idtag: Dict[str, Any],
                                 props: List[GCProp] | None = None) -> None:
        """
        Rebind direct device-pointer properties to equivalent objects from a target lookup.

        This is useful when an object has been copied from another circuit and its pointer
        properties still reference objects from that old circuit instance.

        :param objects_by_idtag: idtag -> target object lookup
        :param props: Optional subset of properties to process. If omitted, all registered
                      properties are considered.
        """
        selected_props = self.registered_properties.values() if props is None else props

        for prop in selected_props:
            if isinstance(prop.tpe, DeviceType):
                val = self.get_property_value(prop=prop, t_idx=None)
                if val is not None:
                    if hasattr(val, "idtag"):
                        pointed = objects_by_idtag.get(val.idtag, None)
                    elif isinstance(val, str):
                        pointed = objects_by_idtag.get(val, None)
                    else:
                        pointed = None

                    if pointed is not None:
                        self.set_property_value(prop=prop, value=pointed, t_idx=None)
            else:
                val = self.get_property_value(prop=prop, t_idx=None)
                rebind = getattr(val, "rebind_device_references", None)
                if callable(rebind):
                    rebind(objects_by_idtag=objects_by_idtag)

            if prop.has_profile():
                profile = self.get_profile_by_prop(prop=prop)
                rebind = getattr(profile, "rebind_device_references", None)
                if callable(rebind):
                    rebind(objects_by_idtag=objects_by_idtag)

    def compare(self, other: Any,
                logger: Logger,
                detailed_profile_comparison=False,
                nt=0) -> Tuple[ActionType, List[GCProp]]:
        """
        Compare two objects
        :param other: other device
        :param logger: Logger
        :param detailed_profile_comparison: Compare profiles?
        :param nt: number of time steps (get it from the circuit)
        :return: ActionType
        """
        action = ActionType.NoAction
        properties_changed: List[GCProp] = list()

        # check differences
        for prop_name, prop in self.registered_properties.items():

            # compare the snapshot values
            v1 = self.get_property_value(prop=prop, t_idx=None)
            v2 = other.get_property_value(prop=prop, t_idx=None)

            if not smart_compare(v1, v2):
                logger.add_info(msg="Different snapshot values",
                                device_class=self.device_type.value,
                                device_property=prop.name,
                                value=v2,
                                expected_value=v1)
                action = ActionType.Modify
                properties_changed.append(prop)

            if prop.has_profile():
                p1 = self.get_profile_by_prop(prop=prop)
                p2 = other.get_profile_by_prop(prop=prop)

                if p1 != p2:
                    logger.add_info(msg="Different profile values",
                                    device_class=self.device_type.value,
                                    device_property=prop.name,
                                    object_value=p2,
                                    expected_object_value=p1)
                    action = ActionType.Modify
                    if prop not in properties_changed:
                        properties_changed.append(prop)

                if detailed_profile_comparison:
                    for t_idx in range(nt):

                        v1 = p1[t_idx]
                        v2 = p2[t_idx]

                        if not smart_compare(v1, v2):
                            logger.add_info(msg="Different time series values",
                                            device_class=self.device_type.value,
                                            device_property=prop.name,
                                            device=str(self),
                                            value=v2,
                                            expected_value=v1)
                            action = ActionType.Modify
                            if prop not in properties_changed:
                                properties_changed.append(prop)

                        v1b = self.get_property_value(prop=prop, t_idx=t_idx)
                        v2b = other.get_property_value(prop=prop, t_idx=t_idx)

                        if not smart_compare(v1, v1b):
                            logger.add_info(
                                msg="Profile values differ with different getter methods!",
                                device_class=self.device_type.value,
                                device_property=prop.name,
                                device=str(self),
                                value=v1b,
                                expected_value=v1)
                            action = ActionType.Modify

                        if not smart_compare(v2, v2b):
                            logger.add_info(
                                msg="Profile getting values differ with different getter methods!",
                                device_class=self.device_type.value,
                                device_property=prop.name,
                                device=str(self),
                                value=v1b,
                                expected_value=v1)
                            action = ActionType.Modify

        return action, properties_changed
