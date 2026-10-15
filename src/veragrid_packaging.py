# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import tarfile
import zipfile
import hashlib
import ast
import time
import urllib.error
import urllib.request
from http.client import HTTPResponse
from pathlib import Path
from typing import List, Tuple
from subprocess import run


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
        val += f"{file_path}, sha256={hsh}\n"

    return val


def get_wheel_info():
    """
    Get the pkg information
    :return:
    """
    val = ""
    val += "Wheel-Version: 1.0\n"
    val += "Generator: VeraGrid packaging\n"
    val += "Root-Is-Purelib: true\n"
    val += "Tag: py3-none-any"
    return val


def check_ext(filename: str, ext_filter: List[str]) -> bool:
    """
    Check of the file complies with the list of extensions
    :param filename: filename
    :param ext_filter: list of extensions
    :return: true/false
    """
    for ext in ext_filter:
        if filename.endswith(ext):
            return True
    return False


def find_pkg_files(path: str, ext_filter: List[str]) -> List[Tuple[str, str]]:
    """
    Get list
    :param path: path to traverse
    :param ext_filter: extensions of files to include
    :return: list of [filename, complete path
    """
    if ext_filter is None:
        ext_filter = ['py']

    excluded_directories: set[str] = set()
    files_list = list()

    excluded_directories.add('__pycache__')
    excluded_directories.add('build')
    excluded_directories.add('dist')

    for (dirpath, dirnames, filenames) in os.walk(path):
        filtered_dirnames: List[str] = list()

        # Skip generated packaging folders so the wheel only contains source assets.
        for dirname in dirnames:
            if dirname in excluded_directories:
                pass
            elif dirname.endswith('.egg-info'):
                pass
            else:
                filtered_dirnames.append(dirname)

        dirnames[:] = filtered_dirnames

        for fname in filenames:
            if check_ext(filename=fname, ext_filter=ext_filter):
                pth = os.path.join(dirpath, fname)
                files_list.append((fname, pth))

    return files_list


def collect_extra_package_files(pkg_name: str, relative_folder: str, suffixes: List[str]) -> List[str]:
    """
    Collect package-relative files that must be included explicitly.
    :param pkg_name: package root folder name
    :param relative_folder: folder inside the package to inspect
    :param suffixes: allowed file suffixes
    :return: list of package-relative file paths
    """
    package_path: Path = Path(__file__).resolve().parent / pkg_name
    folder_path: Path = package_path / relative_folder
    allowed_suffixes: set[str] = set()
    extra_files: List[str] = list()

    # Normalize the suffix list once so each file test stays explicit.
    for suffix in suffixes:
        normalized_suffix: str = suffix.lower()
        allowed_suffixes.add(normalized_suffix)

    # Missing folders are tolerated because some package variants may not ship these assets.
    if folder_path.exists():
        # Traverse recursively so nested assets are picked up without adding more packaging code later.
        for file_path in sorted(folder_path.rglob('*')):
            if file_path.is_file():
                file_suffix: str = file_path.suffix.lower()

                # Keep only the requested asset types.
                if file_suffix in allowed_suffixes:
                    relative_path: Path = file_path.relative_to(package_path)
                    extra_files.append(str(relative_path))
                else:
                    pass
            else:
                pass
    else:
        pass

    return extra_files


def read_module_constant(module_path: str | Path, constant_name: str) -> str:
    """
    Read a simple module-level constant without importing the package.
    """
    module_file = Path(module_path)
    module_ast = ast.parse(module_file.read_text(encoding='utf-8'), filename=str(module_file))

    for node in module_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == constant_name:
                    value = ast.literal_eval(node.value)
                    return str(value)

    raise ValueError(f"Constant {constant_name!r} not found in {module_file}")


def wait_for_pypi_release_index(pkg_name: str, version: str) -> None:
    """Wait until PyPI's pip-facing index lists the uploaded source archive.

    :param pkg_name: Distribution name as uploaded to PyPI.
    :param version: Uploaded release version.
    :return: None.
    :raises RuntimeError: If PyPI does not expose the archive within one minute.
    """
    normalized_name: str = pkg_name.lower().replace('_', '-').replace('.', '-')
    index_url: str = f"https://pypi.org/simple/{normalized_name}/"
    expected_filename: str = f"{normalized_name}-{version}.tar.gz"
    attempt: int = 0
    max_attempts: int = 10
    retry_interval: float = 4.0

    while attempt < max_attempts:
        attempt += 1
        simple_index: str = ''

        try:
            response: HTTPResponse = urllib.request.urlopen(index_url, timeout=2)
            with response:
                simple_index = response.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError):
            simple_index = ''

        if expected_filename in simple_index:
            print(f"Verified {pkg_name} {version} on PyPI's pip index")
            return
        else:
            if attempt < max_attempts:
                time.sleep(retry_interval)
            else:
                raise RuntimeError(
                    f"PyPI accepted {pkg_name} {version}, but {expected_filename} "
                    f"did not appear at {index_url} after {max_attempts} checks"
                )


def get_repo_readme_path() -> Path | None:
    """
    Return the top-level README used for package descriptions when available.
    """
    candidate = Path(__file__).resolve().parent.parent / 'README.md'
    if candidate.exists():
        return candidate

    return None


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
                     ext_filter: List[str] | None= None,
                     extra_files=(),
                     flatten_package_root: bool = False):
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
    :param flatten_package_root: Place package files beside setup.py in the source archive.
    :return:
    """
    pkg_name2 = pkg_name.lower() + '-' + version
    filename = pkg_name2 + '.tar.gz'

    if ext_filter is None:
        ext_filter = ['py']

    if not os.path.exists(folder_to_save):
        os.makedirs(folder_to_save)

    output_filename = os.path.join(folder_to_save, filename)

    package_root: Path = Path(setup_path).resolve().parent
    files = find_pkg_files(path=str(package_root),
                           ext_filter=ext_filter)

    for f in extra_files:
        files.append((f, str(package_root / f)))

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

    readme_path = get_repo_readme_path()

    with tarfile.open(output_filename, "w:gz") as tar:
        for name, file_path in files:
            if not name.endswith('setup.py'):
                archive_path: Path = Path(file_path).relative_to(package_root)
                if flatten_package_root:
                    pass
                else:
                    archive_path = Path(pkg_name) / archive_path
                tar.add(file_path, arcname=os.path.join(pkg_name2, archive_path))

        # add the setup where it belongs
        tar.add(setup_path, arcname=os.path.join(pkg_name2, 'setup.py'))

        # add
        tar.add(pkg_info_path, arcname=os.path.join(pkg_name2, 'PKG-INFO'))
        tar.add(setup_cfg_path, arcname=os.path.join(pkg_name2, 'setup.cfg'))
        if readme_path is not None:
            tar.add(readme_path, arcname=os.path.join(pkg_name2, 'README.md'))

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
                ext_filter: List[str] | None= None,
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

    if ext_filter is None:
        ext_filter = ['py']

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
    readme_path = get_repo_readme_path()

    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as tar:
        for name, file_path in files:
            if not name.endswith('setup.py'):
                tar.write(file_path, arcname=file_path)

        if readme_path is not None:
            tar.write(readme_path, arcname='README.md')

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


def check_all_folders_contain_init_py(
        directory: str,
        exceptions: tuple[str, ...] = ('__pycache__',),
) -> bool:
    """Validate package folders while pruning explicitly excluded subtrees.

    A one-part exception matches an exact directory name at any depth. An
    exception containing multiple path parts matches one exact path relative
    to the package root. Descendants of a matched directory are not inspected.

    :param directory: Package root to validate, relative to this module or absolute.
    :param exceptions: Exact directory names or package-relative subtree paths to prune.
    :return: ``True`` when every non-excluded directory is a Python package.
    :raises Exception: If a non-excluded directory has no ``__init__.py`` file.
    """
    module_root: Path = Path(__file__).resolve().parent
    package_root: Path = module_root / directory
    excluded_names: set[str] = set()
    excluded_relative_paths: set[Path] = set()

    # Preserve exact-name exclusions while allowing one precise resource subtree.
    for exception in exceptions:
        exception_path: Path = Path(exception)
        if len(exception_path.parts) == 1:
            excluded_names.add(exception)
        else:
            excluded_relative_paths.add(exception_path)

    for root, directories, files in os.walk(package_root):
        current_root: Path = Path(root)
        relative_root: Path = current_root.relative_to(package_root)
        retained_directories: list[str] = list()

        # Pruning here prevents excluded resource descendants from being visited.
        for directory_name in directories:
            relative_directory: Path = relative_root / directory_name
            if directory_name in excluded_names or relative_directory in excluded_relative_paths:
                pass
            else:
                retained_directories.append(directory_name)
        directories[:] = retained_directories

        # Every directory that remains in the traversal must be importable.
        if '__init__.py' not in files:
            raise Exception(f"Missing __init__.py in {root}")
        else:
            pass
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
            extra_files=(),
            flatten_package_root: bool = False):
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
    :param flatten_package_root: Match setup.py files that map their package root to the archive root.
    """

    setup_file: Path = Path(setup_path).resolve()
    package_root: Path = setup_file.parent
    source_root: Path = package_root.parent

    check_all_folders_contain_init_py(directory=str(package_root),
                                      exceptions=exeption_paths)

    # build the tar.gz file
    fpath = build_tar_gz_pkg(pkg_name=pkg_name,
                             setup_path=str(setup_file),
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
                             folder_to_save=str(source_root / 'dist'),
                             ext_filter=ext_filter,
                             extra_files=extra_files,
                             flatten_package_root=flatten_package_root)

    # check the tar.gz file
    run([sys.executable, '-m', 'twine', 'check', fpath], check=True)

    user, pwd = read_pypirc()

    # upload the tar.gz file
    upload_return_code: int = run([sys.executable, '-m', 'twine', 'upload',
                                  '--repository', 'pypi',
                                  '--username', user,
                                  '--password', pwd,
                                  fpath]).returncode
    if upload_return_code == 0:
        pass
    else:
        raise RuntimeError(f"Twine upload failed for {pkg_name} {version}")
