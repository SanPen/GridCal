"""

#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.30.tar.gz

"""
import os
import sys
import tarfile
from pathlib import Path
from typing import List
from io import StringIO
from subprocess import call
from GridCalEngine.__version__ import __GridCalEngine_VERSION__
from GridCal.__version__ import __GridCal_VERSION__


def build_setup_cfg() -> str:
    val = '[egg_info]\n'
    val += 'tag_build = \n'
    val += 'tag_date = 0\n'

    return val


def build_pkg_info(name: str,
                   version: str,
                   summary: str,
                   home_page: str,
                   author: str,
                   email: str,
                   license_: str,
                   keywords: str,
                   classifiers_list: List[str],
                   requires_pyhon: str,
                   description_content_type: str,
                   provides_extra: str,
                   long_description: str):
    val = 'Metadata-Version: 2.1\n'
    val += "Name: " + name + '\n'
    val += "Version: " + version + '\n'
    val += "Summary: " + summary + '\n'
    val += "Home-page: " + home_page + '\n'
    val += "Author: " + author + '\n'
    val += "Author-email: " + email + '\n'
    val += "License: " + license_ + '\n'
    val += "Keywords: " + keywords + '\n'

    for classifier in classifiers_list:
        val += "Classifier:  " + classifier + '\n'

    val += "Requires-Python: " + requires_pyhon + '\n'
    val += "Description-Content-Type: " + description_content_type + '\n'
    val += "Provides-Extra: " + provides_extra + '\n'

    val += '\n' + long_description + '\n'

    return val


def check_ext(filename, ext_filter):
    """

    :param filename:
    :param ext_filter:
    :return:
    """
    for ext in ext_filter:
        if filename.endswith(ext):
            return True
    return False


def find_pkg_files(path: str, list_to_avoid: List[str] = (), ext_filter=['.py']):
    """

    :param path:
    :param list_to_avoid:
    :param ext_filter:
    :return:
    """
    f = list()
    for (dirpath, dirnames, filenames) in os.walk(path):
        for fname in filenames:
            if check_ext(filename=fname, ext_filter=ext_filter):
                pth = os.path.join(dirpath, fname)
                f.append((fname, pth))

    return f


def build_tar_gz_pkg(pkg_name: str,
                     setup_path: str,
                     version: str,
                     summary: str,
                     home_page: str,
                     author: str,
                     email: str,
                     license_: str,
                     keywords: str,
                     classifiers_list: List[str],
                     requires_pyhon: str,
                     description_content_type: str,
                     provides_extra: str,
                     long_description: str,
                     folder_to_save='dist', ext_filter=['py']):
    """

    :param pkg_name:
    :param setup_path:
    :param version:
    :param summary:
    :param home_page:
    :param author:
    :param email:
    :param license_:
    :param keywords:
    :param classifiers_list:
    :param requires_pyhon:
    :param description_content_type:
    :param provides_extra:
    :param long_description:
    :param folder_to_save:
    :param ext_filter:
    :return:
    """
    pkg_name2 = pkg_name + '-' + version
    filename = pkg_name2 + '.tar.gz'
    output_filename = os.path.join(folder_to_save, filename)

    files = find_pkg_files(path=pkg_name,
                           list_to_avoid=[],
                           ext_filter=ext_filter)

    pkg_info = build_pkg_info(name=pkg_name,
                              version=version,
                              summary=summary,
                              home_page=home_page,
                              author=author,
                              email=email,
                              license_=license_,
                              keywords=keywords,
                              classifiers_list=classifiers_list,
                              requires_pyhon=requires_pyhon,
                              description_content_type=description_content_type,
                              provides_extra=provides_extra,
                              long_description=long_description)
    pkg_info_path = 'pkg_info' + pkg_name
    with open(pkg_info_path, 'w') as f:
        f.write(pkg_info)

    setup_cfg = build_setup_cfg()
    setup_cfg_path = 'setup_cfg' + pkg_name
    with open(setup_cfg_path, 'w') as f:
        f.write(setup_cfg)

    with tarfile.open(output_filename, "w:gz") as tar:
        for name, file_path in files:
            if not name.endswith('setup.py'):
                tar.add(file_path, arcname=os.path.join(pkg_name2, file_path))

        # add the setup where it belongs
        tar.add(setup_path, arcname=os.path.join(pkg_name2, 'setup.py'))

        # add
        tar.add(pkg_info_path, arcname=os.path.join(pkg_name2, 'PKG-INFO'))
        tar.add(setup_cfg_path, arcname=os.path.join(pkg_name2, 'setup.cfg'))

    os.remove(pkg_info_path)
    os.remove(setup_cfg_path)

    return output_filename


def read_pypirc():

    home = Path.home()
    path = os.path.join(home, 'pypirc')

    with open(path) as file:
        lines = [line.rstrip() for line in file]

    user = ''
    pwd = ''
    for line in lines:
        if '=' in line:
            key, val = line.split('=')

            if key.strip() == 'username':
                user = val.strip()
            elif key.strip() == 'password':
                pwd = val.strip()

    return user, pwd


def publish(pkg_name: str,
            setup_path: str,
            version: str,
            summary: str,
            home_page: str,
            author: str,
            email: str,
            license_: str,
            keywords: str,
            classifiers_list: List[str],
            requires_pyhon: str,
            description_content_type: str,
            provides_extra: str,
            long_description: str):
    """
    Publish package to Pypi using twine
    :param pkg_name: name of the package (i.e GridCal)
    :param setup_path: path to the package setup.py (i.e. GridCal/setup.py)
    :param version: verison of the package (i.e. 5.1.0)
    :param summary:
    :param home_page:
    :param author:
    :param email:
    :param license_:
    :param keywords:
    :param classifiers_list:
    :param requires_pyhon:
    :param description_content_type:
    :param provides_extra:
    :param long_description:
    :return:
    """

    # build the tar.gz file
    fpath = build_tar_gz_pkg(pkg_name=pkg_name,
                             setup_path=setup_path,
                             version=version,
                             summary=summary,
                             home_page=home_page,
                             author=author,
                             email=email,
                             license_=license_,
                             keywords=keywords,
                             classifiers_list=classifiers_list,
                             requires_pyhon=requires_pyhon,
                             description_content_type=description_content_type,
                             provides_extra=provides_extra,
                             long_description=long_description,
                             folder_to_save='dist',
                             ext_filter=['.py', '.csv', '.txt'])

    # check the tar.gz file
    call([sys.executable, '-m', 'twine', 'check', fpath])

    user, pwd = read_pypirc()

    # upload the tar.gz file
    call([sys.executable, '-m', 'twine', 'upload',
          '--repository', 'pypi',
          '--username', user,
          '--password', pwd,
          fpath])


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
                long_description=_long_description
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
                long_description=_long_description
                )

    else:

        print(__GridCalEngine_VERSION__, 'and', __GridCal_VERSION__, "are different :(")
