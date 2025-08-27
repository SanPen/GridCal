# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
import os
import shutil
import platform
import subprocess
from setuptools import setup, find_packages
from setuptools.command.install import install

from VeraGrid.__version__ import __VeraGrid_VERSION__

here = os.path.abspath(os.path.dirname(__file__))

long_description = '''# VeraGrid

This software aims to be a complete platform for power systems research and simulation.

[Watch the video https](https://youtu.be/SY66WgLGo54)

[Check out the documentation](https://veragrid.readthedocs.io)


## Installation

pip install veragrid

For more options (including a standalone setup one), follow the
[installation instructions]( https://veragrid.readthedocs.io/en/latest/getting_started/install.html)
from the project's [documentation](https://veragrid.readthedocs.io)
'''

description = 'VeraGrid is a Power Systems simulation program intended for professional use and research'

base_path = os.path.join('VeraGrid')

pkgs_to_exclude = ['docs', 'research', 'tests', 'tutorials', 'VeraGridEngine']

packages = find_packages(exclude=pkgs_to_exclude)

# ... so we have to do the filtering ourselves
packages2 = list()
for package in packages:
    elms = package.split('.')
    excluded = False
    for exclude in pkgs_to_exclude:
        if exclude in elms:
            excluded = True

    if not excluded:
        packages2.append(package)

package_data = {'VeraGrid': ['*.md',
                            '*.rst',
                            'LICENSE.txt',
                            'setup.py',
                            'data/cables.csv',
                            'data/transformers.csv',
                            'data/wires.csv',
                            'data/sequence_lines.csv',
                            'data/VeraGrid.svg',
                            'data/VeraGrid.ico'],
                }

dependencies = ['setuptools>=41.0.1',
                'wheel>=0.37.2',
                "PySide6>=6.8.0",  # 5.14 breaks the UI generation for development, 6.7.0 breaks all
                "pytest>=7.2",
                "websockets",
                "opencv-python>=4.10.0.84",
                "packaging",
                "VeraGridEngine==" + __VeraGrid_VERSION__,  # the VeraGridEngine version must be exactly the same
                ]

extras_require = {
    'gch5 files': ["tables"]  # this is for h5 compatibility
}


class CustomInstall(install):
    def run(self):
        install.run(self)

        try:
            if platform.system() == "Linux":
                self.create_linux_menu_entry()
            elif platform.system() == "Windows":
                self.create_windows_shortcut()
            elif platform.system() == "macOS":
                self.create_macos_menu_entry()
            else:
                print("Unsupported OS: Installation might be incomplete.")
        except Exception as e:
            print("error creating the menu entry...", e)

    @staticmethod
    def create_linux_menu_entry():
        """

        :return:
        """
        icon_src = "data/VeraGrid.svg"

        # copy the icon
        dest_dir = f"~/.local/share/icons/hicolor/scalable/apps"
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy(icon_src, os.path.join(dest_dir, "VeraGrid.svg"))

        # Update the icon cache
        os.system("gtk-update-icon-cache /usr/share/icons/hicolor")

        desktop_entry = """
                [Desktop Entry]
                Name=VeraGrid
                Comment=Power systems done right
                Exec=veragrid
                Icon=~/.local/share/icons/hicolor/scalable/apps/VeraGrid.svg
                Terminal=false
                Type=Application
                Categories=Utility;Development;
                """
        path = os.path.expanduser("~/.local/share/applications/veragrid.desktop")
        with open(path, "w") as f:
            f.write(desktop_entry)
        os.chmod(path, 0o755)

    @staticmethod
    def create_windows_shortcut():
        """

        :return:
        """
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        shortcut_path = os.path.join(desktop, "VeraGrid.lnk")

        # Use powershell to create a shortcut
        powershell_command = f"""
        $WScriptShell = New-Object -ComObject WScript.Shell;
        $Shortcut = $WScriptShell.CreateShortcut("{shortcut_path}");
        $Shortcut.TargetPath = "veragrid";
        $Shortcut.Arguments = "";
        $Shortcut.IconLocation = "path/to/your/icon.ico";
        $Shortcut.Save();
        """
        subprocess.run(["powershell", "-Command", powershell_command], check=True)
        print(f"Windows shortcut created at: {shortcut_path}")

    @staticmethod
    def create_macos_menu_entry():
        """

        :return:
        """
        svg_icon_src = "data/VeraGrid.svg"
        dest_dir = "/Applications/VeraGrid/icons/"
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy(svg_icon_src, os.path.join(dest_dir, "VeraGrid.svg"))
        print("macOS icon installed.")

        app_dir = "/Applications/VeraGrid.app"
        os.makedirs(app_dir, exist_ok=True)
        plist_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>CFBundleName</key>
            <string>VeraGrid</string>
            <key>CFBundleIconFile</key>
            <string>VeraGrid</string>
            <key>CFBundleExecutable</key>
            <string>run_veragrid</string>
        </dict>
        </plist>
        """
        plist_path = os.path.join(app_dir, "Info.plist")
        with open(plist_path, "w") as f:
            f.write(plist_content)

        script_path = os.path.join(app_dir, "run_veragrid")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\nveragrid\n")
        os.chmod(script_path, 0o755)
        print(f"macOS application bundle created at {app_dir}.")


# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='VeraGrid',  # Required
    version=__VeraGrid_VERSION__,  # Required
    license='MPL2',
    description=description,  # Optional
    long_description=long_description,  # Optional
    long_description_content_type='text/markdown',  # Optional (see note above)
    url='https://github.com/SanPen/VeraGrid',  # Optional
    author='Santiago Peñate Vera et. Al.',  # Optional
    author_email='spenate@eroots.tech',  # Optional
    classifiers=[
        'Programming Language :: Python :: 3.8',
    ],
    keywords='power systems planning',  # Optional
    packages=packages2,  # Required
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=dependencies,
    extras_require=extras_require,
    package_data=package_data,
    entry_points={
        'console_scripts': [
            'veragrid = VeraGrid.ExecuteVeraGrid:runVeraGrid',
            'VeraGrid = VeraGrid.ExecuteVeraGrid:runVeraGrid',
        ],
    },
    cmdclass={'install': CustomInstall},
)
