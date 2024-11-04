# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.auxiliary_equipment import AuxiliaryEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class Sensor(AuxiliaryEquipment):
	def __init__(self, rdfid='', tpe='Sensor'):
		AuxiliaryEquipment.__init__(self, rdfid, tpe)


