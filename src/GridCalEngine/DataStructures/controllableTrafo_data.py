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
import numpy as np
import pandas as pd
import scipy.sparse as sp
import GridCalEngine.Topology.topology as tp
from GridCalEngine.enumerations import WindingsConnection, TransformerControlType
from GridCalEngine.basic_structures import Vec, IntVec, StrVec, ObjVec
from typing import List, Tuple, Dict

class ControllableTrafoData:
    """
    Class to store the data of a controllable transformer
    """
    def __init__(self, nelm: int, nbus: int):
        """
        Constructor
        :param name: name of the transformer
        :param from_bus: name of the from bus
        :param to_bus: name of the to bus
        :param windings: list of tuples with the names of the winding buses
        :param control_type: control type
        :param control_value: control value
        """
        self.nelm: int = nelm
        self.nbus: int = nbus

        self.names: StrVec = np.empty(self.nelm, dtype=object)
        self.idtag: StrVec = np.empty(self.nelm, dtype=object)

        self.dc: IntVec = np.zeros(self.nelm, dtype=int)

        self.active: IntVec = np.zeros(nelm, dtype=int)
        self.rates: Vec = np.zeros(nelm, dtype=float)
        self.contingency_rates: Vec = np.zeros(nelm, dtype=float)
        self.protection_rates: Vec = np.zeros(nelm, dtype=float)

        self.F: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "from" buses
        self.T: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "to" buses

        self.ctrl_bus1: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the control buses1
        self.ctrl_bus2: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the control buses2

        # reliabilty
        self.mttf: Vec = np.zeros(self.nelm, dtype=float)
        self.mttr: Vec = np.zeros(self.nelm, dtype=float)

        # composite losses curve (a * x^2 + b * x + c)
        self.a: Vec = np.zeros(self.nelm, dtype=float)
        self.b: Vec = np.zeros(self.nelm, dtype=float)
        self.c: Vec = np.zeros(self.nelm, dtype=float)

        self.R: Vec = np.zeros(self.nelm, dtype=float)
        self.X: Vec = np.zeros(self.nelm, dtype=float)
        self.G: Vec = np.zeros(self.nelm, dtype=float)
        self.B: Vec = np.zeros(self.nelm, dtype=float)

        self.R0: Vec = np.zeros(self.nelm, dtype=float)
        self.X0: Vec = np.zeros(self.nelm, dtype=float)
        self.G0: Vec = np.zeros(self.nelm, dtype=float)
        self.B0: Vec = np.zeros(self.nelm, dtype=float)

        self.R2: Vec = np.zeros(self.nelm, dtype=float)
        self.X2: Vec = np.zeros(self.nelm, dtype=float)
        self.G2: Vec = np.zeros(self.nelm, dtype=float)
        self.B2: Vec = np.zeros(self.nelm, dtype=float)

        self.conn: ObjVec = np.array([WindingsConnection.GG] * self.nelm)

        self.k: Vec = np.ones(nelm, dtype=float)

        self.tap_module: Vec = np.ones(nelm, dtype=float)
        self.tap_module_min: Vec = np.full(nelm, fill_value=0.1, dtype=float)
        self.tap_module_max: Vec = np.full(nelm, fill_value=1.5, dtype=float)
        self.tap_angle: Vec = np.zeros(nelm, dtype=float)
        self.tap_angle_min: Vec = np.full(nelm, fill_value=-6.28, dtype=float)
        self.tap_angle_max: Vec = np.full(nelm, fill_value=6.28, dtype=float)
        self.Beq: Vec = np.zeros(nelm, dtype=float)
        self.G0sw: Vec = np.zeros(nelm, dtype=float)

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

        self.Pfset: Vec = np.zeros(nelm, dtype=float)
        self.Qfset: Vec = np.zeros(nelm, dtype=float)
        self.Qtset: Vec = np.zeros(nelm, dtype=float)
        self.vf_set: Vec = np.ones(nelm, dtype=float)
        self.vt_set: Vec = np.ones(nelm, dtype=float)

        self.Kdp: Vec = np.ones(self.nelm, dtype=float)
        self.Kdp_va: Vec = np.ones(self.nelm, dtype=float)
        self.alpha1: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha1)
        self.alpha2: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha2)
        self.alpha3: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha3)
        self.control_mode: ObjVec = np.zeros(self.nelm, dtype=object)

        self.contingency_enabled: IntVec = np.ones(self.nelm, dtype=int)
        self.monitor_loading: IntVec = np.ones(self.nelm, dtype=int)

        self.C_branch_bus_f: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus),
                                                           dtype=int)  # connectivity branch with their "from" bus
        self.C_branch_bus_t: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus),
                                                           dtype=int)  # connectivity branch with their "to" bus

        self.overload_cost: Vec = np.zeros(nelm, dtype=float)

        self.original_idx: IntVec = np.zeros(nelm, dtype=int)

        # GENERALISED PF
        self.gpf_ctrl1_elm: StrVec = np.empty(nelm, dtype=object)
        self.gpf_ctrl1_mode: StrVec = np.empty(nelm, dtype=object)
        self.gpf_ctrl1_val: Vec = np.zeros(nelm, dtype=float)
        self.gpf_ctrl2_elm: StrVec = np.empty(nelm, dtype=object)
        self.gpf_ctrl2_mode: StrVec = np.empty(nelm, dtype=object)
        self.gpf_ctrl2_val: Vec = np.zeros(nelm, dtype=float)

        self.name_to_idx: dict = dict()


    def __str__(self):
        """
        String representation
        :return: string
        """
        return f"Controllable transformer {self.name} from {self.from_bus} to {self.to_bus} with windings {self.windings} and control type {self.control_type} and control value {self.control_value}"

    def __repr__(self):
        """
        Representation
        :return: string
        """
        return self.__str__()

    def to_dict(self):
        """
        Convert to dictionary
        :return: dictionary
        """
        return {
            'name': self.name,
            'from_bus': self.from_bus,
            'to_bus': self.to_bus,
            'windings': self.windings,
            'control_type': self.control_type,
            'control_value': self.control_value
        }

    @staticmethod
    def from_dict(data: dict):
        """
        Create instance from dictionary
        :param data: dictionary
        :return: instance
        """
        return ControllableTrafoData(name=data['name'],
                                     from_bus=data['from_bus'],
                                     to_bus=data['to_bus'],
                                     windings=data['windings'],
                                     control_type=data['control_type'],
                                     control_value=data['control_value'])