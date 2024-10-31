# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sensor import Sensor
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class PostLineSensor(Sensor):
	def __init__(self, rdfid='', tpe='PostLineSensor'):
		Sensor.__init__(self, rdfid, tpe)


