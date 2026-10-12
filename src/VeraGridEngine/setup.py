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
    VeraGridEngine installation.

    :param constant_name: Name of the literal assignment to read.
    :return: String representation of the assigned literal value.
    """
    src_root: Path = Path(__file__).resolve().parent
    candidates: Tuple[Path, ...] = (
        src_root / '__version__.py',
        src_root / 'VeraGridEngine' / '__version__.py',
    )
    candidate: Path
    node: ast.stmt
    target: ast.expr
    for candidate in candidates:
        if candidate.exists():
            module_ast: ast.Module = ast.parse(
                candidate.read_text(encoding='utf-8'),
                filename=str(candidate),
            )
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

    raise FileNotFoundError(f'{constant_name} source file not found next to setup.py or in VeraGridEngine/')


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
__VeraGridEngine_VERSION__: str = read_module_constant('__VeraGridEngine_VERSION__')
src_root: Path = Path(__file__).resolve().parent
excluded_packages: Tuple[str, ...] = (
    'docs', 'docs.*', 'research', 'research.*', 'tests', 'tests.*',
    'tutorials', 'tutorials.*', 'VeraGrid', 'VeraGrid.*',
)
discovered_packages: List[str] = find_packages(where=str(src_root), exclude=excluded_packages)
package_names: List[str] = [''] * (len(discovered_packages) + 1)
package_names[0] = 'VeraGridEngine'
package_index: int
package: str
for package_index, package in enumerate(discovered_packages):
    package_names[package_index + 1] = 'VeraGridEngine.' + package
package_data: Dict[str, List[str]] = {
    'VeraGridEngine': [
        'LICENSE.txt',
        'setup.py',
        'data/fmu/**/*.c',
        'data/fmu/**/*.h',
    ],
    'VeraGridEngine.IO.manufacturer_native': [
        'native_worker/source/*.c',
        'native_worker/source/*.h',
        'native_worker/windows_x86/*.exe',
        'native_worker/windows_x86/*.json',
    ],
}

dependencies: List[str] = ["numpy>=2.2.0",
                "autograd>=1.7.0",
                "scipy>=1.10.0",
                "networkx>=3.6.1",
                "pandas>=2.2.3",
                "highspy>=1.8.0",
                "xlwt>=1.3.0",
                "xlrd>=2.0.2",
                "openpyxl>=3.1.5",
                "chardet>=5.2.0",  # for the psse files character detection
                "scikit-learn>=1.5.0",
                "geopy>=2.4.1",
                "h5py>=3.12.0",
                "cbcbox>=2.935",
                "numba>=0.61",  # to compile routines natively
                "pyproj>=3.7.2",
                "pulp>=4.0.0",
                "pyarrow>=23.0.1",
                "windpowerlib>=0.2.2",
                "pvlib>=0.14.0",
                "rdflib>=7.5.0",
                "pymoo>=0.6",
                "websockets>=9.1",
                "brotli>=1.2.0",
                "opencv-python>=4.10.0.84",
                "fmpy>=0.3.22",
                ]

extras_require: Dict[str, List[str]] = {
    'gch5 files': ["tables"]  # this is for h5 compatibility
}
# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='VeraGridEngine',  # Required
    version=__VeraGridEngine_VERSION__,  # Required
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
    package_dir={'VeraGridEngine': '.'},
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=dependencies,
    extras_require=extras_require,
    package_data=package_data,
)
