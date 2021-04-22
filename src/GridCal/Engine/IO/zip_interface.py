# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from io import StringIO, TextIOWrapper, BytesIO
import os
import chardet
from random import randint, seed
import pandas as pd
import zipfile
from typing import List, Dict

from GridCal.Engine.IO.generic_io_functions import parse_config_df


def save_data_frames_to_zip(dfs: Dict[str, pd.DataFrame], filename_zip="file.zip",
                            text_func=None, progress_func=None, use_pkl=False):
    """
    Save a list of DataFrames to a zip file without saving to disk the csv files
    :param dfs: dictionary of pandas dataFrames {name: DataFrame}
    :param filename_zip: file name where to save all
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    """

    n = len(dfs)
    n_failed = 0
    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as myzip:

        # for each DataFrame and name...
        i = 0
        for name, df in dfs.items():

            if text_func is not None:
                text_func('Flushing ' + name + ' to ' + filename_zip + '...')

            if progress_func is not None:
                progress_func((i + 1) / n * 100)

            if name.endswith('_prof'):

                # compose the csv file name
                filename = name + ".pkl"

                # open a string buffer
                try:  # try pickle
                    with BytesIO() as buffer:
                        df.to_pickle(buffer)  # save the DataFrame to the buffer
                        myzip.writestr(filename, buffer.getvalue())  # save the buffer to the zip file

                except:  # otherwise just use csv
                    n_failed += 1
                    filename = name + ".csv"
                    with StringIO() as buffer:
                        df.to_csv(buffer, index=False)  # save the DataFrame to the buffer
                        myzip.writestr(filename, buffer.getvalue())  # save the buffer to the zip file
            else:
                # compose the csv file name
                filename = name + ".csv"

                # open a string buffer
                with StringIO() as buffer:
                    df.to_csv(buffer, index=False)  # save the DataFrame to the buffer
                    myzip.writestr(filename, buffer.getvalue())  # save the buffer to the zip file

            i += 1

    if n_failed:
        print('Failed to pickle several profiles, but saved them as csv.\nFor improved speed install Pandas >= 1.2')


def read_data_frame_from_zip(file_pointer, extension, index_col=None):
    """
    read DataFrame
    :param file_pointer: Pointer to the file within the zip file
    :param extension: Extension, just to determine the reader method
    :param index_col: Index col (only for config file)
    :return: DataFrame
    """
    try:
        if extension == '.csv':
            return pd.read_csv(file_pointer, index_col=index_col)
        elif extension == '.pkl':
            return pd.read_pickle(file_pointer)
    except EOFError:
        return None
    except zipfile.BadZipFile:
        return None


def get_frames_from_zip(file_name_zip, text_func=None, progress_func=None):
    """
    Open the csv files from a zip file
    :param file_name_zip: name of the zip file
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :return: list of DataFrames
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

        # create a buffer to read the file
        file_pointer = zip_file_pointer.open(file_name)

        if name.lower() == "config":
            df = read_data_frame_from_zip(file_pointer, extension, index_col=0)
            data = parse_config_df(df, data)
        else:
            # make pandas read the file
            df = read_data_frame_from_zip(file_pointer, extension)

        # append the DataFrame to the list
        if df is not None:
            data[name] = df

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


def get_xml_from_zip(file_name_zip, text_func=None, progress_func=None):
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


if __name__ == '__main__':

    # Generate some random values to put in the csv file.
    # seed(42)  # Causes random numbers always be the same for testing.
    # data = [[randint(0, 100) for _ in range(10)] for _ in range(10)]
    # df1 = pd.DataFrame(data)
    #
    # seed(44)  # Causes random numbers always be the same for testing.
    # data = [[randint(0, 100) for _ in range(10)] for _ in range(10)]
    # df2 = pd.DataFrame(data)
    #
    # # save
    # save_data_frames_to_zip({'Data1': df1, 'Data2': df2}, 'some_file.gridcal')
    #
    # # read and print
    # df_list = get_frames_from_zip(file_name_zip='some_file.gridcal')
    #
    # for name, df in df_list.items():
    #     print()
    #     print(name)
    #     print(df)

    fname = r'C:\Users\penversa\Documents\Grids\CGMES\TYNDP_2025\2025NT_ES_model_003.zip'
    data = get_xml_from_zip(fname)

    print()