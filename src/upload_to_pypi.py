"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.30.tar.gz

"""
import os
from GridCalEngine.__version__ import __GridCalEngine_VERSION__
from GridCal.__version__ import __GridCal_VERSION__
from gridcal_packaging import publish


if __name__ == "__main__":

    if __GridCalEngine_VERSION__ == __GridCal_VERSION__:  # both packages' versions must be exactly the same

        _long_description = "# GridCal \n"
        _long_description += "This software aims to be a complete platform for power systems research and simulation.)\n"
        _long_description += "\n"
        _long_description += "[Watch the video https](https://youtu.be/SY66WgLGo54)\n"
        _long_description += "[Check out the documentation](https://gridcal.readthedocs.io)\n"
        _long_description += "\n"
        _long_description += "## Installation\n"
        _long_description += "\n"
        _long_description += "pip install GridCalEngine\n"
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

        _requires_pyhon = '>=3.6'

        _provides_extra = 'gch5 files'

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

    else:

        print(__GridCalEngine_VERSION__, 'and', __GridCal_VERSION__, "are different :(")
