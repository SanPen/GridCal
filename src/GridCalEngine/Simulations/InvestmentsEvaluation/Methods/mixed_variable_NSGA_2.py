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
from pymoo.core.mixed import MixedVariableGA
from pymoo.algorithms.moo.nsga2 import RankAndCrowding
# from pymoo.decomposition.asf import ASF
# import matplotlib.pyplot as plt  # this is going to be in results, here for now to show we need to include plots
from pymoo.core.mixed import MixedVariableSampling
from pymoo.optimize import minimize
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Real, Integer, Choice, Binary


class MixedVariableProblem(ElementwiseProblem):
    """
    Problem formulation packaging to use the pymoo library
    """
    def __init__(self, obj_func, n_obj):
        """
        :param obj_func:
        :param n_obj:
        """
        # These will need to be inputted automatically from the csv file on GridCal
        vars = {
            "react1_bi": Binary(),
            "react2_bi": Binary(),
            "react3_bi": Binary(),
            "react4_bi": Binary(),
            "react5_bi": Binary(),
            # "vol_level": Choice(options=["vol132","vol220"]),
            "vol_level": Choice(options=["vol220"]),
            # "vol_level": Choice(options=["vol132"]),
            "n_cables": Integer(bounds=(2, 3)),
            "S_rtr": Real(bounds=(500e6, 1000e6)),
            "react1": Real(bounds=(0.0, 1.0)),
            "react2": Real(bounds=(0.0, 1.0)),
            "react3": Real(bounds=(0.0, 1.0)),
            "react4": Real(bounds=(0.0, 1.0)),
            "react5": Real(bounds=(0.0, 1.0))}
        super().__init__(n_obj=n_obj,
                         vars=vars)
        self.obj_func = obj_func

    def _evaluate(self, x, out, *args, **kwargs):
        """

        :param x:
        :param out:
        :param args:
        :param kwargs:
        :return:
        """
        # Ideally, we want this to be automatically inputted:
        # react1_bi, react2_bi, react3_bi, react4_bi, react5_bi, vol, n_cables, S_rtr, react1, react2, react3, react4,
        #  react5 = x["react1_bi"], x["react2_bi"], x["react3_bi"], x["react4_bi"], x["react5_bi"], x["vol_level"],
        #             x["n_cables"], x["S_rtr"], x["react1"], x["react2"], x["react3"], x["react4"], x["react5"]
        # def build_grid_data
        # then
        # def run_pf or now run_opf
        # then
        # def compute_costs
        # then
        # obj_func = capex + opex
        # to be outputted as out["F"]

        out["F"] = self.obj_func(x)


def NSGA_2(obj_func,
           n_obj: int = 2,
           max_evals: int = 30,
           pop_size: int = 1,
           # crossover_prob: float = 0.05,
           # mutation_probability=0.5,
           # eta: float = 3.0
           ):
    """

    :param obj_func:
    :param n_obj:
    :param max_evals:
    :param pop_size:
    # :param crossover_prob:
    # :param mutation_probability:
    # :param eta:
    :return:
    """
    problem = MixedVariableProblem(obj_func, n_obj)

    algorithm = MixedVariableGA(pop_size=pop_size,
                                sampling=MixedVariableSampling(),
                                survival=RankAndCrowding(crowding_func="pcd"))

    # In terms of setting probability parameters, you have to look quite far deep into MixedVariableGA

    res = minimize(problem=problem,
                   algorithm=algorithm,
                   termination=('n_eval', max_evals),
                   seed=1,
                   verbose=True,
                   save_history=False)

    # Shall we need this?
    # weights = np.array([0.5, 0.5])
    # decomp = ASF()
    # I = decomp(res.F, weights).argmin()

    import pandas as pd
    dff = pd.DataFrame(res.F)
    dff.to_excel('nsga.xlsx')
    return res.X, res.F
