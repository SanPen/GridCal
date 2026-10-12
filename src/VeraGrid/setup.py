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
import ast
from pathlib import Path
from typing import Dict, List, Tuple

from setuptools import setup, find_packages

description: str = 'VeraGrid is a Power Systems simulation program intended for professional use and research'


def read_module_constant(constant_name: str) -> str:
    """
    Read one literal constant without importing the package being built.

    This keeps the isolated ``pip`` build independent from an existing
    VeraGrid installation.

    :param constant_name: Name of the literal assignment to read.
    :return: String representation of the assigned literal value.
    """
    src_root: Path = Path(__file__).resolve().parent
    version_file: Path = src_root / '__version__.py'

    if version_file.exists():
        module_ast: ast.Module = ast.parse(
            version_file.read_text(encoding='utf-8'),
            filename=str(version_file),
        )
        node: ast.stmt
        target: ast.expr
        for node in module_ast.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == constant_name:
                        return str(ast.literal_eval(node.value))
                    else:
                        pass
            else:
                pass
    else:
        pass

    raise FileNotFoundError(f'{constant_name} source file not found in {version_file}')


def read_long_description() -> str:
    """
    Read the nearest available package description.

    :return: Markdown description used by the package metadata.
    """
    src_root: Path = Path(__file__).resolve().parent
    candidates: Tuple[Path, ...] = (
        src_root / 'README.md',
        src_root.parent / 'README.md',
        src_root.parent.parent / 'README.md',
    )
    candidate: Path
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding='utf-8')
        else:
            pass

    return description


long_description: str = read_long_description()
__VeraGrid_VERSION__: str = read_module_constant('__VeraGrid_VERSION__')
src_root: Path = Path(__file__).resolve().parent
excluded_packages: Tuple[str, ...] = (
    'docs', 'docs.*', 'research', 'research.*', 'tests', 'tests.*',
    'tutorials', 'tutorials.*', 'VeraGridEngine', 'VeraGridEngine.*',
)
discovered_packages: List[str] = find_packages(where=str(src_root), exclude=excluded_packages)
package_names: List[str] = [''] * (len(discovered_packages) + 1)
package_names[0] = 'VeraGrid'
package_index: int
package: str
for package_index, package in enumerate(discovered_packages):
    package_names[package_index + 1] = 'VeraGrid.' + package

package_data: Dict[str, List[str]] = {
    'VeraGrid.Gui.translations': ['*.qm'],
    'VeraGrid.Gui.Widgets': ['*.qml', 'shaders/*.qsb'],
    'VeraGrid.data': [
        'cables.csv',
        'transformers.csv',
        'wires.csv',
        'sequence_lines.csv',
        'VeraGrid.svg',
        'VeraGrid.ico',
    ],
    'VeraGrid': ['LICENSE.txt', 'setup.py'],
}

dependencies: List[str] = ["numpy>=2.2.0,<3",
                "PySide6>=6.10.0",  # Qt 6.10 provides the current proxy-filter APIs used by the GUI
                "requests>=2.33.0",
                "urllib3>=2.7.0",
                "websockets>=9.1",
                "opencv-python>=4.10.0.84",
                "packaging>=25.0",
                "VeraGridEngine==" + __VeraGrid_VERSION__,  # the VeraGridEngine version must be exactly the same
                ]

extras_require: Dict[str, List[str]] = {
    'gch5 files': ["tables"]  # this is for h5 compatibility
}


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
    packages=package_names,  # Required
    package_dir={'VeraGrid': '.'},
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=dependencies,
    extras_require=extras_require,
    package_data=package_data,
    entry_points={
        'gui_scripts': [
            'veragrid = VeraGrid.ExecuteVeraGrid:runVeraGrid',
            'VeraGrid = VeraGrid.ExecuteVeraGrid:runVeraGrid',
        ],
    },
)
