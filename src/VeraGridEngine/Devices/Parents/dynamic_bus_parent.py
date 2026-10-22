# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import Any, List, Tuple
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice, GCProp
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import (DeviceType, BuildStatus, SubObjectType, PrpCat)
from enum import Enum


class EmtBusConnectionSide(Enum):
    """
    Enumerate the semantic side by which one EMT model is attached to one bus.

    Connection helpers distinguish single-bus injections from branch terminals
    when mapping bus voltages to device voltage and current references.

    :return: None.
    """
    BUS = "bus"
    FROM = "from"
    TO = "to"


class DynamicBusDevice(PhysicalDevice):
    """
    Parent class for devices with dynamic models
    """
    __slots__ = (
        '_var_factory',
        '_rms_model',
        '_emt_model',
        '_pending_emt_devices',
        "_grid_synchronized_emt_model",
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='rms_model',
            units='',
            tpe=SubObjectType.DaeBlockType,
            definition='RMS dynamic model',
            display=False,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            prop_name='emt_model',
            units='',
            tpe=SubObjectType.DaeBlockType,
            definition='EMT dynamic model',
            display=False,
            cat=[PrpCat.EMT],
        ),
    )

    def __init__(self,
                 name: str,
                 idtag: str | None,
                 code: str,
                 device_type: DeviceType,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param code:
        :param device_type:
        :param build_status:
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type,
                                build_status=build_status)

        self._var_factory: VarFactory | None = None
        self._rms_model: Block = Block()
        self._emt_model: Block = Block()
        self._pending_emt_devices: List[Any] = list()
        self._grid_synchronized_emt_model: Block | None = None

    def set_var_factory(self, val: VarFactory) -> None:
        """
        Store the shared variable factory used by RMS and EMT symbolic blocks.

        :param val: Shared variable factory.
        :return: None.
        """

        if isinstance(val, VarFactory):
            self._var_factory = val
        else:
            raise ValueError(f"VarFactory cannot accept {val}")

    @property
    def rms_model(self) -> Block:
        """
        Get the RMS model
        """
        return self._rms_model

    @rms_model.setter
    def rms_model(self, val: Block) -> None:
        if isinstance(val, Block):
            self._rms_model = val
        else:
            raise ValueError(f"RMS model cannot accept {val}")

    @property
    def emt_model(self) -> Block:
        """
        Get the EMT model
        """
        return self._emt_model

    @emt_model.setter
    def emt_model(self, val: Block) -> None:
        if isinstance(val, Block):
            if val is self._emt_model:
                pass
            else:
                self._grid_synchronized_emt_model = None
            self._emt_model = val
        else:
            raise ValueError(f"EMT model cannot accept {val}")

    def mark_emt_model_grid_synchronized(self) -> None:
        """
        Mark the current EMT shell as managed by grid-topology synchronization.

        :return: None.
        """
        self._grid_synchronized_emt_model = self._emt_model

    def is_emt_model_grid_synchronized(self) -> bool:
        """
        Return whether the current EMT shell is the last grid-managed shell.

        Replacing ``emt_model`` explicitly clears the marker, allowing
        reconciliation to distinguish an external shell contract from one that
        should follow later grid-topology changes.

        :return: ``True`` when the current shell was synchronized from the grid.
        """
        return self._grid_synchronized_emt_model is self._emt_model

    def add_pending_emt_device(self, device: Any) -> None:
        """
        Store one single-bus device whose EMT model must wait for a bus shell.

        :param device: Device waiting for one EMT bus shell.
        :return: None.
        """
        if device in self._pending_emt_devices:
            pass
        else:
            self._pending_emt_devices.append(device)

    def remove_pending_emt_device(self, device: Any) -> None:
        """
        Remove one single-bus device from the pending EMT connection queue.

        :param device: Device that no longer needs deferred EMT bus connection.
        :return: None.
        """
        filtered_devices: List[Any] = list()
        pending_device: Any
        for pending_device in self._pending_emt_devices:
            if pending_device is not device:
                filtered_devices.append(pending_device)
            else:
                pass
        self._pending_emt_devices = filtered_devices

    def get_pending_emt_devices(self) -> List[Any]:
        """
        Return the devices waiting for deferred EMT bus connection.

        :return: Copy of the pending EMT device list.
        """
        return list(self._pending_emt_devices)
