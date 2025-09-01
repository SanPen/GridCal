# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/VeraGrid-2.30.tar.gz

"""
import os
import fnmatch
from VeraGridEngine.__version__ import __VeraGridEngine_VERSION__
from VeraGrid.__version__ import __VeraGrid_VERSION__
from VeraGridServer.__version__ import __VeraGridServer_VERSION__
from veragrid_packaging import publish
from VeraGrid.Gui.update_gui_common import convert_resource_file, convert_ui_file


def update_gui_to_make_sure():
    """

    :return:
    """
    # pyrcc5 icons.qrc -o icons_rc.py
    # pyuic5 -x MainWindow.ui -o MainWindow.py

    rcc_cmd = 'pyside6-rcc'
    uic_cmd = 'pyside6-uic'

    if os.name == 'nt':
        rcc_cmd += '.exe'
        uic_cmd += '.exe'

    # define the path to MAIN
    __here__ = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(__here__, 'VeraGrid', 'Gui', 'Main')

    convert_resource_file(source=os.path.join(path, 'icons.qrc'), rcc_cmd=rcc_cmd)

    for f in ['MainWindow.ui', 'ConsoleLog.ui']:
        convert_ui_file(source=os.path.join(path, f), uic_cmd=uic_cmd)




def search_text_in_python_files(directory, search_terms):
    """
    Search for a list of text strings in all Python files within a directory and its subdirectories.

    Parameters:
        directory (str): The directory to search in.
        search_terms (list): A list of text strings to search for.

    Returns:
        dict: A dictionary where keys are filenames and values are lists of lines containing the search terms.
    """
    results = {}

    # Walk through the directory and subdirectories
    for root, _, files in os.walk(directory):
        for filename in files:
            if fnmatch.fnmatch(filename, "*.py"):
                filepath = os.path.join(root, filename)

                # Open and read the file
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        lines = file.readlines()

                    # Search each line for the terms
                    matched_lines = []
                    for line_num, line in enumerate(lines, start=1):
                        for term in search_terms:
                            if term in line:
                                matched_lines.append(f"Line {line_num}: {line.strip()}")
                                break

                    if matched_lines:
                        results[filepath] = matched_lines

                except (UnicodeDecodeError, IOError) as e:
                    print(f"Error reading file {filepath}: {e}")

    if len(results) > 0:

        for file,matches in results.items():
            print(file, matches)

        raise Exception("Forbidden text found")


def check_versions() -> bool:
    """

    :return:
    """
    if __VeraGridEngine_VERSION__ != __VeraGrid_VERSION__:  # both packages' versions must be exactly the same
        print(__VeraGridEngine_VERSION__, 'and', __VeraGrid_VERSION__, "are different :(")
        return False

    if __VeraGridEngine_VERSION__ != __VeraGridServer_VERSION__:  # both packages' versions must be exactly the same
        print(__VeraGridEngine_VERSION__, 'and', __VeraGridServer_VERSION__, "are different :(")
        return False

    return True


if __name__ == "__main__":

    forbidden_text = [
        'from trunk',
        'import trunk',
        'from tests',
        'import tests'
    ]

    search_text_in_python_files(directory="VeraGrid", search_terms=forbidden_text)
    search_text_in_python_files(directory="VeraGridEngine", search_terms=forbidden_text)
    search_text_in_python_files(directory="VeraGridServer", search_terms=forbidden_text)

    update_gui_to_make_sure()

    if check_versions():

        _long_description = "# VeraGrid \n"
        _long_description += "This software aims to be a complete platform for power systems research and simulation.)\n"
        _long_description += "\n"
        _long_description += "[Watch the video https](https://youtu.be/SY66WgLGo54)\n"
        _long_description += "[Check out the documentation](https://veragrid.readthedocs.io)\n"
        _long_description += "\n"
        _long_description += "## Installation\n"
        _long_description += "\n"
        _long_description += "pip install veragrid\n"
        _long_description += "\n"
        _long_description += "For more options (including a standalone setup one), follow the\n"
        _long_description += "[installation instructions]( https://veragrid.readthedocs.io/en/latest/getting_started/install.html)\n"
        _long_description += "from the project's [documentation](https://veragrid.readthedocs.io)\n"

        _description_content_type = 'text/markdown'

        _summary = 'VeraGrid is a Power Systems simulation program intended for professional use and research'

        _keywords = 'power systems planning'

        _author = 'Santiago Peñate Vera et. Al.'

        _author_email = 'spenate@eroots.tech'

        _home_page = 'https://github.com/SanPen/VeraGrid'

        _classifiers_list = [
            'Programming Language :: Python :: 3.10',
        ]

        _requires_pyhon = '>=3.8'

        _provides_extra = 'gch5'

        _license_ = 'MPL2'

        publish(pkg_name='VeraGridEngine',
                setup_path=os.path.join('VeraGridEngine', 'setup.py'),
                version=__VeraGridEngine_VERSION__,
                summary=_summary,
                home_page=_home_page,
                author=_author,
                email=_author_email,
                license_=_license_,
                keywords=_keywords,
                classifiers_list=_classifiers_list,
                requires_pyhon=_requires_pyhon,
                description_content_type=_description_content_type,
                provides_extra=_provides_extra,
                long_description=_long_description,
                ext_filter=['.py', '.csv', '.txt'],
                exeption_paths=('__pycache__')
                )

        publish(pkg_name='VeraGrid',
                setup_path=os.path.join('VeraGrid', 'setup.py'),
                version=__VeraGrid_VERSION__,
                summary=_summary,
                home_page=_home_page,
                author=_author,
                email=_author_email,
                license_=_license_,
                keywords=_keywords,
                classifiers_list=_classifiers_list,
                requires_pyhon=_requires_pyhon,
                description_content_type=_description_content_type,
                provides_extra=_provides_extra,
                long_description=_long_description,
                ext_filter=['.py', '.csv', '.txt'],
                exeption_paths=('__pycache__', 'icons', 'svg'),
                extra_files=[
                    os.path.join("data", "cables.csv"),
                    os.path.join("data", "VeraGrid.ico"),
                    os.path.join("data", "VeraGrid.svg"),
                    os.path.join("data", "sequence_lines.csv"),
                    os.path.join("data", "transformers.csv"),
                    os.path.join("data", "wires.csv")
                ]
                )

        publish(pkg_name='VeraGridServer',
                setup_path=os.path.join('VeraGridServer', 'setup.py'),
                version=__VeraGridServer_VERSION__,
                summary=_summary,
                home_page=_home_page,
                author=_author,
                email=_author_email,
                license_=_license_,
                keywords=_keywords,
                classifiers_list=_classifiers_list,
                requires_pyhon=_requires_pyhon,
                description_content_type=_description_content_type,
                provides_extra=_provides_extra,
                long_description=_long_description,
                ext_filter=['.py', '.csv', '.txt', '.ico'],
                exeption_paths=('__pycache__')
                )

    else:
        print("Failed because of versions incompatibility")
