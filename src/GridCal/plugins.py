# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import sys
import importlib
import importlib.util
import hashlib
from typing import List, Dict, TYPE_CHECKING, Callable
import json
import zipfile
import shutil
from PySide6.QtGui import QPixmap

from GridCalEngine.IO.file_system import plugins_path
from GridCal.__version__ import __GridCal_VERSION__

if TYPE_CHECKING:
    from GridCal.Gui.Main.SubClasses.Settings.configuration import ConfigurationMain


class PluginFunction:
    """
    Class to handle external function pointers
    """

    def __init__(self) -> None:

        self.name = ""
        self.alias = ""
        self.call_gui = False
        self.function_ptr = None

    def get_pointer_lambda(self, gui_instance: ConfigurationMain) -> Callable:
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
        return lambda e=True, func=self.function_ptr: func(gui_instance)

    def to_dict(self) -> Dict[str, str]:
        """
        To dict
        :return: string, string dictionary to save in json format
        """
        return {
            "name": self.name,
            "alias": self.alias,
            "call_gui": self.call_gui,
        }

    def parse(self, data: Dict[str, str]) -> None:
        """
        Parse data
        :param data: Data like the one saved
        """
        self.name = data.get('name', '').strip()
        self.alias = data.get('alias', '').strip()
        self.call_gui = data.get('call_gui', False)

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
        self.version = "0.0.0"
        self.gridcal_version = "5.2.0"

        self.main_fcn: PluginFunction = PluginFunction()

        self.investments_fcn: PluginFunction = PluginFunction()

        self.icon: QPixmap | None = None

        if os.path.exists(file_path):
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
            "version": self.version,
            "gridcal_version": self.gridcal_version,
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
        self.version = data.get('version', '0.0.0')
        self.gridcal_version = data.get('gridcal_version', '5.2.0')
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

    def is_greater(self, other: "PluginInfo") -> int:

        v1_tuple = tuple(map(int, self.version.split(".")))
        v2_tuple = tuple(map(int, other.version.split(".")))

        # Compare the tuples
        if v1_tuple < v2_tuple:
            return 1
        elif v1_tuple > v2_tuple:
            return -1
        else:
            return 0

    def is_compatible(self) -> int:
        """
        Check if the plugin is compatible
        :return:
        """
        v1_tuple = tuple(map(int, __GridCal_VERSION__.split(".")))
        v2_tuple = tuple(map(int, self.gridcal_version.split(".")))

        # Compare the tuples
        if v1_tuple < v2_tuple:
            return False
        else:
            return True


class PluginsInfo:
    """
    Plugins information
    """

    def __init__(self) -> None:
        """

        """
        # add the plugins directory to the pythonpath
        sys.path.insert(0, plugins_path())

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


def pack_plugin(name: str,
                pkg_folder: str,
                python_file: str,
                main_name: str,
                icon_file: str,
                version: str,
                call_gui: bool,
                gridcal_version: str = "5.2.10"):
    """
    Create plugin package
    :param name: Name of the plugin
    :param pkg_folder: Source folder of the plugin
    :param python_file: main python file for the plugin (relative to pkg_folder)
    :param main_name: name of the main function within the python_file
    :param icon_file: icon file (relative to pkg_folder)
    :param version: Version of the plugin
    :param call_gui: does the main function
    :param gridcal_version: gridcal version of the plugin
    :return: final name of the plugin
    """
    plugin_data = {
        "plugins_tech_version": "1.0.0",
        "name": name,
        "path": python_file,
        "icon_path": icon_file,
        "version": version,
        "gridcal_version": gridcal_version,
        "main_fcn": {
            "name": main_name,
            "alias": name,
            "call_gui": call_gui
        }
    }

    v2 = version.replace(".", "_")
    filename_zip = f'{name}_{v2}.gcplugin'
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:

        folder_name = os.path.basename(pkg_folder)

        config_file = os.path.join(folder_name, "config.plugin.json")

        f_zip_ptr.writestr("manifest.json", json.dumps({
            "name": name,
            "folder": folder_name,
            "version": version,
            "config_file": config_file
        }))

        # save the config files
        f_zip_ptr.writestr(config_file, json.dumps(plugin_data))

        # Get the parent directory of the folder
        parent_folder = os.path.dirname(pkg_folder)

        for root, dirs, files in os.walk(pkg_folder):
            for file in files:
                file_path = os.path.join(root, file)
                # Add file to the zip archive, preserving folder structure
                f_zip_ptr.write(file_path, os.path.relpath(file_path, parent_folder))

    return filename_zip


def get_plugin_info(plugin_file: str) -> PluginInfo | None:
    with zipfile.ZipFile(plugin_file, 'r') as zipf:

        if "manifest.json" in zipf.namelist():
            # read the manifest
            with zipf.open("manifest.json") as json_file:
                data = json.load(json_file)
                info = PluginInfo("", "")
                info.parse(data)
                return info
        else:
            return None


def install_plugin(plugin_file: str):
    """

    :param plugin_file:
    :return:
    """

    plugins_pth = plugins_path()

    with zipfile.ZipFile(plugin_file, 'r') as zipf:

        # read the manifest
        with zipf.open("manifest.json") as json_file:
            data = json.load(json_file)

            folder_name = data.get("folder", None)

            dst_folder = os.path.join(plugins_pth, folder_name)
            if os.path.exists(dst_folder):
                shutil.rmtree(dst_folder)

        if folder_name is not None:
            for member in zipf.namelist():
                if member.startswith(f"{folder_name}/"):  # Replace with the folder you want to extract
                    zipf.extract(member, plugins_pth)
