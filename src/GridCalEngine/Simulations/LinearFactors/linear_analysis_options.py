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
from GridCalEngine.Simulations.options_template import OptionsTemplate


class LinearAnalysisOptions(OptionsTemplate):
    """
    LinearAnalysisOptions
    """

    def __init__(self,
                 distribute_slack=False,
                 correct_values=True,
                 ptdf_threshold: float = 1e-3,
                 lodf_threshold: float = 1e-3):
        """
        Power Transfer Distribution Factors' options
        :param distribute_slack: Distribute the slack effect?
        :param correct_values: correct out of bounds values?
        :param ptdf_threshold: threshold for PTDF's to be converted to sparse
        :param lodf_threshold: threshold for LODF's to be converted to sparse
        """
        OptionsTemplate.__init__(self, name="LinearAnalysisOptions")

        self.distribute_slack = distribute_slack

        self.correct_values = correct_values

        self.ptdf_threshold = ptdf_threshold

        self.lodf_threshold = lodf_threshold

        self.register(key="distribute_slack", tpe=bool)
        self.register(key="correct_values", tpe=bool)
        self.register(key="ptdf_threshold", tpe=float)
        self.register(key="lodf_threshold", tpe=float)
