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

import numpy as np
from GridCal.Engine.Simulations.Stochastic.latin_hypercube_sampling import lhs
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import CDF, CxVec, CxMat


class StochasticPowerFlowInput:
    """
    StochasticPowerFlowInput
    """

    def __init__(self, grid: MultiCircuit):
        """
        Monte carlo input constructor
        @param grid: MultiCircuit instance
        """

        # number of nodes
        self.n = grid.get_bus_number()
        Sprof = grid.get_Sbus_prof(non_dispatchable_only=True)
        self.Scdf = [CDF(Sprof[i, :]) for i in range(self.n)]

    def get(self, samples=0, use_latin_hypercube=False) -> CxMat:
        """
        Call this object
        :param samples: number of samples
        :param use_latin_hypercube: use Latin Hypercube to sample
        :return: CxMat
        """
        if samples == 0:
            raise Exception('Cannot have zero samples :(')

        if use_latin_hypercube:

            lhs_points = lhs(self.n, samples=samples, criterion='center')
            S = np.zeros((samples, self.n), dtype=complex)
            for i in range(self.n):
                if self.Scdf[i] is not None:
                    S[:, i] = self.Scdf[i].get_at(lhs_points[:, i])

        else:

            S = np.zeros((samples, self.n), dtype=complex)

            for i in range(self.n):
                if self.Scdf[i] is not None:
                    S[:, i] = self.Scdf[i].get_sample(samples)

        return S

    def get_at(self, x) -> CxVec:
        """
        Get samples at x
        :param x: values in [0, 1] to sample the CDF
        :return: CxVec
        """

        S = np.zeros(self.n, dtype=complex)

        for i in range(self.n):
            if self.Scdf[i] is not None:
                S[i] = self.Scdf[i].get_at(x[i])

        return S

    def __call__(self, samples=0, use_latin_hypercube=False) -> CxMat:
        return self.get(samples=samples, use_latin_hypercube=use_latin_hypercube)
