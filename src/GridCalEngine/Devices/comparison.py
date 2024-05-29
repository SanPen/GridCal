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


from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class PropertyConflict:
    """
    Objects conflict
    """

    def __init__(self, obj_a: ALL_DEV_TYPES, obj_b: ALL_DEV_TYPES, prop_name: str):
        self.obj_a = obj_a
        self.obj_b = obj_b
        self.prop_name = prop_name

    def preffer_a(self):
        """
        Prefer the object A
        :return:
        """
        val = getattr(self.obj_a, self.prop_name)
        return setattr(self.obj_b, self.prop_name, val)

    def preffer_b(self):
        """
        Prefer the object B
        :return:
        """
        val = getattr(self.obj_b, self.prop_name)
        return setattr(self.obj_a, self.prop_name, val)


class CircuitComparison:
    """
    Comparison between two circuits
    """

    def __init__(self, circuit_a: MultiCircuit, circuit_b: MultiCircuit):
        """

        :param circuit_a:
        :param circuit_b:
        """
        self.circuit_a = circuit_a
        self.circuit_b = circuit_b

    def merge_b_into_a(self):
        """
        Compare two circuits
        :return: stored in place
        """
        objects_a_by_type = self.circuit_a.get_all_elements_dict_by_type()
        objects_b_by_type = self.circuit_b.get_all_elements_dict_by_type()

        # traverse the object types present in B
        for tpe_name, data_b_per_tpe in objects_b_by_type.items():

            data_a_per_tpe = objects_a_by_type.get(tpe_name, None)

            if data_a_per_tpe is None:
                # add all objects from B into A
                for obj_b_idtag, obj_b in data_b_per_tpe.items():

                    pass

            else:
                # compare objects from B with objects from A
                for obj_b_idtag, obj_b in data_b_per_tpe.items():
                    pass


