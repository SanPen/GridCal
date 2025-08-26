# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_switch import DCSwitch
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class DCDisconnector(DCSwitch):
	def __init__(self, rdfid='', tpe='DCDisconnector'):
		DCSwitch.__init__(self, rdfid, tpe)


