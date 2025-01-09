# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import timeit
import numpy as np
import timeit
import pandas as pd
from scipy import sparse as sp
from typing import Tuple
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, csr_matrix, csc_matrix, Vec
from GridCalEngine.Utils.NumericalMethods.ips import interior_point_solver, IpsFunctionReturn
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import AcOpfMode
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger


class NonLinearOptimalPfProblem:

    def __init__(self, options: OptimalPowerFlowOptions):
        self.options = options

        # variables
        self.Va
        self.Vm
        self.Pg
        self.Qg
        self.sl_sf
        self.sl_st
        self.sl_vmax
        self.sl_vmin
        self.slcap
        self.tapm
        self.tapt
        self.Pfdc

    def var2x(self) -> Vec:
        return np.r_[
            self.Va,
            self.Vm,
            self.Pg,
            self.Qg,
            self.sl_sf,
            self.sl_st,
            self.sl_vmax,
            self.sl_vmin,
            self.slcap,
            self.tapm,
            self.tapt,
            self.Pfdc,
        ]

    def x2var(self, x: Vec):
        a = 0
        b = len(self.Va)

        Va = x[a: b]
        a = b
        b += len(self.Vm)

        Vm = x[a: b]
        a = b
        b += len(self.Pg)

        Pg = x[a: b]
        a = b
        b += len(self.Qg)

        Qg = x[a: b]
        a = b

        if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
            b += M

            sl_sf = x[a: b]
            a = b
            b += M

            sl_st = x[a: b]
            a = b
            b += npq

            sl_vmax = x[a: b]
            a = b
            b += npq

            sl_vmin = x[a: b]
            a = b
            b += nslcap

        else:
            b += nslcap
            # Create empty arrays for not used variables
            sl_sf = np.zeros(0)
            sl_st = np.zeros(0)
            sl_vmax = np.zeros(0)
            sl_vmin = np.zeros(0)

        slcap = x[a:b]
        a = b
        b += ntapm

        tapm = x[a: b]
        a = b
        b += ntapt

        tapt = x[a: b]
        a = b
        b += ndc

        Pfdc = x[a: b]

    def update(self, x: Vec):
        pass

    def getJacobian(self):
        pass

    def getHessian(self):
        pass
