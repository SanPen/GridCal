# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Union, Tuple
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, DeviceType, GCProp
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Devices.Events.contingency_group import ContingencyGroup
from VeraGridEngine.enumerations import PrpCat, RemedialActionPropertyEnum


class RemedialActionGroup(EditableDevice):
    """
    Group remedial actions and describe the condition that makes them eligible.

    The contingency reference is optional. A missing reference means that the
    condition applies to the base scenario. Condition evaluation is deliberately
    solver-independent: simulation tools or external scripts provide the observed
    per-unit voltage or loading after obtaining it from their own result object.
    The selected property identifies the limit stored by the monitored device.
    """
    __slots__ = (
        'category',
        '_conn_group',
        '_prev_ra',
        '_monitored_device',
        '_property_type',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='category',
            units='',
            tpe=str,
            definition='Some tag to category the contingency group',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='conn_group',
            units='',
            tpe=DeviceType.ContingencyGroupDevice,
            definition='Optional contingency scenario associated with this group',
            cat=[PrpCat.OPF, PrpCat.TP],
        ),
        GCProp(
            prop_name='prev_ra',
            units='',
            tpe=DeviceType.RemedialActionGroupDevice,
            definition='Optional remedial action group that must precede this group',
            cat=[PrpCat.OPF, PrpCat.TP],
            reflexive=True
        ),
        GCProp(
            prop_name='monitored_device',
            units='',
            tpe=DeviceType.PhysicalDeviceType,
            definition='Physical model element whose result is monitored',
            cat=[PrpCat.OPF, PrpCat.TP],
        ),
        GCProp(
            prop_name='property_type',
            units='',
            tpe=RemedialActionPropertyEnum,
            definition='Limit of the monitored device used by the condition',
            cat=[PrpCat.OPF, PrpCat.TP],
        ),
    )

    def __init__(self,
                 idtag: Union[str, None] = None,
                 name: str = "RemedialActionGroup",
                 category: str = '',
                 conn_group: ContingencyGroup | None = None,
                 remedial_action_dependency: RemedialActionGroup | None = None,
                 monitored_device: PhysicalDevice | None = None,
                 property_type: RemedialActionPropertyEnum | None = None) -> None:
        """
        Create a remedial action group.

        :param idtag: Unique identifier
        :param name: Remedial action group name.
        :param category: User-defined category tag.
        :param conn_group: Optional contingency scenario; None denotes the base scenario.
        :param remedial_action_dependency: Optional remedial action group that precedes this group.
        :param monitored_device: Physical model element to monitor.
        :param property_type: Device limit to monitor.
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.RemedialActionGroupDevice)

        self.category: str = category
        self._conn_group: ContingencyGroup | None = None
        self._prev_ra: RemedialActionGroup | None = None
        self._monitored_device: PhysicalDevice | None = None
        self._property_type: RemedialActionPropertyEnum | None = None

        # self.conn_group = conn_group
        # self.parent_ra = remedial_action_dependency
        # self.monitored_device = monitored_device
        # self.property_type = property_type

    @property
    def conn_group(self) -> ContingencyGroup | None:
        """
        Return the optional contingency scenario.

        :return: Contingency group, or None for a base-scenario condition.
        """
        return self._conn_group

    @conn_group.setter
    def conn_group(self, value: ContingencyGroup | None) -> None:
        """
        Set the optional contingency scenario.

        :param value: Contingency group, or None for a base-scenario condition.
        :return: None.
        """
        if value is None or isinstance(value, ContingencyGroup):
            self._conn_group = value
        else:
            raise TypeError('conn_group must be a ContingencyGroup or None')

    @property
    def prev_ra(self) -> RemedialActionGroup | None:
        """
        Return the remedial action group that must precede this group.

        :return: Dependency group, or None when this group starts a cascade.
        """
        return self._prev_ra

    @prev_ra.setter
    def prev_ra(self, value: RemedialActionGroup | None) -> None:
        """
        Set the remedial action group that must precede this group.

        :param value: Dependency group, or None for an independent group.
        :return: None.
        """
        if value is None:
            self._prev_ra = None
        elif not isinstance(value, RemedialActionGroup):
            raise TypeError('remedial_action_dependency must be a RemedialActionGroup or None')
        else:
            dependency: RemedialActionGroup | None = value
            visited_dependencies: set[int] = set()
            while dependency is not None:
                if dependency is self:
                    raise ValueError('A remedial action group cannot depend on itself directly or indirectly')
                else:
                    pass

                dependency_identity: int = id(dependency)
                if dependency_identity in visited_dependencies:
                    raise ValueError('The remedial action dependency chain contains a cycle')
                else:
                    visited_dependencies.add(dependency_identity)
                    dependency = dependency._prev_ra

            self._prev_ra = value

    @property
    def monitored_device(self) -> PhysicalDevice | None:
        """
        Return the monitored physical model element.

        :return: Monitored device, if one is configured.
        """
        return self._monitored_device

    @monitored_device.setter
    def monitored_device(self, value: PhysicalDevice | None) -> None:
        """
        Set the monitored physical model element.

        :param value: Physical device, or None.
        :return: None.
        """
        if value is None or isinstance(value, PhysicalDevice):
            allowed_device_types: Tuple[DeviceType, ...] = (
                DeviceType.BusDevice,
                DeviceType.LineDevice,
                DeviceType.Transformer2WDevice,
            )
            if value is None or value.device_type in allowed_device_types:
                self._monitored_device = value
                allowed_property_types: List[RemedialActionPropertyEnum] = self.get_allowed_property_types()
                if self._property_type is not None and self._property_type not in allowed_property_types:
                    self._property_type = None
                else:
                    pass
            else:
                raise ValueError('monitored_device must be a bus, line, or two-winding transformer')
        else:
            raise TypeError('monitored_device must be a PhysicalDevice or None')

    @staticmethod
    def get_allowed_property_types_for_device(
            monitored_device: PhysicalDevice | None) -> List[RemedialActionPropertyEnum]:
        """
        Return monitorable limits applicable to one physical device.

        :param monitored_device: Physical device whose results will be monitored.
        :return: Applicable result properties in enumeration order.
        """
        if monitored_device is None:
            property_types: List[RemedialActionPropertyEnum] = list()
        else:
            device_type: DeviceType = monitored_device.device_type
            if device_type == DeviceType.BusDevice:
                property_types = [
                    RemedialActionPropertyEnum.Vmin,
                    RemedialActionPropertyEnum.Vmax,
                ]
            elif device_type in (DeviceType.LineDevice, DeviceType.Transformer2WDevice):
                property_types = [
                    RemedialActionPropertyEnum.Loading,
                    RemedialActionPropertyEnum.ContingencyLoading,
                ]
            else:
                property_types = list()
        return property_types

    def get_allowed_property_types(self) -> List[RemedialActionPropertyEnum]:
        """
        Return result properties applicable to the monitored device.

        :return: Applicable result properties in enumeration order.
        """
        property_types: List[RemedialActionPropertyEnum] = self.get_allowed_property_types_for_device(
            monitored_device=self.monitored_device,
        )
        return property_types

    @property
    def property_type(self) -> RemedialActionPropertyEnum | None:
        """
        Return the monitored result property.

        :return: Selected monitored limit.
        """
        return self._property_type

    @property_type.setter
    def property_type(self, value: RemedialActionPropertyEnum | None) -> None:
        """
        Set the monitored result property.

        :param value: Monitored device limit.
        :return: None.
        """
        if value is None:
            self._property_type = None
        elif isinstance(value, RemedialActionPropertyEnum):
            allowed_property_types: List[RemedialActionPropertyEnum] = self.get_allowed_property_types()
            if value in allowed_property_types:
                self._property_type = value
            else:
                raise ValueError('property_type is not applicable to monitored_device')
        else:
            raise TypeError('property_type must be a RemedialActionPropertyEnum member or None')

    def get_limit_value(self) -> float | None:
        """
        Return the selected limit from the monitored device.

        Loading values are per-unit values relative to the normal rating.

        :return: Limit value, or None when no monitored property is selected.
        """
        if self.property_type is None:
            limit_value: float | None = None
        else:
            if self.monitored_device is None:
                raise ValueError('A monitored device is required to resolve the selected limit')
            else:
                if self.property_type == RemedialActionPropertyEnum.Vmin:
                    limit_value = float(self.monitored_device.get_snapshot_value_by_name('Vmin'))
                elif self.property_type == RemedialActionPropertyEnum.Vmax:
                    limit_value = float(self.monitored_device.get_snapshot_value_by_name('Vmax'))
                elif self.property_type == RemedialActionPropertyEnum.Loading:
                    limit_value = 1.0
                elif self.property_type == RemedialActionPropertyEnum.ContingencyLoading:
                    limit_value = float(self.monitored_device.get_snapshot_value_by_name('contingency_factor'))
                else:
                    raise ValueError('Unsupported remedial action property')
        return limit_value

    def is_condition_met(self, observed_value: float | complex) -> bool:
        """
        Check whether an observed value violates the selected device limit.

        Complex power-flow values are evaluated by magnitude.

        :param observed_value: Value obtained from the model or a simulation result.
        :return: True when the group is unconditional or the value violates its limit.
        """
        if self.property_type is None:
            condition_met: bool = True
        else:
            limit_value: float | None = self.get_limit_value()
            if limit_value is None:
                condition_met = False
            else:
                observed_magnitude: float = abs(observed_value)
                if self.property_type == RemedialActionPropertyEnum.Vmin:
                    condition_met = observed_magnitude < limit_value
                elif self.property_type == RemedialActionPropertyEnum.Vmax:
                    condition_met = observed_magnitude > limit_value
                else:
                    condition_met = observed_magnitude > limit_value

        return condition_met
