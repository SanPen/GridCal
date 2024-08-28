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
from __future__ import annotations

import os
import importlib
import importlib.util
import hashlib
from typing import List, Dict
import json
from PySide6.QtGui import QPixmap
from GridCalEngine.IO.file_system import get_create_gridcal_folder


def plugins_path() -> str:
    """
    get the config file path
    :return: config file path
    """
    pth = os.path.join(get_create_gridcal_folder(), 'plugins')

    if not os.path.exists(pth):
        os.makedirs(pth)

    return pth


class PluginInfo:
    """
    Plugin information
    """

    def __init__(self) -> None:
        """

        """
        self.name = ""
        self.path = ""
        self.icon_path = ""
        self.function_name = ""

        self.function_ptr = None
        self.icon: QPixmap | None = None

    def to_dict(self) -> Dict[str, str]:
        """
        To dict
        :return:
        """
        return {
            'name': self.name,
            'path': self.path,
            'icon_path': self.icon_path,
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
        self.icon_path = data.get('icon_path', '')
        self.function_name = data.get('function_name', '')

    def read_plugin(self):
        """

        :return: 
        """
        base_path = plugins_path()
        plugin_path = os.path.join(base_path, self.path)

        if os.path.exists(plugin_path):

            if plugin_path.endswith('.py'):

                # hot read python file
                try:
                    self.function_ptr = load_function_from_file_path(file_path=plugin_path,
                                                                     function_name=self.function_name)

                except ImportError as e:
                    print(e)
                except AttributeError as e:
                    print(e)
                except TypeError as e:
                    print(e)

            else:
                print(f"Plugin {self.name}: Path {plugin_path} not a python file :(")
        else:
            print(f"Plugin {self.name}: Path {plugin_path} not found :/")

        icon_path = os.path.join(base_path, self.icon_path)
        if os.path.exists(icon_path):
            self.icon = QPixmap(icon_path)
        else:
            print(f"Plugin {self.name}: Path {icon_path} not found :/")


class PluginsInfo:
    """
    Plugins information
    """

    def __init__(self) -> None:
        """

        """
        self.index_fname = os.path.join(plugins_path(), 'plugins.json')

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
        Parse data: Create the plugins information
        :param data:
        :return:
        """
        self.plugins.clear()
        for entry in data:
            pl = PluginInfo()
            pl.parse(entry)
            pl.read_plugin()
            self.plugins.append(pl)

    def read(self) -> None:
        """
        Thead the plugins info file
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


def load_function_from_file_path(file_path, function_name):
    """
    Dynamically load a function from a Python file at a given file path.

    :param file_path: The path to the Python (.py) file.
    :param function_name: The name of the function to load from the file.
    :return: The loaded function object.
    :raises FileNotFoundError: If the specified file does not exist.
    :raises ImportError: If the module cannot be imported.
    :raises AttributeError: If the function does not exist in the module.
    :raises TypeError: If the retrieved attribute is not callable.
    """
    # Ensure the file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    # Generate a unique module name to avoid conflicts
    # Here, we use the file's absolute path hashed to ensure uniqueness
    absolute_path = os.path.abspath(file_path)
    module_name = f"dynamic_module_{hashlib.md5(absolute_path.encode()).hexdigest()}"

    # Create a module specification from the file location
    spec = importlib.util.spec_from_file_location(module_name, absolute_path)
    if spec is None:
        raise ImportError(f"Cannot create a module spec for '{file_path}'")

    # Create a new module based on the spec
    module = importlib.util.module_from_spec(spec)

    try:
        # Execute the module to populate its namespace
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Failed to execute module '{file_path}': {e}") from e

    # Retrieve the function from the module
    if not hasattr(module, function_name):
        raise AttributeError(f"The function '{function_name}' does not exist in '{file_path}'")

    func = getattr(module, function_name)

    if not callable(func):
        raise TypeError(f"'{function_name}' in '{file_path}' is not callable")

    return func
