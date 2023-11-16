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
from sklearn.neighbors import KNeighborsRegressor
from GridCalEngine.Simulations.Stochastic.latin_hypercube_sampling import lhs
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import CDF, CxVec, CxMat


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

        # gathe "generation" and "demand"
        Sprof_fixed = grid.get_Sbus_prof_fixed()
        Sprof_dispatcheable = grid.get_Sbus_prof_dispatchable()

        # build the CFD for the dispatchable values
        self.Scdf_fixed = [CDF(Sprof_fixed[i, :]) for i in range(self.n)]

        # build the relationship of the dispatchable devices to the fixed ones for later
        self.regression_model = KNeighborsRegressor(n_neighbors=4)
        self.regression_model.fit(Sprof_fixed.real, Sprof_dispatcheable.real)

    def get(self, n_samples=0, use_latin_hypercube=False) -> CxMat:
        """
        Call this object
        :param n_samples: number of samples
        :param use_latin_hypercube: use Latin Hypercube to sample
        :return: CxMat (p.u.)
        """
        if n_samples == 0:
            raise Exception('Cannot have zero samples :(')

        if use_latin_hypercube:

            lhs_points = lhs(self.n, samples=n_samples, criterion='center')
            S_fixed = np.zeros((n_samples, self.n), dtype=complex)
            for i in range(self.n):
                if self.Scdf_fixed[i] is not None:
                    S_fixed[:, i] = self.Scdf_fixed[i].get_at(lhs_points[:, i])

        else:
            S_fixed = np.zeros((n_samples, self.n), dtype=complex)

            for i in range(self.n):
                if self.Scdf_fixed[i] is not None:
                    S_fixed[:, i] = self.Scdf_fixed[i].get_sample(n_samples)

        # apply the regression
        S_dispatchable = self.regression_model.predict(S_fixed.real)

        # scale to match
        for t in range(S_fixed.shape[0]):

            demand = -S_fixed[t, :].sum().real
            genertion = S_dispatchable[t, :].sum()

            factor = demand / genertion
            S_dispatchable[t, :] *= factor

        return S_fixed + S_dispatchable

    def get_at(self, x) -> CxVec:
        """
        Get samples at x
        :param x: values in [0, 1] to sample the CDF
        :return: CxVec
        """

        S = np.zeros(self.n, dtype=complex)

        for i in range(self.n):
            if self.Scdf_fixed[i] is not None:
                S[i] = self.Scdf_fixed[i].get_at(x[i])

        return S

    def __call__(self, samples=0, use_latin_hypercube=False) -> CxMat:
        return self.get(n_samples=samples, use_latin_hypercube=use_latin_hypercube)
