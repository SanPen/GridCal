# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_non_linear import PhaseTapChangerNonLinear
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class PhaseTapChangerSymmetrical(PhaseTapChangerNonLinear):
	def __init__(self, rdfid='', tpe='PhaseTapChangerSymmetrical'):
		PhaseTapChangerNonLinear.__init__(self, rdfid, tpe)


