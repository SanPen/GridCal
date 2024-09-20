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
from typing import List, Dict, Union
from pymoo.core.mixed import MixedVariableGA
from pymoo.algorithms.moo.nsga2 import RankAndCrowding
# from pymoo.decomposition.asf import ASF
# import matplotlib.pyplot as plt  # this is going to be in results, here for now to show we need to include plots
from pymoo.core.mixed import MixedVariableSampling
from pymoo.optimize import minimize
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Real, Integer, Choice, Binary

from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.types import BRANCH_TYPES, BRANCH_TEMPLATE_TYPES
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Logger


class MixedVariableProblem(ElementwiseProblem):
    """
    Problem formulation packaging to use the pymoo library
    """

    def __init__(self, grid: MultiCircuit, obj_func, n_obj):
        """
        :param obj_func:
        :param n_obj:
        """

        ElementwiseProblem.__init__(self, n_var=n_obj, n_obj=n_obj)

        self.logger = Logger()

        self.grid = grid

        all_dict, dict_ok = self.grid.get_all_elements_dict()
        self.device_template_dict: Dict[BRANCH_TYPES, List[BRANCH_TEMPLATE_TYPES]] = dict()

        # create the decision vars
        for investment_group, investments_list in self.grid.get_investments_by_groups():

            if len(investments_list) == 1:

                for investment in investments_list:

                    device = all_dict.get(investment.device_idtag, None)

                    if device is not None:
                        if isinstance(device, Transformer2W):

                            for ass_key, association in device.possible_transformer_types.data.items():
                                template = association.api_object
                                lst = self.device_template_dict.get(device, None)
                                if lst is None:
                                    self.device_template_dict[device] = [template]
                                else:
                                    lst.extend([template])

                        elif isinstance(device, Line):

                            for association_type in [device.possible_tower_types,
                                                     device.possible_sequence_line_types,
                                                     device.possible_underground_line_types]:

                                for ass_key, association in association_type.data.items():
                                    template = association.api_object
                                    lst = self.device_template_dict.get(device, None)
                                    if lst is None:
                                        self.device_template_dict[device] = [template]
                                    else:
                                        lst.extend([template])
                        else:
                            self.logger.add_error("Investment device not recognized",
                                                  device=device.name,
                                                  device_class=device.device_type)
                    else:
                        self.logger.add_error("Investment device is none",
                                              device=investment.device_idtag)
            else:
                self.logger.add_error("Only single-investment groups can be considered",
                                      device=investment_group.name,
                                      device_class=investment_group.device_type.value)

        # convert the data to decision vars: the decision vars are
        # integers from 0 to the number of templates of each device (the template position in self.data[device])
        self.variables: Dict[str, Integer] = dict()
        self.devices = list()  # list of devices in sequential order to match the order of the vars
        self.default_template = list()  # list of templates that represent the devices in their initial state
        for elm, template_list in self.device_template_dict.items():
            self.variables[elm.idtag] = Integer(bounds=(0, len(template_list) + 1))
            self.devices.append(elm)

            if isinstance(elm, Line):
                default_template = elm.get_line_type()

            elif isinstance(elm, Transformer2W):
                default_template = elm.get_transformer_type(Sbase=self.grid.Sbase)
            else:
                raise Exception('Device not recognized')

            self.default_template.append(default_template)

        super().__init__(n_obj=n_obj, vars=self.variables)
        self.obj_func = obj_func

    def _evaluate(self, x, out, *args, **kwargs):
        """

        :param x:
        :param out:
        :param args:
        :param kwargs:
        :return:
        """

        for i, xi in enumerate(x):
            device = self.devices[i]
            if i > 0:
                template = self.data[device.idtag][xi]

                if isinstance(device, Line):
                    device.apply_template(template, Sbase=self.grid.Sbase, logger=self.logger)

                elif isinstance(device, Transformer2W):
                    device.apply_template(template, Sbase=self.grid.Sbase, logger=self.logger)

                else:
                    raise Exception('Device not recognized')
            else:
                device.apply_template(self.default_template[i], Sbase=self.grid.Sbase, logger=self.logger)

        out["F"] = self.obj_func(x)
        print("Completed eval")


def NSGA_2(grid: MultiCircuit,
           obj_func,
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
    problem = MixedVariableProblem(grid, obj_func, n_obj)

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

    # Do they want opex or capex to have more weight?
    # weights = np.array([0.5, 0.5])
    # decomp = ASF()
    # I = decomp(res.F, weights).argmin()

    import pandas as pd
    dff = pd.DataFrame(res.F)
    dff.to_excel('nsga.xlsx')
    return res.X, res.F
