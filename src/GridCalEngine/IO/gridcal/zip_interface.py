# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import json
from io import StringIO, TextIOWrapper, BytesIO
import os
import numpy as np
import chardet
import pandas as pd
import zipfile
from warnings import warn
from typing import List, Dict, Any, Union, Callable
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.generic_io_functions import parse_config_df, CustomJSONizer
import GridCalEngine.Devices as dev


def save_gridcal_data_to_zip(dfs: Dict[str, pd.DataFrame],
                             filename_zip: str,
                             model_data: Dict[str, Dict[str, str]],
                             sessions: List[Any],
                             diagrams: List[Union[dev.MapDiagram, dev.BusBranchDiagram, dev.NodeBreakerDiagram]],
                             json_files: Dict[str, dict],
                             text_func: Union[None, Callable[[str], None]] = None,
                             progress_func: Union[None, Callable[[float], None]] = None,
                             logger=Logger()):
    """
    Save a list of DataFrames to a zip file without saving to disk the csv files
    :param dfs: dictionary of pandas dataFrames {name: DataFrame}
    :param filename_zip: file name where to save all
    :param model_data: dictionary of json data opposed to the dataframes collection
    :param sessions: SimulationSession instance
    :param diagrams: List of Diagram objects
    :param json_files: List of configuration json files to save Dict[file_name, dictionary to save]
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :param logger: Logger object
    """

    n = len(dfs)
    n_failed = 0
    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:

        # save the config files
        for name, value in json_files.items():
            filename = name + ".json"
            f_zip_ptr.writestr(filename, json.dumps(value))

        # save the GridCal object as json data
        for object_type_name, object_data in model_data.items():
            filename = "model_data/" + object_type_name + ".model"
            try:
                f_zip_ptr.writestr(filename, json.dumps(object_data, indent=4, cls=CustomJSONizer))
            except TypeError as e:
                logger.add_error(msg=e, device_class=object_type_name)
                warn(f"{object_type_name}: {e}")

        # save diagrams
        for diagram in diagrams:
            filename = "diagrams/" + diagram.idtag + ".diagram"
            f_zip_ptr.writestr(filename, json.dumps(diagram.get_properties_dict(), indent=4))

        # for each DataFrame and name...
        i = 0
        for name, df in dfs.items():

            if text_func is not None:
                text_func('Flushing ' + name + ' to ' + filename_zip + '...')

            if progress_func is not None:
                progress_func((i + 1) / n * 100)

            if name.endswith('_prof'):

                # compose the csv file name
                filename = name + ".parquet"

                # open a string buffer
                try:  # try parquet file
                    with BytesIO() as buffer:
                        # save the DataFrame to the buffer, protocol4 is to be compatible with python 3.6
                        df.to_parquet(buffer)
                        # save the buffer to the zip file
                        f_zip_ptr.writestr(filename, buffer.getvalue())

                except:  # otherwise just use csv
                    n_failed += 1
                    filename = name + ".csv"
                    with StringIO() as buffer:
                        df.to_csv(buffer, index=False)  # save the DataFrame to the buffer
                        f_zip_ptr.writestr(filename, buffer.getvalue())  # save the buffer to the zip file
            else:
                # compose the csv file name
                filename = name + ".csv"

                # open a string buffer
                with StringIO() as buffer:
                    df.to_csv(buffer, index=False)  # save the DataFrame to the buffer
                    f_zip_ptr.writestr(filename, buffer.getvalue())  # save the buffer to the zip file

            i += 1

        # pre-count the sessions
        n_items = 0
        for session in sessions:
            for drv_name, drv in session.drivers.items():
                if hasattr(drv, 'results'):
                    if drv.results is not None:
                        for arr_name, arr in drv.results.get_arrays().items():
                            n_items += 1

        # save sessions
        i = 0
        for session in sessions:
            for drv_name, drv in session.drivers.items():
                if hasattr(drv, 'results'):
                    if drv.results is not None:
                        for arr_name, arr in drv.results.get_arrays().items():
                            filename = 'sessions/' + session.name + '/' + drv.tpe.value + '/' + arr_name

                            if text_func is not None:
                                text_func('Flushing ' + filename + ' to ' + filename_zip + '...')

                            with BytesIO() as buffer:
                                # save the DataFrame to the buffer, protocol4 is to be compatible with python 3.6
                                np.save(buffer, np.array(arr))  # save the DataFrame to the buffer
                                f_zip_ptr.writestr(filename + '.npy',
                                                   buffer.getvalue())  # save the buffer to the zip file

                            if progress_func is not None:
                                progress_func((i + 1) / n_items * 100)

                            i += 1

    if n_failed:
        print('Failed to pickle several profiles, but saved them as csv.\nFor improved speed install Pandas >= 1.2')


def read_data_frame_from_zip(file_pointer, extension: str, index_col=None, logger=Logger()):
    """
    read DataFrame
    :param file_pointer: Pointer to the file within the zip file
    :param extension: Extension, just to determine the reader method
    :param index_col: Index col (only for config file)
    :param logger:
    :return: Data
    """
    try:
        if extension == '.csv':
            return pd.read_csv(file_pointer, index_col=index_col)

        elif extension == '.npy':
            try:
                return np.load(file_pointer)
            except ValueError:
                return np.load(file_pointer, allow_pickle=True)

        elif extension == '.pkl':
            try:
                return pd.read_pickle(file_pointer)
            except ValueError as e:
                logger.add_error(str(e), device=file_pointer.name)
                return None
            except AttributeError as e:
                logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)
                return None

        elif extension == '.parquet':
            try:
                return pd.read_parquet(file_pointer)
            except ValueError as e:
                logger.add_error(str(e), device=file_pointer.name)
                return None
            except AttributeError as e:
                logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)
                return None

    except EOFError:
        logger.add_error("EOF error", device=file_pointer.name)
        return None
    except zipfile.BadZipFile:
        logger.add_error("Bad zip file error", device=file_pointer.name)
        return None


def get_frames_from_zip(file_name_zip: str,
                        text_func: Union[None, Callable[[str], None]] = None,
                        progress_func: Union[None, Callable[[float], None]] = None,
                        logger=Logger()):
    """
    Open the csv files from a zip file
    :param file_name_zip: name of the zip file
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :param logger:
    :return: list of DataFrames
    """

    # open the zip file
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return None

    names = zip_file_pointer.namelist()

    n = len(names)
    data = {'diagrams': list(),
            'model_data': dict()}
    json_files = dict()

    # for each file in the zip file...
    for i, file_name in enumerate(names):

        # split the file name into name and extension
        name, extension = os.path.splitext(file_name)

        if text_func is not None:
            text_func('Unpacking ' + name + ' from ' + file_name_zip)

        if progress_func is not None:
            progress_func((i + 1) / n * 100)

        # create a buffer to read the file
        file_pointer = zip_file_pointer.open(file_name)

        try:
            if name.lower() == "config":
                df = pd.read_csv(file_pointer, index_col=0)
                data = parse_config_df(df, data)

            elif extension == '.json':
                json_files[name] = json.load(file_pointer)

            elif extension == '.diagram':
                data['diagrams'].append(json.load(file_pointer))

            elif extension == '.model':
                folder, object_name = name.split("/")
                data['model_data'][object_name] = json.load(file_pointer)

            elif extension == '.csv':
                df = pd.read_csv(file_pointer, index_col=None)
                data[name] = df

            elif extension == '.npy':
                try:
                    df = np.load(file_pointer)
                except ValueError:
                    df = np.load(file_pointer, allow_pickle=True)
                data[name] = df

            elif extension == '.pkl':
                try:
                    df = pd.read_pickle(file_pointer)
                    data[name] = df
                except ValueError as e:
                    logger.add_error(str(e), device=file_pointer.name)
                except AttributeError as e:
                    logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)

            elif extension == '.parquet':
                try:
                    df = pd.read_parquet(file_pointer)
                    data[name] = df
                except ValueError as e:
                    logger.add_error(str(e), device=file_pointer.name)
                except AttributeError as e:
                    logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)

            else:
                logger.add_info("Unsupported file type inside .gridcal", value=file_name)

        except EOFError:
            logger.add_error("EOF error", device=file_pointer.name)

        except zipfile.BadZipFile:
            logger.add_error("Bad zip file error", device=file_pointer.name)

    return data, json_files


def get_session_tree(file_name_zip: str):
    """
    Get the sessions structure
    :param file_name_zip:
    :return:
    """
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return dict()

    names = zip_file_pointer.namelist()

    data = dict()

    for name in names:
        if '/' in name:
            path = name.split('/')
            if path[0].lower() == 'sessions':

                session_name = path[1]
                study_name = path[2]
                array_name = path[3]

                if session_name not in data.keys():
                    data[session_name] = dict()

                if study_name not in data[session_name].keys():
                    data[session_name][study_name] = list()

                data[session_name][study_name].append(array_name)

    return data


def load_session_driver_objects(file_name_zip: str, session_name: str, study_name: str):
    """
    Get the sessions structure
    :param file_name_zip:
    :param session_name:
    :param study_name:
    :return:
    """
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return dict()

    data = dict()

    # traverse the zip names and pick all those that start with sessions/session_name/study_name
    for name in zip_file_pointer.namelist():
        if '/' in name:
            path = name.split('/')
            if len(path) > 3:
                if path[0].lower() == 'sessions' and session_name == path[1] and study_name == path[2]:
                    # create a buffer to read the file
                    file_pointer = zip_file_pointer.open(name)

                    # split the file name into name and extension
                    _, extension = os.path.splitext(name)
                    arr_name = path[3].replace(extension, '')

                    # read the data
                    data[arr_name] = read_data_frame_from_zip(file_pointer, extension)

                    # try:
                    #     data[arr_name] = np.load(file_pointer)
                    # except ValueError:
                    #     data[arr_name] = np.load(file_pointer, allow_pickle=True)

    return data


def get_xml_content(file_ptr):
    """
    Reads the content of a file
    :param file_ptr: File pointer (from file or zip file)
    :return: list of text lines
    """
    # xml files always have the encoding declared, find it out
    first_line = file_ptr.readline()

    if b'encoding' in first_line:
        encoding = first_line.split()[2].split(b'=')[1].replace(b'"', b'').replace(b'?>', b'').decode()
    else:
        try:
            detection = chardet.detect(first_line)
            encoding = detection['encoding']
        except:
            encoding = 'utf-8'

    # sequential back to the start
    file_ptr.seek(0)

    # read all the lines
    with TextIOWrapper(file_ptr, encoding=encoding) as fle:
        text_lines = [l for l in fle]

    return text_lines


def get_xml_from_zip(file_name_zip: str,
                     text_func: Union[None, Callable[[str], None]] = None,
                     progress_func: Union[None, Callable[[float], None]] = None,):
    """
    Get the .xml files from a zip file
    :param file_name_zip: name of the zip file
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :return: list of xml file contents
    """

    # open the zip file
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return None

    names = zip_file_pointer.namelist()

    n = len(names)
    data = dict()

    # for each file in the zip file...
    for i, file_name in enumerate(names):

        # split the file name into name and extension
        name, extension = os.path.splitext(file_name)

        if text_func is not None:
            text_func('Unpacking ' + name + ' from ' + file_name_zip)

        if progress_func is not None:
            progress_func((i + 1) / n * 100)

        if extension == '.xml':
            file_ptr = zip_file_pointer.open(file_name)

            text_lines = get_xml_content(file_ptr)

            data[name] = text_lines

    return data
