# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


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


