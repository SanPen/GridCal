# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.Simulations.options_template import OptionsTemplate


class ClusteringAnalysisOptions(OptionsTemplate):

    def __init__(self, n_points: int):
        """
        Clustering options
        :param n_points: number of points
        """
        OptionsTemplate.__init__(self, name='Clustering analysis options')

        self.n_points = n_points

        self.register(key="n_points", tpe=int)
