# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import tarfile
import zipfile
import hashlib
from pathlib import Path
from typing import List, Tuple
from subprocess import call


def file_hash(filename: str) -> str:
    """
    Python program to find SHA256 hash string of a file
    :param filename:
    :return:
    """
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


def build_setup_cfg() -> str:
    """
    Generate the content of setup.cgf
    :return:
    """
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
    """
    Generate the content of PKG-INFO
    :param name:
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
    :return:
    """
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


def get_record_info(files):
    """

    :param files:
    :return:
    """
    val = ""
    for name, file_path in files:
        hsh = file_hash(filename=file_path)
        val += f"{file_path},sha256={hsh}\n"

    return val


def get_wheel_info():
    val = ""
    val += "Wheel-Version: 1.0\n"
    val += "Generator: VeraGrid packaging\n"
    val += "Root-Is-Purelib: true\n"
    val += "Tag: py3-none-any"
    return val


def check_ext(filename, ext_filter) -> bool:
    """
    Check of the file complies with the list of extensions
    :param filename: filename
    :param ext_filter: list of extnsions
    :return: true/false
    """
    for ext in ext_filter:
        if filename.endswith(ext):
            return True
    return False


def find_pkg_files(path: str, ext_filter=['.py']) -> List[Tuple[str, str]]:
    """
    Get list
    :param path: path to traverse
    :param ext_filter: extensions of files to include
    :return: list of [filename, complete path
    """
    files_list = list()
    for (dirpath, dirnames, filenames) in os.walk(path):
        for fname in filenames:
            if check_ext(filename=fname, ext_filter=ext_filter):
                pth = os.path.join(dirpath, fname)
                files_list.append((fname, pth))

    return files_list


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
                     folder_to_save='dist',
                     ext_filter=['py'],
                     extra_files=()):
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
    :param extra_files:
    :return:
    """
    pkg_name2 = pkg_name.lower() + '-' + version
    filename = pkg_name2 + '.tar.gz'
    output_filename = os.path.join(folder_to_save, filename)

    files = find_pkg_files(path=pkg_name,
                           ext_filter=ext_filter)

    for f in extra_files:
        files.append((f, os.path.join(pkg_name, f)))

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

    if not os.path.exists('dist'):
        os.makedirs('dist')

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


def build_wheel(pkg_name: str,
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
                folder_to_save='dist',
                ext_filter=['py'],
                extra_files=()):
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
    :param extra_files:
    :return:
    """

    if not os.path.exists(folder_to_save):
        os.makedirs(folder_to_save)

    pkg_name2 = pkg_name + '-' + version
    filename = pkg_name2 + '-py3-none-any.whl'
    dist_info_path = pkg_name2 + '.dist-info'
    output_filename = os.path.join(folder_to_save, filename)

    files = find_pkg_files(path=pkg_name,
                           ext_filter=ext_filter)

    for f in extra_files:
        files.append((f, os.path.join(pkg_name, f)))

    """
    The .dist-info directory

    Wheel .dist-info directories include at a minimum METADATA, WHEEL, and RECORD.
    
    METADATA is the package metadata, the same format as PKG-INFO as found at the root of sdists.
    
    WHEEL is the wheel metadata specific to a build of the package.
    
    RECORD is a list of (almost) all the files in the wheel and their secure hashes. 
    Unlike PEP 376, every file except RECORD, which cannot contain a hash of itself, 
    must include its hash. The hash algorithm must be sha256 or better; specifically, 
    md5 and sha1 are not permitted, as signed wheel files rely on the strong hashes in RECORD 
    to validate the integrity of the archive.
    """
    metadata_info = build_pkg_info(name=pkg_name,
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
    wheel_info = get_wheel_info()
    record_info = get_record_info(files)

    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as tar:
        for name, file_path in files:
            if not name.endswith('setup.py'):
                tar.write(file_path, arcname=file_path)

        # add the setup where it belongs
        # tar.write(setup_path, arcname=os.path.join(pkg_name, 'setup.py'))

        # add
        # tar.writestr(os.path.join(pkg_name2, 'PKG-INFO'), data=pkg_info)
        # tar.writestr(os.path.join(pkg_name2, 'setup.cfg'), data=setup_cfg_path)
        tar.writestr(os.path.join(dist_info_path, 'METADATA'), data=metadata_info)
        tar.writestr(os.path.join(dist_info_path, 'WHEEL'), data=wheel_info)
        tar.writestr(os.path.join(dist_info_path, 'RECORD'), data=record_info)

    # os.delete(pkg_info_path)
    # os.delete(setup_cfg_path)
    # os.delete(metadata_f_path)
    # os.delete(wheel_f_path)
    # os.delete(record_f_path)
    # os.removedirs(dist_info_path)

    return output_filename


def read_pypirc() -> Tuple[str, str]:
    """
    Read the pypirc file located in home
    :return: user, password
    """
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


def check_all_folders_contain_init_py(directory, exceptions=('__pycache__')):
    """

    :param directory:
    :param exceptions:
    :return:
    """
    for root, dirs, files in os.walk(directory):

        root_name = os.path.basename(root)
        if root_name not in exceptions:
            # Check if current folder is not the root folder
            if '__init__.py' not in files:
                raise Exception(f"Missing __init__.py in {root}")
    return True


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
            long_description: str,
            ext_filter=('.py', '.csv', '.txt'),
            exeption_paths=('__pycache__', 'icons', 'svg'),
            extra_files=()):
    """
    Publish package to Pypi using twine
    :param pkg_name: name of the package (i.e VeraGrid)
    :param setup_path: path to the package setup.py (i.e. VeraGrid/setup.py)
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
    :param ext_filter:
    :param exeption_paths:
    :param extra_files:
    """

    check_all_folders_contain_init_py(directory=os.path.dirname(setup_path),
                                      exceptions=exeption_paths)

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
                             ext_filter=ext_filter,
                             extra_files=extra_files)

    # check the tar.gz file
    call([sys.executable, '-m', 'twine', 'check', fpath])

    user, pwd = read_pypirc()

    # upload the tar.gz file
    call([sys.executable, '-m', 'twine', 'upload',
          '--repository', 'pypi',
          '--username', user,
          '--password', pwd,
          fpath])
