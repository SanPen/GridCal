# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import json
import numpy as np
from typing import Tuple, List
from matplotlib import pyplot as plt
from GridCalEngine.basic_structures import Mat


class GeneratorQCurve:
    """
    GeneratorQCurve
    """

    def __init__(self) -> None:

        # Array of points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]
        self._q_points: Mat = np.zeros((0, 3))

    def get_data(self):
        """
        Get the data
        :return:
        """
        return self._q_points

    def get_data_by_type(self):
        """
        Get the data points P, Qmin, Qmax
        :return: P, Qmin, Qmax
        """
        return self._q_points[:, 0], self._q_points[:, 1], self._q_points[:, 2]

    def make_default_q_curve(self, Snom: float, Qmin: float, Qmax: float, n: int = 3):
        """
        Compute the theoretical generator capability curve
        :param Snom: Nominal power
        :param Qmin: Minimum reactive power
        :param Qmax: Maximum reactive power
        :param n: number of points, at least 3
        """
        self._q_points = np.zeros((n, 3))

        if n > 1:

            s2 = Snom * Snom

            Qmax2 = Qmax if Qmax < Snom else Snom
            Qmin2 = Qmin if Qmin > -Snom else -Snom

            # Compute the intersections of the Qlimits with the natural curve
            p0_max = np.sqrt(s2 - Qmax2 * Qmax2)
            p0_min = np.sqrt(s2 - Qmin2 * Qmin2)
            p0 = min(p0_max, p0_min)  # pick the lower limit as the starting point for sampling

            # generate evenly spaced active power points from 0 to Snom
            self._q_points[1:, 0] = np.linspace(p0, Snom, n - 1)

            # enter the base points
            self._q_points[0, 0] = 0
            self._q_points[0, 1] = Qmin2
            self._q_points[0, 2] = Qmax2

            for i in range(1, n):
                p2 = self._q_points[i, 0] * self._q_points[i, 0]  # P^2
                q = np.sqrt(s2 - p2)  # point that naturally matches Q = sqrt(S^2 - P^2)

                # assign the natural point if it does not violates the limits imposes, else set the limit
                qmin = -q if -q > Qmin2 else Qmin2
                qmax = q if q < Qmax2 else Qmax2

                # Enforce that Qmax > Qmin
                if qmax < qmin:
                    qmax = qmin
                if qmin > qmax:
                    qmin = qmax

                # Assign the points
                self._q_points[i, 1] = qmin
                self._q_points[i, 2] = qmax

        else:
            self._q_points[0, 0] = 0
            self._q_points[0, 1] = Qmin
            self._q_points[0, 2] = Qmax

    def get_q_limits(self, p: float) -> Tuple[float, float]:
        """
        Get the reactive power limits
        :param p: active power value (or array)
        :return: Qmin (float), Qmax (float)
        """
        if self._q_points.shape[0] > 1:
            all_p = self._q_points[:, 0]
            all_qmin = self._q_points[:, 1]
            all_qmax = self._q_points[:, 2]

            qmin = np.interp(p, all_p, all_qmin)
            qmax = np.interp(p, all_p, all_qmax)

            return qmin, qmax
        else:
            return self._q_points[0, 1], self._q_points[0, 2]

    def get_qmax(self, p: float) -> float:
        """
        Get Qmax
        :param p: active power value in MW
        :return: Qmax in MVAr
        """
        if self._q_points.shape[0] > 1:
            return np.interp(p, self._q_points[:, 0], self._q_points[:, 2])
        else:
            return self._q_points[0, 2]

    def get_qmin(self, p: float) -> float:
        """
        Get Qmin
        :param p: active power value in MW
        :return: Qmin in MVAr
        """
        if self._q_points.shape[0] > 1:
            return np.interp(p, self._q_points[:, 0], self._q_points[:, 1])
        else:
            return self._q_points[0, 1]

    def __str__(self) -> str:
        """
        Get string representation of the curve
        :return: json string of list of lists: "[[P1, Qmin1, Qmax1], [P2, Qmin2, Qmax2], ...]"
        """
        return self.str()

    def __eq__(self, other: "GeneratorQCurve") -> bool:
        """
        Equality check
        :param other: GeneratorQCurve
        :return: equal?
        """
        return np.allclose(self._q_points, other._q_points)

    def to_list(self) -> list:
        """
        Get list of points
        :return:
        """
        return self._q_points.tolist()

    def str(self) -> str:
        """
        Get string representation of the curve
        :return: json string of list of lists: "[[P1, Qmin1, Qmax1], [P2, Qmin2, Qmax2], ...]"
        """
        return json.dumps(self.to_list())

    # def parse(self, data: List[float]) -> None:
    #     """
    #     Parse json curve data
    #     :param data: string value: [[P1, Qmin1, Qmax1], [P2, Qmin2, Qmax2], ...]
    #     """
    #     n = len(data)
    #     self._q_points = np.zeros((n, 3))
    #     for i, row in enumerate(data):
    #         self._q_points[i, 0] = row[0]
    #         self._q_points[i, 1] = row[1]
    #         self._q_points[i, 2] = row[2]

    def parse(self, data: List[Tuple[float, float, float]]):
        """
        Parse Json data
        :param data: List of lists with (latitude, longitude, altitude)
        """
        if len(data) > 0:
            values = np.array(data)
            self.set(data=values)
        else:
            self._q_points = np.zeros((0, 4))

    def set(self, data: np.ndarray):
        """
        Parse Json data
        :param data: List of lists with (latitude, longitude, altitude)
        """
        if data.ndim == 2:
            if data.shape[1] == 3:
                self._q_points = data
            else:
                raise ValueError('GeneratorQCurve data does not have exactly 3 columns')
        else:
            raise ValueError('GeneratorQCurve data must be 2-dimensional: (n_points, 3)')

    def get_Qmin(self):

        return self._q_points[:, 1].min()

    def get_Qmax(self):

        return self._q_points[:, 2].max()

    def get_Pmin(self):

        return self._q_points[:, 0].min()

    def get_Pmax(self):

        return self._q_points[:, 0].max()

    def get_Snom(self):

        qmin = self._q_points[:, 1].min()
        qmax = self._q_points[:, 2].max()

        qfinal = max(abs(qmin), abs(qmax))
        pmax = self._q_points[:, 0].max()

        return np.sqrt(pmax * pmax + qfinal * qfinal)

    def plot(self, ax: plt.axis):
        """

        :param ax:
        :return:
        """
        x = self._q_points[:, 0]
        y1 = self._q_points[:, 1]
        y2 = self._q_points[:, 2]
        ax.plot(x, y1,
                color='red',
                marker='o',
                linestyle='solid',
                linewidth=2,
                markersize=4)
        ax.plot(x, y2,
                color='red',
                marker='o',
                linestyle='solid',
                linewidth=2,
                markersize=4)
        ax.set_xlabel("Q (MVAr)")
        ax.set_ylabel("P (MW)")
