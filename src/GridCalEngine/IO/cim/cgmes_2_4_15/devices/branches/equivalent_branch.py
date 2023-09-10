# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.reactive_capability_curve import \
    ReactiveCapabilityCurve
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.equivalent_equipment import EquivalentEquipment
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class EquivalentBranch(EquivalentEquipment):

    def __init__(self, rdfid, tpe):
        EquivalentEquipment.__init__(self, rdfid, tpe)

        self.negativeR12: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.negativeR21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.negativeX12: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.negativeX21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.positiveR12: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.positiveR21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.positiveX12: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.positiveX21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.r: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.r21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.x: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.x21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.zeroR12: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.zeroR21: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.zeroX12: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.zeroX21: float = 0.0  # [cgmesProfile.EQ.value, ],

        self.register_property(name='negativeR12',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='negativeR21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='negativeX12',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='negativeX21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='positiveR12',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='positiveR21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='positiveX12',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='positiveX21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='zeroR12',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='zeroR21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='zeroX12',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='zeroX21',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])