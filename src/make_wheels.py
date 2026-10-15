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
from veragrid_packaging import build_wheel, collect_extra_package_files, read_module_constant

SRC_ROOT = os.path.abspath(os.path.dirname(__file__))
__VeraGridEngine_VERSION__ = read_module_constant(
    os.path.join(SRC_ROOT, 'VeraGridEngine', '__version__.py'),
    '__VeraGridEngine_VERSION__',
)
__VeraGrid_VERSION__ = read_module_constant(
    os.path.join(SRC_ROOT, 'VeraGrid', '__version__.py'),
    '__VeraGrid_VERSION__',
)
__VeraGridServer_VERSION__ = read_module_constant(
    os.path.join(SRC_ROOT, 'VeraGridServer', '__version__.py'),
    '__VeraGridServer_VERSION__',
)

if __name__ == "__main__":

    if __VeraGridEngine_VERSION__ == __VeraGrid_VERSION__:  # both packages' versions must be exactly the same
        veragrid_extra_files: list[str] = list()
        veragrid_engine_extra_files: list[str] = collect_extra_package_files(
            pkg_name='VeraGridEngine',
            relative_folder=os.path.join('data', 'fmu'),
            suffixes=['.c', '.h'],
        )
        veragrid_engine_extra_files.extend(
            collect_extra_package_files(
                pkg_name='VeraGridEngine',
                relative_folder=os.path.join('data', 'native_worker'),
                suffixes=['.c', '.h'],
            )
        )
        veragrid_translation_files: list[str] = collect_extra_package_files(
            pkg_name='VeraGrid',
            relative_folder=os.path.join('Gui', 'translations'),
            suffixes=['.qm'],
        )

        # Keep the runtime data files explicit because the custom wheel builder does not read MANIFEST.in.
        veragrid_extra_files.append(os.path.join("data", "cables.csv"))
        veragrid_extra_files.append(os.path.join("data", "VeraGrid.ico"))
        veragrid_extra_files.append(os.path.join("data", "VeraGrid.svg"))
        veragrid_extra_files.append(os.path.join("data", "sequence_lines.csv"))
        veragrid_extra_files.append(os.path.join("data", "transformers.csv"))
        veragrid_extra_files.append(os.path.join("data", "wires.csv"))

        # Add the translation assets explicitly so the handmade wheel includes them.
        veragrid_extra_files.extend(veragrid_translation_files)

        _long_description = "# VeraGrid \n"
        _long_description += "This software aims to be a complete platform for power systems research and simulation.)\n"
        _long_description += "\n"
        _long_description += "[Watch the video https](https://youtu.be/SY66WgLGo54)\n"
        _long_description += "[Check out the documentation](https://gridcal.readthedocs.io)\n"
        _long_description += "\n"
        _long_description += "## Installation\n"
        _long_description += "\n"
        _long_description += "pip install VeraGridEngine\n"
        _long_description += "\n"
        _long_description += "For more options (including a standalone setup one), follow the\n"
        _long_description += "[installation instructions]( https://gridcal.readthedocs.io/en/latest/getting_started/install.html)\n"
        _long_description += "from the project's [documentation](https://gridcal.readthedocs.io)\n"

        _description_content_type = 'text/markdown'

        _summary = 'VeraGrid is a Power Systems simulation program intended for professional use and research'

        _keywords = 'power systems planning'

        _author = 'Santiago Peñate Vera et. Al.'

        _author_email = 'spenate@eroots.tech'

        _home_page = 'https://github.com/SanPen/VeraGrid'

        _classifiers_list = [
            'Programming Language :: Python :: 3.10',
        ]

        _requires_pyhon = '>=3.6'

        _provides_extra = 'gch5 files'

        _license_ = 'MPL2'

        build_wheel(pkg_name='VeraGridEngine',
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
                    extra_files=veragrid_engine_extra_files
                    )

        build_wheel(pkg_name='VeraGridServer',
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
                    long_description=_long_description
                    )

        build_wheel(pkg_name='VeraGrid',
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
                    ext_filter=['py'],
                    extra_files=veragrid_extra_files
                    )

    else:

        print(__VeraGridEngine_VERSION__, 'and', __VeraGrid_VERSION__, "are different :(")
