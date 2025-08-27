# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import BuildStatus, SwitchGraphicType
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.editable_device import DeviceType


class Switch(BranchParent):
    """
    The **Switch** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **VeraGrid**. A Switch is a devices that cuts or allows the flow.
    """
    __slots__ = (
        'R',
        'X',
        'retained',
        'normal_open',
        'rated_current',
        'graphic_type'
    )

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='Switch',
                 idtag=None,
                 code='',
                 r=1e-20,
                 x=1e-20,
                 rate=1.0,
                 active=True,
                 contingency_factor=1.0,
                 protection_rating_factor: float = 1.4,
                 retained=False,
                 normal_open=False,
                 rated_current=0.0,
                 graphic_type: SwitchGraphicType = SwitchGraphicType.CircuitBreaker):
        """
        Switch device
        :param bus_from: Bus from
        :param bus_to: Bus to
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary ID
        :param r: resistance in p.u.
        :param x: reactance in p.u.
        :param rate: Branch rating (MW)
        :param active: is it active?
        :param contingency_factor: Rating factor in case of contingency
        :param graphic_type: SwitchGraphicType to represent the switch in the schematic
        """
        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              active=active,
                              reducible=not retained,
                              rate=rate,
                              contingency_factor=contingency_factor,
                              protection_rating_factor=protection_rating_factor,
                              contingency_enabled=True,
                              monitor_loading=True,
                              mttf=0.0,
                              mttr=0.0,
                              build_status=BuildStatus.Commissioned,
                              capex=0,
                              opex=0,
                              cost=0,
                              device_type=DeviceType.SwitchDevice)

        # total impedance and admittance in p.u.
        self.R = float(r)
        self.X = float(x)

        # self.is_open = is_open
        self.retained = bool(retained)

        self.normal_open = bool(normal_open)
        self.rated_current = float(rated_current)

        self.graphic_type: SwitchGraphicType = graphic_type

        self.register(key='R', units='pu', tpe=float, definition='Positive-sequence resistance')
        self.register(key='X', units='pu', tpe=float, definition='Positive-sequence reactance')

        # self.register(key='is_open', units="", tpe=bool,
        #               definition='Switch is open', old_names=['open'])
        self.register(key='retained', units="", tpe=bool,
                      definition='Switch is retained')

        self.register(key='normal_open', units="", tpe=bool,
                      definition='Normal position of the switch')
        self.register(key='rated_current', units="kA", tpe=float,
                      definition='Rated current of the switch device.')
        self.register(key='graphic_type', units='', tpe=SwitchGraphicType, definition='Graphic to use in the schematic.')
