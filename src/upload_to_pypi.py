"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.30.tar.gz

"""
import os
from GridCalEngine.__version__ import __GridCalEngine_VERSION__
from GridCal.__version__ import __GridCal_VERSION__
from GridCalServer.__version__ import __GridCalServer_VERSION__
from gridcal_packaging import publish
from GridCal.Gui.update_gui_common import convert_resource_file, convert_ui_file


def update_gui_to_make_sure():
    # pyrcc5 icons.qrc -o icons_rc.py
    # pyuic5 -x MainWindow.ui -o MainWindow.py

    rcc_cmd = 'pyside6-rcc'
    uic_cmd = 'pyside6-uic'

    if os.name == 'nt':
        rcc_cmd += '.exe'
        uic_cmd += '.exe'

    # define the path to MAIN
    __here__ = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(__here__, 'GridCal', 'Gui', 'Main')

    convert_resource_file(source=os.path.join(path, 'icons.qrc'), rcc_cmd=rcc_cmd)

    for f in ['MainWindow.ui', 'ConsoleLog.ui']:
        convert_ui_file(source=os.path.join(path, f), uic_cmd=uic_cmd)


def check_versions() -> bool:
    if __GridCalEngine_VERSION__ != __GridCal_VERSION__:  # both packages' versions must be exactly the same
        print(__GridCalEngine_VERSION__, 'and', __GridCal_VERSION__, "are different :(")
        return False

    if __GridCalEngine_VERSION__ != __GridCalServer_VERSION__:  # both packages' versions must be exactly the same
        print(__GridCalEngine_VERSION__, 'and', __GridCalServer_VERSION__, "are different :(")
        return False

    return True


if __name__ == "__main__":

    update_gui_to_make_sure()

    if check_versions():

        _long_description = "# GridCal \n"
        _long_description += "This software aims to be a complete platform for power systems research and simulation.)\n"
        _long_description += "\n"
        _long_description += "[Watch the video https](https://youtu.be/SY66WgLGo54)\n"
        _long_description += "[Check out the documentation](https://gridcal.readthedocs.io)\n"
        _long_description += "\n"
        _long_description += "## Installation\n"
        _long_description += "\n"
        _long_description += "pip install GridCal\n"
        _long_description += "\n"
        _long_description += "For more options (including a standalone setup one), follow the\n"
        _long_description += "[installation instructions]( https://gridcal.readthedocs.io/en/latest/getting_started/install.html)\n"
        _long_description += "from the project's [documentation](https://gridcal.readthedocs.io)\n"

        _description_content_type = 'text/markdown'

        _summary = 'GridCal is a Power Systems simulation program intended for professional use and research'

        _keywords = 'power systems planning'

        _author = 'Santiago Peñate Vera et. Al.'

        _author_email = 'santiago@gridcal.org'

        _home_page = 'https://github.com/SanPen/GridCal'

        _classifiers_list = [
            'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
            'Programming Language :: Python :: 3.10',
        ]

        _requires_pyhon = '>=3.8'

        _provides_extra = 'gch5'

        _license_ = 'LGPL'

        publish(pkg_name='GridCalEngine',
                setup_path=os.path.join('GridCalEngine', 'setup.py'),
                version=__GridCalEngine_VERSION__,
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
                ext_filter=['.py', '.csv', '.txt']
                )

        publish(pkg_name='GridCal',
                setup_path=os.path.join('GridCal', 'setup.py'),
                version=__GridCal_VERSION__,
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
                ext_filter=['.py', '.csv', '.txt']
                )

        publish(pkg_name='GridCalServer',
                setup_path=os.path.join('GridCalServer', 'setup.py'),
                version=__GridCalServer_VERSION__,
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
                ext_filter=['.py', '.csv', '.txt', '.ico']
                )

    else:
        print("Failed because of versions incompatibility")
