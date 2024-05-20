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
from GridCalEngine.DataStructures.branch_data import BranchData

class ControllableTrafoData(BranchData):
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
        super().__init__(nelm, nbus)
        self.nbus: int = nbus
        self.nelm: int = nelm

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