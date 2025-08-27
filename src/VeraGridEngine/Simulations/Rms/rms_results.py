# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.colors as plt_colors
from typing import List, Tuple

from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, CxVec, ConvergenceReport, Logger
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class NumericPowerFlowResults:
    """
    NumericPowerFlowResults, used to return values from the numerical methods
    """

    def __init__(self,
                 V: CxVec,
                 Scalc: CxVec,
                 m: Vec,
                 tau: Vec,
                 Sf: CxVec,
                 St: CxVec,
                 If: CxVec,
                 It: CxVec,
                 loading: CxVec,
                 losses: CxVec,
                 Pf_vsc: Vec,
                 St_vsc: CxVec,
                 If_vsc: Vec,
                 It_vsc: CxVec,
                 losses_vsc: Vec,
                 loading_vsc: Vec,
                 Sf_hvdc: CxVec,
                 St_hvdc: CxVec,
                 losses_hvdc: CxVec,
                 loading_hvdc: Vec,
                 norm_f: float,
                 converged: bool,
                 iterations: int,
                 elapsed: float):
        """
        Object to store the results returned by a numeric power flow routine
        :param V: Voltage vector
        :param Scalc: Calculated power vector
        :param m: Tap modules vector for all the Branches
        :param tau: Tap angles vector for all the Branches
        :param Sf: Power flom vector for all the Branches
        :param St: Power to vector for all the Branches
        :param If: Current flom vector for all the Branches
        :param It: Current to vector for all the Branches
        :param loading: Loading vector for all the Branches
        :param losses: Losses vector for all the Branches
        :param Pf_vsc:
        :param St_vsc:
        :param If_vsc:
        :param It_vsc:
        :param losses_vsc:
        :param Sf_hvdc:
        :param St_hvdc:
        :param losses_hvdc:
        :param norm_f: error
        :param converged: converged?
        :param iterations: number of iterations
        :param elapsed: time elapsed
        """
        self.V = V
        self.Scalc = Scalc

        # regular branches
        self.Sf = Sf
        self.St = St
        self.If = If
        self.It = It
        self.loading = loading
        self.losses = losses

        # controllable branches
        self.tap_module = m
        self.tap_angle = tau

        # VSC
        self.Pf_vsc = Pf_vsc
        self.St_vsc = St_vsc
        self.If_vsc = If_vsc
        self.It_vsc = It_vsc
        self.losses_vsc = losses_vsc
        self.loading_vsc = loading_vsc

        # Hvdc
        self.Sf_hvdc = Sf_hvdc
        self.St_hvdc = St_hvdc
        self.losses_hvdc = losses_hvdc
        self.loading_hvdc = loading_hvdc

        # convergence metrics
        self.converged = converged
        self.norm_f = norm_f
        self.iterations = iterations
        self.elapsed = elapsed
        self.method = None


class RmsResults(ResultsTemplate):

    def __init__(self):
        ResultsTemplate.__init__(
            self,
            name='RMS simulation',
            available_results={

            },
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.RmsSimulation
        )


        self.dt: List[float] = list()
        self.x: List[Vec] = list()
        self.y: List[Vec] = list()

    def add(self, dt: float, x: Vec, y: Vec):
        """

        :param dt:
        :param x:
        :param y:
        :return:
        """
        self.dt.append(dt)
        self.x.append(x)
        self.y.append(y)
