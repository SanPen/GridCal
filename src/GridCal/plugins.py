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
from typing import List, Dict, TYPE_CHECKING, Callable
import json
from PySide6.QtGui import QPixmap

from GridCalEngine.IO.file_system import get_create_gridcal_folder

if TYPE_CHECKING:
    from GridCal.Gui.Main.GridCalMain import MainGUI


def plugins_path() -> str:
    """
    get the config file path
    :return: config file path
    """
    pth = os.path.join(get_create_gridcal_folder(), 'plugins')

    if not os.path.exists(pth):
        os.makedirs(pth)

    return pth


class PluginFunction:
    """
    Class to handle external funtion pointers
    """

    def __init__(self) -> None:

        self.name = ""
        self.alias = ""
        self.function_ptr = None

    def get_pointer_lambda(self, gui_instance: MainGUI) -> Callable:
        """
        Really hard core magic to avoid lambdas shadow each other due to late binding

        lambda e=True, func=self.function_ptr: func(self)

        explanation:
        - e is a bool parameter that the QAction sends when triggered,
            set it by default True, otherwise fails on windows
        - func=self.function_ptr is there for the lambda to force the usage of the value of self.function_ptr
            during the iteration and not after the loop since lambdas in a loop are lazy evaluated
        - func(self) is then what I wanted to lambda in the first place
        """
        return lambda e=True, func=self.function_ptr: func(gui_instance)  # This is not an error, it is correct

    def to_dict(self) -> Dict[str, str]:
        """
        To dict
        :return: string, string dictionary to save in json format
        """
        return {
            "name": self.name,
            "alias": self.alias,
        }

    def parse(self, data: Dict[str, str]) -> None:
        """
        Parse data
        :param data: Data like the one saved
        """
        self.name = data.get('name', '').strip()
        self.alias = data.get('alias', '').strip()

    def read_plugin(self, plugin_path: str) -> None:
        """
        Read the pointed plugin
        :param plugin_path: plugin file path
        """

        # hot read python file˘
        if self.name != "":
            try:

                # read the main function (the one launched upon click on the plugin)
                self.function_ptr = load_function_from_file_path(
                    file_path=plugin_path,
                    function_name=self.name
                )

            except ImportError as e:
                print(e)
            except AttributeError as e:
                print(e)
            except TypeError as e:
                print(e)


class PluginInfo:
    """
    Plugin information
    """

    def __init__(self, folder, file_path) -> None:
        """

        """
        # file info
        self.folder = folder
        self.file_path = file_path

        # plugin data
        self.name = ""
        self.code_file_path = ""
        self.icon_path = ""

        self.main_fcn: PluginFunction = PluginFunction()

        self.investments_fcn: PluginFunction = PluginFunction()

        self.icon: QPixmap | None = None

        with open(file_path, 'r') as f:
            data = json.load(f)
            self.parse(data)
            self.read_plugin()

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    def to_dict(self) -> Dict[str, str | Dict[str, str]]:
        """
        To dict
        :return: string, string dictionary to save in json format
        """
        return {
            "name": self.name,
            "path": self.code_file_path,
            "icon_path": self.icon_path,
            "main_fcn": self.main_fcn.to_dict(),
            "investments_fcn": self.investments_fcn.to_dict(),
        }

    def parse(self, data: Dict[str, str | Dict[str, str]]) -> None:
        """
        Parse data
        :param data: Data like the one saved
        """
        self.name = data.get('name', '')
        self.code_file_path = data.get('path', '')
        self.icon_path = data.get('icon_path', '')

        if 'main_fcn' in data.keys():
            self.main_fcn.parse(data['main_fcn'])

        if 'investments_fcn' in data.keys():
            self.investments_fcn.parse(data['investments_fcn'])

    def read_plugin(self) -> None:
        """
        Read the pointed plugin
        """
        plugin_path = os.path.join(self.folder, self.code_file_path)

        if os.path.exists(plugin_path):

            if plugin_path.endswith('.py'):

                # hot read python file searching for the functions declared
                self.main_fcn.read_plugin(plugin_path)
                self.investments_fcn.read_plugin(plugin_path)

            else:
                print(f"Plugin {self.name}: Path {plugin_path} not a python file :(")
        else:
            print(f"Plugin {self.name}: Path {plugin_path} not found :/")

        # Read the icon file if available
        icon_path = os.path.join(self.folder, self.icon_path)
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
        self.plugins: Dict[str, PluginInfo] = dict()
        self.read()

    def to_data(self) -> List[Dict[str, str]]:
        """
        Get dictionary of plugin data
        :return:
        """
        return [pl.to_dict() for key, pl in self.plugins.items()]

    def read(self) -> None:
        """
        Thead the plugins info file
        :return:
        """
        self.plugins.clear()

        # List all JSON files in the folder
        folder = plugins_path()
        # for file in os.listdir(folder):
        for subdir, dirs, files in os.walk(folder):
            for file in files:
                if file.endswith('.plugin.json'):
                    file_path = os.path.join(subdir, file)

                    try:
                        pl = PluginInfo(subdir, file_path)
                        self.plugins[pl.name] = pl

                    except json.JSONDecodeError as e:
                        print("Error reading the plugins index", e)


def load_function_from_file_path(file_path: str, function_name: str):
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
