# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from GridCal.Engine.Simulations.PowerFlow.time_Series_input import TimeSeriesInput


class StochasticPowerFlowInput:

    def __init__(self, n, Scdf, Icdf, Ycdf):
        """
        Monte carlo input constructor
        @param n: number of nodes
        @param Scdf: Power cumulative density function
        @param Icdf: Current cumulative density function
        @param Ycdf: Admittances cumulative density function
        """

        # number of nodes
        self.n = n

        self.Scdf = Scdf

        self.Icdf = Icdf

        self.Ycdf = Ycdf

    def __call__(self, samples=0, use_latin_hypercube=False):
        """
        Call this object
        :param samples: number of samples
        :param use_latin_hypercube: use Latin Hypercube to sample
        :return: Time series object
        """
        if use_latin_hypercube:

            lhs_points = lhs(self.n, samples=samples, criterion='center')

            if samples > 0:
                S = np.zeros((samples, self.n), dtype=complex)
                I = np.zeros((samples, self.n), dtype=complex)
                Y = np.zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_at(lhs_points[:, i])

        else:
            if samples > 0:
                S = np.zeros((samples, self.n), dtype=complex)
                I = np.zeros((samples, self.n), dtype=complex)
                Y = np.zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_sample(samples)
            else:
                S = np.zeros(self.n, dtype=complex)
                I = np.zeros(self.n, dtype=complex)
                Y = np.zeros(self.n, dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[i] = complex(self.Scdf[i].get_sample()[0])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input

    def get_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1] to sample the CDF

        Returns: Time series object
        """
        S = np.zeros((1, self.n), dtype=complex)
        I = np.zeros((1, self.n), dtype=complex)
        Y = np.zeros((1, self.n), dtype=complex)

        for i in range(self.n):
            if self.Scdf[i] is not None:
                S[:, i] = self.Scdf[i].get_at(x[i])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input

