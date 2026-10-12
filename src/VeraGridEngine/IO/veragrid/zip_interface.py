# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import hashlib
import json
import zipfile
try:
    import msgspec  # optional, faster alternative to read json files
    _HAS_MSGSPEC = True
except ImportError:
    _HAS_MSGSPEC = False

from io import StringIO, TextIOWrapper, BytesIO, BufferedReader
import os
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

from warnings import warn
from typing import BinaryIO, List, Dict, Union, Callable, Tuple, Any
from VeraGridEngine.Devices.types import VERAGRID_FILE_TYPE
from VeraGridEngine.enumerations import IeeeCigreDllPlatform
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.veragrid.generic_io_functions import parse_config_df, CustomJSONizer
from VeraGridEngine.Simulations.driver_template import DriverToSave
from VeraGridEngine.IO.veragrid.pack_unpack import gather_model_as_data_frames, gather_model_as_jsons
import VeraGridEngine.Devices as dev


def _validate_manufacturer_native_member_name(variant: dev.ManufacturerNativeBinaryVariant) -> None:
    """Validate one content-addressed native archive member.

    :param variant: Persistent platform variant whose member is checked.
    :return: None.
    """
    expected_name: str = (
        "native_models/manufacturer/by_sha256/"
        + variant.content_sha256
        + variant.extension
    )
    platform_name: str = (
        "native_models/manufacturer/"
        + variant.platform.value
        + "/"
        + variant.content_sha256
        + variant.extension
    )
    legacy_name: str = (
        "native_models/manufacturer/ieee_cigre_v1_1/"
        + variant.platform.value
        + "/"
        + variant.content_sha256
        + variant.extension
    )
    path: Path = Path(variant.zip_member)
    if (
            variant.zip_member not in (expected_name, platform_name, legacy_name)
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in variant.zip_member
    ):
        raise ValueError("Manufacturer native ZIP member is not canonical")
    else:
        pass


def _stream_manufacturer_native_member(f_zip_ptr: zipfile.ZipFile,
                                   variant: dev.ManufacturerNativeBinaryVariant,
                                   source: dev.ManufacturerNativeBinarySource) -> None:
    """Stream one verified source into its content-addressed ZIP member.

    :param f_zip_ptr: Open temporary target archive.
    :param variant: Expected content identity and destination member.
    :param source: Nonpersistent file or source-archive locator.
    :return: None.
    """
    _validate_manufacturer_native_member_name(variant)
    if source.platform != variant.platform:
        raise ValueError("Manufacturer native source platform does not match its variant")
    else:
        pass
    source_stream: BinaryIO
    source_zip: zipfile.ZipFile | None = None
    if len(source.file_path) > 0:
        source_stream = open(source.file_path, "rb")
    else:
        source_zip = zipfile.ZipFile(source.archive_path, "r")
        if source.archive_member != variant.zip_member:
            source_zip.close()
            raise ValueError("Manufacturer native source archive member does not match its variant")
        else:
            source_stream = source_zip.open(source.archive_member, "r")
    digest = hashlib.sha256()
    byte_count: int = 0
    try:
        with f_zip_ptr.open(variant.zip_member, "w", force_zip64=True) as target_stream:
            while True:
                chunk: bytes = source_stream.read(1024 * 1024)
                if len(chunk) == 0:
                    break
                else:
                    byte_count += len(chunk)
                    if byte_count > 512 * 1024 * 1024:
                        raise ValueError("Manufacturer native binary exceeds 512 MiB")
                    else:
                        digest.update(chunk)
                        target_stream.write(chunk)
    finally:
        source_stream.close()
        if source_zip is not None:
            source_zip.close()
        else:
            pass
    if byte_count != variant.byte_size or digest.hexdigest() != variant.content_sha256:
        raise ValueError("Manufacturer native source bytes do not match the persisted size and SHA-256")
    else:
        pass


def _write_manufacturer_native_members(f_zip_ptr: zipfile.ZipFile,
                                   circuit: dev.MultiCircuit) -> None:
    """Write every unique provider variant owned by one circuit.

    :param f_zip_ptr: Open temporary target archive.
    :param circuit: Circuit whose provider bytes must be embedded.
    :return: None.
    """
    written_members: set[str] = set(f_zip_ptr.namelist())
    provider: dev.ManufacturerNativeModel
    platform: IeeeCigreDllPlatform
    for provider in circuit.manufacturer_native_models:
        for platform in (
                IeeeCigreDllPlatform.WINDOWS_X86,
                IeeeCigreDllPlatform.WINDOWS_X64,
                IeeeCigreDllPlatform.LINUX_X64,
        ):
            variant: dev.ManufacturerNativeBinaryVariant | None = provider.get_platform_variant(platform)
            if variant is not None:
                if variant.zip_member not in written_members:
                    source: dev.ManufacturerNativeBinarySource | None = provider.get_binary_source(platform)
                    if source is None:
                        raise ValueError(
                            f"Manufacturer native provider {provider.idtag} has no source for {platform.value}"
                        )
                    else:
                        _stream_manufacturer_native_member(f_zip_ptr, variant, source)
                        written_members.add(variant.zip_member)
                else:
                    pass
            else:
                pass


def _rebind_manufacturer_native_sources(circuit: dev.MultiCircuit, archive_path: str) -> None:
    """Rebind every saved provider source after atomic replacement succeeds.

    :param circuit: Circuit whose provider locators are updated.
    :param archive_path: Successful target VeraGrid archive.
    :return: None.
    """
    provider: dev.ManufacturerNativeModel
    platform: IeeeCigreDllPlatform
    for provider in circuit.manufacturer_native_models:
        for platform in (
                IeeeCigreDllPlatform.WINDOWS_X86,
                IeeeCigreDllPlatform.WINDOWS_X64,
                IeeeCigreDllPlatform.LINUX_X64,
        ):
            variant: dev.ManufacturerNativeBinaryVariant | None = provider.get_platform_variant(platform)
            if variant is not None:
                provider.set_binary_source(dev.ManufacturerNativeBinarySource(
                    platform=platform,
                    archive_path=archive_path,
                    archive_member=variant.zip_member,
                ))
            else:
                pass

def _get_active_multiverse_grid_idtag(zip_file_pointer: zipfile.ZipFile) -> str | None:
    """
    Resolve the active multiverse scenario circuit idtag from the archive metadata.

    :param zip_file_pointer: Open VeraGrid archive.
    :return: Active scenario circuit idtag, or ``None`` when unavailable.
    """
    metadata_name: str = "multiverse/metadata.json"

    if metadata_name not in zip_file_pointer.namelist():
        return None
    else:
        pass

    metadata: dict[str, Any] = load_json_from_file_pointer(zip_file_pointer.open(metadata_name))
    active_node_id_raw: Any = metadata.get("active_node_id", None)

    if active_node_id_raw is None:
        return None
    else:
        pass

    nodes_data: Any = metadata.get("nodes", dict())
    active_node_key: str = str(active_node_id_raw)
    active_node_data: Any = nodes_data.get(active_node_key, None)

    if active_node_data is None:
        return None
    else:
        return str(active_node_data.get("circuit_idtag", None))


def _split_session_entry_path(path: List[str], active_grid_idtag: str | None) -> Tuple[str, str, str] | None:
    """
    Normalize one archive path to the generic ``session/study/array`` tuple.

    :param path: Archive path split by ``/``.
    :param active_grid_idtag: Active multiverse scenario idtag, when applicable.
    :return: Normalized tuple, or ``None`` when the path is not a supported session entry.
    """
    if len(path) < 4:
        return None
    elif path[0].lower() == "sessions":
        return path[1], path[2], path[3]
    elif (
        active_grid_idtag is not None
        and len(path) >= 6
        and path[0].lower() == "multiverse"
        and path[1] == active_grid_idtag
        and path[2].lower() == "sessions"
    ):
        return path[3], path[4], path[5]
    else:
        return None


def load_json_from_file_pointer(file_pointer) -> list | dict:
    """
    Load JSON from a file pointer using orjson if available, falling back to json.
    :param file_pointer: File pointer (from zip file or regular file)
    :return: Parsed JSON as dict
    """
    content = file_pointer.read()
    if _HAS_MSGSPEC:
        try:
            return msgspec.json.decode(content, type=list)
        except msgspec.ValidationError as e:
            return msgspec.json.decode(content, type=dict)

    return json.loads(content)


def save_results_in_zip(f_zip_ptr: zipfile.ZipFile,
                        filename_zip: str,
                        sessions_data: List[DriverToSave],
                        folder: str,
                        text_func: Union[None, Callable[[str], None]] = None,
                        progress_func: Union[None, Callable[[float], None]] = None):
    """

    :param f_zip_ptr:
    :param filename_zip:
    :param sessions_data:
    :param folder:
    :param text_func:
    :param progress_func:
    :return:
    """
    # pre-count the sessions
    n_items = len(sessions_data)

    # save sessions
    for i, session_data in enumerate(sessions_data):

        if session_data.results is not None:
            session_data.results.prepare_for_saving()

            # traverse the registered results
            for arr_name, arr_prop in session_data.results.data_variables.items():

                filename = folder + '/' + session_data.name + '/' + session_data.tpe.value + '/' + arr_name

                if text_func is not None:
                    text_func('Flushing ' + filename + ' to ' + filename_zip + '...')

                # get the array
                arr = getattr(session_data.results, arr_name)

                with BytesIO() as buffer:
                    # pack the array into a DataFrame

                    try:
                        if np.isscalar(arr):
                            if np.iscomplexobj(arr):
                                filename += "__complex__"
                                pd.DataFrame(data=[[np.real(arr), np.imag(arr)]]).to_parquet(buffer)
                                f_zip_ptr.writestr(filename + ".parquet", buffer.getvalue())
                            else:
                                pd.DataFrame(data=[[arr]]).to_parquet(buffer)
                                f_zip_ptr.writestr(filename + ".parquet", buffer.getvalue())
                        elif isinstance(arr, np.ndarray) and arr.ndim > 2:
                            # Dynamic simulations store tensor-shaped traces.
                            # Those arrays do not fit the historical 2-D parquet
                            # path, so persist them as raw NumPy payloads.
                            np.save(buffer, arr)
                            f_zip_ptr.writestr(filename + ".npy", buffer.getvalue())
                        elif np.iscomplexobj(arr):
                            filename += "__complex__"
                            pd.DataFrame(data=np.c_[arr.real, arr.imag]).to_parquet(buffer)
                            f_zip_ptr.writestr(filename + ".parquet", buffer.getvalue())
                        else:
                            pd.DataFrame(data=arr).to_parquet(buffer)
                            # save the buffer to the zip file
                            f_zip_ptr.writestr(filename + ".parquet", buffer.getvalue())

                    except ValueError as e:
                        warn(str(e))

                if progress_func is not None:
                    progress_func((i + 1) / n_items * 100)

        # save logger
        if session_data.logger is not None:
            filename = folder + '/' + session_data.name + '/' + session_data.tpe.value + '/logger.parquet'
            with BytesIO() as buffer:
                # save the DataFrame to the buffer, protocol4 is to be compatible with python 3.6
                session_data.logger.to_df().to_parquet(buffer)
                # save the buffer to the zip file
                f_zip_ptr.writestr(filename, buffer.getvalue())


def save_multiverse_data_to_zip(f_zip_ptr: zipfile.ZipFile,
                                multiverse: dev.MultiVerse,
                                filename_zip: str,
                                active_grid_idtag: str | None = None,
                                active_sessions_data: List[DriverToSave] | None = None,
                                text_func: Union[None, Callable[[str], None]] = None,
                                progress_func: Union[None, Callable[[float], None]] = None,
                                logger=Logger()) -> None:
    """
    Save only the multiverse-specific payload into an already opened VeraGrid archive.
    """
    multiverse_meta_data, multiverse_model_data, multiverse_drivers_data = multiverse.get_save_data()

    filename = "multiverse/metadata.json"
    f_zip_ptr.writestr(filename, json.dumps(multiverse_meta_data, indent=4))

    for grid_idtag, diff_grid in multiverse_model_data.items():
        base_path = f"multiverse/{grid_idtag}"
        sessions_data: List[DriverToSave] | None = multiverse_drivers_data.get(grid_idtag, None)

        if active_grid_idtag == grid_idtag and active_sessions_data is not None:
            # The GUI save flow provides the active scenario session payload explicitly.
            # Use that payload for the active scenario instead of assuming node.drivers
            # has already been synchronized with the session object.
            sessions_data = active_sessions_data
        else:
            pass

        for key, data in gather_model_as_jsons(diff_grid, project_directory=Path(filename_zip).resolve().parent).items():
            if key == "model_data":
                ext = ".model"
                sub_folder = "model_data"
            elif key == "symbolic_data":
                ext = ".symbolic"
                sub_folder = "model_data/symbolic_data"
            else:
                raise ValueError(f"Unhandled data package to save {key}")

            for object_type_name, object_data in data.items():
                filename = f"{base_path}/{sub_folder}/{object_type_name + ext}"
                try:
                    f_zip_ptr.writestr(filename, json.dumps(object_data, indent=4, cls=CustomJSONizer))
                except TypeError as e:
                    logger.add_error(msg=str(e), device_class=object_type_name)
                    warn(f"{object_type_name}: {e}")

        if sessions_data is not None:
            save_results_in_zip(f_zip_ptr=f_zip_ptr,
                                filename_zip=filename_zip,
                                folder=f"{base_path}/sessions",
                                sessions_data=sessions_data,
                                text_func=text_func,
                                progress_func=progress_func)

        for diagram in diff_grid.diagrams:
            filename = f"{base_path}/diagrams/{diagram.idtag}.diagram"
            f_zip_ptr.writestr(filename, json.dumps(diagram.get_data_dict(), indent=4))

        if hasattr(diff_grid.diagrams, 'get_data_dict'):
            tree_filename = f"{base_path}/diagrams/tree.json"
            f_zip_ptr.writestr(tree_filename, json.dumps(diff_grid.diagrams.get_data_dict(), indent=4))

        _write_manufacturer_native_members(f_zip_ptr=f_zip_ptr, circuit=diff_grid)


def save_single_circuit_data_to_zip(f_zip_ptr: zipfile.ZipFile,
                                    circuit: dev.MultiCircuit,
                                    sessions_data: List[DriverToSave],
                                    filename_zip: str,
                                    text_func: Union[None, Callable[[str], None]] = None,
                                    progress_func: Union[None, Callable[[float], None]] = None,
                                    logger=Logger()) -> None:
    """
    Save the non-multiverse circuit payload into an already opened VeraGrid archive.
    """
    for key, data in gather_model_as_jsons(circuit, project_directory=Path(filename_zip).resolve().parent).items():
        if key == "model_data":
            ext = ".model"
        elif key == "symbolic_data":
            ext = ".symbolic"
        else:
            raise ValueError(f"Unhandled data package to save {key}")

        for object_type_name, object_data in data.items():
            filename = key + "/" + object_type_name + ext
            try:
                f_zip_ptr.writestr(filename, json.dumps(object_data, indent=4, cls=CustomJSONizer))
            except TypeError as e:
                logger.add_error(msg=str(e), device_class=object_type_name)
                warn(f"{object_type_name}: {e}")

    for diagram in circuit.diagrams:
        filename = f"diagrams/{diagram.idtag}.diagram"
        f_zip_ptr.writestr(filename, json.dumps(diagram.get_data_dict(), indent=4))

    if hasattr(circuit.diagrams, 'get_data_dict'):
        tree_filename = "diagrams/tree.json"
        f_zip_ptr.writestr(tree_filename, json.dumps(circuit.diagrams.get_data_dict(), indent=4))

    save_results_in_zip(f_zip_ptr=f_zip_ptr,
                        filename_zip=filename_zip,
                        folder="sessions",
                        sessions_data=sessions_data,
                        text_func=text_func,
                        progress_func=progress_func)

    _write_manufacturer_native_members(f_zip_ptr=f_zip_ptr, circuit=circuit)


def _save_veragrid_data_to_zip_file(filename_zip: str,
                              circuit: dev.MultiCircuit,
                              sessions_data: List[DriverToSave],
                              json_files: Dict[str, dict],
                              text_func: Union[None, Callable[[str], None]] = None,
                              progress_func: Union[None, Callable[[float], None]] = None,
                              logger=Logger()):
    """
    Save a list of DataFrames to a zip file without saving to disk the csv files
    :param filename_zip: file name where to save all
    :param circuit: MultiCircuit object
    :param sessions_data: List of DriverToSave instances, representing the results drivers data
    :param json_files: List of configuration json files to save such as gui_config Dict[file_name, dictionary to save]
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :param logger: Logger object
    """

    n_failed = 0
    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:

        # save the config files ----------------------------------------------------------------------------------------
        for name, value in json_files.items():
            filename = name + ".json"
            f_zip_ptr.writestr(filename, json.dumps(value))

        # save the bulk of the data ------------------------------------------------------------------------------------
        save_single_circuit_data_to_zip(f_zip_ptr=f_zip_ptr,
                                        circuit=circuit,
                                        sessions_data=sessions_data,
                                        filename_zip=filename_zip,
                                        text_func=text_func,
                                        progress_func=progress_func,
                                        logger=logger)

        # gather the dataframes (legacy) -------------------------------------------------------------------------------
        dfs = gather_model_as_data_frames(circuit, logger=logger, legacy=False)

        # for each DataFrame and name...
        i = 0
        for name, df in dfs.items():

            if text_func is not None:
                text_func('Flushing ' + name + ' to ' + filename_zip + '...')

            if progress_func is not None:
                progress_func((i + 1) / len(dfs) * 100)

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

    if n_failed:
        print('Failed to pickle several profiles, but saved them as csv.\nFor improved speed install Pandas >= 1.2')


def save_veragrid_data_to_zip(filename_zip: str,
                              circuit: dev.MultiCircuit,
                              sessions_data: List[DriverToSave],
                              json_files: Dict[str, dict],
                              text_func: Union[None, Callable[[str], None]] = None,
                              progress_func: Union[None, Callable[[float], None]] = None,
                              logger=Logger()) -> None:
    """Atomically save a VeraGrid archive and then rebind native byte sources.

    :param filename_zip: Final archive path.
    :param circuit: Circuit to persist.
    :param sessions_data: Simulation result payloads.
    :param json_files: Additional JSON configuration files.
    :param text_func: Optional textual progress callback.
    :param progress_func: Optional numeric progress callback.
    :param logger: Save diagnostic logger.
    :return: None.
    """
    target_path: Path = Path(filename_zip).resolve()
    temporary_fd: int
    temporary_name: str
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=target_path.name + ".",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    os.close(temporary_fd)
    replaced: bool = False
    try:
        _save_veragrid_data_to_zip_file(
            filename_zip=temporary_name,
            circuit=circuit,
            sessions_data=sessions_data,
            json_files=json_files,
            text_func=text_func,
            progress_func=progress_func,
            logger=logger,
        )
        os.replace(temporary_name, target_path)
        replaced = True
    finally:
        if not replaced and os.path.exists(temporary_name):
            os.remove(temporary_name)
        else:
            pass
    _rebind_manufacturer_native_sources(circuit=circuit, archive_path=str(target_path))

def _save_veragrid_multiverse_data_to_zip_file(filename_zip: str,
                                         json_files: Dict[str, dict],
                                         multiverse: dev.MultiVerse,
                                         active_grid_idtag: str | None = None,
                                         active_sessions_data: List[DriverToSave] | None = None,
                                         text_func: Union[None, Callable[[str], None]] = None,
                                         progress_func: Union[None, Callable[[float], None]] = None,
                                         logger=Logger()):
    """
    Save a list of DataFrames to a zip file without saving to disk the csv files
    :param filename_zip: file name where to save all
    :param json_files: List of configuration json files to save such as gui_config Dict[file_name, dictionary to save]
    :param multiverse: MultiVerse object
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :param logger: Logger object
    """

    n_failed = 0
    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:

        # save the config files ----------------------------------------------------------------------------------------
        for name, value in json_files.items():
            filename = name + ".json"
            f_zip_ptr.writestr(filename, json.dumps(value))

        # save the multicircuit data------------------------------------------------------------------------------------
        save_multiverse_data_to_zip(f_zip_ptr=f_zip_ptr,
                                    multiverse=multiverse,
                                    filename_zip=filename_zip,
                                    active_grid_idtag=active_grid_idtag,
                                    active_sessions_data=active_sessions_data,
                                    text_func=text_func,
                                    progress_func=progress_func,
                                    logger=logger)

    if n_failed:
        print('Failed to pickle several profiles, but saved them as csv.\nFor improved speed install Pandas >= 1.2')


def save_veragrid_multiverse_data_to_zip(filename_zip: str,
                                         json_files: Dict[str, dict],
                                         multiverse: dev.MultiVerse,
                                         active_grid_idtag: str | None = None,
                                         active_sessions_data: List[DriverToSave] | None = None,
                                         text_func: Union[None, Callable[[str], None]] = None,
                                         progress_func: Union[None, Callable[[float], None]] = None,
                                         logger=Logger()) -> None:
    """Atomically save a multiverse archive and rebind all saved provider sources.

    :param filename_zip: Final archive path.
    :param json_files: Additional JSON configuration files.
    :param multiverse: Multiverse to persist.
    :param active_grid_idtag: Active circuit identity.
    :param active_sessions_data: Active circuit result payloads.
    :param text_func: Optional textual progress callback.
    :param progress_func: Optional numeric progress callback.
    :param logger: Save diagnostic logger.
    :return: None.
    """
    target_path: Path = Path(filename_zip).resolve()
    temporary_fd: int
    temporary_name: str
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=target_path.name + ".",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    os.close(temporary_fd)
    replaced: bool = False
    try:
        _save_veragrid_multiverse_data_to_zip_file(
            filename_zip=temporary_name,
            json_files=json_files,
            multiverse=multiverse,
            active_grid_idtag=active_grid_idtag,
            active_sessions_data=active_sessions_data,
            text_func=text_func,
            progress_func=progress_func,
            logger=logger,
        )
        os.replace(temporary_name, target_path)
        replaced = True
    finally:
        if not replaced and os.path.exists(temporary_name):
            os.remove(temporary_name)
        else:
            pass
    multiverse_metadata: Dict[str, Any]
    saved_circuits: Dict[str, dev.MultiCircuit]
    saved_drivers: Dict[str, List[DriverToSave] | None]
    multiverse_metadata, saved_circuits, saved_drivers = multiverse.get_save_data()
    circuit: dev.MultiCircuit
    for circuit in saved_circuits.values():
        _rebind_manufacturer_native_sources(circuit=circuit, archive_path=str(target_path))

def save_results_only(filename_zip: str,
                      sessions_data: List[DriverToSave],
                      text_func: Union[None, Callable[[str], None]] = None,
                      progress_func: Union[None, Callable[[float], None]] = None):
    """
    Save the results into a new file
    :param filename_zip: name of the zip file
    :param sessions_data: Sessions to save
    :param text_func: Text progress function
    :param progress_func: Numerical progress function
    """
    # open zip file for writing
    with zipfile.ZipFile(filename_zip, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:
        # Save the results into the zip file
        save_results_in_zip(f_zip_ptr=f_zip_ptr,
                            filename_zip=filename_zip,
                            sessions_data=sessions_data,
                            text_func=text_func,
                            progress_func=progress_func)


def read_data_frame_from_zip(file_pointer,
                             extension: str,
                             index_col=None, logger=Logger()) -> Union[None, pd.DataFrame]:
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

        elif extension == '.feather':
            try:
                return pd.read_feather(file_pointer)
            except ValueError as e:
                logger.add_error(str(e), device=file_pointer.name)
                return None
            except AttributeError as e:
                logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)
                return None

        elif extension == '.hdf':
            try:
                return pd.read_hdf(file_pointer, key='array')
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
                        logger=Logger()) -> Tuple[VERAGRID_FILE_TYPE, Dict[str, Any], bool]:
    """
    Open the csv files from a zip file
    :param file_name_zip: name of the zip file
    :param text_func: pointer to function that prints the names
    :param progress_func: pointer to function that prints the progress 0~100
    :param logger:
    :return: list of DataFrames
    """

    json_files = dict()
    has_multiverse_data = False
    # open the zip file
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        data = {
            'diagrams': list(),
            'model_data': dict(),
            'symbolic_data': dict()
        }
        zip_file_pointer.close()
        return data, json_files, has_multiverse_data

    names = zip_file_pointer.namelist()

    if 'multiverse/metadata.json' in names:

        data = {
            'multiverse': dict()
        }

        has_multiverse_data = True
        # Loading a multiverse file ------------------------------------------------------------------------------------
        n = len(names)

        # for each file in the zip file...
        for i, file_name in enumerate(names):

            # split the file name into name and extension
            path = file_name.split('/')
            name, extension = os.path.splitext(path[-1])

            if text_func is not None:
                text_func('Unpacking ' + name + ' from ' + file_name_zip)

            if progress_func is not None:
                progress_func((i + 1) / n * 100)

            # create a buffer to read the file
            file_pointer = zip_file_pointer.open(file_name)

            if path[0] == "multiverse":
                model_idtag = path[1]

                if model_idtag not in data['multiverse']: # and ".json" not in model_idtag:
                    # initialize the dict
                    data['multiverse'][model_idtag] = {
                        'diagrams': list(),
                        'model_data': dict(),
                        'symbolic_data': dict(),
                    }

                # model_data = data['multiverse'][model_idtag]

                try:
                    if name.lower() == "config":
                        df = pd.read_csv(file_pointer, index_col=0)
                        data[name] = parse_config_df(df, data)

                    elif extension == '.json':
                        if name == "tree" or file_name.endswith("diagrams/tree.json") or name == "diagram_tree":
                            data['multiverse'][model_idtag]['diagram_tree'] = load_json_from_file_pointer(file_pointer)
                        else:
                            json_files[name] = load_json_from_file_pointer(file_pointer)

                    elif extension == '.diagram':
                        data['multiverse'][model_idtag]['diagrams'].append(load_json_from_file_pointer(file_pointer))

                    elif extension == '.model':
                        data['multiverse'][model_idtag]['model_data'][name] = load_json_from_file_pointer(file_pointer)

                    elif extension == '.symbolic':
                        data['multiverse'][model_idtag]['symbolic_data'][name] = load_json_from_file_pointer(file_pointer)

                    elif extension == '.csv':
                        data['multiverse'][model_idtag][name] = pd.read_csv(file_pointer, index_col=None)

                    elif extension == '.npy':
                        try:
                            df = np.load(file_pointer)
                        except ValueError:
                            df = np.load(file_pointer, allow_pickle=True)
                        data['multiverse'][model_idtag][name] = df

                    elif extension == '.pkl':
                        try:
                            data['multiverse'][model_idtag][name] = pd.read_pickle(file_pointer)
                        except ValueError as e:
                            logger.add_error(str(e), device=file_pointer.name)
                        except AttributeError as e:
                            logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)

                    elif extension == '.parquet':
                        try:
                            data['multiverse'][model_idtag][name] = pd.read_parquet(file_pointer)
                        except ValueError as e:
                            logger.add_error(str(e), device=file_pointer.name)
                        except AttributeError as e:
                            logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)

                    else:
                        logger.add_info("Unsupported file type inside .veragrid", value=file_name)

                except EOFError:
                    logger.add_error("EOF error", device=file_pointer.name)

                except zipfile.BadZipFile:
                    logger.add_error("Bad zip file error", device=file_pointer.name)

            else:
                if name.lower() == "config":
                    df = pd.read_csv(file_pointer, index_col=0)
                    data[name] = parse_config_df(df, data)

        zip_file_pointer.close()
        return data, json_files, has_multiverse_data

    else:

        # Loading a flat file structure with no multiverse -------------------------------------------------------------

        data = {
            'diagrams': list(),
            'model_data': dict(),
            'symbolic_data': dict()
        }

        has_multiverse_data = False
        n = len(names)

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
                    data[name] = parse_config_df(df, data)

                elif extension == '.json':
                    if file_name.endswith("diagrams/tree.json") or name in ("tree", "diagram_tree"):
                        data['diagram_tree'] = load_json_from_file_pointer(file_pointer)
                    else:
                        json_files[name] = load_json_from_file_pointer(file_pointer)

                elif extension == '.diagram':
                    data['diagrams'].append(load_json_from_file_pointer(file_pointer))

                elif extension == '.model':
                    folder, object_name = name.split("/")
                    data['model_data'][object_name] = load_json_from_file_pointer(file_pointer)

                elif extension == '.symbolic':
                    folder, object_name = name.split("/")
                    data['symbolic_data'][object_name] = load_json_from_file_pointer(file_pointer)

                elif extension == '.csv':
                    data[name] = pd.read_csv(file_pointer, index_col=None)

                elif extension == '.npy':
                    try:
                        df = np.load(file_pointer)
                    except ValueError:
                        df = np.load(file_pointer, allow_pickle=True)
                    data[name] = df

                elif extension == '.pkl':
                    try:
                        data[name] = pd.read_pickle(file_pointer)
                    except ValueError as e:
                        logger.add_error(str(e), device=file_pointer.name)
                    except AttributeError as e:
                        logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)

                elif extension == '.parquet':
                    try:
                        data[name] = pd.read_parquet(file_pointer)
                    except ValueError as e:
                        logger.add_error(str(e), device=file_pointer.name)
                    except AttributeError as e:
                        logger.add_error(str(e) + ' Upgrading pandas might help.', device=file_pointer.name)

                else:
                    logger.add_info("Unsupported file type inside .veragrid", value=file_name)

            except EOFError:
                logger.add_error("EOF error", device=file_pointer.name)

            except zipfile.BadZipFile:
                logger.add_error("Bad zip file error", device=file_pointer.name)

        zip_file_pointer.close()
        return data, json_files, has_multiverse_data


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
    active_grid_idtag: str | None = _get_active_multiverse_grid_idtag(zip_file_pointer)

    data = dict()

    for name in names:
        if '/' in name:
            path = name.split('/')
            session_entry = _split_session_entry_path(path=path, active_grid_idtag=active_grid_idtag)

            if session_entry is not None:
                session_name, study_name, array_name = session_entry

                if session_name not in data.keys():
                    data[session_name] = dict()
                else:
                    pass

                if study_name not in data[session_name].keys():
                    data[session_name][study_name] = list()
                else:
                    pass

                data[session_name][study_name].append(array_name)
            else:
                pass

    return data


def load_session_driver_objects(file_name_zip: str,
                                session_name: str,
                                study_name: str) -> Dict[str, Union[None, pd.DataFrame]]:
    """
    Get the sessions structure
    :param file_name_zip:
    :param session_name:
    :param study_name:
    :return: Dict[str, Union[None, pd.DataFrame]]
    """
    try:
        zip_file_pointer = zipfile.ZipFile(file_name_zip)
    except zipfile.BadZipFile:
        return dict()

    data = dict()
    active_grid_idtag: str | None = _get_active_multiverse_grid_idtag(zip_file_pointer)

    # Traverse the zip names and pick all those that belong to the standard
    # session tree or to the active multiverse scenario session tree.
    for name in zip_file_pointer.namelist():
        if '/' in name:
            path = name.split('/')
            session_entry = _split_session_entry_path(path=path, active_grid_idtag=active_grid_idtag)

            if session_entry is not None:
                path_session_name, path_study_name, path_array_name = session_entry

                if session_name == path_session_name and study_name == path_study_name:
                    # create a buffer to read the file
                    file_pointer = zip_file_pointer.open(name)

                    # split the file name into name and extension
                    _, extension = os.path.splitext(name)
                    arr_name = path_array_name.replace(extension, '')

                    # read the data
                    data[arr_name] = read_data_frame_from_zip(file_pointer, extension)
                else:
                    pass
            else:
                pass

    return data


def get_xml_content(file_ptr: zipfile.ZipExtFile | BufferedReader) -> List[str]:
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
        encoding = 'utf-8'

    # sequential back to the start
    file_ptr.seek(0)

    # read all the lines
    with TextIOWrapper(file_ptr, encoding=encoding) as fle:
        text_lines = [l for l in fle]

    return text_lines


def get_xml_from_zip(file_name_zip: str,
                     text_func: Union[None, Callable[[str], None]] = None,
                     progress_func: Union[None, Callable[[float], None]] = None, ):
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
