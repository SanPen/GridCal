# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from GridCalEngine.basic_structures import CxVec


class ContinuationPowerFlowInput:
    """

    """
    def __init__(self, Sbase: CxVec, Vbase: CxVec, Starget: CxVec, base_overload_number=0):
        """
        ContinuationPowerFlowInput constructor
        @param Sbase: Initial power array
        @param Vbase: Initial voltage array
        @param Starget: Final power array
        @:param base_overload_number: number of overloads in the base situation
        """
        self.Sbase = Sbase

        self.Starget = Starget

        self.Vbase = Vbase

        self.base_overload_number = base_overload_number

