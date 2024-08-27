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
import os
from typing import List, Dict
import json


class PluginInfo:
    """
    Plugin information
    """

    def __init__(self):
        """

        """
        self.name = ""
        self.path = ""
        self.icon = ""
        self.function_name = ""

    def to_dict(self) -> Dict[str, str]:
        """
        To dict
        :return:
        """
        return {
            'name': self.name,
            'path': self.path,
            'icon': self.icon,
            'function_name': self.function_name,
        }

    def parse(self, data: Dict[str, str]):
        """
        Parse data
        :param data:
        :return:
        """
        self.name = data.get('name', '')
        self.path = data.get('path', '')
        self.icon = data.get('icon', '')
        self.function_name = data.get('function_name', '')


class PluginsInfo:
    """
    Plugins information
    """

    def __init__(self, index_fname: str):
        """

        :param index_fname:
        """
        self.index_fname = index_fname

        self.plugins: List[PluginInfo] = list()

        if os.path.exists(self.index_fname):
            self.read()
        else:
            self.save()

    def to_data(self) -> List[Dict[str, str]]:
        """
        Get dictionary of plugin data
        :return:
        """
        return [pl.to_dict() for pl in self.plugins]

    def parse(self, data: List[Dict[str, str]]):
        """
        Parse data
        :param data:
        :return:
        """
        for entry in data:
            pl = PluginInfo()
            pl.parse(entry)
            self.plugins.append(pl)

    def read(self):
        """

        :return:
        """
        # Open the JSON file
        with open(self.index_fname, 'r') as file:
            # Load the JSON data into a dictionary
            data = json.load(file)
            self.parse(data)

    def save(self):
        """
        Save the plugins information
        :return:
        """
        # Write the dictionary to a JSON file
        with open(self.index_fname, 'w') as json_file:
            data = self.to_data()
            json.dump(data, json_file)
